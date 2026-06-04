import pandas as pd
import logging
from typing import List, Dict, Any
import os

logger = logging.getLogger(__name__)

class ReportWriter:
    """
    Genera el reporte final de auditoría con los hallazgos encontrados por el
    Reconciliation Engine.
    """
    def write_audit_report(self, hallazgos: List[Dict[str, Any]], output_path: str = "outputs/Reporte_Auditoria.xlsx"):
        """Escribe los hallazgos en un archivo Excel."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        if not hallazgos:
            # Si no hay hallazgos, creamos un reporte vacío pero indicando éxito
            df = pd.DataFrame([{"Mensaje": "No se encontraron discrepancias. Todo aprobado."}])
            df.to_excel(output_path, index=False)
            return

        # Convertir a DataFrame
        df = pd.DataFrame(hallazgos)
        
        # Renombrar columnas para el usuario final
        df.rename(columns={
            "item": "Ítem",
            "severidad": "Severidad",
            "tipo": "Tipo de Hallazgo",
            "mensaje": "Descripción del Problema"
        }, inplace=True)
        
        # Ordenar por severidad (ALTA primero) si es posible
        severidad_orden = {"ALTA": 1, "MEDIA": 2, "BAJA": 3}
        df["_orden"] = df["Severidad"].map(severidad_orden).fillna(4)
        df.sort_values(by=["_orden", "Ítem"], inplace=True)
        df.drop(columns=["_orden"], inplace=True)
        
        try:
            # Uso de ExcelWriter para formateo básico (idealmente con openpyxl)
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name="Hallazgos", index=False)
            logger.info(f"Reporte de Auditoría generado en {output_path}")
        except Exception as e:
            logger.error(f"Error al generar reporte de auditoría: {e}")
