
# Digital-Notebook-AI

Digital-Notebook-AI es una aplicación web para crear informes escolares con apariencia manuscrita. Permite escribir o generar contenido con IA, ajustar el estilo de letra, simular hojas de cuaderno y exportar el resultado como PDF o imagen.

## Características

- Inicio de sesión con Firebase Authentication.
- Registro, login, recuperación de contraseña y acceso con Google.
- Generación de informes escolares con Gemini.
- Análisis de una foto de escritura manual para aplicar un estilo parecido.
- Editor de informes con título, materia, fecha y cuerpo del texto.
- Plantillas para informe, portada, ciencias, matemática y diseño minimalista.
- Personalización de fuente manuscrita, tamaño, inclinación, interlineado, margen, tinta y tipo de hoja.
- Simulación de escritura humana con variaciones, errores y efecto de foto real.
- Historial local de tareas guardadas.
- Exportación a PDF e imagen PNG.
- Backend Flask con protección por autenticación, CORS, límites de uso y cabeceras de seguridad.

## Tecnologías

- HTML, CSS y JavaScript
- Python
- Flask
- Firebase Authentication / Firebase Admin
- Google Gemini API
- html2canvas
- jsPDF
- Gunicorn
- Render

## Estructura del proyecto

```text
Digital-Notebook-AI/
├── index.html
├── servidor.py
├── requirements.txt
├── package.json
├── Procfile
├── render.yaml
├── AUTH_SETUP.md
├── iniciar_servidor.bat
├── css/
│   └── styles.css
└── js/
    └── firebase-config.js
```

## Requisitos

- Python 3.10 o superior
- Cuenta/proyecto en Firebase
- Clave de API de Gemini
- Opcional: cuenta de Render para desplegar

## Instalación local

Clona el repositorio:

```bash
git clone https://github.com/MigueldelaCruzGuillen/Digital-Notebook-AI.git
cd Digital-Notebook-AI
```

Crea y activa un entorno virtual:

```bash
python -m venv .venv
```

En Windows:

```bash
.venv\Scripts\activate
```

En macOS/Linux:

```bash
source .venv/bin/activate
```

Instala las dependencias:

```bash
pip install -r requirements.txt
```

## Configuración

### 1. Firebase en el frontend

Edita `js/firebase-config.js` con los datos de tu proyecto Firebase:

```js
export const firebaseConfig = {
  apiKey: "TU_API_KEY",
  authDomain: "TU_PROYECTO.firebaseapp.com",
  projectId: "TU_PROJECT_ID",
  appId: "TU_APP_ID",
};
```

En Firebase Console activa:

- Email/Password
- Google
- Dominios autorizados para `localhost` y tu dominio de producción

### 2. Firebase Admin en el backend

Descarga una service account desde:

```text
Firebase Console > Project settings > Service accounts > Generate new private key
```

Luego configura una de estas opciones:

```bash
set FIREBASE_SERVICE_ACCOUNT=C:\ruta\segura\service-account.json
```

O, para producción:

```bash
set FIREBASE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
```

### 3. Gemini

Configura tu clave de Gemini:

```bash
set GEMINI_API_KEY=tu_api_key_de_gemini
```

Variables útiles:

```bash
set AUTH_REQUIRED=1
set GEMINI_MODEL=gemini-2.5-flash-lite
set FRONTEND_ORIGINS=http://127.0.0.1:5000,http://localhost:5000
```

Para desarrollo local sin validar Firebase en el backend:

```bash
set AUTH_REQUIRED=0
```

No uses `AUTH_REQUIRED=0` en producción.

## Ejecutar el proyecto

Inicia el servidor:

```bash
python servidor.py
```

Abre en el navegador:

```text
http://127.0.0.1:5000
```

También puedes usar el archivo incluido:

```bash
iniciar_servidor.bat
```

## Endpoints principales

| Método | Ruta | Descripción |
| --- | --- | --- |
| `GET` | `/` | Sirve la aplicación web |
| `GET` | `/health` | Verifica el estado del backend |
| `POST` | `/analizar` | Analiza una imagen de escritura y devuelve parámetros de estilo |
| `POST` | `/generar-informe` | Genera un informe escolar con IA |

Los endpoints de IA requieren autenticación cuando `AUTH_REQUIRED=1`.

## Despliegue en Render

El proyecto incluye `render.yaml` y `Procfile`.

Comando de instalación:

```bash
pip install -r requirements.txt
```

Comando de inicio:

```bash
gunicorn servidor:app
```

Variables recomendadas en Render:

```text
GEMINI_API_KEY
AUTH_REQUIRED=1
APP_ENV=production
GEMINI_MODEL=gemini-2.5-flash-lite
FIREBASE_SERVICE_ACCOUNT_JSON
FRONTEND_ORIGINS
```

En `FRONTEND_ORIGINS` coloca el dominio de tu aplicación desplegada.

## Seguridad

El backend incluye:

- Validación de token Firebase.
- Límite de peticiones por usuario.
- Restricción de tipos de imagen permitidos: JPG, PNG y WebP.
- Límite de tamaño de imagen.
- Cabeceras de seguridad HTTP.
- Manejo centralizado de errores.

## Autor

Desarrollado por Miguel de la Cruz Guillén.

Demo gratis: [https://lnkd.in/ePTCNksd](https://mi-cuaderno.onrender.com)
Repositorio: [MigueldelaCruzGuillen/Digital-Notebook-AI](https://github.com/MigueldelaCruzGuillen/Digital-Notebook-AI)
```

Los cambios principales realizados:
- Actualizado el nombre del repositorio en el título y en todas las referencias
- Cambiada la estructura del proyecto para reflejar el nuevo nombre de la carpeta raíz
- Actualizado el enlace del repositorio en la sección de autor
