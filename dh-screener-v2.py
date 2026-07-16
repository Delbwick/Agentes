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
    "logo_url": "https://doublehelix.vc/wp-content/uploads/2023/03/cropped-DH-Logo-1.png",
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
}

st.set_page_config(
    page_title="🔍 Double Helix Dealflow Finder",
    page_icon="🔍",
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
</style>
""", unsafe_allow_html=True)


# ============================================================================
# UTILS
# ============================================================================
def normalize_url(url: str) -> str:
    if not url or not isinstance(url, str):
        return ""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}" if not url.startswith("www.") else f"https://{url}"
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        remove_params = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
                        'gclid', 'gbraid', 'wbraid', 'fbclid', 'mc_eid', 'pk_campaign',
                        'pk_kwd', 'hsa_cam', 'hsa_grp', 'hsa_mt', 'hsa_src', 'hsa_ad',
                        'hsa_acc', 'hsa_net', 'hsa_ver', '_gl', '_ga', '_gid', 'ref']
        clean_params = {k: v for k, v in query_params.items() if k not in remove_params}
        clean_query = urlencode(clean_params, doseq=True) if clean_params else ""
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if clean_query: clean_url += f"?{clean_query}"
        if parsed.fragment: clean_url += f"#{parsed.fragment}"
        return clean_url
    except:
        return url


def url_hash(url: str) -> str:
    return hashlib.md5(normalize_url(url).encode()).hexdigest()[:16]


def get_cached_data(cache_type: str, key: str) -> Optional[Dict]:
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
    data["cached_at"] = datetime.now().isoformat()
    cache_file = CACHE_DIR / f"{cache_type}_{key}.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def detect_page_type(url: str, content: str, title: str) -> str:
    url_lower, content_lower, title_lower = url.lower(), (content or "").lower(), (title or "").lower()
    if any(kw in url_lower for kw in ['spin', 'startup', 'empresa', 'company']): return "company_directory"
    if any(kw in url_lower for kw in ['project', 'proyecto', 'funding', 'cordis']): return "project_listing"
    if any(kw in url_lower for kw in ['patent', 'patente', 'technology']): return "technology_transfer"
    if any(kw in url_lower for kw in ['publication', 'paper', 'article', 'orcid']): return "research_publications"
    if any(kw in url_lower for kw in ['team', 'people', 'investigator']): return "people_directory"
    if re.search(r'spin[-\s]?off|startup|empresa', content_lower): return "company_directory"
    if re.search(r'patent|patente', content_lower): return "technology_transfer"
    if re.search(r'publication|paper|orcid', content_lower): return "research_publications"
    return "general"


# ============================================================================
# CLASES PRINCIPALES
# ============================================================================
class WebCrawler:
    def __init__(self, user_agent: str = None):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent or "Mozilla/5.0"})
    
    def fetch_page(self, url: str, timeout: int = 30) -> Dict:
        url = normalize_url(url)
        if not url: return {"ok": False, "error": "URL vacía"}
        try:
            if not url.startswith(("http://", "https://")): url = f"https://{url}"
            if not urlparse(url).netloc: return {"ok": False, "error": "URL inválida"}
            resp = self.session.get(url, timeout=timeout)
            if resp.status_code == 200:
                resp.encoding = resp.apparent_encoding
                soup = BeautifulSoup(resp.text, "html.parser")
                title = soup.title.string.strip() if soup.title else ""
                meta_desc = soup.find("meta", attrs={"name": "description"})
                description = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else ""
                return {
                    "ok": True, "url": resp.url, "text": self._extract_main_text(soup),
                    "title": title, "description": description,
                    "page_type": detect_page_type(url, resp.text, title),
                }
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:100]}
    
    def _extract_main_text(self, soup: BeautifulSoup) -> str:
        for elem in soup(["script", "style", "nav", "footer", "header", "aside", "form"]): elem.decompose()
        main = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile("content|main", re.I))
        text = main.get_text(separator="\n", strip=True) if main else soup.get_text(separator="\n", strip=True)
        return re.sub(r'\n\s*\n+', '\n\n', re.sub(r'[ \t]+', ' ', text)).strip()


class EntityExtractor:
    PROMPTS = {
        "technologies": """Eres analista tech para Double Helix. Extrae TECNOLOGÍAS/PATENTES relevantes.
FORMATO JSON: {{"entities": [{{"nombre": "...", "tipo": "tecnología|patente", "descripcion": "...", 
"aplicacion_health": "...", "madurez": "investigación|prototipo|validación|comercial", 
"score": 0-100, "referencia": "URL", "keywords": ["..."]}}], "resumen": "..."}}""",
        "papers": """Extrae ARTÍCULOS CIENTÍFICOS con relevancia healthtech.
FORMATO JSON: {{"entities": [{{"titulo": "...", "journal": "...", "anio": "...", 
"relevancia_health": "...", "transferencia_potencial": "alta|media|baja", 
"score": 0-100, "autores_principales": ["..."], "referencia": "DOI/URL"}}]}}""",
        "companies": """Extrae EMPRESAS/STARTUPS con potencial de inversión healthtech.
FORMATO JSON: {{"entities": [{{"nombre": "...", "tipo": "startup|spin-off", 
"sector": "diagnóstico|terapias|digital health", "descripcion": "...", 
"estado": "seed|series A|growth", "score": 0-100, "referencia": "URL"}}]}}""",
        "people": """Extrae PERSONAS CLAVE (investigadores, founders) relevantes.
FORMATO JSON: {{"entities": [{{"nombre": "...", "rol": "investigador|founder|CEO", 
"afiliacion": "...", "expertise": ["..."], "relevancia": "alta|media|baja", 
"score": 0-100, "contacto": "...", "referencia": "URL", "orcid": "..."}}]}}"""
    }
    
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
    
    def extract_entities(self, content: str, entity_type: str, context: Dict = None) -> Dict:
        prompt = self.PROMPTS.get(entity_type)
        if not prompt: return {"entities": [], "error": f"Tipo no soportado: {entity_type}"}
        ctx = ""
        if context:
            if context.get("centro"): ctx += f"CENTRO: {context['centro']}\n"
            if context.get("tematicas"):
                ctx += "TEMÁTICAS:\n" + "\n".join(f"- {t['segmento']}: {t['definicion'][:100]}" 
                    for t in context["tematicas"][:3] if isinstance(t, dict) and t.get("segmento")) + "\n"
        content_limited = content[:8000] if len(content) > 8000 else content
        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": prompt}, {"role": "user", "content": f"{ctx}\nCONTENIDO:\n{content_limited}"}],
                temperature=0.1, response_format={"type": "json_object"}
            )
            result = json.loads(resp.choices[0].message.content)
            result["entity_type"] = entity_type
            return result
        except Exception as e:
            return {"entities": [], "error": str(e)[:100], "entity_type": entity_type}


class DealflowPipeline:
    EXTRACTION_ORDER = ["technologies", "papers", "companies", "people"]
    
    def __init__(self, api_key: str):
        self.crawler = WebCrawler()
        self.extractor = EntityExtractor(api_key)
    
    def process_center(self, centro: Dict, tematicas: List, max_pages: int = 3) -> Dict:
        results = {"centro": centro["nombre"], "region": centro.get("region", ""), "tipo": centro.get("tipo", ""),
                   "urls_analizadas": [], "entities": defaultdict(list), "page_types_found": []}
        for url in centro["urls"][:max_pages]:
            url_norm = normalize_url(url)
            cache_key = url_hash(url_norm)
            cached = get_cached_data("page_analysis", cache_key)
            if cached and isinstance(cached, dict):
                entities_found = sum(len(cached.get(et, {}).get("entities", [])) for et in self.EXTRACTION_ORDER 
                                   if isinstance(cached.get(et), dict))
                results["urls_analizadas"].append({"url": url_norm, "status": "cached", "entities_found": entities_found})
                for et in self.EXTRACTION_ORDER:
                    if isinstance(cached.get(et), dict) and "entities" in cached[et]:
                        results["entities"][et].extend(cached[et]["entities"])
                if cached.get("page_type"): results["page_types_found"].append(cached["page_type"])
                continue
            page = self.crawler.fetch_page(url_norm)
            if not page["ok"]:
                results["urls_analizadas"].append({"url": url_norm, "status": f"error: {page['error']}"})
                continue
            page_type = page.get("page_type", "general")
            results["page_types_found"].append(page_type)
            context = {"centro": centro["nombre"], "region": centro.get("region"), "tematicas": tematicas, "page_type": page_type}
            for entity_type in self.EXTRACTION_ORDER:
                extracted = self.extractor.extract_entities(page["text"], entity_type, context)
                if isinstance(extracted, dict) and "entities" in extracted and isinstance(extracted["entities"], list):
                    results["entities"][entity_type].extend(extracted["entities"])
            cache_data = {et: {"entities": list(results["entities"][et])} for et in self.EXTRACTION_ORDER}
            cache_data["page_type"] = page_type
            save_cached_data("page_analysis", cache_key, cache_data)
            results["urls_analizadas"].append({"url": url_norm, "status": "processed", 
                                              "entities_found": sum(len(results["entities"][et]) for et in self.EXTRACTION_ORDER)})
        results["summary"] = f"{centro['nombre']}: {sum(len(results['entities'][et]) for et in self.EXTRACTION_ORDER)} oportunidades"
        return results


# ============================================================================
# HELPERS EXCEL
# ============================================================================
def load_excel_files(uploaded_files: List) -> tuple:
    centros_df, tematicas_df = None, None
    for uploaded_file in uploaded_files:
        try:
            xls = pd.ExcelFile(uploaded_file)
            sheets = xls.sheet_names
            if "ENLACES" in sheets: centros_df = pd.read_excel(xls, sheet_name="ENLACES")
            elif sheets: centros_df = pd.read_excel(xls, sheet_name=sheets[0])
            if "TEMÁTICAS" in sheets: tematicas_df = pd.read_excel(xls, sheet_name="TEMÁTICAS")
            elif len(sheets) > 1: tematicas_df = pd.read_excel(xls, sheet_name=sheets[1])
        except Exception as e:
            st.warning(f"⚠️ Error cargando {uploaded_file.name}: {e}")
    return centros_df, tematicas_df


def prepare_tematicas(df: pd.DataFrame) -> List[Dict]:
    if df is None or df.empty: return []
    return [{"vertical": str(r.get("Vertical", "")) if pd.notna(r.get("Vertical")) else "",
             "segmento": str(r.get("Segmento", "")) if pd.notna(r.get("Segmento")) else "",
             "definicion": str(r.get("Qué es (definición)", "")) if pd.notna(r.get("Qué es (definición)")) else "",
             "problema_no_resuelto": str(r.get("Problema no resuelto que ataca", "")) if pd.notna(r.get("Problema no resuelto que ataca")) else ""}
            for _, r in df.iterrows() if pd.notna(r.get("Segmento")) and len(str(r.get("Segmento", ""))) > 5]


def prepare_centros(df: pd.DataFrame) -> List[Dict]:
    if df is None or df.empty: return []
    centros = []
    for _, row in df.iterrows():
        nombre = str(row.get("NOMBRE", "")) if pd.notna(row.get("NOMBRE")) else ""
        if not nombre or nombre == "nan": continue
        urls = [normalize_url(str(row[col]).strip()) for col in df.columns 
                if str(col).upper().startswith("WEB") and pd.notna(row.get(col)) 
                and str(row[col]).strip().lower().startswith("http")]
        if urls:
            centros.append({"nombre": nombre, "region": str(row.get("REGIÓN", "")) if pd.notna(row.get("REGIÓN")) else "",
                           "tipo": str(row.get("TIPO DE CENTRO", "")) if pd.notna(row.get("TIPO DE CENTRO")) else "", "urls": urls})
    return centros


# ============================================================================
# UI COMPONENTS
# ============================================================================
def render_header():
    st.markdown(f"""<div class="main-header"><div style="display:flex;align-items:center;gap:0.75rem">
        <img src="{BRANDING['logo_url']}" class="logo-img" alt="DH"></div>
        <div><h1 class="logo-text">Double Helix</h1><p class="logo-subtitle">Dealflow Finder v3.0 🔍</p></div></div>""", unsafe_allow_html=True)


def render_entity_card(entity: Dict, entity_type: str):
    if not isinstance(entity, dict): return
    score = entity.get("score", 0)
    score_color = "#10B981" if score >= 80 else "#3B82F6" if score >= 65 else "#F59E0B"
    tags = ""
    if entity_type == "technologies": tags += '<span class="entity-tag">🔬 Tecnología</span>'
    elif entity_type == "papers": tags += '<span class="entity-tag">📄 Artículo</span>'
    elif entity_type == "companies": tags += '<span class="entity-tag">🏢 Empresa</span>'
    elif entity_type == "people": tags += '<span class="entity-tag">👤 Investigador</span>'
    nombre = entity.get("nombre") or entity.get("titulo") or "Sin nombre"
    desc = (entity.get("descripcion") or entity.get("relevancia_health") or "")[:200]
    st.markdown(f"""<div class="opportunity-card"><div style="display:flex;justify-content:space-between;gap:1rem">
        <div style="flex:1"><h4 style="margin:0 0 0.5rem;color:{BRANDING['secondary_color']}">{nombre}</h4>
        {tags}<p style="margin:0.5rem 0;color:#555;font-style:italic">{desc}{'...' if len(entity.get('descripcion') or '') > 200 else ''}</p>
        {f'<p style="margin:0.25rem 0;font-size:0.9rem;color:#666">🎯 {entity.get("aplicacion_health") or entity.get("problema_resuelto", "")}</p>' if entity.get("aplicacion_health") or entity.get("problema_resuelto") else ''}
        </div><div style="text-align:right;min-width:80px">
        <span class="match-score" style="background:linear-gradient(135deg,{score_color} 0%,{score_color}cc 100%)">{score}/100</span>
        {f'<br><a href="{entity["referencia"]}" target="_blank" style="font-size:0.8rem;color:{BRANDING["primary_color"]};text-decoration:none">🔗 Ver</a>' if entity.get("referencia") else ''}
        </div></div></div>""", unsafe_allow_html=True)


# ============================================================================
# MAIN APP
# ============================================================================
def main():
    # Session state
    for key in ["centros_df", "tematicas_df", "centros_list", "tematicas_list", "results", 
                "eu_updates", "openai_ok", "api_key", "last_eu_check"]:
        if key not in st.session_state: st.session_state[key] = None if key != "results" else {}
    
    with st.sidebar:
        st.markdown(f"""<div style="text-align:center;padding:1rem 0;border-bottom:1px solid #e0e0e0">
            <img src="{BRANDING['logo_url']}" style="height:40px;margin-bottom:0.5rem">
            <p style="margin:0;color:{BRANDING['primary_color']};font-weight:600">Dealflow Finder</p></div>""", unsafe_allow_html=True)
        st.markdown("### ⚙️ Configuración")
        st.markdown("#### 🤖 OpenAI API")
        api_secret = ""
        try: api_secret = st.secrets.get("OPENAI_API_KEY", "")
        except: pass
        if api_secret:
            st.session_state.api_key = api_secret
            st.success("✅ API key cargada")
        else:
            api_input = st.text_input("API Key OpenAI", type="password")
            if api_input: st.session_state.api_key = api_input
        if st.session_state.api_key:
            if st.button("🔍 Verificar OpenAI"):
                with st.spinner("Verificando..."):
                    try:
                        OpenAI(api_key=st.session_state.api_key).models.list()
                        st.session_state.openai_ok = True
                        st.success("✅ API key válida")
                    except Exception as e:
                        st.session_state.openai_ok = False
                        st.error(f"❌ {str(e)[:80]}")
        if st.session_state.openai_ok: st.success("🟢 OpenAI listo")
        else: st.warning("🟡 OpenAI no configurado")
        st.divider()
        st.markdown("#### 📁 Archivos Excel")
        uploaded = st.file_uploader("Sube archivos con centros y temáticas", type=["xlsx", "xls"], accept_multiple_files=True)
        if uploaded and st.button("🔄 Procesar archivos"):
            with st.spinner("Cargando..."):
                c_df, t_df = load_excel_files(uploaded)
                if c_df is not None:
                    st.session_state.centros_df = c_df
                    st.session_state.centros_list = prepare_centros(c_df)
                    st.success(f"✅ {len(st.session_state.centros_list)} centros cargados")
                else: st.error("❌ No se pudo cargar centros")
                if t_df is not None:
                    st.session_state.tematicas_df = t_df
                    st.session_state.tematicas_list = prepare_tematicas(t_df)
                    st.success(f"✅ {len(st.session_state.tematicas_list)} temáticas cargadas")
                else: st.warning("⚠️ No se cargaron temáticas")
        st.divider()
        st.markdown("#### 📊 Estado")
        st.write(f"🏢 Centros: {len(st.session_state.centros_list)}")
        st.write(f"🎯 Temáticas: {len(st.session_state.tematicas_list)}")
        st.write(f"✅ Resultados: {len(st.session_state.results)}")
        if st.button("🗑️ Limpiar caché"):
            for f in CACHE_DIR.glob("*.json"): f.unlink()
            st.session_state.results = {}
            st.success("✅ Caché limpiada")
            st.rerun()
    
    render_header()
    st.markdown("Identifica **oportunidades de inversión en healthtech** analizando centros tecnológicos y universidades.")
    
    if not st.session_state.openai_ok:
        st.warning("⚠️ Configura tu API Key de OpenAI en la sidebar para comenzar")
        return
    if not st.session_state.centros_list:
        st.info("👉 Sube un archivo Excel con centros y temáticas para comenzar")
        return
    
    tab1, tab2, tab3, tab4 = st.tabs(["🔍 Analizar", "📋 Resultados", "🇪🇺 Europa", "📊 Exportar"])
    
    with tab1:
        st.markdown('<p class="section-title">🔍 Selecciona centros para analizar</p>', unsafe_allow_html=True)
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            regiones = ["Todas"] + list(set(c["region"] for c in st.session_state.centros_list if c["region"]))
            region_filter = st.selectbox("Región", regiones)
        with col_f2:
            tipos = ["Todos"] + list(set(c["tipo"] for c in st.session_state.centros_list if c["tipo"]))
            tipo_filter = st.selectbox("Tipo", tipos)
        with col_f3:
            page_types = ["Todos", "company_directory", "technology_transfer", "research_publications", "project_listing"]
            page_filter = st.selectbox("Tipo página", page_types)
        
        centros_filtered = st.session_state.centros_list
        if region_filter != "Todas": centros_filtered = [c for c in centros_filtered if c["region"] == region_filter]
        if tipo_filter != "Todos": centros_filtered = [c for c in centros_filtered if c["tipo"] == tipo_filter]
        st.caption(f"{len(centros_filtered)} centros disponibles")
        
        centro_opts = {f"{c['nombre']} ({c['region']})": c for c in centros_filtered}
        selected = st.multiselect("Selecciona centros", options=list(centro_opts.keys()), default=list(centro_opts.keys())[:3])
        
        with st.expander("⚙️ Configuración", expanded=False):
            max_pages = st.slider("Máx. páginas por centro", 1, 5, 3)
            min_score = st.slider("Score mínimo", 50, 90, 60)
            st.info(f"💡 Temáticas: {len(st.session_state.tematicas_list)}")
        
        if st.button("🚀 Iniciar análisis", type="primary", use_container_width=True):
            if not selected: st.warning("⚠️ Selecciona al menos un centro")
            else:
                pipeline = DealflowPipeline(api_key=st.session_state.api_key)
                progress = st.progress(0)
                status = st.empty()
                for idx, key in enumerate(selected):
                    centro = centro_opts[key]
                    status.text(f"🔄 Analizando {centro['nombre']}...")
                    result = pipeline.process_center(centro, st.session_state.tematicas_list, max_pages)
                    for et in pipeline.EXTRACTION_ORDER:
                        result["entities"][et] = [e for e in result["entities"][et] 
                                                 if isinstance(e, dict) and e.get("score", 0) >= min_score]
                    st.session_state.results[centro["nombre"]] = result
                    progress.progress((idx + 1) / len(selected))
                    time.sleep(0.5)
                status.text("✅ Análisis completado")
                st.balloons()
                st.rerun()
    
    with tab2:
        st.markdown('<p class="section-title">📋 Oportunidades identificadas</p>', unsafe_allow_html=True)
        if not st.session_state.results:
            st.info("👉 Ejecuta un análisis en 'Analizar' para ver resultados")
        else:
            total = sum(sum(len(r["entities"].get(et, [])) for et in ["technologies", "papers", "companies", "people"]) 
                       for r in st.session_state.results.values())
            st.metric("🎯 Total oportunidades", total)
            
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                entity_filter = st.multiselect("Tipo entidad", ["technologies", "papers", "companies", "people"], 
                                              default=["technologies", "companies"])
            with col_f2:
                vertical_opts = list(set(e.get("vertical") or e.get("sector") 
                    for r in st.session_state.results.values() for et in ["technologies", "papers", "companies", "people"] 
                    for e in r["entities"].get(et, []) if isinstance(e, dict) and (e.get("vertical") or e.get("sector"))))
                vertical_filter = st.multiselect("Vertical", vertical_opts)
            with col_f3:
                score_min = st.slider("Score mínimo", 60, 100, 60)
            
            for centro_nombre, centro_data in st.session_state.results.items():
                total_opp = sum(len(centro_data["entities"].get(et, [])) for et in entity_filter)
                if total_opp == 0: continue
                with st.expander(f"🏢 {centro_nombre} - {total_opp} oportunidades", expanded=True):
                    for entity_type in entity_filter:
                        entities = centro_data["entities"].get(entity_type, [])
                        if not entities: continue
                        label = {"technologies": "🔬 Tecnologías", "papers": "📄 Artículos", 
                                "companies": "🏢 Empresas", "people": "👤 Personas"}
                        st.markdown(f"**{label.get(entity_type, entity_type)}** ({len(entities)})")
                        for entity in entities:
                            if not isinstance(entity, dict) or entity.get("score", 0) < score_min: continue
                            if vertical_filter and (entity.get("vertical") or entity.get("sector")) not in vertical_filter: continue
                            render_entity_card(entity, entity_type)
                        st.divider()
    
    with tab3:
        st.markdown('<p class="section-title">🇪🇺 Monitoreo Europeo</p>', unsafe_allow_html=True)
        st.info("**Portales:** CORDIS, EU-Funding, EIC | **Temas:** health, biotech, medical, pharma")
        if not st.session_state.openai_ok:
            st.warning("⚠️ Configura OpenAI para activar monitoreo")
        else:
            if st.button("🔄 Consultar actualizaciones", use_container_width=True):
                with st.spinner("Consultando..."):
                    # Simulación - en producción usar API real de CORDIS
                    updates = {"new_opportunities": [{"title": f"HealthTech Project Demo", "cordis_id": "DEMO-123", 
                                                     "topics": ["digital health"], "relevance_score": 75, "url": "https://cordis.europa.eu"}]}
                    st.session_state.eu_updates = updates
                    st.session_state.last_eu_check = datetime.now()
                    st.rerun()
            if st.session_state.eu_updates:
                for opp in st.session_state.eu_updates.get("new_opportunities", [])[:5]:
                    st.markdown(f"#### {opp.get('title', 'Proyecto')}")
                    st.caption(f"🆔 {opp.get('cordis_id', '')} | 💰 {opp.get('budget', 'N/A')}")
                    st.markdown(f"**Temas:** {', '.join(opp.get('topics', []))}")
                    if opp.get("url"): st.markdown(f"[🔗 Ver]({opp['url']})")
                    st.divider()
            else:
                st.info("👉 Pulsa 'Consultar actualizaciones' para buscar oportunidades")
    
    with tab4:
        st.markdown('<p class="section-title">📊 Exportar resultados</p>', unsafe_allow_html=True)
        if not st.session_state.results:
            st.info("👉 Ejecuta un análisis primero para exportar")
        else:
            rows = []
            for centro_nombre, centro_data in st.session_state.results.items():
                for entity_type in ["technologies", "papers", "companies", "people"]:
                    for entity in centro_data["entities"].get(entity_type, []):
                        if not isinstance(entity, dict): continue
                        rows.append({
                            "Centro": centro_nombre, "Región": centro_data.get("region", ""), 
                            "Tipo Centro": centro_data.get("tipo", ""), "Tipo Entidad": entity_type,
                            "Nombre": entity.get("nombre") or entity.get("titulo"),
                            "Vertical": entity.get("vertical") or entity.get("sector"),
                            "Descripción": entity.get("descripcion") or entity.get("relevancia_health"),
                            "Score": entity.get("score", 0), "Referencia": entity.get("referencia", ""),
                            "ORCID": entity.get("orcid", ""), "Notas": entity.get("notas", "")
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
                        # ✅ CORRECCIÓN: manejo robusto de NaN y tipos mixtos
                        for i, col in enumerate(df_export.columns):
                            max_len = max(df_export[col].fillna('').astype(str).str.len().max(), len(str(col)))
                            worksheet.set_column(i, i, min(max_len + 2, 50))
                    buffer.seek(0)
                    st.download_button("📥 Descargar Excel", data=buffer, 
                                      file_name=f"double_helix_dealflow_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                      mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                with col_dl2:
                    csv = df_export.to_csv(index=False, encoding="utf-8-sig")
                    st.download_button("📥 Descargar CSV", data=csv,
                                      file_name=f"double_helix_dealflow_{datetime.now().strftime('%Y%m%d')}.csv",
                                      mime="text/csv")
                
                st.markdown("#### 📈 Resumen")
                col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                col_s1.metric("Total", len(df_export))
                col_s2.metric("Score promedio", f"{df_export['Score'].mean():.1f}")
                col_s3.metric("Centros", df_export["Centro"].nunique())
                col_s4.metric("Con ORCID", df_export["ORCID"].notna().sum())
            else:
                st.warning("⚠️ No hay oportunidades para exportar")
    
    # Footer
    st.markdown(f"""<div class="footer"><img src="{BRANDING['logo_url']}" style="height:30px;opacity:0.7">
        <p>Double Helix Dealflow Finder v3.0 © {datetime.now().year} | Healthtech VC</p>
        <p style="font-size:0.75rem;color:#999">Extracción: Tecnologías → Artículos → Empresas → Personas</p></div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
