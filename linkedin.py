"""
LinkedIn CV Analyzer - Spin-off Detector
Adaptado para Streamlit Community Cloud (GitHub)
Autor: Asistente IA para Ivan
"""

# ============================================================================
# IMPORTS
# ============================================================================
import os
import re
import json
import time
import base64
import pickle
import shutil
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
st.set_page_config(
    page_title="🔬 Spin-off Detector",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .status-ok { color: #28a745; font-weight: bold; }
    .status-warn { color: #ffc107; font-weight: bold; }
    .status-err { color: #dc3545; font-weight: bold; }
    .stButton>button { width: 100%; }
    .big-header { font-size: 2.2rem; font-weight: 700; margin-bottom: 0.5rem; }
    .step-card {
        padding: 1rem;
        border-radius: 10px;
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        margin-bottom: 1rem;
    }
    .warning-box {
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# UTILIDADES PARA CHROMIUM EN STREAMLIT CLOUD
# ============================================================================
def _find_chromium_binary() -> str | None:
    """Busca el binario de Chromium en el sistema."""
    candidates = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    # Buscar con which
    try:
        result = subprocess.run(
            ["which", "chromium"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _find_chromedriver() -> str | None:
    """Busca chromedriver en el sistema."""
    candidates = [
        "/usr/bin/chromedriver",
        "/usr/lib/chromium/chromedriver",
        "/snap/bin/chromedriver",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    try:
        result = subprocess.run(
            ["which", "chromedriver"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


# ============================================================================
# CLASE: LINKEDIN SCRAPER (adaptado a Streamlit Cloud)
# ============================================================================
class LinkedInCVScraper:
    """Scraper de CVs de LinkedIn. Adaptado para entornos cloud efímeros."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None
        self.wait = None
        self._cookies = []  # En memoria (no hay filesystem persistente)

    def start(self) -> tuple[bool, str]:
        """Inicia el driver. Devuelve (ok, mensaje)."""
        try:
            opts = Options()
            if self.headless:
                opts.add_argument("--headless=new")

            # Binario de Chromium
            binary = _find_chromium_binary()
            if binary:
                opts.binary_location = binary
            else:
                return False, "❌ Chromium no encontrado. Añade `chromium` a packages.txt"

            # Opciones críticas para cloud
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")  # CRÍTICO en contenedores
            opts.add_argument("--disable-gpu")
            opts.add_argument("--disable-setuid-sandbox")
            opts.add_argument("--disable-infobars")
            opts.add_argument("--window-size=1920,1080")
            opts.add_argument("--single-process")  # Ahorra memoria
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_argument("--disable-extensions")
            opts.add_argument("--disable-background-networking")
            opts.add_argument("--disable-default-apps")
            opts.add_argument("--disable-sync")
            opts.add_argument("--disable-translate")
            opts.add_argument("--mute-audio")
            opts.add_argument("--no-first-run")
            opts.add_argument(
                "--user-agent=Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option("useAutomationExtension", False)

            # chromedriver
            driver_path = _find_chromedriver()
            if driver_path:
                service = Service(driver_path)
            else:
                # Fallback: dejar que Selenium lo gestione
                service = Service()

            self.driver = webdriver.Chrome(service=service, options=opts)
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            })
            self.wait = WebDriverWait(self.driver, 20)
            return True, "✅ Chromium iniciado"
        except Exception as e:
            return False, f"❌ Error iniciando Chromium: {str(e)[:200]}"

    def set_cookies_from_text(self, cookies_text: str) -> bool:
        """Carga cookies desde texto JSON o Netscape exportado."""
        try:
            # Intentar parsear como JSON
            cookies = json.loads(cookies_text)
            if isinstance(cookies, list):
                self._cookies = cookies
                return True
        except json.JSONDecodeError:
            pass

        # Formato Netscape (EditThisCookie, etc.)
        try:
            cookies = []
            for line in cookies_text.strip().split("\n"):
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    cookies.append({
                        "name": parts[5],
                        "value": parts[6],
                        "domain": parts[0],
                        "path": parts[2],
                        "secure": parts[3].upper() == "TRUE",
                    })
            if cookies:
                self._cookies = cookies
                return True
        except Exception:
            pass

        return False

    def inject_cookies(self) -> bool:
        """Inyecta las cookies en el navegador y verifica sesión."""
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
                # LinkedIn requiere que las cookies sean de su dominio
                if "linkedin" not in cookie["domain"]:
                    continue
                try:
                    self.driver.add_cookie(cookie)
                except Exception:
                    pass
            self.driver.refresh()
            time.sleep(4)
            # Verificar si estamos logueados
            url = self.driver.current_url.lower()
            return "feed" in url or "mynetwork" in url or "linkedin.com/in/" in url
        except Exception as e:
            print(f"Error inyectando cookies: {e}")
            return False

    def search_person(self, full_name: str, institution: str = "", orcid: str = "") -> str | None:
        """Busca persona y devuelve URL del perfil."""
        query = full_name
        if institution:
            # Limpiar institución para la búsqueda
            inst_clean = re.sub(r'[;|]', ' ', institution).strip()
            query += f" {inst_clean}"

        search_url = (
            f"https://www.linkedin.com/search/results/people/"
            f"?keywords={requests.utils.quote(query)}&origin=GLOBAL_SEARCH_HEADER"
        )
        self.driver.get(search_url)
        time.sleep(5)

        # Detectar challenge/captcha
        if "challenge" in self.driver.current_url.lower():
            raise RuntimeError("LinkedIn ha detectado automatización (challenge/captcha)")

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
        """Scroll más conservador para ahorrar recursos."""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        for _ in range(max_scrolls):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)

    def _safe_text(self, xpath: str, default: str = "") -> str:
        try:
            return self.driver.find_element(By.XPATH, xpath).text.strip()
        except NoSuchElementException:
            return default

    def extract_full_cv(self, profile_url: str) -> dict:
        """Extrae CV completo del perfil."""
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
            "Experiencia": "//section[contains(@id,'experience') or .//span[text()='Experiencia'] or .//span[text()='Experience']]",
            "Educación": "//section[contains(@id,'education') or .//span[text()='Educación'] or .//span[text()='Education']]",
            "Publicaciones": "//section[contains(@id,'publications') or .//span[text()='Publicaciones']]",
            "Patentes": "//section[contains(@id,'patents') or .//span[text()='Patentes']]",
            "Proyectos": "//section[contains(@id,'projects') or .//span[text()='Proyectos']]",
            "Idiomas": "//section[contains(@id,'languages') or .//span[text()='Idiomas']]",
            "Premios": "//section[contains(@id,'honors') or .//span[text()='Premios']]",
        }

        for nombre_seccion, xpath in sections_xpaths.items():
            try:
                section = self.driver.find_element(By.XPATH, xpath)
                cv["sections"][nombre_seccion] = section.text.strip()
            except NoSuchElementException:
                pass

        if not cv["sections"]:
            try:
                main = self.driver.find_element(By.XPATH, "//main")
                cv["texto_completo"] = main.text.strip()
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
# ALTERNATIVA: PROXY API (recomendado para Streamlit Cloud)
# ============================================================================
class ProxycurlAPI:
    """
    Alternativa más estable que Selenium para Streamlit Cloud.
    Obtén API key en: https://nubela.co/proxycurl
    Plan gratuito: 10 créditos/mes (suficiente para probar).
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://nubela.co/proxycurl/api/v2/linkedin"

    def test_connection(self) -> tuple[bool, str]:
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = requests.get(
                "https://nubela.co/proxycurl/api/v2/linkedin",
                headers=headers,
                params={"url": "https://linkedin.com/in/williamhgates"},
                timeout=15
            )
            if resp.status_code == 200:
                return True, "✅ API válida"
            elif resp.status_code == 401:
                return False, "❌ API key inválida"
            elif resp.status_code == 429:
                return False, "⚠️ Límite de créditos alcanzado"
            else:
                return False, f"❌ Error {resp.status_code}"
        except Exception as e:
            return False, f"❌ {str(e)[:80]}"

    def search_person(self, full_name: str, institution: str = "") -> str | None:
        """Busca persona y devuelve URL del perfil."""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        params = {
            "q": full_name,
            "search_type": "people",
            "page_size": 1,
        }
        if institution:
            params["company_domain"] = institution.split()[0].lower()

        try:
            resp = requests.get(
                f"{self.base_url}/person/search",
                headers=headers,
                params=params,
                timeout=20
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                if results:
                    return results[0].get("profile_url") or results[0].get("link")
            return None
        except Exception:
            return None

    def get_profile(self, profile_url: str) -> dict:
        """Obtiene perfil completo."""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        params = {
            "url": profile_url,
            "skills": "include",
            "use_cache": "if-present",
            "fallback_to_cache": "on-error",
        }
        try:
            resp = requests.get(
                f"{self.base_url}",
                headers=headers,
                params=params,
                timeout=30
            )
            if resp.status_code == 200:
                data = resp.json()
                # Convertir al formato común
                cv = {
                    "url": profile_url,
                    "nombre": data.get("full_name", ""),
                    "headline": data.get("headline", ""),
                    "sections": {},
                }
                # Experiencia
                if data.get("experiences"):
                    exp_text = []
                    for exp in data["experiences"]:
                        exp_text.append(
                            f"• {exp.get('title', '')} @ {exp.get('company', '')} "
                            f"({exp.get('starts_at', {}).get('month', '?')}/{exp.get('starts_at', {}).get('year', '?')} - "
                            f"{exp.get('ends_at', {}).get('month', 'Actual')}/{exp.get('ends_at', {}).get('year', 'Actual')})"
                        )
                        if exp.get("description"):
                            exp_text.append(f"  {exp['description']}")
                    cv["sections"]["Experiencia"] = "\n".join(exp_text)
                # Educación
                if data.get("education"):
                    edu_text = []
                    for ed in data["education"]:
                        edu_text.append(
                            f"• {ed.get('degree_name', '')} @ {ed.get('school', '')} "
                            f"({ed.get('starts_at', {}).get('year', '?')}-{ed.get('ends_at', {}).get('year', '?')})"
                        )
                    cv["sections"]["Educación"] = "\n".join(edu_text)
                # About
                if data.get("summary"):
                    cv["sections"]["Acerca de"] = data["summary"]
                return cv
            return None
        except Exception as e:
            print(f"Error obteniendo perfil: {e}")
            return None


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
        st.session_state.modo_scraper = "proxycurl"  # "selenium" o "proxycurl"

    # ========================================================================
    # SIDEBAR
    # ========================================================================
    with st.sidebar:
        st.markdown("## ⚙️ Configuración")

        # --- Modo de scraping ---
        st.markdown("### 🔍 Modo de obtención de CVs")
        modo = st.radio(
            "Elige el método:",
            ["🌐 Proxycurl API (recomendado)", "🤖 Selenium + Chromium"],
            index=0,
            help="Proxycurl es más estable en Streamlit Cloud. Selenium puede ser bloqueado por LinkedIn."
        )
        st.session_state.modo_scraper = "proxycurl" if "Proxycurl" in modo else "selenium"

        st.divider()

        # --- Configuración según modo ---
        if st.session_state.modo_scraper == "proxycurl":
            st.markdown("### 🌐 Proxycurl API")
            st.caption(
                "Obtén tu API key en [nubela.co/proxycurl](https://nubela.co/proxycurl). "
                "Plan gratuito: 10 créditos/mes."
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
                help="Se guarda solo en esta sesión"
            )

            if proxycurl_key:
                if st.button("🔍 Verificar API Proxycurl"):
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

        else:  # Selenium
            st.markdown("### 🤖 LinkedIn + Selenium")
            st.markdown(
                '<div class="warning-box">⚠️ <b>Importante:</b> LinkedIn bloquea IPs de '
                'Streamlit Cloud. Si falla, usa Proxycurl API.</div>',
                unsafe_allow_html=True
            )

            st.caption("Pega las cookies de LinkedIn (formato JSON o Netscape)")
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
            help="Para analizar CVs con IA"
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

        st.divider()

        # --- Estado ---
        st.markdown("### 📊 Estado")
        st.write(f"🔗 LinkedIn: {'🟢 OK' if st.session_state.linkedin_ok else '🟡 No conectado'}")
        st.write(f"🤖 OpenAI: {'🟢 OK' if st.session_state.openai_ok else '🟡 Pendiente'}")
        st.write(f"👥 CVs extraídos: {len(st.session_state.cvs)}")
        st.write(f"🏭 Análisis hechos: {len(st.session_state.analisis)}")

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
            df = pd.read_excel(uploaded)
            st.session_state.df = df
        except Exception as e:
            st.error(f"Error leyendo Excel: {e}")
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

        seleccion = st.multiselect(
            "Selecciona investigadores a analizar",
            df[col_nombre].tolist(),
            default=df[col_nombre].tolist()[:3],
            help="Empieza con pocos para probar"
        )

        if st.button(
            "🔍 Buscar y extraer CVs",
            type="primary",
            use_container_width=True,
            disabled=len(seleccion) == 0 or not st.session_state.linkedin_ok
        ):
            if not st.session_state.linkedin_ok:
                st.error("⚠️ Configura LinkedIn en la sidebar primero")
                st.stop()

            progress = st.progress(0)
            status_container = st.container()

            for i, nombre in enumerate(seleccion):
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
                                    cv = api.get_profile(url)
                                    if cv:
                                        st.session_state.cvs[nombre] = cv
                                        st.success(f"✅ {nombre}: {cv.get('headline', 'OK')[:80]}")
                                    else:
                                        st.warning(f"⚠️ {nombre}: URL encontrada pero perfil vacío")
                                else:
                                    st.warning(f"❌ {nombre}: no encontrado")
                            else:
                                # Selenium
                                scraper = st.session_state.scraper
                                url = scraper.search_person(nombre, inst, orcid)
                                if url:
                                    cv = scraper.extract_full_cv(url)
                                    st.session_state.cvs[nombre] = cv
                                    st.success(f"✅ {nombre}: {cv.get('headline', 'OK')[:80]}")
                                else:
                                    st.warning(f"❌ {nombre}: no encontrado")
                                time.sleep(3)  # Anti-ban
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
            if st.button(
                "🤖 Analizar con IA",
                type="primary",
                use_container_width=True
            ):
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

                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                    df_out.to_excel(writer, index=False, sheet_name="Sheet1")
                    ws = writer.sheets["Sheet1"]
                    for col in ws.columns:
                        max_length = 0
                        col_letter = col[0].column_letter
                        for cell in col:
                            try:
                                val = str(cell.value) if cell.value else ""
                                max_length = max(max_length, min(len(val), 80))
                            except Exception:
                                pass
                        ws.column_dimensions[col_letter].width = max_length + 2

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
