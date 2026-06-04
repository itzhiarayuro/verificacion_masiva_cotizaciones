import re
from typing import Optional

class ProviderIdentifier:
    """Normaliza nombres de proveedores para poder compararlos y evitar duplicados."""
    
    def normalize_name(self, name: Optional[str]) -> str:
        if not name:
            return "desconocido"
            
        # 1. Convertir a minúsculas
        norm = name.lower()
        # 2. Remover puntos, comas y caracteres especiales
        norm = re.sub(r'[.,;\'"&]', '', norm)
        # 3. Remover sufijos corporativos comunes en Colombia/Latam
        norm = re.sub(r'\b(sas|sa|ltda|limitada|en comandita|sucursal)\b', '', norm)
        # 4. Remover espacios extra
        norm = " ".join(norm.split())
        
        return norm if norm else "desconocido"
    
    def are_same_provider(self, name1: str, name2: str) -> bool:
        """Determina si dos nombres probablemente corresponden al mismo proveedor."""
        n1 = self.normalize_name(name1)
        n2 = self.normalize_name(name2)
        
        if n1 == "desconocido" or n2 == "desconocido":
            return False
            
        # Coincidencia exacta post-normalización
        if n1 == n2:
            return True
            
        # Inclusión de nombre (Ej: "Ferreteria el Sol" en "Ferreteria el Sol del Norte")
        if len(n1) > 5 and len(n2) > 5:
            if n1 in n2 or n2 in n1:
                return True
                
        return False
