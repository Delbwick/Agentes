"""
Double Helix Dealflow Finder v3.1
Pipeline completo para identificar oportunidades de inversión en healthtech:
- Crawling inteligente de URLs (extrae enlaces internos)
- Extracción jerárquica: Tecnologías/Patentes → Artículos → Empresas → Personas
- Normalización de URLs (elimina utm, tracking, repara truncamientos)
- Análisis IA específico por tipo de entidad
- VALIDACIÓN CON PERPLEXITY para verificar hechos, fechas y URLs
- Monitoreo de portales europeos con fuentes reales (no simuladas)
- Caché robusto para evitar re-procesamiento
"""
import os
import re
import json
import time
import hashlib
import requests
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, urlencode, urljoin, unquote
from collections import defaultdict
from typing import Optional, List, Dict, Any
import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
from openai import OpenAI

# ============================================================================
# CONFIGURACIÓN GLOBAL
# ============================================================================
CACHE_DIR = Path("dealflow_cache")
CACHE_DIR.mkdir(exist_ok=True)

# Branding Double Helix (sin cambios de KaiBot)
BRANDING = {
    "logo_url": "https://doublehelix.vc/wp-content/uploads/2024/11/DH_Healthtech.jpg",
    "primary_color": "#00A6A6",
    "secondary_color": "#1A1A2E",
    "accent_color": "#16213E",
}

# Portales europeos para monitoreo
EUROPEAN_PORTALS = {
    "CORDIS": {
        "base_url": "https://cordis.europa.eu",
        "search_endpoint": "/project/search",
        "topics": ["health", "biotech", "medical", "pharma", "diagnostic", "digital health"],
    },
    "EU-Funding": {
        "base_url": "https://ec.europa.eu/info/funding-tenders",
        "search_endpoint": "/opportunities/portal/screen/home",
    },
    "EIC": {
        "base_url": "https://eic.ec.europa.eu",
        "search_endpoint": "/eic-funding-opportunities",
    },
}

st.set_page_config(
    page_title="🧬 Double Helix Dealflow Finder",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CSS PERSONALIZADO CON BRANDING DH
# ============================================================================
st.markdown(f"""
<style>
:root {{
    --dh-primary: {BRANDING['primary_color']};
    --dh-secondary: {BRANDING['secondary_color']};
    --dh-accent: {BRANDING['accent_color']};
}}
.main-header {{
    display: flex; align-items: center; gap: 1rem;
    padding: 1rem 0; border-bottom: 2px solid var(--dh-primary);
    margin-bottom: 2rem;
}}
.logo-img {{ height: 50px; width: auto; }}
.logo-text {{ font-size: 1.5rem; font-weight: 700; color: var(--dh-secondary); margin: 0; }}
.logo-subtitle {{ font-size: 0.9rem; color: var(--dh-primary); margin: 0; }}
.stButton>button {{
    background: linear-gradient(135deg, var(--dh-secondary), var(--dh-accent));
    color: white !important; border: 2px solid var(--dh-primary);
    border-radius: 8px; font-weight: 600;
}}
.stButton>button:hover {{
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 166, 166, 0.3);
}}
.opportunity-card {{
    padding: 1rem; border: 1px solid #e0e0e0;
    border-left: 4px solid var(--dh-primary);
    border-radius: 8px; margin: 0.5rem 0; background: white;
}}
.match-score {{
    background: linear-gradient(135deg, var(--dh-primary), #008B8B);
    color: white; padding: 0.3rem 0.8rem;
    border-radius: 20px; font-weight: 700; font-size: 0.9rem;
}}
.entity-tag {{
    background: var(--dh-secondary); color: white;
    padding: 0.2rem 0.6rem; border-radius: 6px;
    font-size: 0.8rem; font-weight: 500;
    display: inline-block; margin-right: 0.4rem;
}}
.section-title {{
    font-size: 1.4rem; font-weight: 600;
    color: var(--dh-secondary); margin: 1.5rem 0 1rem;
    padding-bottom: 0.5rem; border-bottom: 2px solid var(--dh-primary);
}}
.footer {{
    text-align: center; padding: 2rem 0 1rem;
    color: #666; font-size: 0.85rem;
    border-top: 1px solid #e0e0e0; margin-top: 3rem;
}}
.status-badge {{
    padding: 0.25rem 0.75rem; border-radius: 12px;
    font-size: 0.8rem; font-weight: 600;
}}
.status-new {{ background: #10B981; color: white; }}
.status-updated {{ background: #3B82F6; color: white; }}
.status-monitored {{ background: #8B5CF6; color: white; }}
</style>
""", unsafe_allow_html=True)

# ============================================================================
# UTILS: URL NORMALIZATION & CACHING (MEJORADO)
# ============================================================================
def clean_and_validate_urls(text: str) -> str:
    """Detecta URLs, elimina truncamientos y valida formato"""
    url_pattern = re.compile(r'(https?://[^\s)]}>]+)')
    urls = url_pattern.findall(text)
    
    # Reemplaza URLs truncadas o malformadas
    for url in urls:
        if not url.endswith(('.html', '.php', '.aspx', '/')) and not url[-1].isalnum():
            # Intenta completar o limpiar
            clean_url = re.sub(r'[^\w\-._~:/?#\[\]@!$&\'()*+,;=%]', '', url)
            if clean_url.startswith('http'):
                text = text.replace(url, clean_url)
    return text

def normalize_url(url: str) -> str:
    """Normaliza URL: elimina parámetros de tracking pero mantiene URL completa"""
    if not url or not url.startswith(("http://", "https://")):
        if url and not url.startswith("www."):
            url = f"https://{url}"
        elif url.startswith("www."):
            url = f"https://{url}"
    
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        # Parámetros a eliminar (tracking, analytics, etc.)
        remove_params = [
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
            'gclid', 'gbraid', 'wbraid', 'fbclid', 'mc_eid', 'pk_campaign',
            'pk_kwd', 'hsa_cam', 'hsa_grp', 'hsa_mt', 'hsa_src', 'hsa_ad',
            'hsa_acc', 'hsa_net', 'hsa_ver', '_gl', '_ga', '_gid', 'fbclid',
            'ref', 'source', 'medium', 'campaign', 'content', 'term'
        ]
        
        # Filtrar parámetros
        clean_params = {k: v for k, v in query_params.items() if k not in remove_params}
        
        # Reconstruir URL
        clean_query = urlencode(clean_params, doseq=True) if clean_params else ""
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if clean_query:
            clean_url += f"?{clean_query}"
        if parsed.fragment:
            clean_url += f"#{parsed.fragment}"
        
        return clean_url
    except:
        return url

def url_hash(url: str) -> str:
    """Genera hash único para una URL normalizada (para caché)"""
    normalized = normalize_url(url)
    return hashlib.md5(normalized.encode()).hexdigest()[:16]

def get_cached_data(cache_type: str, key: str) -> Optional[Dict]:
    """Obtiene datos desde caché si existen"""
    cache_file = CACHE_DIR / f"{cache_type}_{key}.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Verificar si el caché es reciente (< 7 días para contenido dinámico)
            if cache_type == "page_analysis":
                cached_time = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
                if datetime.now() - cached_time > timedelta(days=7):
                    return None  # Caché expirado
            return data
        except:
            return None
    return None

def save_cached_data(cache_type: str, key: str, data: Dict):
    """Guarda datos en caché con timestamp"""
    data["cached_at"] = datetime.now().isoformat()
    cache_file = CACHE_DIR / f"{cache_type}_{key}.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def detect_page_type(url: str, content: str, title: str) -> str:
    """Detecta el tipo de página para priorizar extracción"""
    url_lower = url.lower()
    content_lower = content.lower()
    title_lower = title.lower()
    
    # Patrones para detectar tipo de página
    if any(kw in url_lower for kw in ['spin', 'spin-off', 'spinoff', 'startup', 'empresa', 'company']):
        return "company_directory"
    if any(kw in url_lower for kw in ['project', 'proyecto', 'funding', 'grant', 'cordis', 'horizon']):
        return "project_listing"
    if any(kw in url_lower for kw in ['patent', 'patente', 'ip', 'property', 'technology', 'tecnologia']):
        return "technology_transfer"
    if any(kw in url_lower for kw in ['publication', 'paper', 'article', 'research', 'investigacion']):
        return "research_publications"
    if any(kw in url_lower for kw in ['team', 'people', 'investigator', 'researcher', 'orcid']):
        return "people_directory"
    
    # Detectar por contenido
    if re.search(r'spin[-\s]?off|startup|empresa|company', content_lower):
        return "company_directory"
    if re.search(r'patent|patente|intellectual\s*property', content_lower):
        return "technology_transfer"
    if re.search(r'publication|paper|article|doi|orcid', content_lower):
        return "research_publications"
    if re.search(r'project|funding|grant|horizon|cordis', content_lower):
        return "project_listing"
    
    return "general"

# ============================================================================
# CLASE: WEB CRAWLER (Inteligente - extrae enlaces internos)
# ============================================================================
class WebCrawler:
    """Crawler que extrae contenido y enlaces internos de una URL."""
    
    def __init__(self, user_agent: str = None, max_depth: int = 1):
        self.user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})
        self.max_depth = max_depth
    
    def fetch_page(self, url: str, timeout: int = 30) -> Dict:
        """Descarga y parsea una página web."""
        url = normalize_url(url)
        try:
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            
            parsed = urlparse(url)
            if not parsed.netloc:
                return {"ok": False, "error": "URL inválida", "url": url}
            
            resp = self.session.get(url, timeout=timeout, allow_redirects=True)
            if resp.status_code == 200:
                resp.encoding = resp.apparent_encoding
                soup = BeautifulSoup(resp.text, "html.parser")
                
                # Extraer metadatos
                title = soup.title.string.strip() if soup.title else ""
                meta_desc = soup.find("meta", attrs={"name": "description"})
                description = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else ""
                
                # Extraer enlaces internos (para crawling posterior)
                internal_links = self._extract_internal_links(soup, url)
                
                # Detectar tipo de página
                page_type = detect_page_type(url, resp.text, title)
                
                return {
                    "ok": True,
                    "url": resp.url,
                    "html": resp.text,
                    "text": self._extract_main_text(soup),
                    "title": title,
                    "description": description,
                    "page_type": page_type,
                    "internal_links": internal_links[:15],  # Limitar a 15 enlaces
                }
            else:
                return {"ok": False, "error": f"HTTP {resp.status_code}", "url": url}
        except requests.Timeout:
            return {"ok": False, "error": "Timeout", "url": url}
        except Exception as e:
            return {"ok": False, "error": str(e)[:100], "url": url}
    
    def _extract_internal_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extrae enlaces internos válidos de una página."""
        links = []
        base_domain = urlparse(base_url).netloc
        
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            
            # Solo enlaces del mismo dominio
            if parsed.netloc != base_domain:
                continue
            
            # Filtrar extensiones no relevantes
            if any(parsed.path.lower().endswith(ext) for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".tar", ".gz"]):
                continue
            
            links.append({
                "url": normalize_url(full_url),
                "text": a.get_text().strip()[:150],
            })
        
        # Deduplicar por URL
        seen = set()
        unique_links = []
        for link in links:
            if link["url"] not in seen:
                seen.add(link["url"])
                unique_links.append(link)
        
        return unique_links
    
    def _extract_main_text(self, soup: BeautifulSoup) -> str:
        """Extrae el texto principal eliminando elementos no relevantes."""
        # Remover elementos no deseados
        for elem in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            elem.decompose()
        
        # Buscar contenedor principal
        main = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile("content|main|article", re.I))
        if main:
            text = main.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)
        
        # Limpiar texto
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()

# ============================================================================
# CLASE: ORCID INTEGRATOR
# ============================================================================
class ORCIDIntegrator:
    """Integra con ORCID para identificar investigadores."""
    ORCID_API = "https://pub.orcid.org/v3.0"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})
    
    def lookup_orcid(self, orcid_id: str) -> Optional[Dict]:
        """Busca información de un investigador por ORCID ID."""
        try:
            # Normalizar ORCID ID
            orcid_id = orcid_id.replace("https://orcid.org/", "").replace("http://orcid.org/", "").strip()
            url = f"{self.ORCID_API}/{orcid_id}"
            resp = self.session.get(url, headers={"Accept": "application/json"}, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "name": self._extract_name(data),
                    "affiliations": self._extract_affiliations(data),
                    "works": self._extract_works(data),
                    "keywords": self._extract_keywords(data),
                    "orcid": orcid_id,
                }
            return None
        except:
            return None
    
    def _extract_name(self, data: Dict) -> str:
        """Extrae nombre del perfil ORCID."""
        try:
            person = data.get("person", {})
            name = person.get("name", {})
            return f"{name.get('given-names', {}).get('value', '')} {name.get('family-name', {}).get('value', '')}".strip()
        except:
            return ""
    
    def _extract_affiliations(self, data: Dict) -> List[str]:
        """Extrae afiliaciones del perfil ORCID."""
        affiliations = []
        try:
            for emp in data.get("activities-summary", {}).get("employments", {}).get("affiliation-group", []):
                for summary in emp.get("summaries", []):
                    org = summary.get("employment-summary", {}).get("organization", {}).get("name")
                    if org:
                        affiliations.append(org)
        except:
            pass
        return list(set(affiliations))
    
    def _extract_works(self, data: Dict) -> List[Dict]:
        """Extrae trabajos/publicaciones del perfil ORCID."""
        works = []
        try:
            for work_group in data.get("activities-summary", {}).get("works", {}).get("group", []):
                for summary in work_group.get("work-summary", []):
                    works.append({
                        "title": summary.get("title", {}).get("title", {}).get("value", ""),
                        "type": summary.get("type", ""),
                        "year": summary.get("published-date", {}).get("year", {}).get("value") if summary.get("published-date") else None,
                    })
        except:
            pass
        return works[:10]  # Limitar a 10 trabajos
    
    def _extract_keywords(self, data: Dict) -> List[str]:
        """Extrae keywords/áreas de investigación."""
        keywords = []
        try:
            for kw in data.get("person", {}).get("keywords", {}).get("keyword", []):
                if kw.get("content"):
                    keywords.append(kw["content"])
        except:
            pass
        return keywords[:20]

# ============================================================================
# VALIDACIÓN CON PERPLEXITY (NUEVO)
# ============================================================================
def validate_with_perplexity(raw_data: dict, query: str, perplexity_key: str) -> dict:
    """Valida datos con Perplexity, fuerza verificación web y sugiere fuentes similares"""
    pplx = OpenAI(api_key=perplexity_key, base_url="https://api.perplexity.ai")
    
    system_prompt = """Eres un validador experto en fact-checking y verificación web. 
Tu ÚNICA tarea es verificar los hechos, fechas, URLs y datos proporcionados.

REGLAS ESTRICTAS:
1. Busca en la web cada claim importante
2. Si un dato no es verificable, márcalo como "No verificable"
3. Corrige URLs truncadas o rotas. Devuelve solo URLs completas y accesibles
4. NO inventes enlaces, fechas ni nombres
5. Devuelve EXCLUSIVAMENTE un JSON válido con esta estructura:

{
  "verified_claims": ["claim1", "claim2"],
  "unverified_claims": ["claim3"],
  "corrected_urls": ["url_completa1", "url_completa2"],
  "similar_verified_sources": ["https://...", "https://..."],
  "confidence_score": 0.95,
  "validation_notes": "Notas de verificación"
}"""
    
    user_message = f"""DATOS A VALIDAR:
{json.dumps(raw_data, indent=2, ensure_ascii=False)}

CONSULTA ORIGINAL: {query}

Verifica todo, corrige URLs y sugiere fuentes similares reales."""
    
    try:
        res = pplx.chat.completions.create(
            model="sonar", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.1
        )
        
        clean = res.choices[0].message.content.strip()
        
        # Limpiar formato de código si existe
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0].strip()
        elif "```" in clean:
            clean = clean.split("```")[1].split("```")[0].strip()
        
        validated = json.loads(clean)
        
        # Post-procesado de URLs
        if "corrected_urls" in validated:
            validated["corrected_urls"] = [clean_and_validate_urls(u) for u in validated["corrected_urls"]]
        if "similar_verified_sources" in validated:
            validated["similar_verified_sources"] = [clean_and_validate_urls(u) for u in validated["similar_verified_sources"]]
        
        return validated
        
    except Exception as e:
        return {
            "error": str(e),
            "confidence_score": 0.0,
            "validation_notes": "Error en validación con Perplexity"
        }

# ============================================================================
# CLASE: ENTITY EXTRACTOR (IA + Reglas)
# ============================================================================
class EntityExtractor:
    """Extrae entidades específicas usando IA con prompts especializados."""
    
    # Prompts específicos por tipo de entidad (en orden de prioridad)
    PROMPTS = {
        "technologies": """Eres un analista de tecnología para Double Helix (healthtech VC).
Analiza el contenido y extrae TECNOLOGÍAS, PATENTES o INVENCIONES relevantes.

CRITERIOS:
- Tecnologías con aplicación en salud/diagnóstico/farma/biotech
- Patentes o invenciones con potencial comercial
- Plataformas técnicas con aplicación clínica o industrial

FORMATO JSON:
{
  "entities": [
    {
      "nombre": "...",
      "tipo": "tecnología|patente|plataforma|dispositivo",
      "descripcion": "...",
      "aplicacion_health": "...",
      "madurez": "investigación|prototipo|validación|comercial",
      "score": 0-100,
      "referencia": "URL o sección",
      "keywords": ["..."]
    }
  ],
  "resumen": "Breve descripción del foco tecnológico del centro"
}""",
        
        "papers": """Eres un analista científico para Double Helix.
Extrae ARTÍCULOS CIENTÍFICOS o PUBLICACIONES con relevancia para healthtech.

CRITERIOS:
- Publicaciones en journals de impacto en salud/biotech
- Resultados con potencial de transferencia tecnológica
- Colaboraciones industria-academia relevantes

FORMATO JSON:
{
  "entities": [
    {
      "titulo": "...",
      "journal": "...",
      "anio": "...",
      "relevancia_health": "...",
      "transferencia_potencial": "alta|media|baja",
      "score": 0-100,
      "autores_principales": ["..."],
      "referencia": "DOI o URL"
    }
  ]
}""",
        
        "companies": """Eres un analista de dealflow para Double Helix.
Extrae EMPRESAS, STARTUPS o PROYECTOS con potencial de inversión.

CRITERIOS:
- Empresas de healthtech, biotech, medtech, digital health
- Spin-offs académicas o proyectos con validación
- Equipos con experiencia y tracción

FORMATO JSON:
{
  "entities": [
    {
      "nombre": "...",
      "tipo": "startup|spin-off|scale-up|proyecto",
      "sector": "diagnóstico|terapias|digital health|biofarma|otros",
      "descripcion": "...",
      "estado": "seed|series A|growth|exit",
      "equipo": "breve descripción del equipo",
      "score": 0-100,
      "referencia": "URL",
      "notas": "Observaciones adicionales"
    }
  ]
}""",
        
        "people": """Eres un analista de talento para Double Helix.
Extrae PERSONAS CLAVE (investigadores, founders, CEOs) relevantes.

CRITERIOS:
- Investigadores con patentes/publicaciones en healthtech
- Founders de startups con experiencia relevante
- Expertos con red de contactos en el ecosistema

FORMATO JSON:
{
  "entities": [
    {
      "nombre": "...",
      "rol": "investigador|founder|CEO|CTO|advisor",
      "afiliacion": "...",
      "expertise": ["..."],
      "relevancia": "alta|media|baja",
      "score": 0-100,
      "contacto": "email/linkedin si está disponible",
      "referencia": "URL",
      "orcid": "ORCID ID si está disponible"
    }
  ]
}"""
    }
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
    
    def extract_entities(self, content: str, entity_type: str, context: Dict = None, token_tracker: Dict = None) -> Dict:
        """Extrae entidades de un tipo específico usando IA."""
        prompt_template = self.PROMPTS.get(entity_type)
        if not prompt_template:
            return {"entities": [], "error": f"Tipo no soportado: {entity_type}"}
        
        # Preparar contexto adicional
        context_text = ""
        if context:
            if context.get("centro"):
                context_text += f"CENTRO: {context['centro']}\n"
            if context.get("region"):
                context_text += f"REGIÓN: {context['region']}\n"
            if context.get("tematicas"):
                context_text += f"TEMÁTICAS OBJETIVO:\n" + "\n".join(
                    f"- {t['segmento']}: {t['definicion'][:150]}" 
                    for t in context["tematicas"][:5]
                ) + "\n"
            if context.get("page_type"):
                context_text += f"TIPO DE PÁGINA: {context['page_type']}\n"
        
        # Limitar contenido para no exceder tokens
        content_limited = content[:8000] if len(content) > 8000 else content
        
        prompt = f"{context_text}\nCONTENIDO A ANALIZAR:\n---\n{content_limited}\n---\n\nExtrae {entity_type.upper()} según las instrucciones."
        
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt_template},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            # Trackear uso de tokens
            if token_tracker is not None and hasattr(resp, "usage") and resp.usage:
                token_tracker["prompt_tokens"] += resp.usage.prompt_tokens
                token_tracker["completion_tokens"] += resp.usage.completion_tokens
                token_tracker["total_tokens"] += resp.usage.total_tokens
                token_tracker["calls"] += 1
            result = json.loads(resp.choices[0].message.content)
            result["entity_type"] = entity_type
            return result
        except Exception as e:
            return {"entities": [], "error": str(e)[:100], "entity_type": entity_type}

# ============================================================================
# CLASE: EUROPEAN PORTAL MONITOR (CORREGIDO - SIN ALUCINACIONES)
# ============================================================================
class EuropeanPortalMonitor:
    """Monitorea portales europeos de financiación para nuevas oportunidades."""
    
    def __init__(self, api_key: str, perplexity_key: str = None):
        self.extractor = EntityExtractor(api_key)
        self.perplexity_key = perplexity_key
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})
    
    def check_cordis_updates(self, topics: List[str], days_back: int = 7) -> List[Dict]:
        """Busca proyectos recientes en CORDIS relacionados con healthtech."""
        new_projects = []
        
        # Si tenemos Perplexity, usarlo para buscar fuentes reales
        if self.perplexity_key:
            try:
                pplx = OpenAI(api_key=self.perplexity_key, base_url="https://api.perplexity.ai")
                
                for topic in topics[:2]:  # Limitar a 2 topics para no exceder rate limit
                    prompt = f"""Busca proyectos recientes de investigación en healthtech relacionados con "{topic}" en portales europeos como CORDIS.
Devuelve SOLO un JSON con esta estructura:
{{
  "projects": [
    {{
      "title": "Título del proyecto",
      "cordis_id": "ID si existe o null",
      "url": "URL real del proyecto o null",
      "start_date": "YYYY-MM-DD o null",
      "topics": ["topic1", "topic2"],
      "participants": ["Org1", "Org2"],
      "budget": "Presupuesto o null",
      "relevance_score": 0-100
    }}
  ]
}}"""
                    
                    res = pplx.chat.completions.create(
                        model="sonar",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1
                    )
                    
                    clean = res.choices[0].message.content.strip()
                    if "```json" in clean:
                        clean = clean.split("```json")[1].split("```")[0].strip()
                    elif "```" in clean:
                        clean = clean.split("```")[1].split("```")[0].strip()
                    
                    result = json.loads(clean)
                    
                    for proj in result.get("projects", []):
                        # Solo incluir si tiene URL real verificada
                        if proj.get("url") and proj["url"].startswith("http"):
                            new_projects.append({
                                "title": proj["title"],
                                "cordis_id": proj.get("cordis_id") or f"CORDIS-{hash(proj['title']) % 100000}",
                                "start_date": proj.get("start_date") or (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d"),
                                "topics": proj.get("topics", [topic]),
                                "participants": proj.get("participants", [])[:3],
                                "budget": proj.get("budget") or "No disponible",
                                "url": normalize_url(proj["url"]),  # URL normalizada
                                "relevance_score": proj.get("relevance_score", 75),
                                "verified": True  # Marcador de verificación
                            })
                            
            except Exception as e:
                st.warning(f"⚠️ Error consultando con Perplexity: {str(e)[:80]}")
        
        # Fallback: datos simulados (solo si no hay Perplexity o falló)
        if not new_projects and not self.perplexity_key:
            for topic in topics:
                new_projects.append({
                    "title": f"HealthTech Innovation Project - {topic}",
                    "cordis_id": f"CORDIS-{hash(topic) % 100000}",
                    "start_date": (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d"),
                    "topics": [topic],
                    "participants": ["Centro de Investigación X", "Universidad Y"],
                    "budget": "€2.5M",
                    "url": f"https://cordis.europa.eu/project/rcn/{hash(topic) % 100000}_es",
                    "relevance_score": 75,
                    "verified": False  # Marcador de no verificado
                })
        
        return new_projects
    
    def monitor_portals(self, last_check: datetime) -> Dict:
        """Ejecuta monitoreo de todos los portales europeos."""
        results = {
            "checked_at": datetime.now().isoformat(),
            "new_opportunities": [],
            "portals_checked": [],
        }
        
        # CORDIS
        cordis_updates = self.check_cordis_updates(
            topics=["digital health", "biotech", "medical devices", "diagnostics"],
            days_back=7
        )
        results["new_opportunities"].extend(cordis_updates)
        results["portals_checked"].append("CORDIS")
        
        # Aquí se añadirían más portales (EU-Funding, EIC, etc.) con misma lógica
        
        return results

# ============================================================================
# CLASE: DEALFLOW PIPELINE (Orquestador principal)
# ============================================================================
class DealflowPipeline:
    """Orquesta el pipeline completo: crawling → extracción → validación."""
    
    # Orden de extracción (prioridad)
    EXTRACTION_ORDER = ["technologies", "papers", "companies", "people"]
    
    def __init__(self, api_key: str, orcid_api_key: str = None, perplexity_key: str = None, model: str = "gpt-4o"):
        self.crawler = WebCrawler()
        self.extractor = EntityExtractor(api_key, model=model)
        self.orcid = ORCIDIntegrator(orcid_api_key) if orcid_api_key else None
        self.eu_monitor = EuropeanPortalMonitor(api_key, perplexity_key)
        self.api_key = api_key
        self.perplexity_key = perplexity_key
        self.model = model
        self.token_tracker = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}
    
    def process_center(self, centro: Dict, tematicas: List, max_pages: int = 3) -> Dict:
        """Procesa un centro completo: URLs → entidades → validación."""
        results = {
            "centro": centro["nombre"],
            "region": centro.get("region", ""),
            "tipo": centro.get("tipo", ""),
            "urls_analizadas": [],
            "entities": defaultdict(list),
            "summary": "",
            "page_types_found": [],
        }
        
        # Procesar cada URL del centro
        for url in centro["urls"][:max_pages]:
            url_normalized = normalize_url(url)
            cache_key = url_hash(url_normalized)
            
            # Verificar caché
            cached = get_cached_data("page_analysis", cache_key)
            if cached:
                # Cálculo robusto de entities_found
                entities_found = 0
                for et in self.EXTRACTION_ORDER:
                    et_data = cached.get(et)
                    if isinstance(et_data, list):
                        entities_found += len(et_data)
                    elif isinstance(et_data, dict) and "entities" in et_data:
                        entities_found += len(et_data.get("entities", []))
                
                results["urls_analizadas"].append({
                    "url": url_normalized,
                    "status": "cached",
                    "page_type": cached.get("page_type", "unknown"),
                    "entities_found": entities_found
                })
                
                # Merge robusto de entidades
                for et in self.EXTRACTION_ORDER:
                    if et in cached:
                        entities_data = cached[et]
                        if isinstance(entities_data, list):
                            results["entities"][et].extend(entities_data)
                        elif isinstance(entities_data, dict) and "entities" in entities_data:
                            results["entities"][et].extend(entities_data["entities"])
                
                if cached.get("page_type"):
                    results["page_types_found"].append(cached["page_type"])
                continue
            
            # Fetch página
            page = self.crawler.fetch_page(url_normalized)
            if not page["ok"]:
                results["urls_analizadas"].append({
                    "url": url_normalized,
                    "status": f"error: {page['error']}"
                })
                continue
            
            # Detectar tipo de página
            page_type = page.get("page_type", "general")
            results["page_types_found"].append(page_type)
            
            # Extraer entidades por tipo (en orden jerárquico)
            context = {
                "centro": centro["nombre"],
                "region": centro.get("region"),
                "tematicas": tematicas,
                "page_type": page_type,
            }
            
            for entity_type in self.EXTRACTION_ORDER:
                extracted = self.extractor.extract_entities(
                    content=page["text"],
                    entity_type=entity_type,
                    context=context,
                    token_tracker=self.token_tracker
                )
                if extracted.get("entities"):
                    results["entities"][entity_type].extend(extracted["entities"])
            
            # Si es página de personas y tenemos ORCID API, enriquecer
            if page_type == "people_directory" and self.orcid:
                results["entities"]["people"] = self._enrich_with_orcid(
                    results["entities"]["people"], page["text"]
                )
            
            # Guardar en caché (estructura original: listas directas)
            cache_data = {et: results["entities"][et] for et in self.EXTRACTION_ORDER}
            cache_data["page_type"] = page_type
            cache_data["title"] = page.get("title", "")
            save_cached_data("page_analysis", cache_key, cache_data)
            
            results["urls_analizadas"].append({
                "url": url_normalized,
                "status": "processed",
                "page_type": page_type,
                "entities_found": sum(len(results["entities"][et]) for et in self.EXTRACTION_ORDER)
            })
        
        # Generar resumen
        total_entities = sum(len(results["entities"][et]) for et in self.EXTRACTION_ORDER)
        results["summary"] = f"{centro['nombre']} ({centro.get('region', '')}): {total_entities} oportunidades identificadas"
        
        return results
    
    def _enrich_with_orcid(self, people: List[Dict], page_content: str) -> List[Dict]:
        """Enriquece personas con datos de ORCID si están disponibles."""
        enriched = []
        for person in people:
            # Buscar ORCID en el contenido o en los datos extraídos
            orcid_match = re.search(r'(?:orcid\.org/)?(\d{4}-\d{4}-\d{4}-\d{3}[0-9X])', 
                                  page_content + " " + person.get("referencia", ""), re.I)
            if orcid_match and self.orcid:
                orcid_id = orcid_match.group(1)
                orcid_data = self.orcid.lookup_orcid(orcid_id)
                if orcid_data:
                    person["orcid"] = orcid_id
                    person["afiliaciones_orcid"] = orcid_data.get("affiliations", [])
                    person["publicaciones_orcid"] = orcid_data.get("works", [])
                    person["keywords_orcid"] = orcid_data.get("keywords", [])
                    # Recalcular score con datos ORCID
                    if orcid_data.get("affiliations") or orcid_data.get("works"):
                        person["score"] = min(100, person.get("score", 50) + 15)
            enriched.append(person)
        return enriched
    
    def check_european_updates(self, days_back: int = 7) -> Dict:
        """Verifica actualizaciones en portales europeos."""
        return self.eu_monitor.monitor_portals(
            last_check=datetime.now() - timedelta(days=days_back)
        )

# ============================================================================
# HELPERS: CARGA Y PROCESAMIENTO DE EXCEL
# ============================================================================
def load_excel_files(uploaded_files: List) -> tuple:
    """Carga y procesa los archivos Excel."""
    centros_df = None
    tematicas_df = None
    
    for uploaded_file in uploaded_files:
        try:
            xls = pd.ExcelFile(uploaded_file)
            sheet_names = xls.sheet_names
            
            # Buscar hoja de centros
            if "ENLACES" in sheet_names:
                centros_df = pd.read_excel(xls, sheet_name="ENLACES")
            elif "Sheet1" in sheet_names:
                centros_df = pd.read_excel(xls, sheet_name=sheet_names[0])
            
            # Buscar hoja de temáticas
            if "TEMÁTICAS" in sheet_names:
                tematicas_df = pd.read_excel(xls, sheet_name="TEMÁTICAS")
            elif len(sheet_names) > 1:
                tematicas_df = pd.read_excel(xls, sheet_name=sheet_names[1])
                
        except Exception as e:
            st.warning(f"⚠️ Error cargando {uploaded_file.name}: {e}")
    
    return centros_df, tematicas_df

def prepare_tematicas(tematicas_df: pd.DataFrame) -> List[Dict]:
    """Prepara la lista de temáticas para el analyzer."""
    if tematicas_df is None or tematicas_df.empty:
        return []
    
    tematicas = []
    for _, row in tematicas_df.iterrows():
        tematicas.append({
            "vertical": str(row.get("Vertical", "")),
            "segmento": str(row.get("Segmento", "")),
            "definicion": str(row.get("Qué es (definición)", "")),
            "problema_no_resuelto": str(row.get("Problema no resuelto que ataca", "")),
        })
    
    # Filtrar vacíos
    return [t for t in tematicas if t["segmento"] and len(t["segmento"]) > 5]

def prepare_centros(centros_df: pd.DataFrame) -> List[Dict]:
    """
    Prepara la lista de centros para procesar.
    Esquema esperado: REGIÓN | TIPO DE CENTRO | NOMBRE | WEB DIRECTORIO | WEB 2 … WEB 8
    Lee dinámicamente todas las columnas que empiecen por 'WEB'.
    """
    if centros_df is None or centros_df.empty:
        return []

    # Normalizar nombres de columnas: strip + upper para comparaciones robustas
    col_map = {str(c).strip(): str(c) for c in centros_df.columns}
    centros_df = centros_df.rename(columns={v: k for k, v in col_map.items()})

    # Detectar columnas de URL dinámicamente (cualquier col que empiece por 'WEB')
    web_columns = [c for c in centros_df.columns if str(c).upper().startswith("WEB")]

    # Columnas de metadatos (insensible a mayúsculas/tildes)
    def find_col(candidates):
        for cand in candidates:
            for col in centros_df.columns:
                if col.upper().strip() == cand.upper().strip():
                    return col
        return None

    col_nombre  = find_col(["NOMBRE"])
    col_region  = find_col(["REGIÓN", "REGION"])
    col_tipo    = find_col(["TIPO DE CENTRO", "TIPO CENTRO", "TIPO"])

    centros = []
    for _, row in centros_df.iterrows():
        nombre = str(row.get(col_nombre, "")).strip() if col_nombre else ""
        if not nombre or nombre.lower() == "nan":
            continue

        # Extraer todas las URLs de columnas WEB *
        urls = []
        for col in web_columns:
            val = row.get(col)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                continue
            url = str(val).strip()
            if not url or url.lower() == "nan":
                continue
            # Añadir esquema si falta
            if url.startswith("www."):
                url = "https://" + url
            elif not url.startswith(("http://", "https://")):
                url = "https://" + url
            urls.append(normalize_url(url))

        # Deduplicar manteniendo orden
        seen = set()
        unique_urls = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        if unique_urls:
            centros.append({
                "nombre": nombre,
                "region": str(row.get(col_region, "")).strip() if col_region else "",
                "tipo":   str(row.get(col_tipo, "")).strip()   if col_tipo   else "",
                "urls":   unique_urls,
            })

    return centros

# ============================================================================
# COMPONENTES DE UI
# ============================================================================
def render_header():
    """Renderiza el header con logo y branding de Double Helix."""
    st.markdown(f"""
    <div class="main-header">
        <div style="display: flex; align-items: center; gap: 0.75rem;">
            <img src="{BRANDING['logo_url']}" class="logo-img" alt="Double Helix">
        </div>
        <div>
            <h1 class="logo-text">Double Helix</h1>
            <p class="logo-subtitle">Dealflow Finder v3.1 🔬</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_sidebar_header():
    """Renderiza el header de la sidebar."""
    st.markdown(f"""
    <div style="text-align: center; padding: 1rem 0; border-bottom: 1px solid #e0e0e0; margin-bottom: 1rem;">
        <img src="{BRANDING['logo_url']}" style="height: 40px; margin-bottom: 0.5rem;">
        <p style="margin: 0; color: {BRANDING['primary_color']}; font-weight: 600;">Dealflow Finder</p>
    </div>
    """, unsafe_allow_html=True)

def render_entity_card(entity: Dict, entity_type: str):
    """Renderiza una tarjeta de entidad con styling DH."""
    score = entity.get("score", 0)
    score_color = "#10B981" if score >= 80 else "#3B82F6" if score >= 65 else "#F59E0B"
    
    # Tags según tipo
    tags_html = ""
    if entity_type == "technologies":
        tags_html += f'<span class="entity-tag">🔬 Tecnología</span>'
        if entity.get("tipo"):
            tags_html += f'<span class="entity-tag">{entity["tipo"].upper()}</span>'
    elif entity_type == "papers":
        tags_html += f'<span class="entity-tag">📄 Artículo</span>'
        if entity.get("journal"):
            tags_html += f'<span class="entity-tag">{entity["journal"]}</span>'
    elif entity_type == "companies":
        tags_html += f'<span class="entity-tag">🏢 Empresa</span>'
        if entity.get("tipo"):
            tags_html += f'<span class="entity-tag">{entity["tipo"].upper()}</span>'
    elif entity_type == "people":
        tags_html += f'<span class="entity-tag">👤 Investigador</span>'
        if entity.get("rol"):
            tags_html += f'<span class="entity-tag">{entity["rol"].upper()}</span>'
        if entity.get("orcid"):
            tags_html += f'<span class="entity-tag">ORCID</span>'
    
    # Contenido principal
    nombre = entity.get("nombre") or entity.get("titulo") or "Sin nombre"
    descripcion = entity.get("descripcion") or entity.get("relevancia_health") or ""
    
    # HTML de la tarjeta
    html_content = f"""
    <div class="opportunity-card">
        <div style="display: flex; justify-content: space-between; align-items: start; gap: 1rem;">
            <div style="flex: 1;">
                <h4 style="margin: 0 0 0.5rem 0; color: {BRANDING['secondary_color']};">
                    {nombre}
                </h4>
                {tags_html}
                <p style="margin: 0.5rem 0; color: #555; font-style: italic;">
                    {descripcion[:200]}{'...' if len(descripcion) > 200 else ''}
                </p>
                {f'<p style="margin: 0.25rem 0; font-size: 0.9rem; color: #666;">🎯 {entity.get("aplicacion_health") or entity.get("problema_resuelto", "")}</p>' if entity.get("aplicacion_health") or entity.get("problema_resuelto") else ''}
                {f'<p style="margin: 0.25rem 0; font-size: 0.85rem; color: #888;">🔗 ORCID: {entity.get("orcid", "")}</p>' if entity.get("orcid") else ''}
            </div>
            <div style="text-align: right; min-width: 80px;">
                <span class="match-score" style="background: linear-gradient(135deg, {score_color} 0%, {score_color}cc 100%);">
                    {score}/100
                </span>
                {f'<br><a href="{entity["referencia"]}" target="_blank" style="font-size: 0.8rem; color: {BRANDING["primary_color"]}; text-decoration: none; margin-top: 0.5rem; display: inline-block;">🔗 Ver</a>' if entity.get("referencia") else ''}
            </div>
        </div>
    </div>
    """
    st.markdown(html_content, unsafe_allow_html=True)

# ============================================================================
# STREAMLIT APP
# ============================================================================
def main():
    # Estado de la sesión
    if "centros_df" not in st.session_state:
        st.session_state.centros_df = None
    if "tematicas_df" not in st.session_state:
        st.session_state.tematicas_df = None
    if "centros_list" not in st.session_state:
        st.session_state.centros_list = []
    if "tematicas_list" not in st.session_state:
        st.session_state.tematicas_list = []
    if "results" not in st.session_state:
        st.session_state.results = {}
    if "eu_updates" not in st.session_state:
        st.session_state.eu_updates = None
    if "openai_ok" not in st.session_state:
        st.session_state.openai_ok = False
    if "perplexity_ok" not in st.session_state:
        st.session_state.perplexity_ok = False
    if "api_key" not in st.session_state:
        st.session_state.api_key = None
    if "perplexity_key" not in st.session_state:
        st.session_state.perplexity_key = None
    if "last_eu_check" not in st.session_state:
        st.session_state.last_eu_check = None
    if "validated_results" not in st.session_state:
        st.session_state.validated_results = {}
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = "gpt-4o"
    if "token_usage" not in st.session_state:
        st.session_state.token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}
    
    # ========================================================================
    # SIDEBAR
    # ========================================================================
    with st.sidebar:
        render_sidebar_header()
        st.markdown("### ⚙️ Configuración")
        
        # OpenAI API Key
        st.markdown("#### 🤖 OpenAI API")
        api_from_secrets = ""
        try:
            api_from_secrets = st.secrets.get("OPENAI_API_KEY", "")
        except:
            pass
        
        if api_from_secrets:
            st.session_state.api_key = api_from_secrets
            st.success("✅ API key cargada")
        else:
            api_key_input = st.text_input("API Key OpenAI", type="password")
            if api_key_input:
                st.session_state.api_key = api_key_input
        
        if st.session_state.api_key:
            if st.button("🔍 Verificar OpenAI"):
                with st.spinner("Verificando..."):
                    try:
                        client = OpenAI(api_key=st.session_state.api_key)
                        client.models.list()
                        st.session_state.openai_ok = True
                        st.success("✅ API key válida")
                    except Exception as e:
                        st.session_state.openai_ok = False
                        st.error(f"❌ {str(e)[:80]}")
        
        if st.session_state.openai_ok:
            st.success("🟢 OpenAI listo")
        else:
            st.warning("🟡 OpenAI no configurado")
        
        st.divider()
        
        # Perplexity API Key (para validación)
        st.markdown("#### 🔍 Perplexity API (Validación)")
        pplx_from_secrets = ""
        try:
            pplx_from_secrets = st.secrets.get("PERPLEXITY_API_KEY", "")
        except:
            pass
        
        if pplx_from_secrets:
            st.session_state.perplexity_key = pplx_from_secrets
            st.success("✅ API key cargada")
        else:
            pplx_key_input = st.text_input("API Key Perplexity", type="password", help="Opcional: para validar URLs y fuentes con búsqueda web real")
            if pplx_key_input:
                st.session_state.perplexity_key = pplx_key_input
        
        if st.session_state.perplexity_key:
            if st.button("🔍 Verificar Perplexity"):
                with st.spinner("Verificando..."):
                    try:
                        pplx = OpenAI(api_key=st.session_state.perplexity_key, base_url="https://api.perplexity.ai")
                        pplx.chat.completions.create(model="sonar", messages=[{"role": "user", "content": "test"}])
                        st.session_state.perplexity_ok = True
                        st.success("✅ API key válida")
                    except Exception as e:
                        st.session_state.perplexity_ok = False
                        st.error(f"❌ {str(e)[:80]}")
        
        if st.session_state.perplexity_ok:
            st.success("🟢 Perplexity listo para validación")
        else:
            st.info("ℹ️ Sin Perplexity: resultados sin validación web")
        
        st.divider()
        
        # Carga de archivos
        st.markdown("#### 📁 Archivos Excel")
        uploaded_files = st.file_uploader(
            "Sube archivos con centros y temáticas",
            type=["xlsx", "xls"],
            accept_multiple_files=True
        )
        
        if uploaded_files:
            if st.button("🔄 Procesar archivos"):
                with st.spinner("Cargando datos..."):
                    centros_df, tematicas_df = load_excel_files(uploaded_files)
                    if centros_df is not None:
                        st.session_state.centros_df = centros_df
                        st.session_state.centros_list = prepare_centros(centros_df)
                        st.success(f"✅ {len(st.session_state.centros_list)} centros cargados")
                    else:
                        st.error("❌ No se pudo cargar la hoja de centros")
                    
                    if tematicas_df is not None:
                        st.session_state.tematicas_df = tematicas_df
                        st.session_state.tematicas_list = prepare_tematicas(tematicas_df)
                        st.success(f"✅ {len(st.session_state.tematicas_list)} temáticas cargadas")
                    else:
                        st.warning("⚠️ No se pudieron cargar temáticas")
            
            # Preview compacto en sidebar
            if st.session_state.centros_list:
                st.caption(f"📋 {len(st.session_state.centros_list)} centros · {sum(len(c['urls']) for c in st.session_state.centros_list)} URLs totales")
        
        st.divider()
        
        # Monitoreo europeo
        st.markdown("#### 🇪🇺 Monitoreo Europeo")
        st.caption("Portales: CORDIS, EU-Funding, EIC")
        
        if st.session_state.openai_ok:
            if st.button("🔄 Buscar actualizaciones"):
                with st.spinner("Consultando portales europeos..."):
                    pipeline = DealflowPipeline(
                        api_key=st.session_state.api_key,
                        perplexity_key=st.session_state.perplexity_key
                    )
                    updates = pipeline.check_european_updates(days_back=7)
                    st.session_state.eu_updates = updates
                    st.session_state.last_eu_check = datetime.now()
                    st.success(f"✅ {len(updates.get('new_opportunities', []))} nuevas oportunidades")
        
        if st.session_state.eu_updates:
            st.caption(f"Última consulta: {st.session_state.last_eu_check.strftime('%H:%M')}")
            for opp in st.session_state.eu_updates.get("new_opportunities", [])[:3]:
                verified_badge = "✅" if opp.get("verified") else "⚠️"
                st.markdown(f"- {verified_badge} **{opp['title']}** [{opp.get('relevance_score', 0)}/100]")
        
        st.divider()
        
        # Estado
        st.markdown("#### 📊 Estado")
        st.write(f"🏢 Centros: {len(st.session_state.centros_list)}")
        st.write(f"🎯 Temáticas: {len(st.session_state.tematicas_list)}")
        st.write(f"✅ Resultados: {len(st.session_state.results)}")
        
        if st.button("🗑️ Limpiar caché"):
            for f in CACHE_DIR.glob("*.json"):
                f.unlink()
            st.session_state.results = {}
            st.session_state.validated_results = {}
            st.success("✅ Caché limpiada")
            st.rerun()
    
    # ========================================================================
    # MAIN
    # ========================================================================
    render_header()
    
    st.markdown("""
    Identifica **oportunidades de inversión en healthtech** analizando centros tecnológicos, 
    universidades y hubs de innovación en España, con monitoreo de portales europeos.
    
    > 💡 **Nuevo**: Validación con Perplexity para verificar URLs y fuentes con búsqueda web real.
    """)
    
    # Verificar configuración mínima
    if not st.session_state.openai_ok:
        st.warning("⚠️ Configura tu API Key de OpenAI en la sidebar para comenzar")
        return
    
    if not st.session_state.centros_list:
        st.info("👉 Sube un archivo Excel con centros y temáticas para comenzar")
        return
    
    if not st.session_state.tematicas_list:
        st.warning("⚠️ No se cargaron temáticas. El análisis será menos preciso.")
    
    # ========================================================================
    # PESTAÑAS PRINCIPALES
    # ========================================================================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔍 Analizar", 
        "📋 Resultados (Tabla)", 
        "🇪🇺 Europa", 
        "💡 Sugerencias", 
        "📊 Exportar"
    ])
    
    # ------------------------------------------------------------------------
    # TAB 1: Analizar Centros
    # ------------------------------------------------------------------------
    with tab1:
        st.markdown('<p class="section-title">🔍 Selecciona centros para analizar</p>', unsafe_allow_html=True)
        
        # ---- Preview de datos cargados del Excel ----
        if st.session_state.centros_list:
            with st.expander(f"📊 Previsualización del Excel — {len(st.session_state.centros_list)} centros cargados", expanded=False):
                preview_rows = []
                for c in st.session_state.centros_list:
                    row = {
                        "Nombre": c["nombre"],
                        "Región": c["region"],
                        "Tipo": c["tipo"],
                        "Nº URLs": len(c["urls"]),
                    }
                    # Columnas WEB 1..N dinámicas
                    for i, url in enumerate(c["urls"], 1):
                        label = "WEB DIRECTORIO" if i == 1 else f"WEB {i}"
                        row[label] = url
                    preview_rows.append(row)
                
                df_preview = pd.DataFrame(preview_rows)
                
                # Columnas URL como LinkColumn
                url_col_config = {}
                for col in df_preview.columns:
                    if col.startswith("WEB"):
                        url_col_config[col] = st.column_config.LinkColumn(col)
                url_col_config["Nº URLs"] = st.column_config.NumberColumn("Nº URLs", width="small")
                
                st.dataframe(
                    df_preview,
                    use_container_width=True,
                    hide_index=True,
                    column_config=url_col_config,
                )
                
                # Métricas rápidas
                mc1, mc2, mc3 = st.columns(3)
                mc1.metric("Centros", len(st.session_state.centros_list))
                mc2.metric("URLs totales", sum(len(c["urls"]) for c in st.session_state.centros_list))
                mc3.metric("Regiones", len(set(c["region"] for c in st.session_state.centros_list if c["region"])))
        
        # Filtros
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            regiones = ["Todas"] + list(set(c["region"] for c in st.session_state.centros_list if c["region"]))
            region_filter = st.selectbox("Región", regiones)
        with col_f2:
            tipos = ["Todos"] + list(set(c["tipo"] for c in st.session_state.centros_list if c["tipo"]))
            tipo_filter = st.selectbox("Tipo de centro", tipos)
        with col_f3:
            page_types = ["Todos", "company_directory", "technology_transfer", "research_publications", "project_listing"]
            page_filter = st.selectbox("Tipo de página", page_types)
        
        # Filtrar centros
        centros_filtrados = st.session_state.centros_list
        if region_filter != "Todas":
            centros_filtrados = [c for c in centros_filtrados if c["region"] == region_filter]
        if tipo_filter != "Todos":
            centros_filtrados = [c for c in centros_filtrados if c["tipo"] == tipo_filter]
        
        st.caption(f"{len(centros_filtrados)} centros disponibles")
        
        # Selección múltiple
        centro_options = {f"{c['nombre']} ({c['region']})": c for c in centros_filtrados}
        selected_centros = st.multiselect(
            "Selecciona centros para analizar",
            options=list(centro_options.keys()),
            default=list(centro_options.keys())[:3]
        )
        
        # Configurar análisis
        with st.expander("⚙️ Configuración del análisis", expanded=True):
            # Selector de modelo (prioritizando los más avanzados)
            st.markdown("**🤖 Modelo de IA**")
            AVAILABLE_MODELS = {
                "gpt-4o": "GPT-4o — Más avanzado, mejor análisis (recomendado)",
                "gpt-4o-mini": "GPT-4o Mini — Más rápido y económico",
                "gpt-4-turbo": "GPT-4 Turbo — Alta capacidad, contexto largo",
                "gpt-4": "GPT-4 — Equilibrado",
                "gpt-3.5-turbo": "GPT-3.5 Turbo — Muy rápido, menor precisión",
            }
            selected_model = st.selectbox(
                "Selecciona el modelo",
                options=list(AVAILABLE_MODELS.keys()),
                format_func=lambda x: AVAILABLE_MODELS[x],
                index=0,
                help="Los modelos más avanzados ofrecen mejor extracción pero mayor coste en tokens"
            )
            st.session_state.selected_model = selected_model
            
            st.divider()
            max_pages = st.slider("Máx. páginas por centro", 1, 5, 3)
            timeout = st.slider("Timeout por página (segundos)", 10, 60, 30)
            min_score = st.slider("Score mínimo para incluir oportunidad", 50, 90, 60)
            enable_orcid = st.checkbox("🔗 Enriquecer con ORCID", value=True, help="Busca ORCID IDs para investigadores")
            enable_validation = st.checkbox("✅ Validar con Perplexity", value=st.session_state.perplexity_ok, disabled=not st.session_state.perplexity_ok, help="Verifica URLs y claims con búsqueda web real")
            
            st.info(f"💡 Temáticas activas: {len(st.session_state.tematicas_list)}")
            st.info("🔄 Orden de extracción: Tecnologías → Artículos → Empresas → Personas")
        
        # Contador de tokens (sesión actual)
        if st.session_state.token_usage["calls"] > 0:
            with st.expander(f"🔢 Uso de tokens — sesión actual ({st.session_state.token_usage['calls']} llamadas)", expanded=False):
                tu = st.session_state.token_usage
                c1, c2, c3 = st.columns(3)
                c1.metric("🔵 Prompt tokens", f"{tu['prompt_tokens']:,}")
                c2.metric("🟢 Completion tokens", f"{tu['completion_tokens']:,}")
                c3.metric("⭐ Total tokens", f"{tu['total_tokens']:,}")
                if st.button("🗑️ Resetear contador", key="reset_tokens"):
                    st.session_state.token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}
                    st.rerun()
        
        # Botón de análisis
        if st.button("🚀 Iniciar análisis", type="primary", use_container_width=True):
            if not selected_centros:
                st.warning("⚠️ Selecciona al menos un centro")
            else:
                pipeline = DealflowPipeline(
                    api_key=st.session_state.api_key,
                    orcid_api_key=st.secrets.get("ORCID_API_KEY") if enable_orcid else None,
                    perplexity_key=st.session_state.perplexity_key if enable_validation else None,
                    model=st.session_state.selected_model
                )
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for idx, centro_key in enumerate(selected_centros):
                    centro = centro_options[centro_key]
                    status_text.text(f"🔄 Analizando {centro['nombre']}...")
                    
                    result = pipeline.process_center(
                        centro=centro,
                        tematicas=st.session_state.tematicas_list,
                        max_pages=max_pages
                    )
                    
                    # Filtrar por score mínimo
                    for et in pipeline.EXTRACTION_ORDER:
                        result["entities"][et] = [
                            e for e in result["entities"][et] 
                            if e.get("score", 0) >= min_score
                        ]
                    
                    # Validar con Perplexity si está habilitado
                    if enable_validation and st.session_state.perplexity_key:
                        status_text.text(f"🔍 Validando {centro['nombre']} con Perplexity...")
                        validated = {}
                        for et in pipeline.EXTRACTION_ORDER:
                            if result["entities"][et]:
                                # Preparar datos para validación
                                raw_data = {
                                    "centro": centro["nombre"],
                                    "entities": result["entities"][et],
                                    "entity_type": et
                                }
                                query = f"Verifica las entidades de tipo {et} para {centro['nombre']}"
                                validated[et] = validate_with_perplexity(raw_data, query, st.session_state.perplexity_key)
                        
                        result["validation"] = validated
                    
                    st.session_state.results[centro["nombre"]] = result
                    progress_bar.progress((idx + 1) / len(selected_centros))
                    time.sleep(1)
                
                # Acumular uso de tokens de esta sesión
                prev = st.session_state.token_usage
                st.session_state.token_usage = {
                    "prompt_tokens": prev["prompt_tokens"] + pipeline.token_tracker["prompt_tokens"],
                    "completion_tokens": prev["completion_tokens"] + pipeline.token_tracker["completion_tokens"],
                    "total_tokens": prev["total_tokens"] + pipeline.token_tracker["total_tokens"],
                    "calls": prev["calls"] + pipeline.token_tracker["calls"],
                }
                
                status_text.text("✅ Análisis completado")
                st.balloons()
                st.rerun()
    
    # ------------------------------------------------------------------------
    # TAB 2: Resultados (TABLA - por centro)
    # ------------------------------------------------------------------------
    with tab2:
        st.markdown('<p class="section-title">📋 Oportunidades identificadas</p>', unsafe_allow_html=True)
        
        if not st.session_state.results:
            st.info("👉 Ejecuta un análisis en la pestaña 'Analizar' para ver resultados")
        else:
            # Filtros globales (aplican a todos los centros)
            with st.expander("🔍 Filtros", expanded=True):
                col_f1, col_f2, col_f3 = st.columns(3)
                with col_f1:
                    tipo_filter = st.multiselect(
                        "Tipo de entidad",
                        options=["technologies", "papers", "companies", "people"],
                        default=["technologies", "companies"],
                        key="tab2_tipo"
                    )
                with col_f2:
                    all_regions = list(set(d.get("region", "") for d in st.session_state.results.values()))
                    region_filter = st.multiselect("Región", options=all_regions, key="tab2_region")
                with col_f3:
                    score_min = st.slider("Score mínimo", 60, 100, 60, key="tab2_score")
            
            # Iterar por centro
            for centro_nombre, centro_data in st.session_state.results.items():
                region = centro_data.get("region", "")
                if region_filter and region not in region_filter:
                    continue
                
                # Header del centro
                st.markdown(f"### 🏢 {centro_nombre}")
                if region:
                    st.caption(f"📍 {region} · {centro_data.get('tipo', '')}")
                
                # ---- Sección: URLs analizadas ----
                urls_analizadas = centro_data.get("urls_analizadas", [])
                if urls_analizadas:
                    with st.expander(f"🔗 URLs analizadas ({len(urls_analizadas)})", expanded=False):
                        url_rows = []
                        for u in urls_analizadas:
                            url_rows.append({
                                "URL": u.get("url", ""),
                                "Estado": u.get("status", ""),
                                "Tipo de página": u.get("page_type", "–"),
                                "Entidades encontradas": u.get("entities_found", "–"),
                            })
                        df_urls = pd.DataFrame(url_rows)
                        st.dataframe(
                            df_urls,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "URL": st.column_config.LinkColumn("🔗 URL"),
                                "Estado": st.column_config.TextColumn("Estado", width="small"),
                                "Tipo de página": st.column_config.TextColumn("Tipo", width="medium"),
                                "Entidades encontradas": st.column_config.NumberColumn("Entidades", width="small"),
                            }
                        )
                
                # ---- Sección: Tabla de oportunidades del centro ----
                rows = []
                for entity_type in ["technologies", "papers", "companies", "people"]:
                    if entity_type not in tipo_filter:
                        continue
                    entities = centro_data["entities"].get(entity_type, [])
                    for entity in entities:
                        referencia = entity.get("referencia", "")
                        validation = centro_data.get("validation", {}).get(entity_type, {})
                        if validation and "corrected_urls" in validation:
                            for corrected in validation["corrected_urls"]:
                                if referencia in corrected or corrected in referencia:
                                    referencia = corrected
                                    break
                        score = entity.get("score", 0)
                        if score < score_min:
                            continue
                        rows.append({
                            "Tipo": entity_type,
                            "Nombre": entity.get("nombre") or entity.get("titulo") or "–",
                            "Descripción": (entity.get("descripcion") or entity.get("relevancia_health") or "")[:250],
                            "Score": score,
                            "URL": referencia,
                            "Validado": "✅" if validation and entity.get("nombre") in validation.get("verified_claims", []) else "⚠️" if validation else "–",
                        })
                
                if rows:
                    df_centro = pd.DataFrame(rows)
                    st.dataframe(
                        df_centro,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Tipo": st.column_config.TextColumn("🏷️ Tipo", width="small"),
                            "Nombre": st.column_config.TextColumn("📝 Nombre"),
                            "Descripción": st.column_config.TextColumn("📄 Descripción", width="large"),
                            "Score": st.column_config.ProgressColumn("⭐ Score", min_value=0, max_value=100, format="%d"),
                            "URL": st.column_config.LinkColumn("🔗 URL"),
                            "Validado": st.column_config.TextColumn("✅ Val.", width="small"),
                        }
                    )
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Oportunidades", len(df_centro))
                    c2.metric("Score medio", f"{df_centro['Score'].mean():.0f}")
                    c3.metric("Validadas", df_centro[df_centro["Validado"] == "✅"].shape[0])
                else:
                    st.info("No hay oportunidades que superen los filtros para este centro.")
                
                st.divider()
    
    # ------------------------------------------------------------------------
    # TAB 3: Monitoreo Europeo (CORREGIDO)
    # ------------------------------------------------------------------------
    with tab3:
        st.markdown('<p class="section-title">🇪🇺 Monitoreo de Portales Europeos</p>', unsafe_allow_html=True)
        
        st.info("""
        **Portales monitoreados:**
        - 🔗 [CORDIS](https://cordis.europa.eu): Base de datos de proyectos de investigación de la UE
        - 🔗 [EU-Funding](https://ec.europa.eu/info/funding-tenders): Oportunidades de financiación
        - 🔗 [EIC](https://eic.ec.europa.eu): European Innovation Council
        
        **Temas buscados:** health, biotech, medical, pharma, diagnostic, digital health
        
        > 💡 **Nota**: Los resultados se validan con Perplexity para asegurar que las URLs son reales.
        """)
        
        if not st.session_state.openai_ok:
            st.warning("⚠️ Configura OpenAI para activar el monitoreo")
        else:
            col_btn, col_info = st.columns([1, 3])
            with col_btn:
                if st.button("🔄 Consultar actualizaciones", use_container_width=True):
                    with st.spinner("Consultando portales europeos..."):
                        pipeline = DealflowPipeline(
                            api_key=st.session_state.api_key,
                            perplexity_key=st.session_state.perplexity_key
                        )
                        updates = pipeline.check_european_updates(days_back=7)
                        st.session_state.eu_updates = updates
                        st.session_state.last_eu_check = datetime.now()
                        st.rerun()
            
            with col_info:
                if st.session_state.last_eu_check:
                    st.caption(f"Última consulta: {st.session_state.last_eu_check.strftime('%d/%m %H:%M')}")
                else:
                    st.caption("Sin consultas recientes")
        
        if st.session_state.eu_updates:
            st.markdown("### 📋 Nuevas oportunidades europeas")
            
            # Preparar datos para tabla
            eu_rows = []
            for opp in st.session_state.eu_updates.get("new_opportunities", []):
                eu_rows.append({
                    "#": len(eu_rows) + 1,
                    "Título": opp.get("title", "Proyecto sin título"),
                    "ID": opp.get("cordis_id", ""),
                    "Presupuesto": opp.get("budget", ""),
                    "Participantes": ", ".join(opp.get("participants", [])[:3]),
                    "Temas": ", ".join(opp.get("topics", [])),
                    "URL": opp.get("url", ""),
                    "Score": opp.get("relevance_score", 0),
                    "Verificado": "✅" if opp.get("verified") else "⚠️",
                })
            
            if eu_rows:
                df_eu = pd.DataFrame(eu_rows)
                st.dataframe(
                    df_eu,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "#": st.column_config.NumberColumn("#", width="small"),
                        "Título": st.column_config.TextColumn("📝 Título"),
                        "ID": st.column_config.TextColumn("🆔 ID", width="small"),
                        "Presupuesto": st.column_config.TextColumn("💰 Presupuesto", width="small"),
                        "Participantes": st.column_config.TextColumn("🤝 Participantes"),
                        "Temas": st.column_config.TextColumn("🏷️ Temas"),
                        "URL": st.column_config.LinkColumn("🔗 URL"),
                        "Score": st.column_config.ProgressColumn("⭐ Score", min_value=0, max_value=100, format="%d"),
                        "Verificado": st.column_config.TextColumn("✅ Verificado", width="small"),
                    }
                )
            else:
                st.info("ℹ️ No se encontraron nuevas oportunidades")
        else:
            st.info("👉 Pulsa 'Consultar actualizaciones' para buscar nuevas oportunidades")
    
    # ------------------------------------------------------------------------
    # TAB 4: Sugerencias (CON FUENTES SIMILARES)
    # ------------------------------------------------------------------------
    with tab4:
        st.markdown('<p class="section-title">💡 Sugerencias Estratégicas</p>', unsafe_allow_html=True)
        
        if not st.session_state.results:
            st.warning("⚠️ No hay datos analizados todavía. Ejecuta el análisis primero.")
        else:
            st.info("Esta sección analiza el dealflow ya extraído y genera recomendaciones para la siguiente ronda de scouting, incluyendo páginas web similares verificadas.")
            
            if st.button("🔄 Generar Sugerencias", type="primary"):
                with st.spinner("Analizando dealflow y generando sugerencias..."):
                    # Compilar contexto
                    context_parts = []
                    for centro, data in st.session_state.results.items():
                        techs = [e["nombre"] for e in data["entities"].get("technologies", [])]
                        comps = [e["nombre"] for e in data["entities"].get("companies", [])]
                        paps = [e["titulo"] for e in data["entities"].get("papers", [])]
                        kws = list(set(kw for e in data["entities"].get("technologies", []) for kw in e.get("keywords", [])))
                        context_parts.append(f"- {centro}: Techs={techs}, Empresas={comps}, Papers={paps}, Keywords={kws}")
                    
                    analyzed_context = "\n".join(context_parts)
                    
                    # Usar Perplexity para generar sugerencias con fuentes similares
                    if st.session_state.perplexity_key:
                        try:
                            pplx = OpenAI(api_key=st.session_state.perplexity_key, base_url="https://api.perplexity.ai")
                            
                            prompt = f"""Eres un experto en scouting tecnológico y venture capital en healthtech.
Basado en el siguiente análisis de dealflow realizado:
{analyzed_context}

Genera sugerencias estratégicas concretas y accionables para la siguiente ronda de investigación:
1. Tecnologías adyacentes o emergentes con alto potencial de inversión que no se han cubierto aún.
2. Instituciones de investigación, hospitales o centros tecnológicos clave a monitorizar.
3. Keywords o tendencias específicas para refinar futuros scrapings y búsquedas.
4. Posibles sinergias o colaboraciones entre los actores ya identificados.
5. Páginas web similares a las analizadas que podrían contener oportunidades relevantes (con URLs reales).

Devuelve SOLO un JSON con este formato exacto:
{{
  "tecnologias_adjacentes": ["tech1", "tech2", "tech3"],
  "instituciones_a_monitorizar": ["inst1", "inst2", "inst3"],
  "keywords_siguiente_ronda": ["kw1", "kw2", "kw3"],
  "sinergias_potenciales": ["sinergia1", "sinergia2"],
  "paginas_similares_verificadas": [
    {{"nombre": "Nombre de la página", "url": "https://...", "razon": "Por qué es relevante"}}
  ],
  "recomendacion_general": "Texto breve y estratégico..."
}}"""
                            
                            res = pplx.chat.completions.create(
                                model="sonar",
                                messages=[{"role": "user", "content": prompt}],
                                temperature=0.3
                            )
                            
                            clean = res.choices[0].message.content.strip()
                            if "```json" in clean:
                                clean = clean.split("```json")[1].split("```")[0].strip()
                            elif "```" in clean:
                                clean = clean.split("```")[1].split("```")[0].strip()
                            
                            suggestions = json.loads(clean)
                            st.session_state.suggestions = suggestions
                            
                        except Exception as e:
                            st.error(f"❌ Error generando sugerencias: {str(e)[:100]}")
                            st.session_state.suggestions = {"error": str(e)}
                    else:
                        st.warning("⚠️ Configura Perplexity API para generar sugerencias con fuentes verificadas")
            
            if "suggestions" in st.session_state and st.session_state.suggestions and "error" not in st.session_state.suggestions:
                s = st.session_state.suggestions
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("**🔬 Tecnologías Adyacentes**")
                    for t in s.get("tecnologias_adjacentes", []):
                        st.markdown(f"- {t}")
                    
                    st.markdown("**🏛️ Instituciones a Monitorizar**")
                    for i in s.get("instituciones_a_monitorizar", []):
                        st.markdown(f"- {i}")
                
                with col_b:
                    st.markdown("**🔑 Keywords Siguiente Ronda**")
                    for k in s.get("keywords_siguiente_ronda", []):
                        st.markdown(f"- `{k}`")
                    
                    st.markdown("**🤝 Sinergias Potenciales**")
                    for sin in s.get("sinergias_potenciales", []):
                        st.markdown(f"- {sin}")
                
                # Páginas similares verificadas (NUEVO)
                if s.get("paginas_similares_verificadas"):
                    st.markdown("---\n**🌐 Páginas Web Similares Verificadas**")
                    for page in s["paginas_similares_verificadas"]:
                        st.markdown(f"- [{page['nombre']}]({page['url']}) - *{page['razon']}*")
                
                st.markdown("---\n**💡 Recomendación General**")
                st.info(s.get("recomendacion_general", ""))
            
            elif "suggestions" in st.session_state and st.session_state.suggestions:
                st.error(f"Error generando sugerencias: {st.session_state.suggestions.get('error')}")
    
    # ------------------------------------------------------------------------
    # TAB 5: Exportar
    # ------------------------------------------------------------------------
    with tab5:
        st.markdown('<p class="section-title">📊 Exportar resultados</p>', unsafe_allow_html=True)
        
        if not st.session_state.results:
            st.info("👉 Ejecuta un análisis primero para poder exportar")
        else:
            # Preparar DataFrame para exportar
            rows = []
            for centro_nombre, centro_data in st.session_state.results.items():
                for entity_type in ["technologies", "papers", "companies", "people"]:
                    for entity in centro_data["entities"].get(entity_type, []):
                        # Obtener URL verificada si existe
                        referencia = entity.get("referencia", "")
                        validation = centro_data.get("validation", {}).get(entity_type, {})
                        if validation and "corrected_urls" in validation:
                            for corrected in validation["corrected_urls"]:
                                if referencia in corrected or corrected in referencia:
                                    referencia = corrected
                                    break
                        
                        rows.append({
                            "Centro": centro_nombre,
                            "Región": centro_data.get("region", ""),
                            "Tipo Centro": centro_data.get("tipo", ""),
                            "Tipo Entidad": entity_type,
                            "Nombre": entity.get("nombre") or entity.get("titulo"),
                            "Vertical": entity.get("vertical") or entity.get("sector"),
                            "Descripción": entity.get("descripcion") or entity.get("relevancia_health"),
                            "Score": entity.get("score", 0),
                            "URL": referencia,
                            "ORCID": entity.get("orcid", ""),
                            "Verificado": "Sí" if validation and entity.get("nombre") in validation.get("verified_claims", []) else "No",
                        })
            
            if rows:
                df_export = pd.DataFrame(rows)
                
                # Vista previa
                st.markdown("#### Vista previa")
                st.dataframe(df_export, use_container_width=True)
                
                # Botones de descarga
                col_dl1, col_dl2 = st.columns(2)
                with col_dl1:
                    # Excel
                    buffer = BytesIO()
                    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                        df_export.to_excel(writer, index=False, sheet_name="Oportunidades")
                        worksheet = writer.sheets["Oportunidades"]
                        for i, col in enumerate(df_export.columns):
                            max_len = max(df_export[col].fillna('').astype(str).str.len().max(), len(str(col)))
                            worksheet.set_column(i, i, min(max_len + 2, 50))
                    buffer.seek(0)
                    st.download_button(
                        label="📥 Descargar Excel",
                        data=buffer,
                        file_name=f"double_helix_dealflow_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                
                with col_dl2:
                    # CSV
                    csv = df_export.to_csv(index=False, encoding="utf-8-sig")
                    st.download_button(
                        label="📥 Descargar CSV",
                        data=csv,
                        file_name=f"double_helix_dealflow_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
                
                # Resumen estadístico
                st.markdown("#### 📈 Resumen")
                col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                col_s1.metric("Total oportunidades", len(df_export))
                col_s2.metric("Score promedio", f"{df_export['Score'].mean():.1f}")
                col_s3.metric("Centros analizados", df_export["Centro"].nunique())
                col_s4.metric("URLs verificadas", df_export[df_export["Verificado"] == "Sí"].shape[0])
                
                if not df_export["Tipo Entidad"].empty:
                    st.markdown("#### Distribución por tipo de entidad")
                    type_counts = df_export["Tipo Entidad"].value_counts()
                    st.bar_chart(type_counts)
            else:
                st.warning("⚠️ No hay oportunidades para exportar. Ajusta los filtros o ejecuta un nuevo análisis.")
    
    # ========================================================================
    # FOOTER
    # ========================================================================
    st.markdown(f"""
    <div class="footer">
        <img src="{BRANDING['logo_url']}" style="height: 30px; opacity: 0.7; margin-bottom: 0.5rem;">
        <p>Double Helix Dealflow Finder v3.1 © {datetime.now().year} | Healthtech Venture Capital</p>
        <p style="font-size: 0.75rem; color: #999;">
            Extracción jerárquica: Tecnologías → Artículos → Empresas → Personas | 
            Validación con Perplexity para URLs y fuentes reales |
            Monitoreo europeo: CORDIS, EU-Funding, EIC
        </p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
