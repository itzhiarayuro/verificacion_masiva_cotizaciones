import pandas as pd
import os

os.makedirs('templates', exist_ok=True)

# Plantilla 1: Obra Civil (PTAR)
df_obra = pd.DataFrame({
    'ÍTEM': ['1', '2'],
    'DESCRIPCIÓN': ['Cemento Portland 50kg', 'Acero de refuerzo 1/2"'],
    'VALOR SIN IVA COT 1': [25000, 30000],
    'IVA COT 1': [4750, 5700],
    'VALOR CON IVA COT 1': [29750, 35700],
    'PROVEEDOR COT 1': ['Ferretería A', 'Ferretería B'],
    'AÑO COT 1': [2026, 2026]
})
df_obra.to_excel('templates/plantilla_obra_civil.xlsx', index=False)

# Plantilla 2: Alquiler de Equipos
df_equipos = pd.DataFrame({
    'ÍTEM': ['1', '2'],
    'EQUIPO': ['Retroexcavadora', 'Vibrocompactador'],
    'TARIFA DÍA (SIN IVA)': [800000, 450000],
    'IVA': [152000, 85500],
    'TARIFA DÍA (CON IVA)': [952000, 535500],
    'INCLUYE OPERADOR': ['Sí', 'Sí'],
    'INCLUYE COMBUSTIBLE': ['No', 'No'],
    'PROVEEDOR': ['Maquinaria XYZ', 'Maquinaria XYZ']
})
df_equipos.to_excel('templates/plantilla_alquiler_equipos.xlsx', index=False)

# Plantilla 3: Material Eléctrico
df_electrico = pd.DataFrame({
    'ÍTEM': ['1', '2'],
    'REFERENCIA': ['Cable THHN 12 AWG', 'Tubo Conduit PVC 1/2"'],
    'MARCA': ['Centelsa', 'Pavco'],
    'UNIDAD': ['Metro', 'Tubo 3m'],
    'PRECIO UNITARIO (SIN IVA)': [1200, 4500],
    'IVA': [228, 855],
    'PRECIO TOTAL': [1428, 5355],
    'PROVEEDOR': ['Eléctricos del Norte', 'Eléctricos del Norte']
})
df_electrico.to_excel('templates/plantilla_material_electrico.xlsx', index=False)

print("Plantillas creadas exitosamente.")
