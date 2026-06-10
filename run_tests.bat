@echo off
echo ==============================================
echo Ejecutando suite de tests - Auditor de Cotizaciones V3
echo ==============================================

call venv\Scripts\activate.bat 2>nul || echo [WARN] No se pudo activar venv automaticamente. Asegurate de estar en el entorno correcto.

python -m pytest tests/ -q --tb=short

echo.
echo Tests finalizados.
pause
