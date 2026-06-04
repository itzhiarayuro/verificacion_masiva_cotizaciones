from typing import List, Dict, Any
import logging
from .provider_identifier import ProviderIdentifier

logger = logging.getLogger(__name__)

class ReconciliationEngine:
    """
    Motor central que toma todas las cotizaciones de un ítem, las cruza y genera hallazgos
    si detecta inconsistencias de auditoría.
    """
    def __init__(self):
        self.provider_id = ProviderIdentifier()
        self.hallazgos = []

    def clear_hallazgos(self):
        self.hallazgos = []

    def audit_item(self, item_id: str, cotizaciones: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analiza el set de cotizaciones de un único ítem y decide su estado final.
        """
        estado = "APROBADO"
        
        # 1. Validar cantidad mínima
        if len(cotizaciones) < 2:
            self.hallazgos.append({
                "item": item_id,
                "severidad": "MEDIA",
                "tipo": "COTIZACIONES_INSUFICIENTES",
                "mensaje": f"Se requieren al menos 2 cotizaciones. Solo se encontraron {len(cotizaciones)}."
            })
            estado = "CON_DISCREPANCIAS"

        # 2. Detección de Proveedores Múltiples Precios
        proveedores_vistos = {}
        for idx, cot in enumerate(cotizaciones):
            data = cot.get("data", {})
            prov_raw = data.get("Proveedor")
            if prov_raw:
                prov_norm = self.provider_id.normalize_name(prov_raw)
                precio = data.get("Valor_Sin_IVA")
                
                if prov_norm in proveedores_vistos:
                    precio_anterior = proveedores_vistos[prov_norm]["precio"]
                    if precio != precio_anterior:
                        self.hallazgos.append({
                            "item": item_id,
                            "severidad": "ALTA",
                            "tipo": "PROVEEDOR_MULTIPLE_PRECIOS",
                            "mensaje": f"El proveedor '{prov_raw}' tiene distintos precios ({precio} y {precio_anterior}) para el mismo ítem."
                        })
                        estado = "CON_DISCREPANCIAS"
                else:
                    proveedores_vistos[prov_norm] = {"precio": precio, "index": idx}

        # 3. Múltiples descripciones para el mismo ítem
        # Si un PDF dice "Tubo 1/2" y otro "Tubo 3/4" en la extracción, es un riesgo.
        descripciones = set()
        for cot in cotizaciones:
            desc = str(cot.get("data", {}).get("Descripcion", "")).strip().lower()
            if desc and desc != "none":
                descripciones.add(desc)
                
        if len(descripciones) > 1:
            self.hallazgos.append({
                "item": item_id,
                "severidad": "ALTA",
                "tipo": "DESCRIPCIONES_INCONSISTENTES",
                "mensaje": f"Se encontraron descripciones diferentes para el mismo ítem: {list(descripciones)}"
            })
            estado = "CON_DISCREPANCIAS"

        # Retornar resumen del ítem
        return {
            "item_id": item_id,
            "estado": estado,
            "cotizaciones_procesadas": len(cotizaciones),
            "hallazgos_count": len([h for h in self.hallazgos if h["item"] == item_id]),
            "mejor_precio": self._get_best_price(cotizaciones)
        }

    def _get_best_price(self, cotizaciones: List[Dict[str, Any]]) -> Any:
        precios = []
        for c in cotizaciones:
            try:
                # Intenta extraer precio numérico asumiendo que es dict o string limpiable
                p = c.get("data", {}).get("Valor_Sin_IVA")
                if p:
                    # Lógica simple de limpieza para obtener numérico
                    p_str = str(p).replace("$", "").replace(".", "").replace(",", ".").strip()
                    precios.append(float(p_str))
            except ValueError:
                pass
        return min(precios) if precios else None
