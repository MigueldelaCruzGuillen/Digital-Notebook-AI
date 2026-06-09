@echo off
set "FIREBASE_SERVICE_ACCOUNT=C:\Xampp1\firebase-keys\mi-cuaderno-service-account.json"
set "PYTHONPATH=%~dp0.python-packages"
set "APP_PYTHON=C:\Users\Admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if "%GEMINI_API_KEY%"=="" (
  echo Falta configurar GEMINI_API_KEY como variable de entorno.
  echo No pegues la clave dentro de este archivo.
  pause
  exit /b 1
)

"%APP_PYTHON%" "%~dp0servidor.py"
pause
