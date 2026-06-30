"""
Double Helix Dealflow Finder
Aplicación Streamlit para identificar oportunidades de inversión en healthtech
basado en análisis de centros tecnológicos, universidades y temáticas objetivo
"""

import os
import re
import json
import time
import requests
from io import BytesIO
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse

import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
from openai import OpenAI

# ============================================================================
# CONFIGURACIÓN DE BRANDING
# ============================================================================
BRANDING = {
    "logo_url": "https://doublehelix.vc/wp-content/uploads/2023/03/cropped-DH-Logo-1.png",
    "primary_color": "#00A6A6",      # Teal Double Helix
    "secondary_color": "#1A1A2E",     # Dark navy
    "accent_color": "#16213E",        # Deep blue
    "text_light": "#FFFFFF",
    "text_dark": "#333333",
    "bg_light": "#F8F9FA",
    "bg_dark": "#0F172A",
}

CACHE_DIR = Path("dealflow_cache")
CACHE_DIR.mkdir(exist_ok=True)

st.set_page_config(
    page_title="🧬 Double Helix Dealflow Finder",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CSS PERSONALIZADO - ESTILO DOUBLE HELIX
# ============================================================================
st.markdown(f"""
<style>
    /* ===== VARIABLES DE TEMA ===== */
    :root {{
        --dh-primary: {BRANDING['primary_color']};
        --dh-secondary: {BRANDING['secondary_color']};
        --dh-accent: {BRANDING['accent_color']};
        --dh-text-light: {BRANDING['text_light']};
        --dh-text-dark: {BRANDING['text_dark']};
        --dh-bg-light: {BRANDING['bg_light']};
        --dh-bg-dark: {BRANDING['bg_dark']};
    }}
    
    /* ===== HEADER & LOGO ===== */
    .main-header {{
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 1rem 0;
        border-bottom: 2px solid var(--dh-primary);
        margin-bottom: 2rem;
    }}
    
    .logo-container {{
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }}
    
    .logo-img {{
        height: 50px;
        width: auto;
        object-fit: contain;
    }}
    
    .logo-text {{
        font-size: 1.5rem;
        font-weight: 700;
        color: var(--dh-secondary);
        margin: 0;
    }}
    
    .logo-subtitle {{
        font-size: 0.9rem;
        color: var(--dh-primary);
        margin: 0;
        font-weight: 500;
    }}
    
    /* ===== BOTONES ===== */
    .stButton>button {{
        background: linear-gradient(135deg, var(--dh-secondary) 0%, var(--dh-accent) 100%);
        color: white !important;
        border: 2px solid var(--dh-primary);
        border-radius: 8px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }}
    
    .stButton>button:hover {{
        background: linear-gradient(135deg, var(--dh-accent) 0%, var(--dh-secondary) 100%);
        border-color: var(--dh-primary);
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 166, 166, 0.3);
    }}
    
    .stButton>button:active {{
        transform: translateY(0);
    }}
    
    /* ===== TARJETAS DE OPORTUNIDAD ===== */
    .opportunity-card {{
        padding: 1.25rem;
        border: 1px solid #e0e0e0;
        border-left: 4px solid var(--dh-primary);
        border-radius: 12px;
        margin: 0.75rem 0;
        background: white;
        transition: all 0.3s ease;
    }}
    
    .opportunity-card:hover {{
        border-color: var(--dh-primary);
        box-shadow: 0 4px 20px rgba(0, 166, 166, 0.15);
        transform: translateX(4px);
    }}
    
    /* ===== BADGES & TAGS ===== */
    .match-score {{
        background: linear-gradient(135deg, var(--dh-primary) 0%, #008B8B 100%);
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.9rem;
        display: inline-block;
        box-shadow: 0 2px 8px rgba(0, 166, 166, 0.3);
    }}
    
    .vertical-tag {{
        background: var(--dh-secondary);
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 500;
        display: inline-block;
        margin-right: 0.4rem;
    }}
    
    .type-tag {{
        background: #E8F4F4;
        color: var(--dh-secondary);
        padding: 0.15rem 0.5rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
        margin-right: 0.3rem;
        border: 1px solid var(--dh-primary);
    }}
    
    /* ===== SIDEBAR ===== */
    .sidebar-header {{
        text-align: center;
        padding: 1rem 0;
        border-bottom: 1px solid #e0e0e0;
        margin-bottom: 1rem;
    }}
    
    .sidebar-logo {{
        height: 40px;
        margin-bottom: 0.5rem;
    }}
    
    /* ===== EXPANDERS ===== */
    .streamlit-expanderHeader {{
        background: linear-gradient(90deg, var(--dh-bg-light) 0%, white 100%);
        border-left: 3px solid var(--dh-primary);
        border-radius: 8px !important;
    }}
    
    .streamlit-expanderHeader:hover {{
        background: linear-gradient(90deg, #E8F4F4 0%, #F0F9F9 100%);
    }}
    
    /* ===== MÉTRICAS ===== */
    .stMetric {{
        background: white;
        padding: 0.75rem;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        border-left: 3px solid var(--dh-primary);
    }}
    
    .stMetricLabel {{
        color: var(--dh-secondary) !important;
        font-weight: 600;
    }}
    
    .stMetricValue {{
        color: var(--dh-primary) !important;
        font-weight: 700;
    }}
    
    /* ===== TABS ===== */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0.5rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid var(--dh-primary);
    }}
    
    .stTabs [data-baseweb="tab"] {{
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        color: var(--dh-secondary);
        border-radius: 8px 8px 0 0;
        transition: all 0.2s ease;
    }}
    
    .stTabs [aria-selected="true"] {{
        background: var(--dh-primary);
        color: white !important;
    }}
    
    /* ===== ALERTAS & MENSAJES ===== */
    .stSuccess {{
        background: #E8F4F4 !important;
        border-left: 4px solid var(--dh-primary) !important;
        color: var(--dh-secondary) !important;
    }}
    
    .stWarning {{
        background: #FFF4E5 !important;
        border-left: 4px solid #FF9800 !important;
    }}
    
    .stError {{
        background: #FEE2E2 !important;
        border-left: 4px solid #EF4444 !important;
    }}
    
    /* ===== PROGRESS BAR ===== */
    .stProgress > div > div > div > div {{
        background: linear-gradient(90deg, var(--dh-primary), #008B8B);
    }}
    
    /* ===== FOOTER ===== */
    .footer {{
        text-align: center;
        padding: 2rem 0 1rem;
        color: #666;
        font-size: 0.85rem;
        border-top: 1px solid #e0e0e0;
        margin-top: 3rem;
    }}
    
    .footer-logo {{
        height: 30px;
        opacity: 0.7;
        margin-bottom: 0.5rem;
    }}
    
    /* ===== UTILS ===== */
    .big-header {{
        font-size: 2rem;
        font-weight: 700;
        color: var(--dh-secondary);
        margin-bottom: 0.5rem;
    }}
    
    .section-title {{
        font-size: 1.4rem;
        font-weight: 600;
        color: var(--dh-secondary);
        margin: 1.5rem 0 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid var(--dh-primary);
    }}
    
    .info-box {{
        background: linear-gradient(135deg, #E8F4F4 0%, #F0F9F9 100%);
        border-left: 4px solid var(--dh-primary);
        padding: 1rem;
        border-radius: 0 8px 8px 0;
        margin: 1rem 0;
    }}
    
    /* ===== RESPONSIVE ===== */
    @media (max-width: 768px) {{
        .main-header {{
            flex-direction: column;
            text-align: center;
        }}
        .logo-img {{
            height: 40px;
        }}
    }}
</style>
""", unsafe_allow_html=True)


# ============================================================================
# COMPONENTES DE UI REUTILIZABLES
# ============================================================================
def render_header():
    """Renderiza el header con logo y branding de Double Helix."""
    st.markdown(f"""
    <div class="main-header">
        <div class="logo-container">
            <img src="{BRANDING['logo_url']}" class="logo-img" alt="Double Helix">
        </div>
        <div>
            <h1 class="logo-text">Double Helix</h1>
            <p class="logo-subtitle">Dealflow Finder 🔬</p>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_sidebar_header():
    """Renderiza el header de la sidebar."""
    st.markdown(f"""
    <div class="sidebar-header">
        <img src="{BRANDING['logo_url']}" class="sidebar-logo" alt="DH">
        <p style="margin: 0; color: {BRANDING['primary_color']}; font-weight: 600;">Dealflow Finder</p>
    </div>
    """, unsafe_allow_html=True)


def render_opportunity_card(opp: dict):
    """Renderiza una tarjeta de oportunidad con styling DH."""
    score = opp.get("score", 0)
    score_color = "#00A6A6" if score >= 80 else "#FF9800" if score >= 65 else "#EF4444"
    
    tags_html = ""
    if opp.get("vertical"):
        tags_html += f'<span class="vertical-tag">{opp["vertical"]}</span>'
    if opp.get("tipo"):
        tags_html += f'<span class="type-tag">{opp["tipo"].upper()}</span>'
    
    st.markdown(f"""
    <div class="opportunity-card">
        <div style="display: flex; justify-content: space-between; align-items: start; gap: 1rem;">
            <div style="flex: 1;">
                <h4 style="margin: 0 0 0.5rem 0; color: {BRANDING['secondary_color']};">
                    {opp.get('nombre', 'Sin nombre')}
                </h4>
                {tags_html}
                <p style="margin: 0.5rem 0; color: #555; font-style: italic;">
                    {opp.get('descripcion', '')}
                </p>
                {f'<p style="margin: 0.25rem 0; font-size: 0.9rem; color: #666;">🎯 {opp.get("problema_resuelto", "")}</p>' if opp.get('problema_resuelto') else ''}
            </div>
            <div style="text-align: right; min-width: 80px;">
                <span class="match-score" style="background: linear-gradient(135deg, {score_color} 0%, {score_color}cc 100%);">
                    {score}/100
                </span>
                {f'<br><a href="{opp["referencia"]}" target="_blank" style="font-size: 0.8rem; color: {BRANDING["primary_color"]}; text-decoration: none;">🔗 Ver</a>' if opp.get('referencia') else ''}
            </div>
        </div>
        {f'''
        <details style="margin-top: 0.75rem; font-size: 0.9rem;">
            <summary style="cursor: pointer; color: {BRANDING['primary_color']}; font-weight: 500;">
                🔗 Por qué coincide con nuestras temáticas
            </summary>
            <p style="margin: 0.5rem 0 0; color: #555; padding-left: 0.5rem;">
                {opp.get('matching_rationale', '')}
            </p>
        </details>
        ''' if opp.get('matching_rationale') else ''}
    </div>
    """, unsafe_allow_html=True)


# ============================================================================
# CLASE: WEB SCRAPER
# ============================================================================
class WebScraper:
    """Scraper básico para extraer contenido de webs."""
    
    def __init__(self, user_agent: str = None):
        self.user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})
    
    def fetch_page(self, url: str, timeout: int = 30) -> dict:
        """Extrae contenido de una URL."""
        try:
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            
            parsed = urlparse(url)
            if not parsed.netloc:
                return {"ok": False, "error": "URL inválida"}
            
            resp = self.session.get(url, timeout=timeout)
            
            if resp.status_code == 200:
                resp.encoding = resp.apparent_encoding
                return {
                    "ok": True,
                    "url": resp.url,
                    "html": resp.text,
                    "title": self._extract_title(resp.text),
                    "meta_desc": self._extract_meta(resp.text, "description"),
                }
            else:
                return {"ok": False, "error": f"HTTP {resp.status_code}", "url": url}
                
        except requests.Timeout:
            return {"ok": False, "error": "Timeout", "url": url}
        except requests.RequestException as e:
            return {"ok": False, "error": str(e)[:100], "url": url}
    
    def _extract_title(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title
        if title and title.string:
            return title.string.strip()
        return ""
    
    def _extract_meta(self, html: str, name: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        meta = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": f"og:{name}"})
        if meta and meta.get("content"):
            return meta["content"].strip()
        return ""
    
    def extract_links(self, html: str, base_url: str) -> list:
        soup = BeautifulSoup(html, "html.parser")
        links = []
        
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith(("#", "javascript:", "mailto:")):
                continue
            full_url = urljoin(base_url, href)
            if urlparse(full_url).netloc == urlparse(base_url).netloc:
                links.append({"url": full_url, "text": a.get_text().strip()[:100]})
        
        return links[:20]


# ============================================================================
# CLASE: DEALFLOW ANALYZER (OpenAI)
# ============================================================================
class DealflowAnalyzer:
    """Analiza contenido web buscando oportunidades de inversión."""
    
    SYSTEM_PROMPT = """Eres un analista experto en healthtech para Double Helix, un fondo de venture capital.
Tu objetivo es identificar oportunidades de inversión (empresas, proyectos, tecnologías) en centros de investigación, universidades y hubs tecnológicos.

TEMÁTICAS OBJETIVO:
{tematicas}

INSTRUCCIONES:
1. Analiza el contenido proporcionado de un centro tecnológico/universidad
2. Identifica empresas, proyectos, tecnologías o iniciativas que coincidan con las temáticas objetivo
3. Para cada oportunidad encontrada, proporciona:
   - Nombre de la empresa/proyecto/tecnología
   - Vertical/segmento al que pertenece
   - Descripción breve de qué hace y qué problema resuelve
   - Por qué es relevante para las temáticas objetivo (matching rationale)
   - Score de relevancia (0-100) basado en:
     * Alineación con definición del segmento (40%)
     * Claridad del problema que resuelve (30%)
     * Potencial de inversión/escalabilidad (30%)
   - Enlace o referencia donde se encontró
   - Tipo: "empresa", "proyecto", "tecnología", "spin-off", "startup"

4. Sé conservador: solo incluye oportunidades con score >= 60
5. Ignora contenido genérico, publicaciones académicas sin aplicación comercial, o proyectos muy tempranos sin validación

FORMATO DE RESPUESTA (JSON estricto):
{{
  "oportunidades": [
    {{
      "nombre": "...",
      "vertical": "...",
      "segmento": "...",
      "descripcion": "...",
      "problema_resuelto": "...",
      "matching_rationale": "...",
      "score": 75,
      "tipo": "empresa|proyecto|tecnología|spin-off|startup",
      "referencia": "URL o sección donde se encontró",
      "notas": "Observaciones adicionales (opcional)"
    }}
  ],
  "resumen_centro": "Breve descripción del centro y su foco en healthtech",
  "total_oportunidades": <número>
}}

Si no hay oportunidades relevantes (score >= 60), devuelve:
{{
  "oportunidades": [],
  "resumen_centro": "...",
  "total_oportunidades": 0,
  "razon": "Explicación breve de por qué no se encontraron oportunidades"
}}
"""

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
    
    def analizar_centro(self, nombre_centro: str, contenido: str, tematicas: list, 
                       url_origen: str = "", max_tokens: int = 4000) -> dict:
        """Analiza el contenido de un centro buscando oportunidades."""
        
        tematicas_text = "\n".join([
            f"- {t.get('segmento', '')}: {t.get('definicion', '')[:200]} (Problema: {t.get('problema_no_resuelto', '')[:150]})"
            for t in tematicas[:10]
        ])
        
        contenido_limpio = self._clean_content(contenido)
        contenido_truncado = contenido_limpio[:max_tokens]
        
        prompt = f"""CENTRO: {nombre_centro}
URL: {url_origen}

CONTENIDO ANALIZADO:
---
{contenido_truncado}
---

TEMÁTICAS OBJETIVO:
{tematicas_text}

Identifica oportunidades de inversión para Double Helix."""

        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT.format(tematicas=tematicas_text)},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            return {
                "oportunidades": [],
                "resumen_centro": f"Error en análisis: {str(e)[:100]}",
                "total_oportunidades": 0
            }
    
    def _clean_content(self, content: str) -> str:
        soup = BeautifulSoup(content, "html.parser")
        for elem in soup(["script", "style", "nav", "footer", "header"]):
            elem.decompose()
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        return text.strip()


# ============================================================================
# HELPERS
# ============================================================================
def load_excel_files(uploaded_files: list) -> tuple:
    """Carga y procesa los archivos Excel."""
    centros_df = None
    tematicas_df = None
    
    for uploaded_file in uploaded_files:
        try:
            xls = pd.ExcelFile(uploaded_file)
            sheet_names = xls.sheet_names
            
            if "ENLACES" in sheet_names or "Sheet1" in sheet_names:
                centros_sheet = "ENLACES" if "ENLACES" in sheet_names else sheet_names[0]
                centros_df = pd.read_excel(xls, sheet_name=centros_sheet)
            
            if "TEMÁTICAS" in sheet_names:
                tematicas_df = pd.read_excel(xls, sheet_name="TEMÁTICAS")
            elif len(sheet_names) > 1:
                tematicas_df = pd.read_excel(xls, sheet_name=sheet_names[1])
                
        except Exception as e:
            st.warning(f"⚠️ Error cargando {uploaded_file.name}: {e}")
    
    return centros_df, tematicas_df


def prepare_tematicas(tematicas_df: pd.DataFrame) -> list:
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


def prepare_centros(centros_df: pd.DataFrame) -> list:
    """Prepara la lista de centros para procesar."""
    if centros_df is None or centros_df.empty:
        return []
    
    centros = []
    for _, row in centros_df.iterrows():
        nombre = str(row.get("NOMBRE", ""))
        if not nombre or nombre == "nan":
            continue
        
        urls = []
        for col in centros_df.columns:
            if str(col).upper().startswith("WEB") and pd.notna(row.get(col)):
                url = str(row.get(col)).strip()
                if url and url.startswith("http"):
                    urls.append(url)
        
        if urls:
            centros.append({
                "nombre": nombre,
                "region": str(row.get("REGIÓN", "")),
                "tipo": str(row.get("TIPO DE CENTRO", "")),
                "urls": urls,
            })
    
    return centros


def cache_key(centro_nombre: str, url: str) -> str:
    return f"{centro_nombre}_{url}".replace(" ", "_").replace("/", "_").replace(":", "_")


def get_cached_analysis(centro_nombre: str, url: str) -> dict:
    cache_file = CACHE_DIR / f"{cache_key(centro_nombre, url)}.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return None
    return None


def save_cached_analysis(centro_nombre: str, url: str, result: dict):
    cache_file = CACHE_DIR / f"{cache_key(centro_nombre, url)}.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


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
    if "openai_ok" not in st.session_state:
        st.session_state.openai_ok = False
    if "api_key" not in st.session_state:
        st.session_state.api_key = None

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
                        st.success(f"✅ {len(st.session_state.centros_list)} centros")
                    else:
                        st.error("❌ No se cargó la hoja de centros")
                    
                    if tematicas_df is not None:
                        st.session_state.tematicas_df = tematicas_df
                        st.session_state.tematicas_list = prepare_tematicas(tematicas_df)
                        st.success(f"✅ {len(st.session_state.tematicas_list)} temáticas")
                    else:
                        st.warning("⚠️ No se cargaron temáticas")
        
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
            st.success("✅ Caché limpiada")
            st.rerun()

    # ========================================================================
    # MAIN
    # ========================================================================
    render_header()
    
    st.markdown("""
    Identifica **oportunidades de inversión en healthtech** analizando centros tecnológicos, 
    universidades y hubs de innovación en España.
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
    tab1, tab2, tab3 = st.tabs(["🔍 Analizar Centros", "📋 Resultados", "📊 Exportar"])
    
    # ------------------------------------------------------------------------
    # TAB 1: Analizar Centros
    # ------------------------------------------------------------------------
    with tab1:
        st.markdown('<p class="section-title">🔍 Selecciona centros para analizar</p>', unsafe_allow_html=True)
        
        # Filtros
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            regiones = ["Todas"] + list(set(c["region"] for c in st.session_state.centros_list if c["region"]))
            region_filter = st.selectbox("Región", regiones)
        
        with col_f2:
            tipos = ["Todos"] + list(set(c["tipo"] for c in st.session_state.centros_list if c["tipo"]))
            tipo_filter = st.selectbox("Tipo de centro", tipos)
        
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
        with st.expander("⚙️ Configuración del análisis", expanded=False):
            max_pages = st.slider("Máx. páginas por centro", 1, 5, 2)
            timeout = st.slider("Timeout por página (segundos)", 10, 60, 30)
            min_score = st.slider("Score mínimo para incluir oportunidad", 50, 90, 60)
            st.info(f"💡 Temáticas activas: {len(st.session_state.tematicas_list)}")
        
        # Botón de análisis
        if st.button("🚀 Iniciar análisis", type="primary", use_container_width=True):
            if not selected_centros:
                st.warning("⚠️ Selecciona al menos un centro")
            else:
                scraper = WebScraper()
                analyzer = DealflowAnalyzer(api_key=st.session_state.api_key)
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for idx, centro_key in enumerate(selected_centros):
                    centro = centro_options[centro_key]
                    status_text.text(f"🔄 Analizando {centro['nombre']}...")
                    
                    centro_results = []
                    
                    for url_idx, url in enumerate(centro["urls"][:max_pages]):
                        cached = get_cached_analysis(centro["nombre"], url)
                        if cached:
                            centro_results.append(cached)
                            continue
                        
                        status_text.text(f"🌐 Descargando {url[:50]}...")
                        page = scraper.fetch_page(url, timeout=timeout)
                        
                        if not page["ok"]:
                            st.warning(f"⚠️ No se pudo acceder a {url}: {page['error']}")
                            continue
                        
                        status_text.text(f"🧠 Analizando contenido...")
                        result = analyzer.analizar_centro(
                            nombre_centro=centro["nombre"],
                            contenido=page["html"],
                            tematicas=st.session_state.tematicas_list,
                            url_origen=url
                        )
                        
                        result["centro"] = centro["nombre"]
                        result["region"] = centro["region"]
                        result["url_analizada"] = url
                        result["page_title"] = page["title"]
                        
                        if "oportunidades" in result:
                            result["oportunidades"] = [
                                o for o in result["oportunidades"] 
                                if o.get("score", 0) >= min_score
                            ]
                            result["total_oportunidades"] = len(result["oportunidades"])
                        
                        save_cached_analysis(centro["nombre"], url, result)
                        centro_results.append(result)
                        time.sleep(1)
                    
                    st.session_state.results[centro["nombre"]] = {
                        "centro": centro,
                        "analisis": centro_results,
                        "total_oportunidades": sum(r.get("total_oportunidades", 0) for r in centro_results)
                    }
                    
                    progress_bar.progress((idx + 1) / len(selected_centros))
                
                status_text.text("✅ Análisis completado")
                st.balloons()
                st.rerun()
    
    # ------------------------------------------------------------------------
    # TAB 2: Resultados
    # ------------------------------------------------------------------------
    with tab2:
        st.markdown('<p class="section-title">📋 Oportunidades identificadas</p>', unsafe_allow_html=True)
        
        if not st.session_state.results:
            st.info("👉 Ejecuta un análisis en 'Analizar Centros' para ver resultados")
        else:
            total_opp = sum(r["total_oportunidades"] for r in st.session_state.results.values())
            st.metric("🎯 Total oportunidades", total_opp)
            
            # Filtros
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                vertical_filter = st.multiselect(
                    "Vertical",
                    options=list(set(
                        o.get("vertical", "Sin vertical")
                        for r in st.session_state.results.values()
                        for a in r["analisis"]
                        for o in a.get("oportunidades", [])
                    ))
                )
            with col_f2:
                tipo_filter = st.multiselect(
                    "Tipo",
                    options=list(set(
                        o.get("tipo", "Sin tipo")
                        for r in st.session_state.results.values()
                        for a in r["analisis"]
                        for o in a.get("oportunidades", [])
                    ))
                )
            with col_f3:
                score_min = st.slider("Score mínimo", 60, 100, 60)
            
            # Resultados por centro
            for centro_nombre, centro_data in st.session_state.results.items():
                centro = centro_data["centro"]
                analisis_list = centro_data["analisis"]
                total_opp_centro = centro_data["total_oportunidades"]
                
                if total_opp_centro == 0:
                    continue
                
                with st.expander(f"🏢 {centro_nombre} ({centro['region']}) - {total_opp_centro} oportunidades", expanded=True):
                    st.caption(f"📍 {centro['tipo']} | 🔗 {centro['urls'][0] if centro['urls'] else 'N/A'}")
                    
                    for analysis in analisis_list:
                        if not analysis.get("oportunidades"):
                            continue
                        
                        st.markdown(f"**🌐 Página:** [{analysis.get('page_title', analysis.get('url_analizada', 'N/A'))[:60]}]({analysis.get('url_analizada', '#')})")
                        
                        for opp in analysis["oportunidades"]:
                            if vertical_filter and opp.get("vertical") not in vertical_filter:
                                continue
                            if tipo_filter and opp.get("tipo") not in tipo_filter:
                                continue
                            if opp.get("score", 0) < score_min:
                                continue
                            
                            render_opportunity_card(opp)
    
    # ------------------------------------------------------------------------
    # TAB 3: Exportar
    # ------------------------------------------------------------------------
    with tab3:
        st.markdown('<p class="section-title">📊 Exportar resultados</p>', unsafe_allow_html=True)
        
        if not st.session_state.results:
            st.info("👉 Ejecuta un análisis primero para poder exportar")
        else:
            rows = []
            for centro_nombre, centro_data in st.session_state.results.items():
                centro = centro_data["centro"]
                for analysis in centro_data["analisis"]:
                    for opp in analysis.get("oportunidades", []):
                        rows.append({
                            "Centro": centro_nombre,
                            "Región": centro.get("region", ""),
                            "Tipo Centro": centro.get("tipo", ""),
                            "URL Analizada": analysis.get("url_analizada", ""),
                            "Página Título": analysis.get("page_title", ""),
                            "Oportunidad": opp.get("nombre", ""),
                            "Vertical": opp.get("vertical", ""),
                            "Segmento": opp.get("segmento", ""),
                            "Tipo": opp.get("tipo", ""),
                            "Descripción": opp.get("descripcion", ""),
                            "Problema Resuelto": opp.get("problema_resuelto", ""),
                            "Matching Rationale": opp.get("matching_rationale", ""),
                            "Score": opp.get("score", 0),
                            "Referencia": opp.get("referencia", ""),
                            "Notas": opp.get("notas", ""),
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
                            max_len = max(df_export[col].astype(str).map(len).max(), len(col))
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
                col_s4.metric("Verticales", df_export["Vertical"].nunique())
                
                if not df_export["Vertical"].empty:
                    st.markdown("#### Distribución por vertical")
                    vertical_counts = df_export["Vertical"].value_counts()
                    st.bar_chart(vertical_counts)
            else:
                st.warning("⚠️ No hay oportunidades para exportar. Ajusta filtros o ejecuta nuevo análisis.")
    
    # ========================================================================
    # FOOTER
    # ========================================================================
    st.markdown(f"""
    <div class="footer">
        <img src="{BRANDING['logo_url']}" class="footer-logo" alt="Double Helix">
        <p>Double Helix Dealflow Finder © {datetime.now().year} | Healthtech Venture Capital</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
