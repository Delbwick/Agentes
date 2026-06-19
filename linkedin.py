"""
LinkedIn CV Analyzer - Spin-off Detector
Versión con información detallada en resultados + búsqueda manual mejorada
"""

import os
import re
import json
import time
import webbrowser
from io import BytesIO
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

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
    .result-card {
        padding: 0.8rem;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        margin: 0.3rem 0;
        background: #fafafa;
    }
    .result-card:hover { background: #f0f0f0; }
    .score-badge {
        display: inline-block;
        padding: 0.2rem 0.5rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: bold;
    }
    .score-high { background: #d4edda; color: #155724; }
    .score-medium { background: #fff3cd; color: #856404; }
    .score-low { background: #f8d7da; color: #721c24; }
    .warning-box {
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .info-box {
        background-color: #d1ecf1;
        border-left: 5px solid #0c5460;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
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
            result["debug_info"] = "⚠️ LinkedIn redirigió a login."
            return result

        if "challenge" in html.lower()[:2000]:
            result["is_challenge"] = True
            result["debug_info"] = "⚠️ LinkedIn muestra captcha."
            return result

        session_indicators = [
            "/feed/" in result["final_url"].lower(),
            "feed" in result["title"].lower(),
            len(html) > 500000,
            soup.select_one("nav.global-nav"),
            soup.select_one("div.feed-shared-update-v2"),
            soup.select_one("header"),
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
                f"Longitud HTML: {result['html_length']} chars\n"
                f"URL: {result['final_url']}"
            )

        return result

    def check_critical_cookies(self) -> dict:
        """Verifica qué cookies críticas están presentes."""
        critical = ["li_at", "JSESSIONID", "bscookie", "liap"]
        found = {}
        for cookie_name in critical:
            cookie = next((c for c in self.cookies if c["name"] == cookie_name), None)
            if cookie:
                found[cookie_name] = len(cookie.get("value", ""))
            else:
                found[cookie_name] = 0
        return found

    def search_person(self, full_name: str, institution: str = "", debug_mode: bool = False) -> list:
        """
        Busca persona y devuelve lista de resultados con información detallada.
        Extrae: nombre, headline, ubicación, empresa actual, conexiones mutuas.
        """
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
            if debug_mode:
                st.error(f"❌ Error en /content: {response.get('error')}")
            return []

        html = response["html"]
        self.debug_info["html_length"] = len(html)
        self.debug_info["final_url"] = response.get("final_url", "")

        if not html:
            self.debug_info["error"] = "HTML vacío"
            if debug_mode:
                st.error("❌ HTML vacío devuelto")
            return []

        # Detectar si nos redirigieron a login
        if "signin" in html.lower()[:1000] or "login" in html.lower()[:1000]:
            self.debug_info["error"] = "Redirigido a login"
            if debug_mode:
                st.error("❌ Sesión expirada durante la búsqueda")
                st.warning("💡 Las cookies pueden no estar aplicándose correctamente")
            return []

        soup = BeautifulSoup(html, "html.parser")
        self.debug_info["page_title"] = soup.title.string if soup.title else ""

        # Buscar enlaces a perfiles
        all_links = soup.select("a[href*='/in/']")
        self.debug_info["total_links_in"] = len(all_links)

        # Filtrar y extraer información detallada de cada perfil
        profile_links = []
        seen_urls = set()
        
        for link in all_links:
            href = link.get("href", "")
            if "/in/" not in href or "login" in href or "challenge" in href:
                continue
                
            href = href.split("?")[0]
            
            # Evitar duplicados
            if href in seen_urls:
                continue
            seen_urls.add(href)

            # Extraer nombre (múltiples selectores)
            name = ""
            name_span = link.select_one("span[aria-hidden='true']")
            if name_span:
                name = name_span.get_text().strip()
            
            # Si no hay nombre en el span, buscar en el texto del enlace
            if not name:
                name = link.get_text().strip().split('\n')[0]

            # Extraer contexto completo del elemento padre
            parent = link.find_parent("li") or link.find_parent("div.entity-result")
            context_text = parent.get_text(separator="|", strip=True) if parent else ""
            
            # Parsear información del contexto
            context_parts = [p.strip() for p in context_text.split("|") if p.strip()]
            
            # Headline (normalmente es la segunda línea después del nombre)
            headline = ""
            if len(context_parts) > 1:
                headline = context_parts[1] if len(context_parts[1]) < 200 else ""
            
            # Ubicación (busca palabras clave)
            ubicacion = ""
            for part in context_parts:
                if any(loc_word in part.lower() for loc_word in 
                       ['spain', 'españa', 'madrid', 'barcelona', 'sevilla', 'valencia', 
                        'united', 'kingdom', 'usa', 'france', 'germany', 'italy']):
                    ubicacion = part
                    break
            
            # Empresa actual (busca "at @" o "en @")
            empresa_actual = ""
            for part in context_parts:
                if "@" in part or " at " in part.lower() or " en " in part.lower():
                    empresa_actual = part
                    break
            
            # Conexiones mutuas (busca "X mutual connections" o "X contactos en común")
            conexiones = ""
            for part in context_parts:
                if "mutual" in part.lower() or "en común" in part.lower() or "contacto" in part.lower():
                    if any(char.isdigit() for char in part):
                        conexiones = part
                        break
            
            # Grado de conexión (1st, 2nd, 3rd)
            grado = ""
            for part in context_parts:
                if part.strip() in ["1st", "2nd", "3rd", "1º", "2º", "3º"]:
                    grado = part
                    break

            profile_links.append({
                "href": href,
                "name": name or "Sin nombre",
                "headline": headline[:150] if headline else "",
                "ubicacion": ubicacion[:100] if ubicacion else "",
                "empresa_actual": empresa_actual[:100] if empresa_actual else "",
                "conexiones": conexiones[:50] if conexiones else "",
                "grado": grado,
                "context_raw": context_text[:500],
            })

        self.debug_info["profile_links_found"] = len(profile_links)

        if not profile_links:
            self.debug_info["error"] = "No se encontraron enlaces a perfiles"
            if debug_mode:
                st.warning("⚠️ No se encontraron enlaces a perfiles en el HTML")
                st.info(f"Total enlaces en página: {len(all_links)}")
            return []

        # Calcular score mejorado
        target_words = set(full_name.lower().split())
        target_institution = set(institution.lower().split()) if institution else set()
        
        for pl in profile_links:
            name_lower = pl["name"].lower()
            name_words = set(name_lower.split())
            
            # Score base por nombre
            score = len(target_words & name_words) * 10
            
            # Bonus por coincidencia exacta de nombre completo
            if full_name.lower() in name_lower:
                score += 20
            
            # Bonus por institución en headline o empresa
            if institution:
                context_lower = (pl["headline"] + " " + pl["empresa_actual"]).lower()
                inst_words = [w for w in institution.lower().split() if len(w) > 3]
                for word in inst_words:
                    if word in context_lower:
                        score += 3
            
            # Bonus por conexiones mutuas
            if pl["conexiones"]:
                score += 2
            
            # Bonus por grado de conexión
            if pl["grado"] == "1st":
                score += 5
            elif pl["grado"] == "2nd":
                score += 2

            pl["score"] = score

        # Ordenar por score
        profile_links.sort(key=lambda x: x["score"], reverse=True)

        if debug_mode:
            st.success(f"✅ {len(profile_links)} resultados encontrados")

        return profile_links

    def extract_full_cv(self, profile_url: str, debug_mode: bool = False) -> dict | None:
        """Extrae CV completo usando /content."""
        response = self.api.get_content(profile_url, cookies=self.cookies)

        if not response["ok"] or not response["html"]:
            if debug_mode:
                st.error(f"❌ Error extrayendo CV: {response.get('error')}")
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
            st.info(f"📄 CV extraído: {cv['nombre']}")
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


def format_result_card(result: dict) -> str:
    """Formatea un resultado como HTML card para mejor visualización."""
    score = result.get("score", 0)
    score_class = "score-high" if score >= 15 else "score-medium" if score >= 8 else "score-low"
    
    html = f"""
    <div class="result-card">
        <strong style="font-size: 1.05rem;">{result.get('name', 'Sin nombre')}</strong>
        <span class="score-badge {score_class}">Score: {score}</span>
        {f"<br><small style='color: #666;'>🎯 {result.get('headline', '')}</small>" if result.get('headline') else ''}
        {f"<br><small style='color: #888;'>📍 {result.get('ubicacion', '')}</small>" if result.get('ubicacion') else ''}
        {f"<br><small style='color: #888;'>🏢 {result.get('empresa_actual', '')}</small>" if result.get('empresa_actual') else ''}
        {f"<br><small style='color: #0077b5;'>🔗 {result.get('conexiones', '')} | {result.get('grado', '')}</small>" if result.get('conexiones') or result.get('grado') else ''}
    </div>
    """
    return html


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

        # --- MODO DEBUG ---
        st.markdown("### 🐛 Modo Debug")
        debug_mode = st.checkbox(
            "🔍 Activar modo debug",
            value=False,
            help="Muestra información detallada en cada búsqueda"
        )
        st.session_state.debug_mode = debug_mode

        st.divider()

        # --- Browserless ---
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
            if st.button("🔌 Verificar conexión Browserless"):
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

        # --- LinkedIn Cookies ---
        st.markdown("### 🔐 LinkedIn Cookies")
        st.caption("Exporta cookies desde tu Chrome local con 'Cookie-Editor'.")

        cookies_text = st.text_area(
            "Pega las cookies (JSON)",
            height=150,
            label_visibility="collapsed",
        )

        if cookies_text and st.button("🔑 Cargar cookies"):
            with st.spinner("Parseando cookies..."):
                cookies = parse_cookies_text(cookies_text)
                if cookies:
                    st.session_state.cookies = cookies
                    st.success(f"✅ {len(cookies)} cookies cargadas")

                    if st.session_state.api:
                        st.session_state.scraper = LinkedInScraper(
                            st.session_state.api,
                            cookies
                        )
                        
                        # Verificar cookies críticas
                        critical = st.session_state.scraper.check_critical_cookies()
                        st.write("**Cookies críticas:**")
                        for name, length in critical.items():
                            if length > 0:
                                st.success(f"✅ {name}: {length} chars")
                            else:
                                st.error(f"❌ {name}: FALTA")
                else:
                    st.error("❌ No se pudo parsear. Usa formato JSON.")

        # --- DIAGNÓSTICO ---
        if st.session_state.scraper:
            st.divider()
            st.markdown("### 🔍 Diagnóstico de sesión LinkedIn")
            
            if st.button("🧪 Testear sesión LinkedIn"):
                with st.spinner("Probando cookies..."):
                    test_result = st.session_state.scraper.test_linkedin_session()
                    
                    if test_result["ok"]:
                        st.session_state.linkedin_ok = True
                        st.success(test_result["debug_info"])
                    else:
                        st.session_state.linkedin_ok = False
                        if test_result["is_login_page"]:
                            st.error("❌ Cookies inválidas o expiradas.")
                        elif test_result["is_challenge"]:
                            st.error("❌ LinkedIn muestra captcha.")
                        else:
                            st.warning(test_result["debug_info"])
                    
                    with st.expander("🔧 Info de debug"):
                        st.write(f"**URL final:** {test_result['final_url']}")
                        st.write(f"**Título:** {test_result['title']}")
                        st.write(f"**Longitud HTML:** {test_result['html_length']} chars")
                        st.markdown(f"**Debug:**\n```\n{test_result['debug_info']}\n```")

        if st.session_state.linkedin_ok:
            st.success("🟢 LinkedIn listo")
        else:
            st.warning("🟡 LinkedIn no verificado")

        st.divider()

        # --- OpenAI ---
        st.markdown("### 🤖 OpenAI API")
        
        openai_from_secrets = ""
        try:
            openai_from_secrets = st.secrets.get("OPENAI_API_KEY", "")
        except Exception:
            pass

        if openai_from_secrets:
            api_key = openai_from_secrets
            st.success("✅ OpenAI key cargada desde secrets")
        else:
            api_key = st.text_input("API Key OpenAI (manual)", type="password")

        if api_key:
            if st.button("🔍 Verificar OpenAI"):
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
            st.success("🟢 OpenAI listo")
        else:
            st.warning("🟡 OpenAI no configurado")

        st.divider()

        # --- Estado ---
        st.markdown("### 📊 Estado")
        st.write(f"🌐 Browserless: {'🟢 OK' if st.session_state.api else '🟡 No conectado'}")
        st.write(f"🔗 LinkedIn: {'🟢 OK' if st.session_state.linkedin_ok else '🟡 No verificado'}")
        st.write(f"🤖 OpenAI: {'🟢 OK' if st.session_state.openai_ok else '🟡 Pendiente'}")
        st.write(f"👥 CVs extraídos: {len(st.session_state.cvs)}")
        st.write(f"🏭 Análisis hechos: {len(st.session_state.analisis)}")
        if st.session_state.api:
            st.write(f"💳 Créditos usados: {st.session_state.api.credits_used}")

        if st.button("🔄 Reiniciar sesión"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    # ========================================================================
    # MAIN
    # ========================================================================
    st.markdown('<p class="big-header">🚀 Spin-off Detector</p>', unsafe_allow_html=True)
    st.markdown(
        "Analiza investigadores a partir de su CV de LinkedIn y detecta "
        "**empresas** y **spin-offs** en las que han participado."
    )

    # STEP 1: Excel
    st.markdown("### 1️⃣ Cargar Excel de investigadores")
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

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("👤 Nombre", col_map.get("nombre", "❌"))
        c2.metric("🏛️ Institución", col_map.get("institucion", "❌"))
        c3.metric("🆔 ORCID", col_map.get("orcid", "❌"))
        c4.metric("🏭 Industrial", col_map.get("industrial", "⚠️ nueva"))

        with st.expander("👀 Vista previa"):
            st.dataframe(df, use_container_width=True)

        if "nombre" not in col_map:
            st.error("❌ No se detectó la columna de nombres.")
            st.stop()

        col_nombre = col_map["nombre"]
        col_inst = col_map.get("institucion")

        # STEP 2: Buscar CVs - CON 2 MÉTODOS MEJORADOS
        st.markdown("### 2️⃣ Buscar CVs en LinkedIn")

        if not st.session_state.linkedin_ok:
            st.warning("⚠️ Primero carga las cookies y pulsa '🧪 Testear sesión LinkedIn'")
        else:
            # Tabs para los 2 métodos
            tab1, tab2 = st.tabs(["🔍 Búsqueda automática", "🔗 URL manual"])
            
            with tab1:
                st.info("💡 Busca automáticamente y muestra información detallada para seleccionar el perfil correcto")
                seleccion = st.multiselect(
                    "Selecciona investigadores",
                    df[col_nombre].tolist(),
                    default=df[col_nombre].tolist()[:1]
                )

                if st.button(
                    "🔍 Buscar candidatos",
                    type="primary",
                    use_container_width=True,
                    disabled=len(seleccion) == 0
                ):
                    progress = st.progress(0)
                    status_container = st.container()

                    for i, nombre in enumerate(seleccion):
                        inst = ""
                        if col_inst:
                            inst = str(df[df[col_nombre] == nombre][col_inst].iloc[0])

                        with status_container:
                            with st.spinner(f"🔍 {nombre}..."):
                                results = st.session_state.scraper.search_person(
                                    nombre, inst, debug_mode=st.session_state.debug_mode
                                )
                                
                                if results:
                                    st.session_state.search_results[nombre] = results
                                    st.success(f"✅ {nombre}: {len(results)} candidatos encontrados")
                                else:
                                    st.warning(f"❌ {nombre}: no encontrado")
                        
                        progress.progress((i + 1) / len(seleccion))
                        time.sleep(2)

            with tab2:
                st.info("💡 Busca manualmente en LinkedIn y pega la URL del perfil correcto")
                
                col_sel, col_btn = st.columns([3, 1])
                with col_sel:
                    selected_name = st.selectbox(
                        "Selecciona investigador",
                        df[col_nombre].tolist(),
                        key="manual_name_select"
                    )
                with col_btn:
                    st.write("")  # Espaciador
                    st.write("")
                    # Botón para abrir LinkedIn con búsqueda pre-cargada
                    if selected_name:
                        inst = ""
                        if col_inst:
                            inst = str(df[df[col_nombre] == selected_name][col_inst].iloc[0])
                        
                        # Construir query de búsqueda
                        query = selected_name
                        if inst:
                            inst_clean = re.sub(r'[;|,()\[\]]', ' ', inst)
                            words = [w for w in inst_clean.split() if len(w) > 3]
                            if words:
                                query += " " + " ".join(words[:2])
                        
                        linkedin_search_url = f"https://www.linkedin.com/search/results/people/?keywords={quote(query)}"
                        
                        st.markdown(
                            f'<a href="{linkedin_search_url}" target="_blank" style="text-decoration:none;">'
                            f'<button style="background:#0077b5; color:white; border:none; padding:0.5rem 1rem; '
                            f'border-radius:5px; cursor:pointer; width:100%;">🔗 Buscar en LinkedIn</button></a>',
                            unsafe_allow_html=True
                        )
                
                manual_url = st.text_input(
                    "URL de LinkedIn (después de buscar manualmente)",
                    placeholder="https://www.linkedin.com/in/valerio-pruneri-123456/",
                    key="manual_url_input"
                )
                
                col_save, col_clear = st.columns([2, 1])
                with col_save:
                    if manual_url and "linkedin.com/in/" in manual_url:
                        if st.button("💾 Guardar URL", use_container_width=True):
                            # Limpiar URL
                            clean_url = manual_url.split("?")[0]
                            st.session_state.selected_profiles[selected_name] = clean_url
                            st.success(f"✅ URL guardada para {selected_name}")
                    elif manual_url:
                        st.warning("⚠️ URL no válida. Debe contener linkedin.com/in/")
                
                with col_clear:
                    if selected_name in st.session_state.selected_profiles:
                        if st.button("🗑️ Borrar", use_container_width=True):
                            del st.session_state.selected_profiles[selected_name]
                            st.rerun()

            # Mostrar resultados de búsqueda para seleccionar
            if st.session_state.search_results:
                st.markdown("### 📋 Selecciona el perfil correcto")
                st.caption("Los resultados muestran nombre, headline, ubicación y empresa actual para ayudarte a elegir")
                
                for nombre, results in st.session_state.search_results.items():
                    with st.expander(f"👤 {nombre} ({len(results)} candidatos)", expanded=True):
                        # Crear opciones para radio con HTML formateado
                        options = []
                        for i, r in enumerate(results[:15]):  # Mostrar hasta 15 resultados
                            label = f"{i+1}. {r['name']} (score: {r['score']})"
                            options.append((label, r['href'], r))
                        
                        if options:
                            # Mostrar información detallada de cada resultado
                            for label, href, r in options:
                                st.markdown(format_result_card(r), unsafe_allow_html=True)
                                col_radio, col_link = st.columns([4, 1])
                                with col_radio:
                                    is_selected = st.radio(
                                        f"Seleccionar {r['name']}:",
                                        options=["Seleccionar este perfil"],
                                        key=f"select_{nombre}_{href}",
                                        label_visibility="collapsed"
                                    )
                                with col_link:
                                    st.markdown(
                                        f'<a href="{href}" target="_blank" style="font-size:0.8rem;">👁️ Ver perfil</a>',
                                        unsafe_allow_html=True
                                    )
                                
                                if is_selected:
                                    st.session_state.selected_profiles[nombre] = href
                                    st.success(f"✅ Seleccionado: {r['name']}")
                                    break
                                st.divider()

        # Extraer CVs de los perfiles seleccionados
        if st.session_state.selected_profiles:
            st.markdown("### 📄 Extraer CVs")
            st.info(f"📌 {len(st.session_state.selected_profiles)} perfiles seleccionados para extraer CV")
            
            # Mostrar resumen de selecciones
            for nombre, url in st.session_state.selected_profiles.items():
                st.caption(f"✅ **{nombre}**: {url}")
            
            if st.button("📥 Extraer CVs seleccionados", type="primary", use_container_width=True):
                progress = st.progress(0)
                status_container = st.container()
                
                for i, (nombre, url) in enumerate(st.session_state.selected_profiles.items()):
                    cached = get_cached_cv(nombre)
                    if cached:
                        st.session_state.cvs[nombre] = cached
                        with status_container:
                            st.info(f"⚡ {nombre}: de caché")
                    else:
                        with status_container:
                            with st.spinner(f"📄 {nombre}..."):
                                cv = st.session_state.scraper.extract_full_cv(
                                    url, debug_mode=st.session_state.debug_mode
                                )
                                if cv:
                                    st.session_state.cvs[nombre] = cv
                                    save_cv_cache(nombre, cv)
                                    st.success(f"✅ {nombre}: {cv.get('headline', 'OK')[:80]}")
                                else:
                                    st.warning(f"⚠️ {nombre}: no se pudo extraer CV")
                    
                    progress.progress((i + 1) / len(st.session_state.selected_profiles))
                    time.sleep(2)
                
                st.balloons()

        # Mostrar CVs
        if st.session_state.cvs:
            with st.expander(f"📄 CVs ({len(st.session_state.cvs)})", expanded=False):
                for nombre, cv in st.session_state.cvs.items():
                    st.markdown(f"**👤 {nombre}**")
                    st.caption(f"🎯 {cv.get('headline', 'N/A')}")
                    st.caption(f"🔗 {cv.get('url', 'N/A')}")
                    for sec, txt in cv.get("sections", {}).items():
                        with st.expander(f"  • {sec}", expanded=False):
                            st.text(txt[:1500])
                    st.divider()

        # STEP 3: Analizar
        st.markdown("### 3️⃣ Analizar con IA")

        if not st.session_state.openai_ok:
            st.warning("⚠️ Configura OpenAI en la sidebar")
        elif not st.session_state.cvs:
            st.info("👉 Busca CVs primero")
        else:
            if st.button("🤖 Analizar con IA", type="primary", use_container_width=True):
                analyzer = CVAnalyzer(api_key=st.session_state.openai_key)
                progress = st.progress(0)
                status_container = st.container()

                for i, (nombre, cv) in enumerate(st.session_state.cvs.items()):
                    with status_container:
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
                            tipo = "🚀 **SPIN-OFF**" if emp.get("es_spinoff") else "🏢 Empresa"
                            st.markdown(f"- {tipo}: **{emp.get('nombre', '?')}** ({emp.get('rol', 'N/A')})")
                            if emp.get("descripcion"):
                                st.caption(f"   _{emp['descripcion']}_")
                    else:
                        st.caption("Sin actividad industrial.")
                    if analisis.get("resumen_industrial"):
                        st.info(analisis["resumen_industrial"])
                    st.divider()

        # STEP 4: Excel final
        st.markdown("### 4️⃣ Generar Excel")

        if st.session_state.analisis:
            if st.button("📊 Generar Excel final", type="primary", use_container_width=True):
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
