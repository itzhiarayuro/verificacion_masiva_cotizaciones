from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class AgentRole:
    id: str
    name: str
    department: str
    responsibility: str


AGENT_ROSTER: List[AgentRole] = [
    AgentRole("senior_dev", "Senior Developer", "Liderazgo", "Orquesta el pipeline completo y toma decisiones de fallback"),
    AgentRole("tech_lead", "Tech Lead", "Liderazgo", "Define estrategia de extracción por tipo de PDF"),
    AgentRole("backend_dev", "Backend Developer", "Desarrollo", "Ejecuta parsers y transformaciones de datos"),
    AgentRole("frontend_dev", "UI Developer", "Desarrollo", "Formatea salida para vista en vivo y exportación"),
    AgentRole("api_specialist", "API Integration Specialist", "Desarrollo", "Gestiona llamadas Gemini/NVIDIA"),
    AgentRole("devops", "DevOps Engineer", "Desarrollo", "Maneja archivos temporales y recursos del sistema"),
    AgentRole("data_engineer", "Data Engineer", "Datos", "Normaliza filas al esquema CSV consolidado"),
    AgentRole("ml_engineer", "ML/LLM Engineer", "Datos", "Construye prompts y parsea respuestas JSON de IA"),
    AgentRole("ocr_specialist", "OCR Specialist", "Datos", "Procesa PDFs escaneados e imágenes"),
    AgentRole("nlp_parser", "NLP Parser Specialist", "Datos", "Extrae ítems de texto no tabular"),
    AgentRole("procurement_analyst", "Procurement Analyst", "Dominio", "Valida que cada fila sea un producto/servicio real"),
    AgentRole("civil_engineer", "Civil Engineering Specialist", "Dominio", "Revisa descripciones técnicas de construcción"),
    AgentRole("pdf_analyst", "PDF Document Analyst", "Dominio", "Clasifica tipo de documento (cotización, catálogo, ficha)"),
    AgentRole("qa_lead", "QA Lead", "Calidad", "Coordina pruebas y aprueba/rechaza lotes"),
    AgentRole("qa_automation", "QA Automation Tester", "Calidad", "Ejecuta tests automáticos por fila"),
    AgentRole("qa_live", "Real-time QA Monitor", "Calidad", "Monitorea extracción en tiempo real"),
    AgentRole("data_validator", "Data Validation Specialist", "Calidad", "Verifica campos obligatorios y formatos"),
    AgentRole("provider_id", "Provider Identifier", "Especialistas", "Identifica proveedor emisor vs cliente"),
    AgentRole("price_normalizer", "Price Normalizer", "Especialistas", "Limpia precios COP/USD y separadores"),
    AgentRole("metadata_extractor", "Metadata Extractor", "Especialistas", "Extrae NIT, contacto, condiciones comerciales"),
    AgentRole("table_analyst", "Table Structure Analyst", "Especialistas", "Detecta y parsea tablas con pdfplumber"),
    AgentRole("reconciliation", "Reconciliation Auditor", "Especialistas", "Cruza resultados y detecta anomalías"),
    AgentRole("csv_exporter", "CSV Export Specialist", "Especialistas", "Genera CSV consolidado formato Grok"),
    AgentRole("security", "Security/Compliance Reviewer", "Especialistas", "Evita exponer datos sensibles en logs"),
]

LEAD_AGENT_ID = "senior_dev"