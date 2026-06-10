#!/bin/bash
echo "=============================================="
echo "Ejecutando suite de tests - Auditor de Cotizaciones V3"
echo "=============================================="

source venv/bin/activate 2>/dev/null || echo "[WARN] No se pudo activar venv automaticamente."

python -m pytest tests/ -q --tb=short

echo ""
echo "Tests finalizados."
