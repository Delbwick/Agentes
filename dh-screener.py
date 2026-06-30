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
# CONFIGURACIÓN
# ============================================================================
CACHE_DIR = Path("dealflow_cache")
CACHE_DIR.mkdir(exist_ok=True)

st.set_page_config(
    page_title="🧬 Double Helix Dealflow Finder",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stButton>button { width: 100%; }
    .big-header { font-size: 2.2rem; font-weight: 700; margin-bottom: 0.5rem; }
    .opportunity-card {
        padding: 1rem;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        margin: 0.5rem 0;
        background: #fafafa;
    }
    .opportunity-card:hover {
        border-color: #0073b1;
        box-shadow: 0 2px 4px rgba(0,115,177,0.1);
    }
    .match-score {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-weight: bold;
        font-size: 0.85rem;
    }
    .vertical-tag {
        background: #28a745;
        color: white;
        padding: 0.15rem 0.5rem;
        border-radius: 8px;
        font-size: 0.8rem;
    }
</style>
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
            # Normalizar URL
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            
            parsed = urlparse(url)
            if not parsed.netloc:
                return {"ok": False, "error": "URL inválida"}
            
            resp = self.session.get(url, timeout=timeout)
            
            if resp.status_code == 200:
                # Detectar encoding
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
        """Extrae el título de la página."""
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title
        if title and title.string:
            return title.string.strip()
        return ""
    
    def _extract_meta(self, html: str, name: str) -> str:
        """Extrae meta tags."""
        soup = BeautifulSoup(html, "html.parser")
        meta = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": f"og:{name}"})
        if meta and meta.get("content"):
            return meta["content"].strip()
        return ""
    
    def extract_links(self, html: str, base_url: str) -> list:
        """Extrae enlaces internos de una página."""
        soup = BeautifulSoup(html, "html.parser")
        links = []
        
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Filtrar enlaces internos relevantes
            if href.startswith(("#", "javascript:", "mailto:")):
                continue
            
            # Normalizar URL
            full_url = urljoin(base_url, href)
            
            # Solo enlaces del mismo dominio
            if urlparse(full_url).netloc == urlparse(base_url).netloc:
                links.append({
                    "url": full_url,
                    "text": a.get_text().strip()[:100],
                })
        
        return links[:20]  # Limitar a 20 enlaces


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
        
        # Preparar temáticas para el prompt
        tematicas_text = "\n".join([
            f"- {t.get('segmento', '')}: {t.get('definicion', '')[:200]} (Problema: {t.get('problema_no_resuelto', '')[:150]})"
            for t in tematicas[:10]  # Limitar a 10 temáticas para no exceder tokens
        ])
        
        # Preparar contenido (limitar longitud)
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
                temperature=0.1,  # Bajo para respuestas consistentes
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
        """Limpia contenido HTML para análisis."""
        # Eliminar scripts, styles, etc.
        soup = BeautifulSoup(content, "html.parser")
        
        # Remover elementos no relevantes
        for elem in soup(["script", "style", "nav", "footer", "header"]):
            elem.decompose()
        
        # Extraer texto con estructura básica
        text = soup.get_text(separator="\n", strip=True)
        
        # Limpiar líneas vacías múltiples
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        return text.strip()


# ============================================================================
# HELPERS
# ============================================================================
def load_excel_files(uploaded_files: list) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Carga y procesa los archivos Excel."""
    centros_df = None
    tematicas_df = None
    
    for uploaded_file in uploaded_files:
        try:
            # Leer todas las hojas
            xls = pd.ExcelFile(uploaded_file)
            
            # Buscar hoja de centros (primera hoja o por nombre)
            sheet_names = xls.sheet_names
            if "ENLACES" in sheet_names or "Sheet1" in sheet_names:
                centros_sheet = "ENLACES" if "ENLACES" in sheet_names else sheet_names[0]
                centros_df = pd.read_excel(xls, sheet_name=centros_sheet)
            
            # Buscar hoja de temáticas
            if "TEMÁTICAS" in sheet_names:
                tematicas_df = pd.read_excel(xls, sheet_name="TEMÁTICAS")
            elif len(sheet_names) > 1:
                # Segunda hoja como temáticas
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
    
    # Filtrar vacíos
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
        
        # Buscar URLs en columnas WEB
        urls = []
        for col in centros_df.columns:
            if col.upper().startswith("WEB") and pd.notna(row.get(col)):
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
    """Genera clave de caché para un centro+URL."""
    return f"{centro_nombre}_{url}".replace(" ", "_").replace("/", "_").replace(":", "_")


def get_cached_analysis(centro_nombre: str, url: str) -> dict | None:
    """Obtiene análisis desde caché si existe."""
    cache_file = CACHE_DIR / f"{cache_key(centro_nombre, url)}.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return None
    return None


def save_cached_analysis(centro_nombre: str, url: str, result: dict):
    """Guarda análisis en caché."""
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
        st.markdown("## ⚙️ Configuración")
        
        # OpenAI API Key
        st.markdown("### 🤖 OpenAI API")
        
        api_from_secrets = ""
        try:
            api_from_secrets = st.secrets.get("OPENAI_API_KEY", "")
        except:
            pass
        
        if api_from_secrets:
            st.session_state.api_key = api_from_secrets
            st.success("✅ API key cargada desde secrets")
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
        st.markdown("### 📁 Archivos Excel")
        uploaded_files = st.file_uploader(
            "Sube archivos Excel con centros y temáticas",
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
                        st.warning("⚠️ No se pudo cargar la hoja de temáticas")
        
        st.divider()
        
        # Estado
        st.markdown("### 📊 Estado")
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
    st.markdown('<p class="big-header">🧬 Double Helix Dealflow Finder</p>', unsafe_allow_html=True)
    st.markdown("""
    Identifica **oportunidades de inversión en healthtech** analizando centros tecnológicos, 
    universidades y hubs de innovación.
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
        st.markdown("### 🔍 Selecciona centros para analizar")
        
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
        
        # Selección múltiple de centros
        centro_options = {f"{c['nombre']} ({c['region']})": c for c in centros_filtrados}
        selected_centros = st.multiselect(
            "Selecciona centros para analizar",
            options=list(centro_options.keys()),
            default=list(centro_options.keys())[:3]  # Seleccionar primeros 3 por defecto
        )
        
        # Configurar análisis
        with st.expander("⚙️ Configuración del análisis", expanded=False):
            max_pages = st.slider("Máx. páginas por centro a analizar", 1, 5, 2)
            timeout = st.slider("Timeout por página (segundos)", 10, 60, 30)
            min_score = st.slider("Score mínimo para incluir oportunidad", 50, 90, 60)
            st.info(f"💡 Las temáticas usadas para búsqueda: {len(st.session_state.tematicas_list)}")
        
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
                        # Verificar caché
                        cached = get_cached_analysis(centro["nombre"], url)
                        if cached:
                            centro_results.append(cached)
                            continue
                        
                        # Fetch página
                        status_text.text(f"🌐 Descargando {url[:50]}...")
                        page = scraper.fetch_page(url, timeout=timeout)
                        
                        if not page["ok"]:
                            st.warning(f"⚠️ No se pudo acceder a {url}: {page['error']}")
                            continue
                        
                        # Analizar con IA
                        status_text.text(f"🧠 Analizando contenido...")
                        result = analyzer.analizar_centro(
                            nombre_centro=centro["nombre"],
                            contenido=page["html"],
                            tematicas=st.session_state.tematicas_list,
                            url_origen=url
                        )
                        
                        # Añadir metadata
                        result["centro"] = centro["nombre"]
                        result["region"] = centro["region"]
                        result["url_analizada"] = url
                        result["page_title"] = page["title"]
                        
                        # Filtrar por score mínimo
                        if "oportunidades" in result:
                            result["oportunidades"] = [
                                o for o in result["oportunidades"] 
                                if o.get("score", 0) >= min_score
                            ]
                            result["total_oportunidades"] = len(result["oportunidades"])
                        
                        # Guardar en caché
                        save_cached_analysis(centro["nombre"], url, result)
                        centro_results.append(result)
                        
                        # Pequeña pausa para no saturar
                        time.sleep(1)
                    
                    # Guardar resultados del centro
                    st.session_state.results[centro["nombre"]] = {
                        "centro": centro,
                        "analisis": centro_results,
                        "total_oportunidades": sum(r.get("total_oportunidades", 0) for r in centro_results)
                    }
                    
                    # Actualizar progreso
                    progress_bar.progress((idx + 1) / len(selected_centros))
                
                status_text.text("✅ Análisis completado")
                st.balloons()
                st.rerun()
    
    # ------------------------------------------------------------------------
    # TAB 2: Resultados
    # ------------------------------------------------------------------------
    with tab2:
        st.markdown("### 📋 Oportunidades identificadas")
        
        if not st.session_state.results:
            st.info("👉 Ejecuta un análisis en la pestaña 'Analizar Centros' para ver resultados")
        else:
            # Resumen global
            total_opp = sum(r["total_oportunidades"] for r in st.session_state.results.values())
            st.metric("🎯 Total oportunidades", total_opp)
            
            # Filtros de resultados
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
            
            # Mostrar resultados por centro
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
                        
                        st.markdown(f"**🌐 Página analizada:** [{analysis.get('page_title', analysis.get('url_analizada', 'N/A'))[:80]}]({analysis.get('url_analizada', '#')})")
                        
                        for opp in analysis["oportunidades"]:
                            # Aplicar filtros
                            if vertical_filter and opp.get("vertical") not in vertical_filter:
                                continue
                            if tipo_filter and opp.get("tipo") not in tipo_filter:
                                continue
                            if opp.get("score", 0) < score_min:
                                continue
                            
                            # Card de oportunidad
                            with st.container():
                                col1, col2 = st.columns([4, 1])
                                
                                with col1:
                                    st.markdown(f"#### {opp.get('nombre', 'Sin nombre')}")
                                    
                                    # Tags
                                    tags = []
                                    if opp.get("vertical"):
                                        tags.append(f"<span class='vertical-tag'>{opp['vertical']}</span>")
                                    if opp.get("tipo"):
                                        tags.append(f"`{opp['tipo']}`")
                                    if opp.get("segmento"):
                                        tags.append(f"📦 {opp['segmento']}")
                                    st.markdown(" ".join(tags), unsafe_allow_html=True)
                                    
                                    # Descripción
                                    st.markdown(f"*{opp.get('descripcion', '')}*")
                                    
                                    # Problema resuelto
                                    if opp.get("problema_resuelto"):
                                        st.caption(f"🎯 Problema: {opp['problema_resuelto']}")
                                    
                                    # Matching rationale
                                    if opp.get("matching_rationale"):
                                        with st.expander("🔗 Por qué coincide con nuestras temáticas"):
                                            st.markdown(opp["matching_rationale"])
                                
                                with col2:
                                    st.markdown(f"<div style='text-align:center'><span class='match-score'>{opp.get('score', 0)}/100</span></div>", unsafe_allow_html=True)
                                    if opp.get("referencia"):
                                        st.markdown(f"[🔗 Ver]({opp['referencia']})", unsafe_allow_html=True)
                                
                                st.divider()
    
    # ------------------------------------------------------------------------
    # TAB 3: Exportar
    # ------------------------------------------------------------------------
    with tab3:
        st.markdown("### 📊 Exportar resultados")
        
        if not st.session_state.results:
            st.info("👉 Ejecuta un análisis primero para poder exportar")
        else:
            # Preparar DataFrame para exportar
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
                        # Ajustar columnas
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
                col_s4.metric("Verticales", df_export["Vertical"].nunique())
                
                # Distribución por vertical
                if not df_export["Vertical"].empty:
                    st.markdown("#### Distribución por vertical")
                    vertical_counts = df_export["Vertical"].value_counts()
                    st.bar_chart(vertical_counts)
            else:
                st.warning("⚠️ No hay oportunidades para exportar. Ajusta los filtros o ejecuta un nuevo análisis.")


if __name__ == "__main__":
    main()
