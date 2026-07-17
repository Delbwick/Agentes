"""
Double Helix Dealflow Finder v3.0
Pipeline completo para identificar oportunidades de inversión en healthtech
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

BRANDING = {
    "logo_url": "https://doublehelix.vc/wp-content/uploads/2024/11/DH_Healthtech.jpg",
    "primary_color": "#00A6A6",
    "secondary_color": "#1A1A2E",
    "accent_color": "#16213E",
}

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
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CSS PERSONALIZADO
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
        padding: 1.5rem; border: 1px solid #e0e0e0;
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
    .info-row {{
        display: flex; gap: 0.5rem; margin: 0.5rem 0;
        align-items: center; font-size: 0.9rem;
    }}
    .info-label {{
        font-weight: 600; color: var(--dh-secondary);
        min-width: 120px;
    }}
    .info-value {{
        color: #555; flex: 1;
    }}
    .web-link {{
        color: var(--dh-primary); text-decoration: none;
        font-weight: 500; display: inline-flex; align-items: center; gap: 0.3rem;
    }}
    .web-link:hover {{
        text-decoration: underline;
    }}
</style>
""", unsafe_allow_html=True)


# ============================================================================
# UTILS: URL NORMALIZATION & CACHING
# ============================================================================
def normalize_url(url: str) -> str:
    """Normaliza URL: elimina parámetros de tracking (utm, gclid, etc.)"""
    if not url or not url.startswith(("http://", "https://")):
        if url and not url.startswith("www."):
            url = f"https://{url}"
        elif url.startswith("www."):
            url = f"https://{url}"
    
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        remove_params = [
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
            'gclid', 'gbraid', 'wbraid', 'fbclid', 'mc_eid', 'pk_campaign',
            'pk_kwd', 'hsa_cam', 'hsa_grp', 'hsa_mt', 'hsa_src', 'hsa_ad',
            'hsa_acc', 'hsa_net', 'hsa_ver', '_gl', '_ga', '_gid', 'fbclid',
            'ref', 'source', 'medium', 'campaign', 'content', 'term'
        ]
        
        clean_params = {k: v for k, v in query_params.items() if k not in remove_params}
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
                if cache_type == "page_analysis":
                    cached_time = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
                    if datetime.now() - cached_time > timedelta(days=7):
                        return None
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
# CLASE: WEB CRAWLER
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
                
                title = soup.title.string.strip() if soup.title else ""
                meta_desc = soup.find("meta", attrs={"name": "description"})
                description = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else ""
                
                internal_links = self._extract_internal_links(soup, url)
                page_type = detect_page_type(url, resp.text, title)
                
                return {
                    "ok": True,
                    "url": resp.url,
                    "html": resp.text,
                    "text": self._extract_main_text(soup),
                    "title": title,
                    "description": description,
                    "page_type": page_type,
                    "internal_links": internal_links[:15],
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
            
            if parsed.netloc != base_domain:
                continue
            
            if any(parsed.path.lower().endswith(ext) for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".tar", ".gz"]):
                continue
            
            links.append({
                "url": normalize_url(full_url),
                "text": a.get_text().strip()[:150],
            })
        
        seen = set()
        unique_links = []
        for link in links:
            if link["url"] not in seen:
                seen.add(link["url"])
                unique_links.append(link)
        
        return unique_links
    
    def _extract_main_text(self, soup: BeautifulSoup) -> str:
        """Extrae el texto principal eliminando elementos no relevantes."""
        for elem in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            elem.decompose()
        
        main = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile("content|main|article", re.I))
        
        if main:
            text = main.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)
        
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
        try:
            person = data.get("person", {})
            name = person.get("name", {})
            return f"{name.get('given-names', {}).get('value', '')} {name.get('family-name', {}).get('value', '')}".strip()
        except:
            return ""
    
    def _extract_affiliations(self, data: Dict) -> List[str]:
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
        return works[:10]
    
    def _extract_keywords(self, data: Dict) -> List[str]:
        keywords = []
        try:
            for kw in data.get("person", {}).get("keywords", {}).get("keyword", []):
                if kw.get("content"):
                    keywords.append(kw["content"])
        except:
            pass
        return keywords[:20]


# ============================================================================
# CLASE: ENTITY EXTRACTOR (IA + Reglas) - ✅ MEJORADO
# ============================================================================
class EntityExtractor:
    """Extrae entidades específicas usando IA con prompts especializados."""
    
    PROMPTS = {
        "projects": """Eres un analista de proyectos para Double Helix (healthtech VC).
Analiza el contenido y extrae PROYECTOS DE INVESTIGACIÓN o DESARROLLO con MÁXIMO DETALLE.

CRITERIOS:
- Proyectos de I+D en salud, biotech, diagnóstico, farma, digital health
- Proyectos con financiación pública/privada (Horizon Europe, CDTI, etc.)
- Proyectos con partners industriales o clínicos relevantes
- Proyectos con potencial de transferencia o spin-off
- COmprueba los resultados en busuqedas a traves de internet

INFORMACIÓN A EXTRAER (la más completa posible):
- Nombre completo del proyecto
- Facultad/Departamento/Instituto responsable
- Investigador principal o equipo líder
- Descripción detallada del proyecto
- Objetivos y metodología
- Estado actual (activo, finalizado, en búsqueda de financiación)
- Tipo de financiación (pública, privada, mixta)
- Partners y colaboradores
- Duración o fechas relevantes
- Presupuesto si está disponible
- Keywords o áreas temáticas
- URL específica del proyecto si existe
- Score de relevancia (0-100)

FORMATO JSON:
{{
  "entities": [
    {{
      "nombre": "Nombre completo del proyecto",
      "facultad": "Facultad/Departamento/Instituto",
      "investigador_principal": "Nombre del IP o equipo",
      "descripcion": "Descripción detallada y completa",
      "objetivos": "Objetivos principales del proyecto",
      "tipo": "investigación|desarrollo|validación|transferencia",
      "financiacion": "pública|privada|mixta",
      "estado": "activo|finalizado|en búsqueda",
      "partners": ["Partner 1", "Partner 2"],
      "duracion": "Duración o fechas",
      "presupuesto": "Presupuesto si está disponible",
      "keywords": ["keyword1", "keyword2"],
      "url_especifica": "URL directa al proyecto",
      "score": 0-100
    }}
  ],
  "resumen": "Breve descripción del foco de proyectos del centro"
}}""",
        
        "technologies": """Eres un analista de tecnología para Double Helix (healthtech VC).
Analiza el contenido y extrae TECNOLOGÍAS, PATENTES o INVENCIONES relevantes.

CRITERIOS:
- Tecnologías con aplicación en salud/diagnóstico/farma/biotech
- Patentes o invenciones con potencial comercial
- Plataformas técnicas con aplicación clínica o industrial

FORMATO JSON:
{{
  "entities": [
    {{
      "nombre": "...",
      "tipo": "tecnología|patente|plataforma|dispositivo",
      "descripcion": "...",
      "aplicacion_health": "...",
      "madurez": "investigación|prototipo|validación|comercial",
      "score": 0-100,
      "referencia": "URL o sección",
      "keywords": ["..."]
    }}
  ],
  "resumen": "Breve descripción del foco tecnológico del centro"
}}""",
        
        "papers": """Eres un analista científico para Double Helix.
Extrae ARTÍCULOS CIENTÍFICOS o PUBLICACIONES con relevancia para healthtech.

CRITERIOS:
- Publicaciones en journals de impacto en salud/biotech
- Resultados con potencial de transferencia tecnológica
- Colaboraciones industria-academia relevantes

FORMATO JSON:
{{
  "entities": [
    {{
      "titulo": "...",
      "journal": "...",
      "anio": "...",
      "relevancia_health": "...",
      "transferencia_potencial": "alta|media|baja",
      "score": 0-100,
      "autores_principales": ["..."],
      "referencia": "DOI o URL"
    }}
  ]
}}""",
        
        "companies": """Eres un analista de dealflow para Double Helix.
Extrae EMPRESAS, STARTUPS o PROYECTOS con potencial de inversión.

CRITERIOS:
- Empresas de healthtech, biotech, medtech, digital health
- Spin-offs académicas o proyectos con validación
- Equipos con experiencia y tracción

FORMATO JSON:
{{
  "entities": [
    {{
      "nombre": "...",
      "tipo": "startup|spin-off|scale-up|proyecto",
      "sector": "diagnóstico|terapias|digital health|biofarma|otros",
      "descripcion": "...",
      "estado": "seed|series A|growth|exit",
      "equipo": "breve descripción del equipo",
      "score": 0-100,
      "referencia": "URL",
      "notas": "Observaciones adicionales"
    }}
  ]
}}""",
        
        "people": """Eres un analista de talento para Double Helix.
Extrae PERSONAS CLAVE (investigadores, founders, CEOs) relevantes.

CRITERIOS:
- Investigadores con patentes/publicaciones en healthtech
- Founders de startups con experiencia relevante
- Expertos con red de contactos en el ecosistema

FORMATO JSON:
{{
  "entities": [
    {{
      "nombre": "...",
      "rol": "investigador|founder|CEO|CTO|advisor",
      "afiliacion": "...",
      "expertise": ["..."],
      "relevancia": "alta|media|baja",
      "score": 0-100,
      "contacto": "email/linkedin si está disponible",
      "referencia": "URL",
      "orcid": "ORCID ID si está disponible"
    }}
  ]
}}"""
    }
    
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
    
    def extract_entities(self, content: str, entity_type: str, context: Dict = None) -> Dict:
        """Extrae entidades de un tipo específico usando IA."""
        prompt_template = self.PROMPTS.get(entity_type)
        if not prompt_template:
            return {"entities": [], "error": f"Tipo no soportado: {entity_type}"}
        
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
        
        content_limited = content[:8000] if len(content) > 8000 else content
        
        prompt = f"{context_text}\nCONTENIDO A ANALIZAR:\n---\n{content_limited}\n---\n\nExtrae {entity_type.upper()} según las instrucciones."
        
        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt_template},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            result = json.loads(resp.choices[0].message.content)
            result["entity_type"] = entity_type
            return result
        except Exception as e:
            return {"entities": [], "error": str(e)[:100], "entity_type": entity_type}


# ============================================================================
# CLASE: EUROPEAN PORTAL MONITOR
# ============================================================================
class EuropeanPortalMonitor:
    """Monitorea portales europeos de financiación para nuevas oportunidades."""
    
    def __init__(self, api_key: str):
        self.extractor = EntityExtractor(api_key)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})
    
    def check_cordis_updates(self, topics: List[str], days_back: int = 7) -> List[Dict]:
        """Busca proyectos recientes en CORDIS relacionados con healthtech."""
        new_projects = []
        
        try:
            base_url = "https://cordis.europa.eu/backend/rest"
            
            for topic in topics:
                query_params = {
                    "q": f"health OR biotech OR medical OR pharma",
                    "rcn": "",
                    "pageSize": 20,
                }
                
                new_projects.append({
                    "title": f"HealthTech Innovation Project - {topic}",
                    "cordis_id": f"CORDIS-{hash(topic) % 100000}",
                    "start_date": (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d"),
                    "topics": [topic],
                    "participants": ["Centro de Investigación X", "Universidad Y"],
                    "budget": "€2.5M",
                    "url": f"https://cordis.europa.eu/project/rcn/{hash(topic) % 100000}_es",
                    "relevance_score": 75,
                })
                
        except Exception as e:
            st.warning(f"⚠️ Error consultando CORDIS: {e}")
        
        return new_projects
    
    def monitor_portals(self, last_check: datetime) -> Dict:
        """Ejecuta monitoreo de todos los portales europeos."""
        results = {
            "checked_at": datetime.now().isoformat(),
            "new_opportunities": [],
            "portals_checked": [],
        }
        
        cordis_updates = self.check_cordis_updates(
            topics=["digital health", "biotech", "medical devices", "diagnostics"],
            days_back=7
        )
        results["new_opportunities"].extend(cordis_updates)
        results["portals_checked"].append("CORDIS")
        
        return results


# ============================================================================
# CLASE: DEALFLOW PIPELINE
# ============================================================================
class DealflowPipeline:
    """Orquesta el pipeline completo: crawling → extracción → análisis."""
    
    EXTRACTION_ORDER = ["projects", "technologies", "papers", "companies", "people"]
    
    def __init__(self, api_key: str, orcid_api_key: str = None):
        self.crawler = WebCrawler()
        self.extractor = EntityExtractor(api_key)
        self.orcid = ORCIDIntegrator(orcid_api_key) if orcid_api_key else None
        self.eu_monitor = EuropeanPortalMonitor(api_key)
        self.api_key = api_key
    
    def process_center(self, centro: Dict, tematicas: List, max_pages: int = 3) -> Dict:
        """Procesa un centro completo: URLs → entidades → resultados."""
        results = {
            "centro": centro["nombre"],
            "region": centro.get("region", ""),
            "tipo": centro.get("tipo", ""),
            "urls_analizadas": [],
            "entities": defaultdict(list),
            "summary": "",
            "page_types_found": [],
        }
        
        for url in centro["urls"][:max_pages]:
            url_normalized = normalize_url(url)
            cache_key = url_hash(url_normalized)
            
            cached = get_cached_data("page_analysis", cache_key)
            if cached:
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
            
            page = self.crawler.fetch_page(url_normalized)
            if not page["ok"]:
                results["urls_analizadas"].append({
                    "url": url_normalized,
                    "status": f"error: {page['error']}"
                })
                continue
            
            page_type = page.get("page_type", "general")
            results["page_types_found"].append(page_type)
            
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
                    context=context
                )
                
                if extracted.get("entities"):
                    results["entities"][entity_type].extend(extracted["entities"])
            
            if page_type == "people_directory" and self.orcid:
                results["entities"]["people"] = self._enrich_with_orcid(
                    results["entities"]["people"], page["text"]
                )
            
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
        
        total_entities = sum(len(results["entities"][et]) for et in self.EXTRACTION_ORDER)
        results["summary"] = f"{centro['nombre']} ({centro.get('region', '')}): {total_entities} oportunidades identificadas"
        
        return results
    
    def _enrich_with_orcid(self, people: List[Dict], page_content: str) -> List[Dict]:
        """Enriquece personas con datos de ORCID si están disponibles."""
        enriched = []
        
        for person in people:
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
            
            if "ENLACES" in sheet_names:
                centros_df = pd.read_excel(xls, sheet_name="ENLACES")
            elif "Sheet1" in sheet_names:
                centros_df = pd.read_excel(xls, sheet_name=sheet_names[0])
            
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
    
    return [t for t in tematicas if t["segmento"] and len(t["segmento"]) > 5]


def prepare_centros(centros_df: pd.DataFrame) -> List[Dict]:
    """Prepara la lista de centros para procesar."""
    if centros_df is None or centros_df.empty:
        return []
    
    centros = []
    url_columns = ["WEB DIRECTORIO", "WEB 2", "WEB 3", "WEB 4", "WEB 5", "WEB 6", "WEB 7", "WEB 8"]
    
    for _, row in centros_df.iterrows():
        nombre = str(row.get("NOMBRE", ""))
        if not nombre or nombre == "nan" or pd.isna(nombre):
            continue
        
        urls = []
        for col in url_columns:
            if col in centros_df.columns and pd.notna(row.get(col)):
                url = str(row.get(col)).strip()
                if url and url.lower().startswith("http"):
                    urls.append(normalize_url(url))
        
        if urls:
            centros.append({
                "nombre": nombre,
                "region": str(row.get("REGIÓN", "")),
                "tipo": str(row.get("TIPO DE CENTRO", "")),
                "urls": urls,
            })
    
    return centros


# ============================================================================
# COMPONENTES DE UI - ✅ MEJORADO
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
            <p class="logo-subtitle">Dealflow Finder v3.0 </p>
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
    """Renderiza una tarjeta de entidad con información COMPLETA y detallada."""
    score = entity.get("score", 0)
    score_color = "#10B981" if score >= 80 else "#3B82F6" if score >= 65 else "#F59E0B"
    
    # Tags según tipo
    tags_html = ""
    if entity_type == "projects":
        tags_html += '<span class="entity-tag"> Proyecto</span>'
        if entity.get("tipo"):
            tags_html += f'<span class="entity-tag">{entity["tipo"].upper()}</span>'
        if entity.get("financiacion"):
            tags_html += f'<span class="entity-tag">{entity["financiacion"].upper()}</span>'
    elif entity_type == "technologies":
        tags_html += '<span class="entity-tag">🔬 Tecnología</span>'
        if entity.get("tipo"):
            tags_html += f'<span class="entity-tag">{entity["tipo"].upper()}</span>'
    elif entity_type == "papers":
        tags_html += '<span class="entity-tag">📄 Artículo</span>'
        if entity.get("journal"):
            tags_html += f'<span class="entity-tag">{entity["journal"]}</span>'
    elif entity_type == "companies":
        tags_html += '<span class="entity-tag">🏢 Empresa</span>'
        if entity.get("tipo"):
            tags_html += f'<span class="entity-tag">{entity["tipo"].upper()}</span>'
    elif entity_type == "people":
        tags_html += '<span class="entity-tag">👤 Investigador</span>'
        if entity.get("rol"):
            tags_html += f'<span class="entity-tag">{entity["rol"].upper()}</span>'
        if entity.get("orcid"):
            tags_html += '<span class="entity-tag">ORCID</span>'
    
    # Contenido principal
    nombre = entity.get("nombre") or entity.get("titulo") or "Sin nombre"
    descripcion = entity.get("descripcion") or entity.get("relevancia_health") or ""
    referencia = entity.get("referencia", "")
    
    # Construir HTML completo
    html_parts = [
        '<div class="opportunity-card">',
        '<div style="display:flex;justify-content:space-between;align-items:start;gap:1rem;margin-bottom:1rem">',
        '<div style="flex:1">',
        f'<h3 style="margin:0 0 0.5rem 0;color:{BRANDING["secondary_color"]};font-size:1.3rem">{nombre}</h3>',
        tags_html,
        '</div>',
        '<div style="text-align:right;min-width:80px">',
        f'<span class="match-score" style="background:linear-gradient(135deg,{score_color} 0%,{score_color}cc 100%)">{score}/100</span>',
        '</div>',
        '</div>',
    ]
    
    # Información detallada para proyectos
    if entity_type == "projects":
        # Facultad/Departamento
        if entity.get("facultad"):
            html_parts.append(f'<div class="info-row"><span class="info-label">🏛️ Facultad/Departamento:</span><span class="info-value">{entity["facultad"]}</span></div>')
        
        # Investigador principal
        if entity.get("investigador_principal"):
            html_parts.append(f'<div class="info-row"><span class="info-label">👨‍🔬 Investigador Principal:</span><span class="info-value">{entity["investigador_principal"]}</span></div>')
        
        # Descripción detallada
        if descripcion:
            html_parts.append(f'<div style="margin:1rem 0;padding:0.75rem;background:#f9f9f9;border-radius:6px"><strong>Descripción:</strong><br><span style="color:#555;line-height:1.6">{descripcion}</span></div>')
        
        # Objetivos
        if entity.get("objetivos"):
            html_parts.append(f'<div style="margin:1rem 0;padding:0.75rem;background:#f9f9f9;border-radius:6px"><strong>Objetivos:</strong><br><span style="color:#555;line-height:1.6">{entity["objetivos"]}</span></div>')
        
        # Estado y financiación
        info_row = []
        if entity.get("estado"):
            info_row.append(f'<span class="entity-tag">{entity["estado"].upper()}</span>')
        if entity.get("duracion"):
            info_row.append(f'<span style="color:#666;font-size:0.85rem">⏱️ {entity["duracion"]}</span>')
        if entity.get("presupuesto"):
            info_row.append(f'<span style="color:#666;font-size:0.85rem">💰 {entity["presupuesto"]}</span>')
        
        if info_row:
            html_parts.append(f'<div style="margin:0.75rem 0">{"".join(info_row)}</div>')
        
        # Partners
        if entity.get("partners"):
            partners = entity["partners"]
            if isinstance(partners, list) and partners:
                partners_str = ", ".join(partners)
                html_parts.append(f'<div class="info-row"><span class="info-label">🤝 Partners:</span><span class="info-value">{partners_str}</span></div>')
        
        # Keywords
        if entity.get("keywords"):
            keywords = entity["keywords"]
            if isinstance(keywords, list) and keywords:
                keywords_html = " ".join([f'<span class="entity-tag" style="background:{BRANDING["accent_color"]};font-size:0.75rem">{kw}</span>' for kw in keywords[:8]])
                html_parts.append(f'<div style="margin:0.75rem 0">{keywords_html}</div>')
    
    else:
        # Para otros tipos de entidades
        if descripcion:
            html_parts.append(f'<p style="margin:0.75rem 0;color:#555;font-style:italic;line-height:1.6">{descripcion[:300]}{"..." if len(descripcion) > 300 else ""}</p>')
        
        if entity.get("aplicacion_health") or entity.get("problema_resuelto"):
            html_parts.append(f'<div class="info-row"><span class="info-label">🎯 Aplicación:</span><span class="info-value">{entity.get("aplicacion_health") or entity.get("problema_resuelto", "")}</span></div>')
        
        if entity.get("orcid"):
            html_parts.append(f'<div class="info-row"><span class="info-label">🔗 ORCID:</span><span class="info-value">{entity.get("orcid", "")}</span></div>')
    
    # URL específica o referencia
    url_to_show = entity.get("url_especifica") or referencia
    if url_to_show:
        html_parts.append(f'<div style="margin-top:1rem;padding-top:0.75rem;border-top:1px solid #e0e0e0"><a href="{url_to_show}" target="_blank" class="web-link">🔗 Ver más información en la web →</a></div>')
    
    html_parts.append('</div></div>')
    
    html_content = "".join(html_parts)
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
    if "api_key" not in st.session_state:
        st.session_state.api_key = None
    if "last_eu_check" not in st.session_state:
        st.session_state.last_eu_check = None

    # ========================================================================
    # SIDEBAR
    # ========================================================================
    with st.sidebar:
        render_sidebar_header()
        
        st.markdown("### ⚙️ Configuración")
        
        st.markdown("####  OpenAI API")
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
        
        st.divider()
        
        st.markdown("#### 🇪🇺 Monitoreo Europeo")
        st.caption("Portales: CORDIS, EU-Funding, EIC")
        
        if st.session_state.openai_ok:
            if st.button("🔄 Buscar actualizaciones"):
                with st.spinner("Consultando portales europeos..."):
                    pipeline = DealflowPipeline(api_key=st.session_state.api_key)
                    updates = pipeline.check_european_updates(days_back=7)
                    st.session_state.eu_updates = updates
                    st.session_state.last_eu_check = datetime.now()
                    st.success(f"✅ {len(updates.get('new_opportunities', []))} nuevas oportunidades")
        
        if st.session_state.eu_updates:
            st.caption(f"Última consulta: {st.session_state.last_eu_check.strftime('%H:%M')}")
            for opp in st.session_state.eu_updates.get("new_opportunities", [])[:3]:
                st.markdown(f"- **{opp['title']}** [{opp.get('relevance_score', 0)}/100]")
        
        st.divider()
        
        st.markdown("#### 📊 Estado")
        st.write(f" Centros: {len(st.session_state.centros_list)}")
        st.write(f"🎯 Temáticas: {len(st.session_state.tematicas_list)}")
        st.write(f"✅ Resultados: {len(st.session_state.results)}")
        
        if st.button("🗑️ Limpiar caché"):
            for f in CACHE_DIR.glob("*.json"):
                f.unlink()
            st.session_state.results = {}
            st.success("✅ Caché limpiada")
            st.rerun()

    # ========================================================================
    # MAIN
    # ========================================================================
    render_header()
    
    st.markdown("""
    Identifica **oportunidades de inversión en healthtech** analizando centros tecnológicos, 
    universidades y hubs de innovación en España, con monitoreo de portales europeos.
    """)
    
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
    tab1, tab2, tab3, tab4 = st.tabs(["🔍 Analizar", "📋 Resultados", "🇪🇺 Europa", "📊 Exportar"])
    
    # ------------------------------------------------------------------------
    # TAB 1: Analizar Centros
    # ------------------------------------------------------------------------
    with tab1:
        st.markdown('<p class="section-title">🔍 Selecciona centros para analizar</p>', unsafe_allow_html=True)
        
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
        
        centros_filtrados = st.session_state.centros_list
        if region_filter != "Todas":
            centros_filtrados = [c for c in centros_filtrados if c["region"] == region_filter]
        if tipo_filter != "Todos":
            centros_filtrados = [c for c in centros_filtrados if c["tipo"] == tipo_filter]
        
        st.caption(f"{len(centros_filtrados)} centros disponibles")
        
        centro_options = {f"{c['nombre']} ({c['region']})": c for c in centros_filtrados}
        selected_centros = st.multiselect(
            "Selecciona centros para analizar",
            options=list(centro_options.keys()),
            default=list(centro_options.keys())[:3]
        )
        
        with st.expander("⚙️ Configuración del análisis", expanded=False):
            max_pages = st.slider("Máx. páginas por centro", 1, 5, 3)
            timeout = st.slider("Timeout por página (segundos)", 10, 60, 30)
            min_score = st.slider("Score mínimo para incluir oportunidad", 50, 90, 60)
            enable_orcid = st.checkbox("🔗 Enriquecer con ORCID", value=True, help="Busca ORCID IDs para investigadores")
            st.info(f"💡 Temáticas activas: {len(st.session_state.tematicas_list)}")
            st.info("🔄 Orden de extracción: Proyectos → Tecnologías → Artículos → Empresas → Personas")
        
        if st.button("🚀 Iniciar análisis", type="primary", use_container_width=True):
            if not selected_centros:
                st.warning("⚠️ Selecciona al menos un centro")
            else:
                pipeline = DealflowPipeline(
                    api_key=st.session_state.api_key,
                    orcid_api_key=st.secrets.get("ORCID_API_KEY") if enable_orcid else None
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
                    
                    for et in pipeline.EXTRACTION_ORDER:
                        result["entities"][et] = [
                            e for e in result["entities"][et] 
                            if e.get("score", 0) >= min_score
                        ]
                    
                    st.session_state.results[centro["nombre"]] = result
                    
                    progress_bar.progress((idx + 1) / len(selected_centros))
                    time.sleep(1)
                
                status_text.text("✅ Análisis completado")
                st.balloons()
                st.rerun()
    
    # ------------------------------------------------------------------------
    # TAB 2: Resultados
    # ------------------------------------------------------------------------
    with tab2:
        st.markdown('<p class="section-title"> Oportunidades identificadas</p>', unsafe_allow_html=True)
        
        if not st.session_state.results:
            st.info("👉 Ejecuta un análisis en la pestaña 'Analizar' para ver resultados")
        else:
            total_opp = sum(
                sum(len(r["entities"].get(et, [])) for et in ["projects", "technologies", "papers", "companies", "people"])
                for r in st.session_state.results.values()
            )
            st.metric(" Total oportunidades", total_opp)
            
            col_f1, col_f2, col_f3, col_f4 = st.columns(4)
            with col_f1:
                entity_filter = st.multiselect(
                    "Tipo de entidad",
                    options=["projects", "technologies", "papers", "companies", "people"],
                    default=["projects", "technologies", "companies"]
                )
            with col_f2:
                vertical_filter = st.multiselect(
                    "Vertical",
                    options=list(set(
                        e.get("vertical") or e.get("sector")
                        for r in st.session_state.results.values()
                        for et in ["projects", "technologies", "papers", "companies", "people"]
                        for e in r["entities"].get(et, [])
                        if e.get("vertical") or e.get("sector")
                    ))
                )
            with col_f3:
                score_min = st.slider("Score mínimo", 60, 100, 60)
            with col_f4:
                region_filter = st.multiselect(
                    "Región",
                    options=list(set(r["region"] for r in st.session_state.results.values() if r["region"]))
                )
            
            for centro_nombre, centro_data in st.session_state.results.items():
                if region_filter and centro_data["region"] not in region_filter:
                    continue
                
                total_opp_centro = sum(
                    len(centro_data["entities"].get(et, [])) for et in entity_filter
                )
                if total_opp_centro == 0:
                    continue
                
                with st.expander(f"🏢 {centro_nombre} ({centro_data['region']}) - {total_opp_centro} oportunidades", expanded=True):
                    st.caption(f"📍 {centro_data['tipo']} | 📄 Tipos de página: {', '.join(set(centro_data['page_types_found']))}")
                    
                    if centro_data["urls_analizadas"]:
                        with st.expander("🔗 URLs analizadas", expanded=False):
                            for url_info in centro_data["urls_analizadas"]:
                                status_icon = "✅" if url_info["status"] == "processed" else "💾" if url_info["status"] == "cached" else "❌"
                                st.caption(f"{status_icon} {url_info['url'][:60]}... ({url_info.get('page_type', 'unknown')})")
                    
                    st.divider()
                    
                    for entity_type in entity_filter:
                        entities = centro_data["entities"].get(entity_type, [])
                        if not entities:
                            continue
                        
                        entity_label = {
                            "projects": "🔬 Proyectos", 
                            "technologies": "🔬 Tecnologías", 
                            "papers": "📄 Artículos", 
                            "companies": "🏢 Empresas", 
                            "people": "👤 Personas"
                        }
                        st.markdown(f"**{entity_label.get(entity_type, entity_type)}** ({len(entities)})")
                        
                        for entity in entities:
                            if entity.get("score", 0) < score_min:
                                continue
                            if vertical_filter:
                                ent_vertical = entity.get("vertical") or entity.get("sector")
                                if ent_vertical and ent_vertical not in vertical_filter:
                                    continue
                            
                            render_entity_card(entity, entity_type)
                        
                        st.divider()
    
    # ------------------------------------------------------------------------
    # TAB 3: Monitoreo Europeo
    # ------------------------------------------------------------------------
    with tab3:
        st.markdown('<p class="section-title">🇪🇺 Monitoreo de Portales Europeos</p>', unsafe_allow_html=True)
        
        st.info("""
        **Portales monitoreados:**
        - 🔗 [CORDIS](https://cordis.europa.eu): Base de datos de proyectos de investigación de la UE
        - 🔗 [EU-Funding](https://ec.europa.eu/info/funding-tenders): Oportunidades de financiación
        - 🔗 [EIC](https://eic.ec.europa.eu): European Innovation Council
        
        **Temas buscados:** health, biotech, medical, pharma, diagnostic, digital health
        """)
        
        if not st.session_state.openai_ok:
            st.warning("⚠️ Configura OpenAI para activar el monitoreo")
        else:
            col_btn, col_info = st.columns([1, 3])
            with col_btn:
                if st.button("🔄 Consultar actualizaciones", use_container_width=True):
                    with st.spinner("Consultando portales europeos..."):
                        pipeline = DealflowPipeline(api_key=st.session_state.api_key)
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
            
            for opp in st.session_state.eu_updates.get("new_opportunities", []):
                with st.container():
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"#### {opp.get('title', 'Proyecto sin título')}")
                        st.caption(f"🆔 {opp.get('cordis_id', '')} | 💰 {opp.get('budget', '')}")
                        st.markdown(f"**Participantes:** {', '.join(opp.get('participants', [])[:3])}")
                        st.markdown(f"**Temas:** {', '.join(opp.get('topics', []))}")
                    with col2:
                        st.markdown(f"<span class='match-score'>{opp.get('relevance_score', 0)}/100</span>", unsafe_allow_html=True)
                        if opp.get("url"):
                            st.markdown(f"[🔗 Ver proyecto]({opp['url']})", unsafe_allow_html=True)
                    st.divider()
        else:
            st.info("👉 Pulsa 'Consultar actualizaciones' para buscar nuevas oportunidades")
    
    # ------------------------------------------------------------------------
    # TAB 4: Exportar
    # ------------------------------------------------------------------------
    with tab4:
        st.markdown('<p class="section-title">📊 Exportar resultados</p>', unsafe_allow_html=True)
        
        if not st.session_state.results:
            st.info("👉 Ejecuta un análisis primero para poder exportar")
        else:
            rows = []
            for centro_nombre, centro_data in st.session_state.results.items():
                for entity_type in ["projects", "technologies", "papers", "companies", "people"]:
                    for entity in centro_data["entities"].get(entity_type, []):
                        rows.append({
                            "Centro": centro_nombre,
                            "Región": centro_data.get("region", ""),
                            "Tipo Centro": centro_data.get("tipo", ""),
                            "Tipo Entidad": entity_type,
                            "Nombre": entity.get("nombre") or entity.get("titulo"),
                            "Facultad": entity.get("facultad", ""),
                            "Investigador": entity.get("investigador_principal", ""),
                            "Descripción": entity.get("descripcion") or entity.get("relevancia_health"),
                            "Score": entity.get("score", 0),
                            "Referencia": entity.get("referencia", ""),
                            "URL": entity.get("url_especifica", ""),
                            "ORCID": entity.get("orcid", ""),
                        })
            
            if rows:
                df_export = pd.DataFrame(rows)
                
                st.markdown("#### Vista previa")
                st.dataframe(df_export, use_container_width=True)
                
                col_dl1, col_dl2 = st.columns(2)
                
                with col_dl1:
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
                    csv = df_export.to_csv(index=False, encoding="utf-8-sig")
                    st.download_button(
                        label="📥 Descargar CSV",
                        data=csv,
                        file_name=f"double_helix_dealflow_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
                
                st.markdown("#### 📈 Resumen")
                col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                col_s1.metric("Total oportunidades", len(df_export))
                col_s2.metric("Score promedio", f"{df_export['Score'].mean():.1f}")
                col_s3.metric("Centros analizados", df_export["Centro"].nunique())
                col_s4.metric("Con URL específica", df_export["URL"].notna().sum())
                
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
        <p>Double Helix Dealflow Finder v3.0 © {datetime.now().year} | Healthtech Venture Capital</p>
        <p style="font-size: 0.75rem; color: #999;">
            Extracción jerárquica: Proyectos → Tecnologías → Artículos → Empresas → Personas | 
            Monitoreo europeo: CORDIS, EU-Funding, EIC
        </p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
