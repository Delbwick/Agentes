"""
LinkedIn CV Analyzer - Spin-off Detector
Versión Streamlit Cloud + Browserless API REST
Autor: Asistente IA para Ivan
"""

import os
import re
import json
import time
from io import BytesIO
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# ============================================================================
# CONFIGURACIÓN
# ============================================================================
CACHE_DIR = Path("cv_cache")
CACHE_DIR.mkdir(exist_ok=True)

st.set_page_config(
    page_title="🔬 Spin-off Detector",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stButton>button { width: 100%; }
    .big-header { font-size: 2.2rem; font-weight: 700; margin-bottom: 0.5rem; }
    .score-badge {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-weight: bold;
        font-size: 0.85rem;
        display: inline-block;
    }
    .match-badge {
        background: #28a745;
        color: white;
        padding: 0.15rem 0.5rem;
        border-radius: 8px;
        font-size: 0.8rem;
        margin-right: 0.3rem;
        display: inline-block;
    }
    .candidate-row {
        padding: 0.5rem;
        border-bottom: 1px solid #e0e0e0;
    }
    .candidate-row:hover {
        background: #f8f9fa;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# CLASE: BROWSERLESS API REST
# ============================================================================
class BrowserlessAPI:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://chrome.browserless.io"
        self.credits_used = 0

    def test_connection(self) -> tuple[bool, str]:
        try:
            resp = requests.get(
                f"{self.base_url}/json/version",
                params={"token": self.token},
                timeout=15
            )
            if resp.status_code == 200:
                return True, "✅ Token válido"
            elif resp.status_code == 401:
                return False, "❌ Token inválido"
            elif resp.status_code == 429:
                return False, "⚠️ Límite de créditos alcanzado"
            else:
                return False, f"❌ Error {resp.status_code}"
        except Exception as e:
            return False, f"❌ Error: {str(e)[:100]}"

    def get_content(self, url: str, cookies: list = None) -> dict:
        payload = {"url": url}
        if cookies:
            payload["cookies"] = cookies
        try:
            resp = requests.post(
                f"{self.base_url}/content",
                params={"token": self.token},
                json=payload,
                timeout=60
            )
            self.credits_used += 1
            if resp.status_code == 200:
                return {"ok": True, "html": resp.text, "final_url": url}
            else:
                return {"ok": False, "error": f"HTTP {resp.status_code}", "html": "", "final_url": url}
        except Exception as e:
            return {"ok": False, "error": str(e), "html": "", "final_url": url}


# ============================================================================
# CLASE: LINKEDIN SCRAPER
# ============================================================================
class LinkedInScraper:
    def __init__(self, api: BrowserlessAPI, cookies: list):
        self.api = api
        self.cookies = cookies
        self.debug_info = {}

    def test_linkedin_session(self) -> dict:
        result = {
            "ok": False,
            "final_url": "",
            "is_login_page": False,
            "is_challenge": False,
            "title": "",
            "debug_info": "",
            "html_length": 0,
        }

        response = self.api.get_content(
            "https://www.linkedin.com/feed/",
            cookies=self.cookies
        )

        if not response["ok"]:
            result["debug_info"] = f"Error: {response.get('error')}"
            return result

        html = response["html"]
        result["html_length"] = len(html)
        result["final_url"] = response.get("final_url", "")

        if not html:
            result["debug_info"] = "HTML vacío"
            return result

        soup = BeautifulSoup(html, "html.parser")
        result["title"] = soup.title.string if soup.title else ""

        if "signin" in html.lower()[:2000] or "login" in html.lower()[:2000]:
            result["is_login_page"] = True
            result["debug_info"] = "️ LinkedIn redirigió a login."
            return result

        if "challenge" in html.lower()[:2000]:
            result["is_challenge"] = True
            result["debug_info"] = "️ LinkedIn muestra captcha."
            return result

        session_indicators = [
            "/feed/" in result["final_url"].lower(),
            "feed" in result["title"].lower(),
            len(html) > 500000,
        ]

        active_count = sum(1 for x in session_indicators if x)
        
        if active_count >= 2:
            result["ok"] = True
            result["debug_info"] = f"✅ Sesión LinkedIn activa. ({active_count} indicadores)"
        else:
            result["debug_info"] = (
                f"⚠️ No se detectó sesión activa.\n"
                f"Indicadores: {active_count}/{len(session_indicators)}\n"
                f"Título: '{result['title']}'\n"
                f"Longitud HTML: {result['html_length']} chars"
            )

        return result

    def check_critical_cookies(self) -> dict:
        critical = ["li_at", "JSESSIONID", "bscookie", "liap"]
        found = {}
        for cookie_name in critical:
            cookie = next((c for c in self.cookies if c["name"] == cookie_name), None)
            if cookie:
                found[cookie_name] = len(cookie.get("value", ""))
            else:
                found[cookie_name] = 0
        return found

    def _extract_name_from_link(self, link) -> str:
        name = ""
        
        # Método 1: aria-label
        aria_label = link.get("aria-label", "")
        if aria_label and len(aria_label) > 2:
            name = aria_label.strip()
        
        # Método 2: span[aria-hidden='true']
        if not name:
            name_span = link.select_one("span[aria-hidden='true']")
            if name_span:
                name = name_span.get_text().strip()
        
        # Método 3: primer span con texto
        if not name:
            spans = link.select("span")
            for span in spans:
                text = span.get_text().strip()
                if text and len(text) > 2 and not text.startswith("Ver"):
                    name = text
                    break
        
        # Método 4: texto directo
        if not name:
            text = link.get_text().strip()
            if text and len(text) > 2 and len(text) < 100:
                name = text
        
        # Limpiar nombre
        name = re.sub(r'\s+', ' ', name).strip()
        name = re.sub(r'^(Ver perfil de|View profile de|View)\s*', '', name, flags=re.IGNORECASE)
        
        return name

    def _extract_headline_from_context(self, parent) -> str:
        if not parent:
            return ""
        text = parent.get_text(separator=" ", strip=True)
        if len(text) > 300:
            text = text[:300]
        return text

    def search_person(self, full_name: str, institution: str = "", orcid: str = "", debug_mode: bool = False) -> list:
        self.debug_info = {}
        
        query = full_name
        if institution:
            inst_clean = re.sub(r'[;|,()\[\]]', ' ', institution)
            words = [w for w in inst_clean.split() if len(w) > 3]
            if words:
                query += " " + " ".join(words[:2])

        search_url = (
            f"https://www.linkedin.com/search/results/people/"
            f"?keywords={requests.utils.quote(query)}&origin=GLOBAL_SEARCH_HEADER"
        )

        self.debug_info["search_url"] = search_url
        self.debug_info["query"] = query

        response = self.api.get_content(search_url, cookies=self.cookies)
        
        if not response["ok"]:
            self.debug_info["error"] = response.get("error")
            return []

        html = response["html"]
        self.debug_info["html_length"] = len(html)
        self.debug_info["final_url"] = response.get("final_url", "")

        if not html:
            self.debug_info["error"] = "HTML vacío"
            return []

        if "signin" in html.lower()[:1000] or "login" in html.lower()[:1000]:
            self.debug_info["error"] = "Redirigido a login"
            return []

        soup = BeautifulSoup(html, "html.parser")
        self.debug_info["page_title"] = soup.title.string if soup.title else ""

        all_links = soup.select("a[href*='/in/']")
        self.debug_info["total_links_in"] = len(all_links)

        profile_links = []
        seen_urls = set()
        
        for link in all_links:
            href = link.get("href", "")
            if "/in/" not in href or "login" in href or "challenge" in href:
                continue
            
            href = href.split("?")[0]
            
            if href in seen_urls:
                continue
            seen_urls.add(href)
            
            name = self._extract_name_from_link(link)
            
            # Extraer headline
            headline = ""
            headline_elem = link.select_one(".entity-result__title-line, .t-14 span, .t-bold")
            if headline_elem:
                headline = headline_elem.get_text().strip()
            
            # Extraer ubicación
            location = ""
            location_elem = link.select_one(".entity-result__summary, .t-14.t-black--light")
            if location_elem:
                text = location_elem.get_text().strip()
                if "·" in text:
                    location = text.split("·")[-1].strip()
                else:
                    location = text[:100]
            
            parent = link.find_parent("li") or link.find_parent("div", class_=re.compile("entity-result|search-result"))
            context = self._extract_headline_from_context(parent)
            
            profile_links.append({
                "href": href,
                "name": name,
                "headline": headline,
                "location": location,
                "context": context,
            })

        self.debug_info["profile_links_found"] = len(profile_links)

        if not profile_links:
            self.debug_info["error"] = "No se encontraron enlaces"
            return []

        # Calcular score
        target_words = set(full_name.lower().split())
        for pl in profile_links:
            name = pl["name"].lower()
            context = pl["context"].lower()
            headline = pl["headline"].lower()
            
            name_words = set(name.split())
            score = len(target_words & name_words) * 10

            if institution:
                inst_lower = institution.lower()
                inst_words = [w for w in inst_lower.split() if len(w) > 3]
                for word in inst_words[:3]:
                    if word in context or word in headline:
                        score += 10

            if orcid and orcid in context:
                score += 20

            if pl["headline"]:
                score += 2

            if pl["location"]:
                score += 1

            pl["score"] = score

        profile_links.sort(key=lambda x: x["score"], reverse=True)

        return profile_links

    def extract_full_cv(self, profile_url: str, debug_mode: bool = False) -> dict | None:
        response = self.api.get_content(profile_url, cookies=self.cookies)

        if not response["ok"] or not response["html"]:
            if debug_mode:
                st.error(f"❌ Error: {response.get('error')}")
            return None

        html = response["html"]
        soup = BeautifulSoup(html, "html.parser")
        
        cv = {"url": profile_url, "sections": {}}

        h1 = soup.select_one("h1")
        cv["nombre"] = h1.get_text().strip() if h1 else ""

        headline = soup.select_one(".text-body-medium.break-words")
        cv["headline"] = headline.get_text().strip() if headline else ""

        ubicacion = soup.select_one(".text-body-small.inline")
        cv["ubicacion"] = ubicacion.get_text().strip() if ubicacion else ""

        section_ids = {
            "Acerca de": "about",
            "Experiencia": "experience",
            "Educación": "education",
            "Publicaciones": "publications",
            "Patentes": "patents",
            "Proyectos": "projects",
            "Idiomas": "languages",
            "Premios": "honors",
        }

        for nombre_seccion, section_id in section_ids.items():
            section = soup.select_one(f"section#{section_id}")
            if section:
                cv["sections"][nombre_seccion] = section.get_text(separator="\n", strip=True)

        main = soup.select_one("main")
        if main:
            cv["texto_completo"] = main.get_text(separator="\n", strip=True)
        else:
            cv["texto_completo"] = soup.get_text(separator="\n", strip=True)

        if debug_mode:
            st.info(f" CV extraído: {cv['nombre']}")
            st.write(f"**Headline:** {cv['headline']}")
            st.write(f"**Secciones:** {', '.join(cv['sections'].keys())}")

        return cv


# ============================================================================
# CLASE: CV ANALYZER (OpenAI)
# ============================================================================
class CVAnalyzer:
    SYSTEM_PROMPT = """Eres un analista experto en transferencia de tecnología y spin-offs académicas españolas.
Analiza el CV de un investigador y extrae:
1. Lista de EMPRESAS privadas en las que ha trabajado (excluyendo universidades y OPIs).
2. SPIN-OFFs que haya fundado, cofundado o asesorado.
3. Para cada empresa/spin-off, descripción breve de su actividad.

Responde SOLO en JSON:
{
  "empresas": [
    {"nombre": "...", "rol": "...", "descripcion": "...", "es_spinoff": true/false}
  ],
  "resumen_industrial": "Párrafo resumen"
}
Si no hay actividad industrial:
{"empresas": [], "resumen_industrial": "Sin actividad industrial relevante."}
"""

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def analizar_cv(self, nombre: str, cv_text: str) -> dict:
        prompt = f"""Investigador: {nombre}

CV:
---
{cv_text[:12000]}
---

Extrae empresas y spin-offs."""
        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            return {"empresas": [], "resumen_industrial": f"Error: {e}"}


def formatear_para_excel(nombre_original: str, cv: dict, analisis: dict) -> str:
    lineas = [f"=== {nombre_original} ===", ""]
    if cv:
        lineas.append("📄 PERFIL LINKEDIN:")
        if cv.get("headline"):
            lineas.append(f"🎯 {cv['headline']}")
        if cv.get("url"):
            lineas.append(f"🔗 {cv['url']}")
        for seccion, texto in cv.get("sections", {}).items():
            lineas.append(f"\n— {seccion.upper()} —")
            lineas.append(texto)
        if cv.get("texto_completo"):
            lineas.append("\n— TEXTO COMPLETO —")
            lineas.append(cv["texto_completo"])
    lineas.append("\n" + "=" * 60)
    lineas.append("🏭 ANÁLISIS INDUSTRIAL / SPIN-OFFS:")
    lineas.append("=" * 60)
    if analisis.get("empresas"):
        for emp in analisis["empresas"]:
            tipo = "🚀 SPIN-OFF" if emp.get("es_spinoff") else "🏢 EMPRESA"
            lineas.append(f"\n{tipo}: {emp.get('nombre', '?')}")
            if emp.get("rol"):
                lineas.append(f"   Rol: {emp['rol']}")
            if emp.get("descripcion"):
                lineas.append(f"   Actividad: {emp['descripcion']}")
    else:
        lineas.append("\nNo se detectaron empresas ni spin-offs.")
    if analisis.get("resumen_industrial"):
        lineas.append(f"\n📋 RESUMEN: {analisis['resumen_industrial']}")
    return "\n".join(lineas)


# ============================================================================
# HELPERS
# ============================================================================
def parse_cookies_text(cookies_text: str) -> list | None:
    try:
        cookies = json.loads(cookies_text)
        if isinstance(cookies, list):
            normalized = []
            for c in cookies:
                if not c.get("name") or not c.get("value"):
                    continue
                normalized.append({
                    "name": c.get("name"),
                    "value": c.get("value"),
                    "domain": c.get("domain", ".linkedin.com"),
                    "path": c.get("path", "/"),
                })
            return normalized if normalized else None
    except json.JSONDecodeError:
        pass
    return None


def _cv_cache_path(nombre: str) -> Path:
    safe = re.sub(r'[^\w\-]', '_', nombre)
    return CACHE_DIR / f"{safe}.json"


def get_cached_cv(nombre: str) -> dict | None:
    path = _cv_cache_path(nombre)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def save_cv_cache(nombre: str, cv: dict):
    with open(_cv_cache_path(nombre), "w", encoding="utf-8") as f:
        json.dump(cv, f, ensure_ascii=False, indent=2)


# ============================================================================
# STREAMLIT APP
# ============================================================================
def main():
    # Estado
    if "api" not in st.session_state:
        st.session_state.api = None
    if "scraper" not in st.session_state:
        st.session_state.scraper = None
    if "df" not in st.session_state:
        st.session_state.df = None
    if "cvs" not in st.session_state:
        st.session_state.cvs = {}
    if "analisis" not in st.session_state:
        st.session_state.analisis = {}
    if "openai_ok" not in st.session_state:
        st.session_state.openai_ok = False
    if "linkedin_ok" not in st.session_state:
        st.session_state.linkedin_ok = False
    if "cookies" not in st.session_state:
        st.session_state.cookies = None
    if "debug_mode" not in st.session_state:
        st.session_state.debug_mode = False
    if "search_results" not in st.session_state:
        st.session_state.search_results = {}
    if "selected_profiles" not in st.session_state:
        st.session_state.selected_profiles = {}

    # ========================================================================
    # SIDEBAR
    # ========================================================================
    with st.sidebar:
        st.markdown("## ⚙️ Configuración")

        st.markdown("### 🐛 Modo Debug")
        debug_mode = st.checkbox(
            "🔍 Activar modo debug",
            value=False,
            help="Muestra información detallada"
        )
        st.session_state.debug_mode = debug_mode

        st.divider()

        st.markdown("### 🌐 Browserless API")

        token_from_secrets = ""
        try:
            token_from_secrets = st.secrets.get("BROWSERLESS_TOKEN", "")
        except Exception:
            pass

        if token_from_secrets:
            token = token_from_secrets
            st.success("✅ Token cargado desde secrets")
        else:
            token = st.text_input("Token Browserless (manual)", type="password")

        if token:
            if st.button("🔌 Verificar conexión"):
                with st.spinner("Verificando..."):
                    api = BrowserlessAPI(token)
                    ok, msg = api.test_connection()
                    if ok:
                        st.session_state.api = api
                        st.success(msg)
                    else:
                        st.error(msg)

        if st.session_state.api:
            st.success("🟢 Browserless conectado")
        else:
            st.warning("🟡 Browserless no conectado")

        st.divider()

        st.markdown("### 🔐 LinkedIn Cookies")
        st.caption("Exporta cookies con 'Cookie-Editor'.")

        cookies_text = st.text_area(
            "Pega las cookies (JSON)",
            height=150,
            label_visibility="collapsed",
        )

        if cookies_text and st.button("🔑 Cargar cookies"):
            with st.spinner("Parseando..."):
                cookies = parse_cookies_text(cookies_text)
                if cookies:
                    st.session_state.cookies = cookies
                    st.success(f"✅ {len(cookies)} cookies cargadas")

                    if st.session_state.api:
                        st.session_state.scraper = LinkedInScraper(
                            st.session_state.api,
                            cookies
                        )
                        
                        critical = st.session_state.scraper.check_critical_cookies()
                        st.write("**Cookies críticas:**")
                        for name, length in critical.items():
                            if length > 0:
                                st.success(f"✅ {name}: {length} chars")
                            else:
                                st.error(f"❌ {name}: FALTA")
                else:
                    st.error("❌ Formato inválido")

        if st.session_state.scraper:
            st.divider()
            st.markdown("### 🔍 Diagnóstico")
            
            if st.button("🧪 Testear sesión"):
                with st.spinner("Probando..."):
                    test_result = st.session_state.scraper.test_linkedin_session()
                    
                    if test_result["ok"]:
                        st.session_state.linkedin_ok = True
                        st.success(test_result["debug_info"])
                    else:
                        st.session_state.linkedin_ok = False
                        st.warning(test_result["debug_info"])

        if st.session_state.linkedin_ok:
            st.success("🟢 LinkedIn listo")
        else:
            st.warning("🟡 LinkedIn no verificado")

        st.divider()

        st.markdown("### 🤖 OpenAI API")
        
        openai_from_secrets = ""
        try:
            openai_from_secrets = st.secrets.get("OPENAI_API_KEY", "")
        except Exception:
            pass

        if openai_from_secrets:
            api_key = openai_from_secrets
            st.success("✅ OpenAI key cargada")
        else:
            api_key = st.text_input("API Key OpenAI", type="password")

        if api_key:
            if st.button(" Verificar OpenAI"):
                with st.spinner("Verificando..."):
                    try:
                        client = OpenAI(api_key=api_key)
                        client.models.list()
                        st.session_state.openai_ok = True
                        st.session_state.openai_key = api_key
                        st.success("✅ API key válida")
                    except Exception as e:
                        st.session_state.openai_ok = False
                        st.error(f"❌ {str(e)[:80]}")

        if st.session_state.openai_ok:
            st.success(" OpenAI listo")
        else:
            st.warning("🟡 OpenAI no configurado")

        st.divider()

        st.markdown("### 📊 Estado")
        st.write(f"🌐 Browserless: {'🟢 OK' if st.session_state.api else '🟡'}")
        st.write(f"🔗 LinkedIn: {'🟢 OK' if st.session_state.linkedin_ok else '🟡'}")
        st.write(f"🤖 OpenAI: {'🟢 OK' if st.session_state.openai_ok else '🟡'}")
        st.write(f"👥 CVs: {len(st.session_state.cvs)}")
        st.write(f"🏭 Análisis: {len(st.session_state.analisis)}")
        if st.session_state.api:
            st.write(f" Créditos: {st.session_state.api.credits_used}")

        if st.button("🔄 Reiniciar"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    # ========================================================================
    # MAIN
    # ========================================================================
    st.markdown('<p class="big-header">🚀 Spin-off Detector</p>', unsafe_allow_html=True)
    st.markdown("Analiza investigadores y detecta **empresas** y **spin-offs**.")

    # STEP 1: Excel
    st.markdown("### 1️ Cargar Excel")
    uploaded = st.file_uploader("Sube el Excel", type=["xlsx", "xls"])

    if uploaded is not None:
        try:
            df = pd.read_excel(uploaded)
            st.session_state.df = df
        except Exception as e:
            st.error(f"❌ Error: {e}")
            st.stop()

        col_map = {}
        for col in df.columns:
            cl = str(col).lower()
            if "person" in cl or "name" in cl:
                col_map["nombre"] = col
            elif "institution" in cl or "universidad" in cl:
                col_map["institucion"] = col
            elif "orcid" in cl:
                col_map["orcid"] = col
            elif "industrial" in cl:
                col_map["industrial"] = col

        c1, c2, c3 = st.columns(3)
        c1.metric("👤 Nombre", col_map.get("nombre", "❌"))
        c2.metric("️ Institución", col_map.get("institucion", "❌"))
        c3.metric("🆔 ORCID", col_map.get("orcid", "❌"))

        if "nombre" not in col_map:
            st.error("❌ No se detectó columna de nombres.")
            st.stop()

        col_nombre = col_map["nombre"]
        col_inst = col_map.get("institucion")
        col_orcid = col_map.get("orcid")

        # STEP 2: Buscar CVs
        st.markdown("### 2️⃣ Buscar CVs en LinkedIn")

        if not st.session_state.linkedin_ok:
            st.warning("⚠️ Primero verifica sesión LinkedIn")
        else:
            tab1, tab2 = st.tabs(["🔍 Búsqueda automática", "🔗 URL manual"])
            
            with tab1:
                seleccion = st.multiselect(
                    "Selecciona investigadores",
                    df[col_nombre].tolist(),
                    default=df[col_nombre].tolist()[:1]
                )

                if st.button("🔍 Buscar candidatos", type="primary", use_container_width=True):
                    progress = st.progress(0)
                    
                    for i, nombre in enumerate(seleccion):
                        inst = str(df[df[col_nombre] == nombre][col_inst].iloc[0]) if col_inst else ""
                        orcid = str(df[df[col_nombre] == nombre][col_orcid].iloc[0]) if col_orcid else ""

                        with st.spinner(f"🔍 {nombre}..."):
                            results = st.session_state.scraper.search_person(
                                nombre, inst, orcid, debug_mode=st.session_state.debug_mode
                            )
                            
                            if results:
                                st.session_state.search_results[nombre] = results
                                st.success(f"✅ {nombre}: {len(results)} candidatos")
                            else:
                                st.warning(f"❌ {nombre}: no encontrado")
                        
                        progress.progress((i + 1) / len(seleccion))
                        time.sleep(2)

            with tab2:
                selected_name = st.selectbox("Selecciona investigador", df[col_nombre].tolist())
                
                search_query = st.text_input(
                    "Query Google",
                    value=f'site:linkedin.com/in "{selected_name}"'
                )
                
                if st.button("🔍 Buscar en Google"):
                    google_url = f"https://www.google.com/search?q={requests.utils.quote(search_query)}"
                    st.markdown(f'[🌐 Abrir Google]({google_url})', unsafe_allow_html=True)
                
                manual_url = st.text_input("URL LinkedIn", placeholder="https://www.linkedin.com/in/...")
                
                if manual_url and st.button("💾 Guardar URL"):
                    st.session_state.selected_profiles[selected_name] = manual_url
                    st.success(f"✅ URL guardada para {selected_name}")

            # Mostrar resultados COMPACTOS
            if st.session_state.search_results:
                st.markdown("### 📋 Selecciona el perfil correcto")
                st.info("💡 Ordenados por relevancia. Busca coincidencias en nombre e institución.")
                
                for nombre, results in st.session_state.search_results.items():
                    with st.expander(f"👤 {nombre} ({len(results)} candidatos)", expanded=True):
                        # Info del Excel
                        inst_excel = str(df[df[col_nombre] == nombre][col_inst].iloc[0]) if col_inst else ""
                        orcid_excel = str(df[df[col_nombre] == nombre][col_orcid].iloc[0]) if col_orcid else ""
                        
                        col_ref1, col_ref2 = st.columns(2)
                        with col_ref1:
                            st.markdown(f"**🏛️ Institución:** {inst_excel[:80]}{'...' if len(inst_excel) > 80 else ''}")
                        with col_ref2:
                            if orcid_excel:
                                st.markdown(f"**🔗 ORCID:** [{orcid_excel[-8:]}]({orcid_excel})")
                        
                        st.divider()
                        
                        # Mostrar top 10 resultados
                        for i, r in enumerate(results[:10]):
                            name = r.get('name', 'Sin nombre')
                            headline = r.get('headline', '')
                            location = r.get('location', '')
                            context = r.get('context', '')
                            score = r.get('score', 0)
                            href = r.get('href', '')
                            
                            # Calcular coincidencias
                            name_match = nombre.lower() in name.lower()
                            inst_match = False
                            inst_words_found = []
                            if inst_excel and context:
                                inst_words = [w for w in inst_excel.lower().split() if len(w) > 4]
                                for word in inst_words[:5]:
                                    if word in context.lower():
                                        inst_match = True
                                        inst_words_found.append(word)
                            
                            # Tarjeta compacta
                            col_checkbox, col_content = st.columns([0.08, 0.92])
                            
                            with col_checkbox:
                                selected = st.checkbox(
                                    "",
                                    key=f"select_{nombre}_{i}",
                                    label_visibility="collapsed",
                                    help="Marca para seleccionar"
                                )
                            
                            with col_content:
                                # Header: Nombre + Score
                                col_h1, col_h2 = st.columns([3, 1])
                                with col_h1:
                                    st.markdown(f"**{name}**")
                                with col_h2:
                                    if score > 10:
                                        st.markdown(f'<span class="score-badge">Score: {score}</span>', unsafe_allow_html=True)
                                    elif score > 0:
                                        st.caption(f"Score: {score}")
                                
                                # Badges de coincidencia
                                badges = []
                                if name_match:
                                    badges.append("🎯 Nombre")
                                if inst_match:
                                    badges.append(f"🏢 Institución ({', '.join(inst_words_found[:2])})")
                                
                                if badges:
                                    badge_html = " ".join([f'<span class="match-badge">{b}</span>' for b in badges])
                                    st.markdown(badge_html, unsafe_allow_html=True)
                                
                                # Info relevante
                                info_parts = []
                                if headline:
                                    info_parts.append(f"💼 {headline}")
                                if location:
                                    info_parts.append(f"📍 {location}")
                                
                                if info_parts:
                                    st.caption(" • ".join(info_parts))
                                
                                # Contexto recortado
                                if context and len(context) > 20:
                                    context_preview = context[:250] + "..." if len(context) > 250 else context
                                    st.markdown(f"*{context_preview}*")
                                
                                # Link
                                if href:
                                    st.markdown(f"[🔗 Ver perfil LinkedIn]({href})")
                                
                                st.markdown("---")
                        
                        # Botón guardar selección
                        col_btn1, col_btn2 = st.columns([2, 1])
                        with col_btn1:
                            if st.button(f"💾 Guardar selección", key=f"save_{nombre}", type="primary", use_container_width=True):
                                seleccionado = False
                                for i, r in enumerate(results[:10]):
                                    if st.session_state.get(f"select_{nombre}_{i}", False):
                                        st.session_state.selected_profiles[nombre] = r['href']
                                        st.success(f"✅ Seleccionado: {r.get('name', 'N/A')} (Score: {r.get('score', 0)})")
                                        seleccionado = True
                                        break
                                
                                if not seleccionado:
                                    st.warning("⚠️ Selecciona un candidato primero")
                        
                        with col_btn2:
                            if st.button(f"🔄 Limpiar", key=f"clear_{nombre}"):
                                for i in range(len(results[:10])):
                                    key = f"select_{nombre}_{i}"
                                    if key in st.session_state:
                                        st.session_state[key] = False
                                st.rerun()
                        
                        st.markdown("<br>", unsafe_allow_html=True)

        # Extraer CVs
        if st.session_state.selected_profiles:
            st.markdown("### 📄 Extraer CVs")
            st.write(f"**Perfiles:** {len(st.session_state.selected_profiles)}")
            
            for nombre, url in st.session_state.selected_profiles.items():
                st.caption(f"• **{nombre}**: {url}")
            
            if st.button("📥 Extraer CVs", type="primary", use_container_width=True):
                progress = st.progress(0)
                
                for i, (nombre, url) in enumerate(st.session_state.selected_profiles.items()):
                    cached = get_cached_cv(nombre)
                    if cached:
                        st.session_state.cvs[nombre] = cached
                        st.info(f"⚡ {nombre}: de caché")
                    else:
                        with st.spinner(f"📄 {nombre}..."):
                            cv = st.session_state.scraper.extract_full_cv(url)
                            if cv:
                                st.session_state.cvs[nombre] = cv
                                save_cv_cache(nombre, cv)
                                st.success(f"✅ {nombre}: {cv.get('headline', 'OK')[:80]}")
                            else:
                                st.warning(f"️ {nombre}: no se pudo extraer")
                    
                    progress.progress((i + 1) / len(st.session_state.selected_profiles))
                    time.sleep(2)
                
                st.balloons()

        # Mostrar CVs
        if st.session_state.cvs:
            with st.expander(f"📄 CVs ({len(st.session_state.cvs)})", expanded=False):
                for nombre, cv in st.session_state.cvs.items():
                    st.markdown(f"** {nombre}**")
                    st.caption(f"🎯 {cv.get('headline', 'N/A')}")
                    st.caption(f"🔗 {cv.get('url', 'N/A')}")
                    for sec, txt in cv.get("sections", {}).items():
                        with st.expander(f"  • {sec}", expanded=False):
                            st.text(txt[:1500])
                    st.divider()

        # STEP 3: Analizar
        st.markdown("### 3️⃣ Analizar con IA")

        if not st.session_state.openai_ok:
            st.warning("⚠️ Configura OpenAI")
        elif not st.session_state.cvs:
            st.info("👉 Busca CVs primero")
        else:
            if st.button("🤖 Analizar con IA", type="primary", use_container_width=True):
                analyzer = CVAnalyzer(api_key=st.session_state.openai_key)
                progress = st.progress(0)

                for i, (nombre, cv) in enumerate(st.session_state.cvs.items()):
                    with st.spinner(f"🧠 {nombre}..."):
                        cv_text = "\n\n".join(cv.get("sections", {}).values()) or cv.get("texto_completo", "")
                        analisis = analyzer.analizar_cv(nombre, cv_text)
                        st.session_state.analisis[nombre] = analisis
                        n_emp = len(analisis.get("empresas", []))
                        n_spin = sum(1 for e in analisis.get("empresas", []) if e.get("es_spinoff"))
                        st.success(f"✅ **{nombre}**: {n_emp} empresas, {n_spin} spin-offs")
                    progress.progress((i + 1) / len(st.session_state.cvs))

                st.balloons()

        # Mostrar análisis
        if st.session_state.analisis:
            with st.expander(f"🏭 Análisis ({len(st.session_state.analisis)})", expanded=False):
                for nombre, analisis in st.session_state.analisis.items():
                    st.markdown(f"**👤 {nombre}**")
                    if analisis.get("empresas"):
                        for emp in analisis["empresas"]:
                            tipo = "🚀 **SPIN-OFF**" if emp.get("es_spinoff") else " Empresa"
                            st.markdown(f"- {tipo}: **{emp.get('nombre', '?')}** ({emp.get('rol', 'N/A')})")
                            if emp.get("descripcion"):
                                st.caption(f"   _{emp['descripcion']}_")
                    else:
                        st.caption("Sin actividad industrial.")
                    if analisis.get("resumen_industrial"):
                        st.info(analisis["resumen_industrial"])
                    st.divider()

        # STEP 4: Excel
        st.markdown("### 4️ Generar Excel")

        if st.session_state.analisis:
            if st.button("📊 Generar Excel", type="primary", use_container_width=True):
                df_out = df.copy()
                col_industrial = col_map.get("industrial", "INDUSTRIAL info")
                if col_industrial not in df_out.columns:
                    df_out[col_industrial] = ""

                for idx, row in df_out.iterrows():
                    nombre = row[col_nombre]
                    cv = st.session_state.cvs.get(nombre, {})
                    analisis = st.session_state.analisis.get(nombre, {})
                    if cv or analisis:
                        df_out.at[idx, col_industrial] = formatear_para_excel(nombre, cv, analisis)

                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_out.to_excel(writer, index=False, sheet_name='Sheet1')
                    workbook = writer.book
                    worksheet = writer.sheets['Sheet1']
                    for i, col in enumerate(df_out.columns):
                        max_len = max(
                            df_out[col].astype(str).map(len).max() if len(df_out) > 0 else 0,
                            len(str(col))
                        )
                        worksheet.set_column(i, i, min(max_len + 2, 80))
                    if col_industrial in df_out.columns:
                        text_format = workbook.add_format({'text_wrap': True, 'valign': 'top'})
                        col_idx = df_out.columns.get_loc(col_industrial)
                        worksheet.set_column(col_idx, col_idx, 80, text_format)

                buffer.seek(0)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")

                st.download_button(
                    label="⬇️ Descargar Excel",
                    data=buffer,
                    file_name=f"investigadores_spinoffs_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                st.success("✅ Excel generado")

                st.markdown("### 📈 Resumen")
                total_emp = sum(len(a.get("empresas", [])) for a in st.session_state.analisis.values())
                total_spin = sum(
                    sum(1 for e in a.get("empresas", []) if e.get("es_spinoff"))
                    for a in st.session_state.analisis.values()
                )
                c1, c2, c3 = st.columns(3)
                c1.metric("👥 Investigadores", len(st.session_state.analisis))
                c2.metric("🏢 Empresas", total_emp)
                c3.metric("🚀 Spin-offs", total_spin)

        elif st.session_state.cvs:
            st.info("👉 Pulsa 'Analizar con IA'")


if __name__ == "__main__":
    main()
