"""
LinkedIn CV Analyzer - Spin-off Detector
Versión Streamlit Cloud + Browserless (Chrome remoto)
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
from openai import OpenAI

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

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
</style>
""", unsafe_allow_html=True)


# ============================================================================
# CLASE: LINKEDIN SCRAPER (conexión a Browserless remoto)
# ============================================================================
class LinkedInCVScraper:
    """Scraper que se conecta a un Chrome remoto (Browserless o similar)."""

    def __init__(self, browserless_url: str):
        """
        Args:
            browserless_url: URL WebSocket de Browserless.
                Ejemplo: "wss://chrome.browserless.io?token=TU_TOKEN"
        """
        self.browserless_url = browserless_url
        self.driver = None
        self.wait = None

    def start(self) -> tuple[bool, str]:
        """Conecta al Chrome remoto."""
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_argument("--window-size=1920,1080")
            options.add_argument(
                "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            # Conexión remota vía WebSocket
            self.driver = webdriver.Remote(
                command_executor=self.browserless_url,
                options=options
            )
            self.wait = WebDriverWait(self.driver, 20)
            return True, "✅ Conectado a Chrome remoto"
        except Exception as e:
            return False, f"❌ Error conectando: {str(e)[:200]}"

    def set_cookies_from_text(self, cookies_text: str) -> bool:
        """Carga cookies desde JSON."""
        try:
            cookies = json.loads(cookies_text)
            if isinstance(cookies, list):
                self._cookies = cookies
                return True
        except json.JSONDecodeError:
            pass
        return False

    def inject_cookies(self) -> bool:
        """Inyecta cookies y verifica sesión."""
        if not hasattr(self, '_cookies') or not self._cookies:
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
        except Exception as e:
            print(f"Error inyectando cookies: {e}")
            return False

    def check_login(self) -> bool:
        """Verifica si hay sesión activa."""
        self.driver.get("https://www.linkedin.com/feed/")
        time.sleep(4)
        return "feed" in self.driver.current_url.lower()

    def search_person(self, full_name: str, institution: str = "") -> str | None:
        """Busca persona y devuelve URL del mejor perfil."""
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
        self.driver.get(search_url)
        time.sleep(5)

        if "challenge" in self.driver.current_url.lower():
            raise RuntimeError("⚠️ LinkedIn pide captcha")

        try:
            results = self.wait.until(
                EC.presence_of_all_elements_located(
                    (By.XPATH, "//ul[contains(@class,'reusable-search__result-container')]"
                               "//a[contains(@class,'app-aware-link') and contains(@href,'/in/')]")
                )
            )
            if results:
                best = self._best_result(results, full_name, institution)
                return best.get_attribute("href").split("?")[0]
            return None
        except TimeoutException:
            return None

    def _best_result(self, results, target_name: str, institution: str = ""):
        """Elige el resultado más parecido al nombre buscado."""
        target_words = set(target_name.lower().split())
        best_score = -1
        best_elem = results[0]

        for elem in results[:5]:
            try:
                name_elem = elem.find_element(By.XPATH, ".//span[@aria-hidden='true']")
                name = name_elem.text.lower()
                name_words = set(name.split())
                score = len(target_words & name_words) * 10

                if institution:
                    try:
                        subtitle = elem.find_element(
                            By.XPATH, ".//div[contains(@class,'entity-result__summary')]"
                        ).text.lower()
                        inst_lower = institution.lower()
                        if any(w in subtitle for w in inst_lower.split() if len(w) > 3):
                            score += 5
                    except Exception:
                        pass

                if score > best_score:
                    best_score = score
                    best_elem = elem
            except Exception:
                continue
        return best_elem

    def _scroll_full_page(self, max_scrolls: int = 20, pause: float = 1.0):
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

    # ========================================================================
    # SIDEBAR
    # ========================================================================
    with st.sidebar:
        st.markdown("## ⚙️ Configuración")

        # --- Browserless ---
        st.markdown("### 🌐 Browserless (Chrome remoto)")
        st.markdown(
            '<div class="info-box">📌 Regístrate gratis en '
            '<a href="https://www.browserless.io" target="_blank">browserless.io</a><br>'
            'Plan gratuito: <b>1000 ejecuciones/mes</b></div>',
            unsafe_allow_html=True
        )

        # Intentar leer de secrets
        default_url = ""
        try:
            token = st.secrets.get("BROWSERLESS_TOKEN", "")
            if token:
                default_url = f"wss://chrome.browserless.io?token={token}"
        except Exception:
            pass

        browserless_url = st.text_input(
            "URL WebSocket de Browserless",
            value=default_url,
            placeholder="wss://chrome.browserless.io?token=TU_TOKEN",
            help="Lo obtienes en tu dashboard de Browserless"
        )

        if browserless_url:
            if st.button("🔌 Conectar a Chrome remoto"):
                with st.spinner("Conectando..."):
                    scraper = LinkedInCVScraper(browserless_url)
                    ok, msg = scraper.start()
                    if ok:
                        st.session_state.scraper = scraper
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        if st.session_state.scraper:
            st.success("🟢 Chrome remoto conectado")

            # --- LinkedIn Login ---
            st.markdown("### 🔐 LinkedIn")
            st.caption("Pega las cookies de LinkedIn (formato JSON)")
            st.caption("Exporta con extensión 'EditThisCookie' en tu Chrome local")

            cookies_text = st.text_area(
                "Cookies LinkedIn (JSON)",
                height=150,
                label_visibility="collapsed"
            )

            if cookies_text and st.button("🔑 Cargar cookies"):
                with st.spinner("Inyectando cookies..."):
                    if st.session_state.scraper.set_cookies_from_text(cookies_text):
                        if st.session_state.scraper.inject_cookies():
                            st.session_state.linkedin_ok = True
                            st.success("✅ Sesión LinkedIn activa")
                        else:
                            st.error("❌ Cookies inválidas o sesión expirada")
                    else:
                        st.error("❌ Formato JSON inválido")

            if st.button("🔄 Verificar sesión"):
                with st.spinner("Verificando..."):
                    if st.session_state.scraper.check_login():
                        st.session_state.linkedin_ok = True
                        st.success("✅ Sesión activa")
                    else:
                        st.session_state.linkedin_ok = False
                        st.warning("⚠️ Sesión expirada")

            if st.button("🚪 Desconectar Chrome"):
                st.session_state.scraper.close()
                st.session_state.scraper = None
                st.session_state.linkedin_ok = False
                st.rerun()

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

        if st.session_state.openai_ok:
            st.success("🟢 OpenAI listo")
        else:
            st.warning("🟡 OpenAI no configurado")

        st.divider()

        # --- Estado ---
        st.markdown("### 📊 Estado")
        st.write(f"🌐 Chrome: {'🟢 OK' if st.session_state.scraper else '🟡 No conectado'}")
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
            st.warning("⚠️ Inicia sesión en LinkedIn en la sidebar")
            seleccion = []
        else:
            seleccion = st.multiselect(
                "Selecciona investigadores",
                df[col_nombre].tolist(),
                default=df[col_nombre].tolist()[:3]
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
                            url = st.session_state.scraper.search_person(nombre, inst)

                    if url:
                        with status_container:
                            with st.spinner(f"📄 {nombre}..."):
                                cv = st.session_state.scraper.extract_full_cv(url)
                                st.session_state.cvs[nombre] = cv
                                save_cv_cache(nombre, cv)
                                st.success(f"✅ {nombre}: {cv.get('headline', 'OK')[:80]}")
                    else:
                        with status_container:
                            st.warning(f"❌ {nombre}: no encontrado")
                except Exception as e:
                    with status_container:
                        st.error(f"❌ {nombre}: {str(e)[:100]}")

                progress.progress((i + 1) / len(seleccion))
                time.sleep(3)

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
