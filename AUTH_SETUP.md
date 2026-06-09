# Configurar autenticacion con Firebase

Esta app usa Firebase Authentication para login, registro, Google, recuperacion de contrasena y sesiones.

## 1. Crear proyecto

1. Entra a Firebase Console.
2. Crea un proyecto.
3. Ve a Authentication > Sign-in method.
4. Activa Email/Password.
5. Activa Google.
6. En Authentication > Settings > Authorized domains agrega tu dominio. Para pruebas locales deja `localhost` y agrega el host que uses con XAMPP si hace falta.

## 2. Configurar frontend

En `js/firebase-config.js`, cambia los placeholders:

```js
export const firebaseConfig = {
  apiKey: "TU_API_KEY",
  authDomain: "TU_PROYECTO.firebaseapp.com",
  projectId: "TU_PROJECT_ID",
  appId: "TU_APP_ID",
};
```

Esos datos salen en Firebase Console > Project settings > General > Your apps > Web app.

## 3. Configurar backend Flask

Instala dependencias:

```bash
pip install -r requirements.txt
```

Descarga una service account desde Firebase Console > Project settings > Service accounts > Generate new private key.

Luego define estas variables antes de iniciar `servidor.py`:

```bash
set FIREBASE_SERVICE_ACCOUNT=C:\ruta\segura\service-account.json
set GEMINI_API_KEY=tu_api_key_de_gemini
python servidor.py
```

En esta computadora ya quedo creado `iniciar_servidor.bat`, que configura:

- `FIREBASE_SERVICE_ACCOUNT=C:\Xampp1\firebase-keys\mi-cuaderno-service-account.json`
- `PYTHONPATH=.python-packages`
- Python incluido por Codex

Antes de ejecutarlo, configura `GEMINI_API_KEY` como variable de entorno del sistema o de la terminal. No pegues la clave dentro del archivo `.bat`.

Puedes iniciar el backend ejecutando:

```bash
iniciar_servidor.bat
```

Para desarrollo local temporal sin autenticar el backend:

```bash
set AUTH_REQUIRED=0
python servidor.py
```

No uses `AUTH_REQUIRED=0` en produccion.
