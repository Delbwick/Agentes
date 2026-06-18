"""
LinkedIn CV Analyzer - Spin-off Detector
Adaptado para Streamlit Community Cloud (sin openpyxl)
Autor: Asistente IA para Ivan
"""

# ============================================================================
# IMPORTS
# ============================================================================
import os
import re
import json
import time
import pickle
import subprocess
from io import BytesIO
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd
import requests

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

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

# CSS personalizado
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
    .metric-card {
        padding: 1rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# UTILIDADES CHROMIUM (solo si se usa Selenium)
# ============================================================================
def _find_chromium_binary() -> str | None:
    candidates = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
        "/usr/bin/google-chrome",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    try:
        result = subprocess.run(["which", "chromium"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _find_chromedriver() -> str | None:
    candidates = ["/usr/bin/chromedriver", "/usr/lib/chromium/chromedriver"]
    for path in candidates:
        if os.path.exists(path):
            return path
    try:
        result = subprocess.run(["which", "chromedriver"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


# ============================================================================
# CLASE: PROXYCURL API (MÉTODO RECOMENDADO)
# ============================================================================
class ProxycurlAPI:
    """
    API para obtener perfiles de LinkedIn de forma estable.
    Documentación: https://nubela.co/proxycurl/docs
    Plan gratuito: 10 créditos/mes (suficiente para ~5 investigadores).
    """

    BASE_URL = "https://nubela.co/proxycurl/api/v2/linkedin"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}"}
        self.credits_used = 0

    def test_connection(self) -> tuple[bool, str]:
        """Verifica que la API key es válida usando un perfil conocido."""
        try:
            resp = requests.get(
                self.BASE_URL,
                headers=self.headers,
                params={"url": "https://linkedin.com/in/williamhgates"},
                timeout=15
            )
            if resp.status_code == 200:
                self.credits_used += 1
                return True, "✅ API válida. Conexión establecida."
            elif resp.status_code == 401:
                return False, "❌ API key inválida"
            elif resp.status_code == 429:
                return False, "⚠️ Límite de créditos alcanzado este mes"
            elif resp.status_code == 404:
                return False, "⚠️ Endpoint no encontrado (revisa plan)"
            else:
                return False, f"❌ Error {resp.status_code}: {resp.text[:100]}"
        except Exception as e:
            return False, f"❌ Error de conexión: {str(e)[:100]}"

    def get_credits(self) -> int | None:
        """Consulta los créditos disponibles (si el plan lo permite)."""
        try:
            resp = requests.get(
                "https://nubela.co/proxycurl/api/linkedin/profile/resolve",
                headers=self.headers,
                timeout=10
            )
            # Este endpoint no da créditos directamente, pero verifica la key
            return None
        except Exception:
            return None

    def search_person(self, full_name: str, institution: str = "") -> str | None:
        """
        Busca una persona en LinkedIn y devuelve la URL del mejor perfil.
        Coste: 6 créditos por búsqueda (según plan).
        """
        # Construir query más inteligente
        query = full_name
        if institution:
            # Extraer palabras clave relevantes de la institución
            inst_clean = re.sub(r'[;|,()\[\]]', ' ', institution)
            words = [w for w in inst_clean.split() if len(w) > 3]
            # Añadir las 2 más significativas
            if words:
                query += " " + " ".join(words[:2])

        params = {
            "q": query,
            "search_type": "people",
            "page_size": 5,
        }

        try:
            resp = requests.get(
                f"{self.BASE_URL}/person/search",
                headers=self.headers,
                params=params,
                timeout=20
            )
            if resp.status_code == 200:
                self.credits_used += 1
                data = resp.json()
                results = data.get("results", [])
                if results:
                    best = self._best_match(results, full_name, institution)
                    return best.get("profile_url") or best.get("link")
            elif resp.status_code == 404:
                # Endpoint alternativo
                return self._search_person_alt(full_name, institution)
            return None
        except Exception as e:
            print(f"Error en búsqueda: {e}")
            return None

    def _search_person_alt(self, full_name: str, institution: str = "") -> str | None:
        """Búsqueda alternativa usando el endpoint de resolución."""
        params = {
            "q": full_name,
            "search_type": "people",
            "page_size": 1,
        }
        try:
            resp = requests.get(
                "https://nubela.co/proxycurl/api/v2/linkedin/person/search",
                headers=self.headers,
                params=params,
                timeout=20
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                if results:
                    return results[0].get("profile_url") or results[0].get("link")
        except Exception:
            pass
        return None

    def _best_match(self, results: list, target_name: str, institution: str = "") -> dict:
        """Elige el resultado con mayor similitud al nombre objetivo."""
        target = target_name.lower().strip()
        best_score = -1
        best_result = results[0]

        for r in results:
            name = (r.get("full_name") or r.get("name") or "").lower()
            # Score basado en coincidencia de palabras
            target_words = set(target.split())
            name_words = set(name.split())
            score = len(target_words & name_words) * 10

            # Bonus si la institución coincide
            if institution:
                inst_lower = institution.lower()
                headline = (r.get("headline") or "").lower()
                if any(w in headline for w in inst_lower.split() if len(w) > 3):
                    score += 5

            # Bonus por longitud de coincidencia exacta
            common = sum(1 for a, b in zip(target, name) if a == b)
            score += common * 0.1

            if score > best_score:
                best_score = score
                best_result = r
        return best_result

    def get_profile(self, profile_url: str) -> dict | None:
        """
        Obtiene el perfil completo de LinkedIn.
        Coste: 1 crédito.
        """
        params = {
            "url": profile_url,
            "skills": "include",
            "instructions": "include",
            "recommendations": "exclude",
            "personal_contact_number": "exclude",
            "personal_email": "exclude",
            "twitter_profile_id": "exclude",
            "facebook_profile_id": "exclude",
            "github_profile_id": "exclude",
            "use_cache": "if-present",
            "fallback_to_cache": "on-error",
        }

        try:
            resp = requests.get(
                self.BASE_URL,
                headers=self.headers,
                params=params,
                timeout=30
            )
            if resp.status_code == 200:
                self.credits_used += 1
                data = resp.json()
                return self._format_profile(data, profile_url)
            else:
                print(f"Error obteniendo perfil: {resp.status_code} - {resp.text[:100]}")
                return None
        except Exception as e:
            print(f"Error en get_profile: {e}")
            return None

    def _format_profile(self, data: dict, url: str) -> dict:
        """Convierte la respuesta de Proxycurl al formato interno."""
        cv = {
            "url": url,
            "nombre": data.get("full_name", ""),
            "headline": data.get("headline", ""),
            "location": ", ".join(filter(None, [data.get("city"), data.get("country_full_name")])),
            "sections": {},
        }

        # About
        if data.get("summary"):
            cv["sections"]["Acerca de"] = data["summary"]

        # Experiencia
        if data.get("experiences"):
            lines = []
            for exp in data["experiences"]:
                title = exp.get("title", "N/A")
                company = exp.get("company", "N/A")
                start = exp.get("starts_at") or {}
                end = exp.get("ends_at") or {}
                start_str = f"{start.get('month', '?')}/{start.get('year', '?')}"
                if end:
                    end_str = f"{end.get('month', '?')}/{end.get('year', '?')}"
                else:
                    end_str = "Actualidad"
                line = f"• {title} @ {company} ({start_str} - {end_str})"
                if exp.get("description"):
                    desc = exp["description"][:400].replace("\n", " ")
                    line += f"\n  {desc}"
                lines.append(line)
            cv["sections"]["Experiencia"] = "\n".join(lines)

        # Educación
        if data.get("education"):
            lines = []
            for ed in data["education"]:
                degree = ed.get("degree_name", "")
                field = ed.get("field_of_study", "")
                school = ed.get("school", "")
                start = (ed.get("starts_at") or {}).get("year", "?")
                end = (ed.get("ends_at") or {}).get("year", "?")
                degree_str = f"{degree} {field}".strip()
                lines.append(f"• {degree_str} @ {school} ({start}-{end})")
            cv["sections"]["Educación"] = "\n".join(lines)

        # Publicaciones
        if data.get("publications"):
            lines = []
            for pub in data["publications"][:10]:  # Limitar a 10
                title = pub.get("name") or pub.get("title", "")
                publisher = pub.get("publisher", "")
                date = pub.get("published_date") or pub.get("published_at", "")
                lines.append(f"• {title} ({publisher}, {date})")
            cv["sections"]["Publicaciones"] = "\n".join(lines)

        # Patentes
        if data.get("patents"):
            lines = []
            for pat in data["patents"][:10]:
                title = pat.get("title", "")
                num = pat.get("number", "")
                lines.append(f"• {title} ({num})")
            cv["sections"]["Patentes"] = "\n".join(lines)

        # Proyectos
        if data.get("projects"):
            lines = []
            for proj in data["projects"][:10]:
                title = proj.get("title", "")
                desc = (proj.get("description") or "")[:200]
                lines.append(f"• {title}: {desc}")
            cv["sections"]["Proyectos"] = "\n".join(lines)

        # Idiomas
        if data.get("languages"):
            cv["sections"]["Idiomas"] = ", ".join(data["languages"])

        # Skills
        if data.get("skills"):
            cv["sections"]["Skills"] = ", ".join(data["skills"][:30])

        # Intereses
        if data.get("interests"):
            cv["sections"]["Intereses"] = ", ".join(data["interests"][:20])

        # Cargos (para análisis industrial)
        cv["cargos_actuales"] = [
            e for e in data.get("experiences", [])
            if not e.get("ends_at")
        ]
        cv["todos_cargos"] = data.get("experiences", [])

        return cv

    def close(self):
        """No hay sesión que cerrar en API REST."""
        pass


# ============================================================================
# CLASE: LINKEDIN SCRAPER (alternativa con Selenium)
# ============================================================================
class LinkedInCVScraper:
    """Scraper de CVs con Selenium. Alternativa a Proxycurl."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None
        self.wait = None
        self._cookies = []

    def start(self) -> tuple[bool, str]:
        try:
            opts = Options()
            if self.headless:
                opts.add_argument("--headless=new")
            binary = _find_chromium_binary()
            if binary:
                opts.binary_location = binary
            else:
                return False, "❌ Chromium no encontrado"

            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--window-size=1920,1080")
            opts.add_argument("--single-process")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_argument(
                "--user-agent=Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option("useAutomationExtension", False)

            driver_path = _find_chromedriver()
            service = Service(driver_path) if driver_path else Service()
            self.driver = webdriver.Chrome(service=service, options=opts)
            self.wait = WebDriverWait(self.driver, 20)
            return True, "✅ Chromium iniciado"
        except Exception as e:
            return False, f"❌ Error: {str(e)[:200]}"

    def set_cookies_from_text(self, cookies_text: str) -> bool:
        try:
            cookies = json.loads(cookies_text)
            if isinstance(cookies, list):
                self._cookies = cookies
                return True
        except json.JSONDecodeError:
            pass
        return False

    def inject_cookies(self) -> bool:
        if not self._cookies:
            return False
        try:
            self.driver.get("https://www.linkedin.com/feed/")
            time.sleep(2)
            for c in self._cookies:
                cookie = {
                    "name": c.get("name"),
                    "value": c.get("value"),
                    "domain": c.get("domain", ".linkedin.com"),
                    "path": c.get("path", "/"),
                }
                if "linkedin" not in cookie["domain"]:
                    continue
                try:
                    self.driver.add_cookie(cookie)
                except Exception:
                    pass
            self.driver.refresh()
            time.sleep(4)
            return "feed" in self.driver.current_url.lower()
        except Exception:
            return False

    def search_person(self, full_name: str, institution: str = "", orcid: str = "") -> str | None:
        query = full_name
        if institution:
            query += f" {re.sub(r'[;|]', ' ', institution).strip()}"
        search_url = (
            f"https://www.linkedin.com/search/results/people/"
            f"?keywords={requests.utils.quote(query)}&origin=GLOBAL_SEARCH_HEADER"
        )
        self.driver.get(search_url)
        time.sleep(5)
        if "challenge" in self.driver.current_url.lower():
            raise RuntimeError("LinkedIn challenge/captcha detectado")
        try:
            first = self.wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//ul[contains(@class,'reusable-search__result-container')]"
                               "//a[contains(@class,'app-aware-link') and contains(@href,'/in/')]")
                )
            )
            return first.get_attribute("href").split("?")[0]
        except TimeoutException:
            return None

    def _scroll_full_page(self, max_scrolls: int = 15, pause: float = 1.0):
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        for _ in range(max_scrolls):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    def _safe_text(self, xpath: str, default: str = "") -> str:
        try:
            return self.driver.find_element(By.XPATH, xpath).text.strip()
        except NoSuchElementException:
            return default

    def extract_full_cv(self, profile_url: str) -> dict:
        self.driver.get(profile_url)
        time.sleep(4)
        self._scroll_full_page()
        cv = {"url": profile_url, "sections": {}}
        cv["nombre"] = self._safe_text("//h1")
        cv["headline"] = self._safe_text(
            "//div[contains(@class,'text-body-medium') and contains(@class,'break-words')]"
        )
        sections_xpaths = {
            "Acerca de": "//section[contains(@id,'about')]",
            "Experiencia": "//section[contains(@id,'experience')]",
            "Educación": "//section[contains(@id,'education')]",
            "Publicaciones": "//section[contains(@id,'publications')]",
            "Patentes": "//section[contains(@id,'patents')]",
            "Proyectos": "//section[contains(@id,'projects')]",
        }
        for nombre_seccion, xpath in sections_xpaths.items():
            try:
                section = self.driver.find_element(By.XPATH, xpath)
                cv["sections"][nombre_seccion] = section.text.strip()
            except NoSuchElementException:
                pass
        if not cv["sections"]:
            try:
                cv["texto_completo"] = self.driver.find_element(By.XPATH, "//main").text.strip()
            except Exception:
                cv["texto_completo"] = ""
        return cv

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None


# ============================================================================
# CLASE: CV ANALYZER (OpenAI)
# ============================================================================
class CVAnalyzer:
    """Analiza CVs con OpenAI para extraer empresas y spin-offs."""

    SYSTEM_PROMPT = """Eres un analista experto en transferencia de tecnología y spin-offs académicas españolas.
Analiza el CV de un investigador y extrae:
1. Lista de EMPRESAS privadas en las que ha trabajado (excluyendo universidades y OPIs como CSIC).
2. SPIN-OFFs que haya fundado, cofundado o asesorado (empresas nacidas de la universidad).
3. Para cada empresa/spin-off, una descripción breve (1-2 frases) de su actividad.

Responde SOLO en JSON con este formato exacto:
{
  "empresas": [
    {"nombre": "...", "rol": "...", "descripcion": "...", "es_spinoff": true/false}
  ],
  "resumen_industrial": "Párrafo de 2-3 líneas resumiendo su actividad industrial y spin-offs"
}
Si no hay actividad industrial, devuelve:
{"empresas": [], "resumen_industrial": "Sin actividad industrial relevante detectada en el CV."}
"""

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def analizar_cv(self, nombre: str, cv_text: str) -> dict:
        prompt = f"""Investigador: {nombre}

CV extraído de LinkedIn:
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
            return {"empresas": [], "resumen_industrial": f"Error en análisis: {e}"}


def formatear_para_excel(nombre_original: str, cv: dict, analisis: dict) -> str:
    """Formatea el resultado final para la celda INDUSTRIAL info."""
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
def _cv_cache_path(nombre: str) -> Path:
    safe = re.sub(r'[^\w\-]', '_', nombre)
    return CACHE_DIR / f"{safe}.pkl"


def get_cached_cv(nombre: str) -> dict | None:
    path = _cv_cache_path(nombre)
    if path.exists():
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None
    return None


def save_cv_cache(nombre: str, cv: dict):
    with open(_cv_cache_path(nombre), "wb") as f:
        pickle.dump(cv, f)


def read_excel_safe(uploaded_file) -> pd.DataFrame:
    """Lee Excel intentando varios motores (sin openpyxl obligatorio)."""
    # Intentar con calamine (rápido y ligero)
    try:
        return pd.read_excel(uploaded_file, engine='calamine')
    except Exception:
        pass
    # Fallback a openpyxl si está disponible
    try:
        uploaded_file.seek(0)
        return pd.read_excel(uploaded_file, engine='openpyxl')
    except Exception:
        pass
    # Fallback a xlrd (solo .xls)
    try:
        uploaded_file.seek(0)
        return pd.read_excel(uploaded_file, engine='xlrd')
    except Exception as e:
        raise RuntimeError(
            f"No se pudo leer el Excel. Instala python-calamine o openpyxl. Error: {e}"
        )


# ============================================================================
# STREAMLIT APP
# ============================================================================
def main():
    # --- Estado de sesión ---
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
    if "modo_scraper" not in st.session_state:
        st.session_state.modo_scraper = "proxycurl"
    if "proxycurl_api" not in st.session_state:
        st.session_state.proxycurl_api = None

    # ========================================================================
    # SIDEBAR
    # ========================================================================
    with st.sidebar:
        st.markdown("## ⚙️ Configuración")

        # --- Modo de scraping ---
        st.markdown("### 🔍 Método de obtención de CVs")
        modo = st.radio(
            "Elige el método:",
            ["🌐 Proxycurl API (recomendado)", "🤖 Selenium + Chromium"],
            index=0,
            help="Proxycurl es más estable en Streamlit Cloud. Selenium requiere Chromium instalado."
        )
        st.session_state.modo_scraper = "proxycurl" if "Proxycurl" in modo else "selenium"

        st.divider()

        # --- Configuración según modo ---
        if st.session_state.modo_scraper == "proxycurl":
            st.markdown("### 🌐 Proxycurl API")
            st.markdown(
                '<div class="info-box">📌 Obtén tu API key gratuita en '
                '<a href="https://nubela.co/proxycurl" target="_blank">nubela.co/proxycurl</a><br>'
                'Plan gratuito: <b>10 créditos/mes</b> (~5 investigadores)</div>',
                unsafe_allow_html=True
            )

            # Intentar leer de secrets
            default_key = ""
            try:
                default_key = st.secrets.get("PROXYCURL_API_KEY", "")
            except Exception:
                pass

            proxycurl_key = st.text_input(
                "API Key Proxycurl",
                type="password",
                value=default_key,
                help="Se guarda solo en esta sesión. También puedes usar st.secrets"
            )

            if proxycurl_key:
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔍 Verificar API"):
                        with st.spinner("Verificando..."):
                            api = ProxycurlAPI(proxycurl_key)
                            ok, msg = api.test_connection()
                            if ok:
                                st.success(msg)
                                st.session_state.linkedin_ok = True
                                st.session_state.proxycurl_api = api
                            else:
                                st.error(msg)
                                st.session_state.linkedin_ok = False
                with col2:
                    if st.session_state.linkedin_ok and st.session_state.proxycurl_api:
                        st.success("🟢 Conectado")
                    else:
                        st.warning("🟡 Pendiente")
            else:
                st.info("👉 Introduce tu API key para continuar")

        else:  # Selenium
            st.markdown("### 🤖 LinkedIn + Selenium")
            st.markdown(
                '<div class="warning-box">⚠️ <b>Importante:</b> LinkedIn bloquea IPs de '
                'Streamlit Cloud. Si falla, usa Proxycurl API.</div>',
                unsafe_allow_html=True
            )

            st.caption("Pega las cookies de LinkedIn (formato JSON)")
            cookies_text = st.text_area(
                "Cookies LinkedIn",
                height=150,
                help="Exporta cookies desde tu navegador (extensión EditThisCookie)",
                label_visibility="collapsed"
            )

            if cookies_text and st.button("🔑 Cargar cookies"):
                with st.spinner("Iniciando Chromium..."):
                    scraper = LinkedInCVScraper(headless=True)
                    ok, msg = scraper.start()
                    if not ok:
                        st.error(msg)
                    else:
                        st.session_state.scraper = scraper
                        if scraper.set_cookies_from_text(cookies_text):
                            if scraper.inject_cookies():
                                st.success("✅ Sesión LinkedIn activa")
                                st.session_state.linkedin_ok = True
                            else:
                                st.error("❌ Cookies inválidas o sesión expirada")
                        else:
                            st.error("❌ No se pudo parsear el formato de cookies")

        st.divider()

        # --- OpenAI ---
        st.markdown("### 🤖 OpenAI API")
        default_openai = ""
        try:
            default_openai = st.secrets.get("OPENAI_API_KEY", "")
        except Exception:
            pass

        api_key = st.text_input(
            "API Key OpenAI",
            type="password",
            value=default_openai,
            help="Para analizar CVs con IA (GPT-4o-mini)"
        )

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
        st.write(f"🔗 LinkedIn: {'🟢 OK' if st.session_state.linkedin_ok else '🟡 No conectado'}")
        st.write(f"🤖 OpenAI: {'🟢 OK' if st.session_state.openai_ok else '🟡 Pendiente'}")
        st.write(f"👥 CVs extraídos: {len(st.session_state.cvs)}")
        st.write(f"🏭 Análisis hechos: {len(st.session_state.analisis)}")

        if st.session_state.modo_scraper == "proxycurl" and st.session_state.proxycurl_api:
            st.write(f"💳 Créditos usados: {st.session_state.proxycurl_api.credits_used}")

        st.divider()

        if st.button("🔄 Reiniciar sesión"):
            if st.session_state.scraper:
                st.session_state.scraper.close()
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    # ========================================================================
    # MAIN CONTENT
    # ========================================================================
    st.markdown('<p class="big-header">🚀 Spin-off Detector</p>', unsafe_allow_html=True)
    st.markdown(
        "Analiza investigadores a partir de su CV de LinkedIn y detecta "
        "**empresas** y **spin-offs** en las que han participado."
    )

    # --- STEP 1: Cargar Excel ---
    st.markdown("### 1️⃣ Cargar Excel de investigadores")
    uploaded = st.file_uploader(
        "Sube el Excel con los investigadores",
        type=["xlsx", "xls"],
        help="Columnas esperadas: Person_Name, Institution, ORCID, INDUSTRIAL info"
    )

    if uploaded is not None:
        try:
            df = read_excel_safe(uploaded)
            st.session_state.df = df
        except Exception as e:
            st.error(f"❌ Error leyendo Excel: {e}")
            st.stop()

        # Detectar columnas
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

        with st.expander("👀 Vista previa del Excel"):
            st.dataframe(df, use_container_width=True)

        if "nombre" not in col_map:
            st.error("❌ No se detectó la columna de nombres.")
            st.stop()

        col_nombre = col_map["nombre"]
        col_inst = col_map.get("institucion")
        col_orcid = col_map.get("orcid")

        # --- STEP 2: Seleccionar y buscar CVs ---
        st.markdown("### 2️⃣ Buscar CVs en LinkedIn")

        if not st.session_state.linkedin_ok:
            st.warning("⚠️ Configura LinkedIn en la sidebar primero")
            seleccion = []
        else:
            seleccion = st.multiselect(
                "Selecciona investigadores a analizar",
                df[col_nombre].tolist(),
                default=df[col_nombre].tolist()[:3],
                help="Empieza con pocos para probar (Proxycurl tiene límite de créditos)"
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
                # Comprobar caché primero
                cached = get_cached_cv(nombre)
                if cached:
                    st.session_state.cvs[nombre] = cached
                    with status_container:
                        st.info(f"⚡ {nombre}: recuperado de caché")
                    progress.progress((i + 1) / len(seleccion))
                    continue

                inst = ""
                if col_inst:
                    inst = str(df[df[col_nombre] == nombre][col_inst].iloc[0])
                orcid = ""
                if col_orcid:
                    orcid = str(df[df[col_nombre] == nombre][col_orcid].iloc[0])

                try:
                    with status_container:
                        with st.spinner(f"🔍 Buscando {nombre}..."):
                            if st.session_state.modo_scraper == "proxycurl":
                                api = st.session_state.proxycurl_api
                                url = api.search_person(nombre, inst)
                                if url:
                                    with st.spinner(f"📄 Extrayendo CV de {nombre}..."):
                                        cv = api.get_profile(url)
                                        if cv:
                                            st.session_state.cvs[nombre] = cv
                                            save_cv_cache(nombre, cv)
                                            st.success(
                                                f"✅ {nombre}: {cv.get('headline', 'OK')[:80]}"
                                            )
                                        else:
                                            st.warning(f"⚠️ {nombre}: URL encontrada pero perfil vacío")
                                else:
                                    st.warning(f"❌ {nombre}: no encontrado en LinkedIn")
                            else:
                                scraper = st.session_state.scraper
                                url = scraper.search_person(nombre, inst, orcid)
                                if url:
                                    cv = scraper.extract_full_cv(url)
                                    st.session_state.cvs[nombre] = cv
                                    save_cv_cache(nombre, cv)
                                    st.success(f"✅ {nombre}: {cv.get('headline', 'OK')[:80]}")
                                else:
                                    st.warning(f"❌ {nombre}: no encontrado")
                                time.sleep(3)
                except Exception as e:
                    with status_container:
                        st.error(f"❌ Error con {nombre}: {str(e)[:100]}")

                progress.progress((i + 1) / len(seleccion))

            st.balloons()

        # Mostrar CVs extraídos
        if st.session_state.cvs:
            with st.expander(f"📄 CVs extraídos ({len(st.session_state.cvs)})", expanded=False):
                for nombre, cv in st.session_state.cvs.items():
                    st.markdown(f"**👤 {nombre}**")
                    st.caption(f"🎯 {cv.get('headline', 'N/A')}")
                    st.caption(f"🔗 {cv.get('url', 'N/A')}")
                    for sec, txt in cv.get("sections", {}).items():
                        with st.expander(f"  • {sec}", expanded=False):
                            st.text(txt[:1500])
                    st.divider()

        # --- STEP 3: Analizar con IA ---
        st.markdown("### 3️⃣ Analizar CVs con IA")

        if not st.session_state.openai_ok:
            st.warning("⚠️ Configura la API Key de OpenAI en la sidebar.")
        elif not st.session_state.cvs:
            st.info("👉 Primero busca los CVs en LinkedIn")
        else:
            if st.button("🤖 Analizar con IA", type="primary", use_container_width=True):
                analyzer = CVAnalyzer(api_key=st.session_state.openai_key)
                progress = st.progress(0)
                status_container = st.container()

                for i, (nombre, cv) in enumerate(st.session_state.cvs.items()):
                    with status_container:
                        with st.spinner(f"🧠 Analizando {nombre}..."):
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
            with st.expander(f"🏭 Análisis industriales ({len(st.session_state.analisis)})", expanded=False):
                for nombre, analisis in st.session_state.analisis.items():
                    st.markdown(f"**👤 {nombre}**")
                    if analisis.get("empresas"):
                        for emp in analisis["empresas"]:
                            tipo = "🚀 **SPIN-OFF**" if emp.get("es_spinoff") else "🏢 Empresa"
                            st.markdown(f"- {tipo}: **{emp.get('nombre', '?')}** ({emp.get('rol', 'N/A')})")
                            if emp.get("descripcion"):
                                st.caption(f"   _{emp['descripcion']}_")
                    else:
                        st.caption("Sin actividad industrial detectada.")
                    if analisis.get("resumen_industrial"):
                        st.info(analisis["resumen_industrial"])
                    st.divider()

        # --- STEP 4: Generar Excel final ---
        st.markdown("### 4️⃣ Generar Excel con INDUSTRIAL info")

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

                # Usar xlsxwriter en lugar de openpyxl
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_out.to_excel(writer, index=False, sheet_name='Sheet1')
                    workbook = writer.book
                    worksheet = writer.sheets['Sheet1']

                    # Auto-ajustar anchos de columna
                    for i, col in enumerate(df_out.columns):
                        max_len = max(
                            df_out[col].astype(str).map(len).max() if len(df_out) > 0 else 0,
                            len(str(col))
                        )
                        # Limitar ancho máximo a 80 para celdas muy largas
                        worksheet.set_column(i, i, min(max_len + 2, 80))

                    # Formato especial para la columna INDUSTRIAL info
                    if col_industrial in df_out.columns:
                        text_format = workbook.add_format({'text_wrap': True, 'valign': 'top'})
                        col_idx = df_out.columns.get_loc(col_industrial)
                        worksheet.set_column(col_idx, col_idx, 80, text_format)

                buffer.seek(0)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")

                st.download_button(
                    label="⬇️ Descargar Excel actualizado",
                    data=buffer,
                    file_name=f"investigadores_spinoffs_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                st.success("✅ Excel generado correctamente")

                # Estadísticas
                st.markdown("### 📈 Resumen final")
                total_emp = sum(len(a.get("empresas", [])) for a in st.session_state.analisis.values())
                total_spin = sum(
                    sum(1 for e in a.get("empresas", []) if e.get("es_spinoff"))
                    for a in st.session_state.analisis.values()
                )
                c1, c2, c3 = st.columns(3)
                c1.metric("👥 Investigadores", len(st.session_state.analisis))
                c2.metric("🏢 Empresas detectadas", total_emp)
                c3.metric("🚀 Spin-offs", total_spin)

        elif st.session_state.cvs:
            st.info("👉 Pulsa 'Analizar con IA' para continuar")


if __name__ == "__main__":
    main()
