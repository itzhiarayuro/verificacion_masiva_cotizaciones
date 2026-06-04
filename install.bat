@echo off
echo ==============================================
echo Instalando Auditor de Cotizaciones V3...
echo ==============================================

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta instalado o no esta en el PATH.
    echo Por favor instala Python 3.11 o superior.
    pause
    exit /b
)

echo Creando entorno virtual (venv)...
python -m venv venv

echo Activando entorno e instalando dependencias (esto puede tomar unos minutos)...
call venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

echo ==============================================
echo ¡Instalacion Completada!
echo Iniciando la aplicacion web...
echo ==============================================
streamlit run app.py
pause
