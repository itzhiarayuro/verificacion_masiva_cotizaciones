#!/bin/bash

echo "=============================================="
echo "Instalando Auditor de Cotizaciones V3..."
echo "=============================================="

if ! command -v python3 &> /dev/null
then
    echo "[ERROR] Python3 no está instalado."
    exit 1
fi

echo "Creando entorno virtual (venv)..."
python3 -m venv venv

echo "Activando entorno e instalando dependencias (esto puede tomar unos minutos)..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "=============================================="
echo "¡Instalación Completada!"
echo ""
echo "Para ejecutar los tests (pytest):"
echo "  ./run_tests.sh"
echo ""
echo "Iniciando la aplicación web..."
echo "=============================================="
streamlit run app.py
