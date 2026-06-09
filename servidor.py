from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from functools import wraps
from google import genai
from google.genai import types
from werkzeug.exceptions import HTTPException
import json
import logging
import os
import time
import uuid

try:
    import firebase_admin
    from firebase_admin import auth as firebase_auth
    from firebase_admin import credentials
except ImportError:
    firebase_admin = None
    firebase_auth = None
    credentials = None

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("mi-cuaderno")

allowed_origins = [
    origin.strip()
    for origin in os.environ.get(
        "FRONTEND_ORIGINS",
        "http://127.0.0.1:5000,http://localhost:5000,http://127.0.0.1,http://localhost",
    ).split(",")
    if origin.strip()
]
CORS(
    app,
    resources={
        r"/analizar": {"origins": allowed_origins},
        r"/generar-informe": {"origins": allowed_origins},
    },
    allow_headers=["Content-Type", "Authorization"],
    methods=["POST", "OPTIONS"],
    max_age=3600,
)

api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

AUTH_REQUIRED = os.environ.get("AUTH_REQUIRED", "1").lower() not in ("0", "false", "no")
firebase_ready = False
rate_buckets = {}
RATE_LIMITS = {
    "analizar": (int(os.environ.get("ANALYZE_RATE_LIMIT", "8")), 3600),
    "generar_informe": (int(os.environ.get("GENERATE_RATE_LIMIT", "20")), 3600),
}
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_TOPIC_LENGTH = int(os.environ.get("MAX_TOPIC_LENGTH", "180"))
MAX_GRADE_LENGTH = int(os.environ.get("MAX_GRADE_LENGTH", "80"))

try:
    service_account_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    service_account_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    firebase_project_id = os.environ.get("FIREBASE_PROJECT_ID")

    if firebase_admin is None:
        print("firebase-admin no esta instalado. Ejecuta: pip install -r requirements.txt")
    elif service_account_json:
        firebase_credential = credentials.Certificate(json.loads(service_account_json))
        firebase_admin.initialize_app(firebase_credential)
        firebase_ready = True
    elif service_account_path:
        firebase_credential = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(firebase_credential)
        firebase_ready = True
    elif firebase_project_id:
        firebase_admin.initialize_app(credentials.ApplicationDefault(), {"projectId": firebase_project_id})
        firebase_ready = True
except Exception as error:
    print("Firebase Admin no configurado:", error)


def require_auth(route_handler):
    @wraps(route_handler)
    def wrapper(*args, **kwargs):
        if not AUTH_REQUIRED:
            request.user = {"uid": "local-dev", "email": "local-dev"}
            return route_handler(*args, **kwargs)

        if not firebase_ready:
            return jsonify({
                "error": "Autenticacion no configurada en el servidor. Define FIREBASE_SERVICE_ACCOUNT o FIREBASE_PROJECT_ID."
            }), 503

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Debes iniciar sesion para usar esta funcion."}), 401

        token = auth_header.replace("Bearer ", "", 1).strip()
        try:
            decoded = firebase_auth.verify_id_token(token)
        except Exception:
            return jsonify({"error": "Sesion invalida o expirada. Vuelve a iniciar sesion."}), 401

        if decoded.get("email") and not decoded.get("email_verified", False):
            return jsonify({"error": "Verifica tu correo antes de usar esta funcion."}), 403

        request.user = decoded

        return route_handler(*args, **kwargs)

    return wrapper


def rate_limit(bucket_name):
    def decorator(route_handler):
        @wraps(route_handler)
        def wrapper(*args, **kwargs):
            limit, window_seconds = RATE_LIMITS[bucket_name]
            now = time.time()
            user = getattr(request, "user", {}) or {}
            identity = user.get("uid") or request.remote_addr or "anonymous"
            key = f"{bucket_name}:{identity}"
            bucket = [stamp for stamp in rate_buckets.get(key, []) if now - stamp < window_seconds]

            if len(bucket) >= limit:
                return jsonify({"error": "Limite de uso alcanzado. Intenta nuevamente mas tarde."}), 429

            bucket.append(now)
            rate_buckets[key] = bucket
            return route_handler(*args, **kwargs)

        return wrapper

    return decorator


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-XSS-Protection", "0")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' https://www.gstatic.com https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' http://127.0.0.1:5000 http://localhost:5000 https://identitytoolkit.googleapis.com https://securetoken.googleapis.com; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
    )
    return response


@app.errorhandler(413)
def payload_too_large(error):
    return jsonify({"error": "La imagen es demasiado grande. Maximo permitido: 5 MB."}), 413


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    if isinstance(error, HTTPException):
        return jsonify({"error": error.description}), error.code

    request_id = str(uuid.uuid4())[:8]
    logger.exception("request_id=%s unexpected_error=%s", request_id, error)
    return jsonify({"error": "Error interno del servidor.", "request_id": request_id}), 500

PROMPT_ANALISIS = """
Analiza esta imagen de escritura a mano y responde SOLO con un objeto JSON valido,
sin markdown ni explicaciones, con estos campos exactos:

{
  "font": "<una de: caveat | kalam | patrick | architects | reenie | homemade>",
  "slant": "<una de: none | light | medium>",
  "ink": "<una de: blue | black | red | green>",
  "textSize": <numero entero entre 16 y 32>,
  "lineH": <numero entero entre 24 y 48>,
  "fontWeight": "<una de: 300 | 400 | 600>",
  "letterSpacing": <numero decimal entre -1 y 3>,
  "jitter": <numero decimal entre 0 y 2>,
  "wordSpacing": <numero decimal entre 0 y 6>,
  "lineRotation": <numero decimal entre 0 y 1.2>,
  "baselineWave": <numero decimal entre 0 y 3>,
  "confidence": <numero entre 0 y 1>,
  "description": "<descripcion breve del estilo en espanol, maximo 15 palabras>"
}

Reglas de decision:
- font: elige la fuente que mas se parezca al estilo visual de la letra manuscrita.
- slant: none=recta, light=leve inclinacion menor de 10 grados, medium=cursiva pronunciada mayor de 10 grados.
- ink: detecta el color dominante de los trazos.
- textSize: estima el tamano relativo de los caracteres.
- lineH: estima el interlineado relativo.
- fontWeight: 300=trazo delgado, 400=normal, 600=trazo grueso o presionado.
- letterSpacing: espacio entre letras, donde -1=compacta, 0=normal y 3=espaciada.
- jitter: irregularidad visual de letras y palabras, 0=muy uniforme, 2=muy irregular.
- wordSpacing: espacio entre palabras, 0=compacto, 6=muy separado.
- lineRotation: micro rotacion natural por renglon.
- baselineWave: variacion vertical natural sobre el renglon.
"""

PROMPT_GENERAR_INFORME = """
Crea un informe escolar en espanol a partir del tema indicado. Responde SOLO con JSON valido,
sin markdown ni explicaciones, con estos campos exactos:

{
  "title": "titulo claro del informe",
  "subject": "materia o area escolar + grado si aplica",
  "body": "texto completo del informe con parrafos y viñetas simples cuando convenga",
  "template": "una de: report | cover | science | math | minimal"
}

Reglas:
- Usa lenguaje escolar, claro y natural.
- No inventes datos demasiado especificos si no son necesarios.
- Incluye introduccion, desarrollo y cierre.
- Si el tema es de ciencias, sugiere template science.
- Si el tema es de matematica, sugiere template math.
- Si piden portada o presentacion, sugiere template cover.
- El body debe venir como texto plano, sin markdown pesado.
"""




def get_gemini_models():
    configured = os.environ.get("GEMINI_MODELS")
    if configured:
        models = [model.strip() for model in configured.split(",") if model.strip()]
    else:
        primary = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
        models = [
            primary,
            "gemini-2.5-flash",
            "gemini-2.0-flash",
        ]

    unique = []
    for model in models:
        if model not in unique:
            unique.append(model)
    return unique


def is_retryable_gemini_error(error):
    text = str(error).lower()
    retryable_markers = [
        "503",
        "unavailable",
        "high demand",
        "resource_exhausted",
        "429",
        "rate limit",
        "quota",
    ]
    return any(marker in text for marker in retryable_markers)


def generate_content_with_fallback(contents, config, attempts_per_model=2):
    last_error = None
    models = get_gemini_models()

    for model in models:
        for attempt in range(attempts_per_model):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                return response, model
            except Exception as error:
                last_error = error
                if not is_retryable_gemini_error(error):
                    raise
                if attempt < attempts_per_model - 1:
                    time.sleep(2 + attempt * 2)

    raise RuntimeError(
        "Gemini esta saturado o sin cuota disponible ahora mismo. "
        "Espera un minuto y vuelve a intentar. Ultimo error: " + str(last_error)
    )
def clamp_number(value, minimum, maximum, default, cast=float):
    try:
        return max(minimum, min(maximum, cast(value)))
    except (TypeError, ValueError):
        return default


def sanitize_result(result):
    valid_fonts = ["caveat", "kalam", "patrick", "architects", "reenie", "homemade"]
    valid_slants = ["none", "light", "medium"]
    valid_inks = ["blue", "black", "red", "green"]
    valid_weights = ["300", "400", "600"]

    font = result.get("font")
    slant = result.get("slant")
    ink = result.get("ink")
    font_weight = str(result.get("fontWeight", "400"))

    return {
        "font": font if font in valid_fonts else "caveat",
        "slant": slant if slant in valid_slants else "none",
        "ink": ink if ink in valid_inks else "blue",
        "textSize": clamp_number(result.get("textSize"), 16, 32, 22, int),
        "lineH": clamp_number(result.get("lineH"), 24, 48, 32, int),
        "fontWeight": font_weight if font_weight in valid_weights else "400",
        "letterSpacing": clamp_number(result.get("letterSpacing"), -1, 3, 0, float),
        "jitter": clamp_number(result.get("jitter"), 0, 2, 0.8, float),
        "wordSpacing": clamp_number(result.get("wordSpacing"), 0, 6, 2, float),
        "lineRotation": clamp_number(result.get("lineRotation"), 0, 1.2, 0.25, float),
        "baselineWave": clamp_number(result.get("baselineWave"), 0, 3, 0.8, float),
        "confidence": clamp_number(result.get("confidence"), 0, 1, 0.8, float),
        "description": str(result.get("description") or "Estilo detectado automaticamente")[:90],
    }


def strip_json_markdown(raw):
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1].strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return text


@app.route("/analizar", methods=["POST"])
@require_auth
@rate_limit("analizar")
def analizar():
    if client is None:
        return jsonify({"error": "Falta configurar la variable de entorno GEMINI_API_KEY"}), 500

    raw = ""
    try:
        file = request.files.get("image")
        if not file:
            return jsonify({"error": "No se recibio imagen"}), 400

        img_bytes = file.read()
        if not img_bytes:
            return jsonify({"error": "La imagen esta vacia"}), 400

        mime_type = file.content_type or "image/jpeg"
        if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
            return jsonify({"error": "Formato no permitido. Usa JPG, PNG o WebP."}), 415

        response, model_used = generate_content_with_fallback(
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type=mime_type),
                PROMPT_ANALISIS,
            ],
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=300,
                response_mime_type="application/json",
            ),
        )

        raw = response.text or ""
        result = json.loads(strip_json_markdown(raw))
        return jsonify(sanitize_result(result))

    except json.JSONDecodeError as error:
        logger.warning("gemini_analysis_json_error=%s raw_prefix=%s", error, raw[:160])
        return jsonify({"error": "La IA devolvio una respuesta invalida. Intenta nuevamente."}), 502
    except Exception as error:
        logger.exception("analysis_error=%s", error)
        return jsonify({"error": "No se pudo analizar la imagen en este momento."}), 502


def sanitize_report_result(result, tema, grado):
    valid_templates = ["report", "cover", "science", "math", "minimal"]
    template = result.get("template", "report")

    title = str(result.get("title") or f"Informe sobre {tema}").strip()
    subject = str(result.get("subject") or grado or "Trabajo escolar").strip()
    body = str(result.get("body") or "").strip()

    if not body:
        body = (
            f"Introduccion:\n"
            f"Este informe presenta informacion importante sobre {tema}.\n\n"
            f"Desarrollo:\n"
            f"El tema se explica de forma clara para facilitar su comprension escolar.\n\n"
            f"Conclusion:\n"
            f"Comprender {tema} ayuda a ampliar los conocimientos y relacionarlos con la vida diaria."
        )

    return {
        "title": title[:120],
        "subject": subject[:120],
        "body": body[:6000],
        "template": template if template in valid_templates else "report",
    }


@app.route("/generar-informe", methods=["POST"])
@require_auth
@rate_limit("generar_informe")
def generar_informe():
    if client is None:
        return jsonify({"error": "Falta configurar la variable de entorno GEMINI_API_KEY"}), 500

    raw = ""
    try:
        data = request.get_json(silent=True) or {}
        tema = str(data.get("tema") or "").strip()
        grado = str(data.get("grado") or "nivel escolar").strip()
        extension = str(data.get("extension") or "medio").strip().lower()
        plantilla = str(data.get("plantilla") or "report").strip()

        if not tema:
            return jsonify({"error": "Falta el tema del informe"}), 400
        if len(tema) > MAX_TOPIC_LENGTH:
            return jsonify({"error": f"El tema no puede superar {MAX_TOPIC_LENGTH} caracteres."}), 400
        if len(grado) > MAX_GRADE_LENGTH:
            return jsonify({"error": f"El grado o nivel no puede superar {MAX_GRADE_LENGTH} caracteres."}), 400

        extension_map = {
            "corto": "350 a 500 palabras",
            "medio": "650 a 850 palabras",
            "largo": "1000 a 1300 palabras",
        }
        target_length = extension_map.get(extension, extension_map["medio"])
        model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

        prompt = (
            PROMPT_GENERAR_INFORME
            + f"\nTema: {tema}\n"
            + f"Grado o nivel: {grado}\n"
            + f"Extension deseada: {target_length}\n"
            + f"Plantilla actual: {plantilla}\n"
        )

        response, model_used = generate_content_with_fallback(
            contents=[prompt],
            config=types.GenerateContentConfig(
                temperature=0.45,
                max_output_tokens=1800,
                response_mime_type="application/json",
            ),
        )

        raw = response.text or ""
        result = json.loads(strip_json_markdown(raw))
        return jsonify(sanitize_report_result(result, tema, grado))

    except json.JSONDecodeError as error:
        logger.warning("gemini_report_json_error=%s raw_prefix=%s", error, raw[:160])
        return jsonify({"error": "La IA devolvio una respuesta invalida. Intenta nuevamente."}), 502
    except Exception as error:
        logger.exception("report_error=%s", error)
        return jsonify({"error": "No se pudo generar el informe en este momento."}), 502



@app.route("/", methods=["GET"])
def index():
    return send_from_directory(app.root_path, "index.html")


@app.route("/index.html", methods=["GET"])
def index_html():
    return send_from_directory(app.root_path, "index.html")


@app.route("/css/<path:filename>", methods=["GET"])
def css_files(filename):
    return send_from_directory(os.path.join(app.root_path, "css"), filename)


@app.route("/js/<path:filename>", methods=["GET"])
def js_files(filename):
    return send_from_directory(os.path.join(app.root_path, "js"), filename)

@app.route("/health", methods=["GET"])
def health():
    payload = {
        "status": "ok",
        "gemini_key_configured": client is not None,
        "auth_required": AUTH_REQUIRED,
        "firebase_admin_configured": firebase_ready,
    }
    if os.environ.get("APP_ENV", "development") != "production":
        payload["model"] = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
        payload["fallback_models"] = get_gemini_models()
    return jsonify(payload)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")






