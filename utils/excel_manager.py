import pandas as pd
import json
import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class ExcelManager:
    def __init__(self, config_path: str = "outputs/config.json"):
        self.config_path = config_path
        self.mapping: Dict[str, str] = {}
        self.load_config()

    def load_config(self):
        """Carga el mapeo de columnas guardado si existe."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.mapping = data.get("column_mapping", {})
            except Exception as e:
                logger.warning(f"Error al leer config.json: {e}")

    def save_mapping(self, new_mapping: Dict[str, str]):
        """Guarda un nuevo mapeo en el archivo config."""
        self.mapping = new_mapping
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump({"column_mapping": self.mapping}, f, indent=4)
        except Exception as e:
            logger.error(f"Error al guardar config.json: {e}")

    def get_columns_from_excel(self, file_path: str) -> List[str]:
        """Lee la cabecera de un Excel para devolver las columnas."""
        try:
            df = pd.read_excel(file_path, nrows=0)
            return list(df.columns)
        except Exception as e:
            logger.error(f"Error leyendo columnas del Excel: {e}")
            return []

    def get_preview_from_excel(self, file_path: str, rows: int = 5) -> pd.DataFrame:
        """Obtiene las primeras filas para visualización en UI."""
        try:
            return pd.read_excel(file_path, nrows=rows)
        except Exception as e:
            logger.error(f"Error leyendo preview del Excel: {e}")
            return pd.DataFrame()

    def apply_data_to_excel(self, input_file: str, output_file: str, extracted_data: List[Dict[str, Any]]):
        """
        Escribe los datos extraídos en un nuevo Excel basado en la plantilla original.
        Utiliza el mapping para saber en qué columna va cada dato extraído.
        """
        try:
            df = pd.read_excel(input_file)
            
            # TODO: Lógica avanzada para buscar en qué fila va qué dato (basado en items, descripción)
            # Por ahora, un append simple o buscar la fila vacía.
            # Suponemos que extracted_data es una lista donde cada item es un row extraído.
            
            new_rows = []
            for record in extracted_data:
                # Mapeamos record dict a la estructura de columnas de df usando self.mapping
                row_data = {}
                for col_name in df.columns:
                    # Si la columna del excel está en nuestro mapping, extraemos el valor correspondiente
                    # mapping: {"columna_excel": "clave_json"}
                    json_key = self.mapping.get(col_name)
                    if json_key and json_key in record:
                        row_data[col_name] = record[json_key]
                    else:
                        row_data[col_name] = None
                new_rows.append(row_data)
            
            if new_rows:
                df_new = pd.DataFrame(new_rows)
                df_result = pd.concat([df, df_new], ignore_index=True)
                df_result.to_excel(output_file, index=False)
            else:
                df.to_excel(output_file, index=False)
                
            return True
        except Exception as e:
            logger.error(f"Error escribiendo al Excel: {e}")
            return False
