"""
LinkedIn CV Analyzer - Spin-off Detector
Versión con DEBUG completo de Puppeteer
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
    .debug-box {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
        font-family: monospace;
        font-size: 0.85rem;
        max-height: 600px;
        overflow-y: auto;
        white-space: pre-wrap;
        word-wrap: break-word;
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

    def run_puppeteer(self, script_code: str, cookies: list = None) -> dict | None:
        payload = {"code": script_code, "context": {}}
        if cookies:
            payload["cookies"] = cookies
        try:
            resp = requests.post(
                f"{self.base_url}/function",
                params={"token": self.token},
                json=payload,
                timeout=90
            )
            self.credits_used += 1
            if resp.status_code == 200:
                return resp.json()
            else:
                return None
        except Exception as e:
            print(f"Error en run_puppeteer: {e}")
            return None


# ============================================================================
# CLASE: LINKEDIN SCRAPER
# ============================================================================
class LinkedInScraper:
    def __init__(self, api: BrowserlessAPI, cookies: list):
        self.api = api
        self.cookies = cookies
        self.debug_info = {}  # Almacena info de debug

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
            soup.select_one("meta[name='linkedin-knowledge-graph-person-id']"),
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

    def search_person(self, full_name: str, institution: str = "", debug_mode: bool = False) -> str | None:
        """Busca persona con debug completo."""
        self.debug_info = {}  # Reset debug info
        
        query = full_name
        if institution:
            inst_clean = re.sub(r'[;|,()\[\]]', ' ', institution)
            words = [w for w in inst_clean.split() if len(w) > 3]
            if words:
                query += " " + " ".join(words[:2])

        # Script Puppeteer MEJORADO con más logging
        puppeteer_code = f"""
        module.exports = async ({{ page }}) => {{
            const searchUrl = "https://www.linkedin.com/search/results/people/?keywords={requests.utils.quote(query)}&origin=GLOBAL_SEARCH_HEADER";
            
            const debug = {{
                searchUrl,
                steps: [],
                errors: [],
                results: [],
                finalUrl: '',
                pageTitle: '',
                pageContent: {{}}
            }};
            
            try {{
                debug.steps.push("1. Navegando a URL de búsqueda...");
                await page.goto(searchUrl, {{ waitUntil: 'networkidle2', timeout: 30000 }});
                debug.finalUrl = page.url();
                debug.pageTitle = await page.title();
                debug.steps.push("2. URL cargada: " + debug.finalUrl);
                
                // Esperar a que carguen los resultados
                debug.steps.push("3. Esperando resultados...");
                const resultsContainer = await page.waitForSelector('ul.reusable-search__result-container, a.app-aware-link[href*="/in/"]', {{ timeout: 10000 }}).catch(() => null);
                
                if (!resultsContainer) {{
                    debug.steps.push("⚠️ No se encontró el contenedor de resultados");
                    debug.errors.push("No results container found");
                }} else {{
                    debug.steps.push("4. Contenedor de resultados encontrado");
                }}
                
                // Pequeña espera adicional
                await new Promise(r => setTimeout(r, 2000));
                
                // Verificar si hay redirect a login
                const currentUrl = page.url();
                if (currentUrl.includes('login') || currentUrl.includes('checkpoint')) {{
                    debug.steps.push("❌ Redirigido a login/challenge");
                    debug.errors.push("Redirected to login");
                    return {{ debug, results: [], url: currentUrl }};
                }}
                
                // Extraer resultados
                debug.steps.push("5. Extrayendo resultados...");
                const results = await page.evaluate(() => {{
                    const links = Array.from(document.querySelectorAll('a.app-aware-link[href*="/in/"]'));
                    debug.steps.push(`Encontrados ${{links.length}} enlaces`);
                    
                    return links.slice(0, 10).map((link, index) => {{
                        const href = link.getAttribute('href');
                        const nameSpan = link.querySelector("span[aria-hidden='true']");
                        const name = nameSpan ? nameSpan.innerText.trim() : '';
                        const parent = link.closest('li');
                        const subtitle = parent ? parent.innerText : '';
                        const headline = link.querySelector('.entity-result__title-line')?.innerText || '';
                        
                        return {{ 
                            index,
                            href: href ? href.split('?')[0] : '',
                            name,
                            headline,
                            subtitle: subtitle.substring(0, 200)
                        }};
                    }});
                }});
                
                debug.results = results;
                debug.steps.push(`6. Extraídos ${{results.length}} resultados`);
                debug.pageContent = {{
                    hasResults: results.length > 0,
                    totalLinks: document.querySelectorAll('a').length,
                    bodyLength: document.body.innerText.length
                }};
                
            }} catch (error) {{
                debug.steps.push("❌ Error: " + error.message);
                debug.errors.push(error.message);
            }}
            
            return {{ debug, results, url: page.url() }};
        }};
        """

        result = self.api.run_puppeteer(puppeteer_code, cookies=self.cookies)
        
        # Guardar debug info
        if result and result.get("debug"):
            self.debug_info = result["debug"]
        
        if debug_mode and self.debug_info:
            st.session_state.last_search_debug = self.debug_info
        
        if not result:
            if debug_mode:
                st.error("❌ Puppeteer no devolvió respuesta")
            return self._search_person_fallback(full_name, institution)

        results = result.get("results", [])
        if not results:
            if debug_mode:
                st.warning(f"⚠️ No se encontraron resultados para '{full_name}'")
                if self.debug_info.get("errors"):
                    st.error(f"Errores: {', '.join(self.debug_info['errors'])}")
            return None

        # Elegir el mejor resultado
        target_words = set(full_name.lower().split())
        best_url = None
        best_score = -1

        for r in results:
            href = r.get("href", "")
            if "/in/" not in href:
                continue

            name = r.get("name", "").lower()
            name_words = set(name.split())
            score = len(target_words & name_words) * 10

            if institution:
                subtitle = r.get("subtitle", "").lower()
                inst_lower = institution.lower()
                if any(w in subtitle for w in inst_lower.split() if len(w) > 3):
                    score += 5

            if score > best_score:
                best_score = score
                best_url = href

        if debug_mode:
            st.success(f"✅ Encontrado: {best_url} (score: {best_score})")
            st.json(results[:3])  # Mostrar top 3 resultados

        return best_url

    def _search_person_fallback(self, full_name: str, institution: str = "") -> str | None:
        """Fallback: búsqueda con /content."""
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

        response = self.api.get_content(search_url, cookies=self.cookies)
        if not response["ok"] or not response["html"]:
            return None

        soup = BeautifulSoup(response["html"], "html.parser")
        links = soup.select("a[href*='/in/']")

        if not links:
            return None

        target_words = set(full_name.lower().split())
        best_url = None
        best_score = -1

        for link in links[:10]:
            href = link.get("href", "").split("?")[0]
            if "/in/" not in href:
                continue

            name_span = link.select_one("span[aria-hidden='true']")
            if name_span:
                name = name_span.get_text().lower()
                name_words = set(name.split())
                score = len(target_words & name_words) * 10

                if institution:
                    parent = link.find_parent("li")
                    if parent:
                        text = parent.get_text().lower()
                        inst_lower = institution.lower()
                        if any(w in text for w in inst_lower.split() if len(w) > 3):
                            score += 5

                if score > best_score:
                    best_score = score
                    best_url = href

        return best_url

    def extract_full_cv(self, profile_url: str, debug_mode: bool = False) -> dict | None:
        """Extrae CV completo usando Puppeteer con scroll."""
        puppeteer_code = f"""
        module.exports = async ({{ page }}) => {{
            const debug = {{ steps: [] }};
            
            try {{
                debug.steps.push("Navegando al perfil...");
                await page.goto('{profile_url}', {{ waitUntil: 'networkidle2', timeout: 30000 }});
                
                debug.steps.push("Esperando h1...");
                await page.waitForSelector('h1', {{ timeout: 10000 }}).catch(() => {{
                    debug.steps.push("⚠️ No se encontró h1");
                }});
                
                debug.steps.push("Haciendo scroll...");
                await page.evaluate(async () => {{
                    await new Promise((resolve) => {{
                        let totalHeight = 0;
                        const distance = 300;
                        const timer = setInterval(() => {{
                            const scrollHeight = document.body.scrollHeight;
                            window.scrollBy(0, distance);
                            totalHeight += distance;
                            if (totalHeight >= scrollHeight) {{
                                clearInterval(timer);
                                resolve();
                            }}
                        }}, 100);
                    }});
                }});
                
                await new Promise(r => setTimeout(r, 2000));
                await page.evaluate(() => window.scrollTo(0, 0));
                await new Promise(r => setTimeout(r, 500));
                
                debug.steps.push("Extrayendo datos...");
                const data = await page.evaluate(() => {{
                    const getText = (sel) => {{
                        const el = document.querySelector(sel);
                        return el ? el.innerText.trim() : '';
                    }};
                    
                    return {{
                        nombre: getText('h1'),
                        headline: getText('.text-body-medium.break-words'),
                        ubicacion: getText('.text-body-small.inline'),
                        about: getText('section#about') || '',
                        experience: getText('section#experience') || '',
                        education: getText('section#education') || '',
                        publications: getText('section#publications') || '',
                        patents: getText('section#patents') || '',
                        projects: getText('section#projects') || '',
                        languages: getText('section#languages') || '',
                        honors: getText('section#honors') || '',
                        fullText: document.querySelector('main') ? document.querySelector('main').innerText : document.body.innerText
                    }};
                }});
                
                debug.steps.push("Extracción completada");
                return {{ debug, data }};
                
            }} catch (error) {{
                debug.steps.push("❌ Error: " + error.message);
                return {{ debug, data: null, error: error.message }};
            }}
        }};
        """

        result = self.api.run_puppeteer(puppeteer_code, cookies=self.cookies)

        if debug_mode and result and result.get("debug"):
            st.session_state.last_cv_debug = result["debug"]
            if result.get("debug", {}).get("steps"):
                st.info("📋 Pasos de extracción:\n" + "\n".join(result["debug"]["steps"]))

        if not result:
            return self._extract_simple(profile_url)

        if result.get("error"):
            if debug_mode:
                st.error(f"Error en Puppeteer: {result['error']}")
            return self._extract_simple(profile_url)

        data = result.get("data")
        if not data:
            return None

        cv = {
            "url": profile_url,
            "nombre": data.get("nombre", ""),
            "headline": data.get("headline", ""),
            "ubicacion": data.get("ubicacion", ""),
            "sections": {},
        }

        sections = {
            "Acerca de": data.get("about"),
            "Experiencia": data.get("experience"),
            "Educación": data.get("education"),
            "Publicaciones": data.get("publications"),
            "Patentes": data.get("patents"),
            "Proyectos": data.get("projects"),
            "Idiomas": data.get("languages"),
            "Premios": data.get("honors"),
        }

        for nombre, texto in sections.items():
            if texto and len(texto) > 10:
                cv["sections"][nombre] = texto

        if not cv["sections"] and data.get("fullText"):
            cv["texto_completo"] = data["fullText"]

        return cv

    def _extract_simple(self, profile_url: str) -> dict | None:
        response = self.api.get_content(profile_url, cookies=self.cookies)

        if not response["ok"] or not response["html"]:
            return None

        soup = BeautifulSoup(response["html"], "html.parser")
        cv = {"url": profile_url, "sections": {}}

        h1 = soup.select_one("h1")
        cv["nombre"] = h1.get_text().strip() if h1 else ""

        headline = soup.select_one(".text-body-medium.break-words")
        cv["headline"] = headline.get_text().strip() if headline else ""

        main = soup.select_one("main")
        if main:
            cv["texto_completo"] = main.get_text(separator="\n", strip=True)
        else:
            cv["texto_completo"] = soup.get_text(separator="\n", strip=True)

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
    if "last_search_debug" not in st.session_state:
        st.session_state.last_search_debug = {}
    if "last_cv_debug" not in st.session_state:
        st.session_state.last_cv_debug = {}

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
            help="Muestra información detallada de Puppeteer en cada búsqueda"
        )
        st.session_state.debug_mode = debug_mode

        if debug_mode:
            st.info("💡 El debug se mostrará después de cada búsqueda")

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

                    li_at = next((c for c in cookies if c["name"] == "li_at"), None)
                    if li_at:
                        st.success(f"✅ Cookie 'li_at' encontrada (longitud: {len(li_at['value'])})")
                    else:
                        st.warning("⚠️ Cookie 'li_at' NO encontrada.")

                    if st.session_state.api:
                        st.session_state.scraper = LinkedInScraper(
                            st.session_state.api,
                            cookies
                        )
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

        # STEP 2: Buscar CVs
        st.markdown("### 2️⃣ Buscar CVs en LinkedIn")

        if not st.session_state.linkedin_ok:
            st.warning("⚠️ Primero carga las cookies y pulsa '🧪 Testear sesión LinkedIn'")
            seleccion = []
        else:
            seleccion = st.multiselect(
                "Selecciona investigadores",
                df[col_nombre].tolist(),
                default=df[col_nombre].tolist()[:1]  # Solo 1 por defecto para debug
            )

        if st.button(
            "🔍 Buscar y extraer CVs",
            type="primary",
            use_container_width=True,
            disabled=len(seleccion) == 0 or not st.session_state.linkedin_ok
        ):
            progress = st.progress(0)
            status_container = st.container()

            for i, nombre in enumerate(seleccion):
                cached = get_cached_cv(nombre)
                if cached:
                    st.session_state.cvs[nombre] = cached
                    with status_container:
                        st.info(f"⚡ {nombre}: de caché")
                    progress.progress((i + 1) / len(seleccion))
                    continue

                inst = ""
                if col_inst:
                    inst = str(df[df[col_nombre] == nombre][col_inst].iloc[0])

                try:
                    with status_container:
                        with st.spinner(f"🔍 {nombre}..."):
                            url = st.session_state.scraper.search_person(
                                nombre, inst, debug_mode=st.session_state.debug_mode
                            )

                    # Mostrar debug de búsqueda si está activado
                    if st.session_state.debug_mode and hasattr(st.session_state, 'last_search_debug'):
                        with st.expander("🐛 Debug de búsqueda Puppeteer", expanded=True):
                            debug = st.session_state.last_search_debug
                            if debug.get("steps"):
                                st.markdown("**📋 Pasos ejecutados:**")
                                for step in debug["steps"]:
                                    st.text(step)
                            if debug.get("errors"):
                                st.error(f"**❌ Errores:** {', '.join(debug['errors'])}")
                            st.markdown(f"**🔗 URL final:** {debug.get('finalUrl', 'N/A')}")
                            st.markdown(f"**📄 Título:** {debug.get('pageTitle', 'N/A')}")
                            if debug.get("results"):
                                st.markdown(f"**📊 Resultados encontrados:** {len(debug['results'])}")
                                st.json(debug["results"][:5])
                            if debug.get("pageContent"):
                                st.json(debug["pageContent"])

                    if url:
                        with status_container:
                            with st.spinner(f"📄 {nombre}..."):
                                cv = st.session_state.scraper.extract_full_cv(
                                    url, debug_mode=st.session_state.debug_mode
                                )
                                if cv:
                                    st.session_state.cvs[nombre] = cv
                                    save_cv_cache(nombre, cv)
                                    st.success(f"✅ {nombre}: {cv.get('headline', 'OK')[:80]}")
                                    
                                    # Mostrar debug de CV si está activado
                                    if st.session_state.debug_mode and hasattr(st.session_state, 'last_cv_debug'):
                                        with st.expander("🐛 Debug de extracción de CV", expanded=False):
                                            if st.session_state.last_cv_debug.get("steps"):
                                                st.markdown("**📋 Pasos:**")
                                                for step in st.session_state.last_cv_debug["steps"]:
                                                    st.text(step)
                                else:
                                    st.warning(f"⚠️ {nombre}: no se pudo extraer CV")
                    else:
                        with status_container:
                            st.warning(f"❌ {nombre}: no encontrado")
                except Exception as e:
                    with status_container:
                        st.error(f"❌ {nombre}: {str(e)[:100]}")

                progress.progress((i + 1) / len(seleccion))
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
