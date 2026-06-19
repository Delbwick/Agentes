"""
LinkedIn CV Analyzer - Spin-off Detector
Versión con filtrado, extracción mejorada y análisis IA enfocado en spin-offs/patentes
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
                return False, "⚠️ Límite de créditos"
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
# CLASE: LINKEDIN SCRAPER (CORREGIDO)
# ============================================================================
class LinkedInScraper:
    def __init__(self, api: BrowserlessAPI, cookies: list):
        self.api = api
        self.cookies = cookies
        self.debug_info = {}

    def test_linkedin_session(self) -> dict:
        # ... (igual que antes)
        pass

    def check_critical_cookies(self) -> dict:
        # ... (igual que antes)
        pass

    def _extract_name_from_link(self, link) -> str:
        """Extrae nombre del enlace."""
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
        
        # Limpiar
        name = re.sub(r'\s+', ' ', name).strip()
        name = re.sub(r'^(Ver perfil de|View profile de|View)\s*', '', name, flags=re.IGNORECASE)
        
        return name

    def _extract_headline_from_parent(self, parent) -> str:
        """Extrae headline/cargo del contexto del resultado."""
        if not parent:
            return ""
        
        # Buscar patrones de headline
        headline_elem = parent.select_one(".entity-result__summary")
        if headline_elem:
            return headline_elem.get_text().strip()[:200]
        
        # Fallback: texto completo
        text = parent.get_text(separator=" ", strip=True)
        if len(text) > 300:
            text = text[:300]
        
        return text

    def _extract_location(self, parent) -> str:
        """Extrae ubicación del resultado."""
        if not parent:
            return ""
        
        # Buscar patrón de ubicación (suele estar después de ·)
        text = parent.get_text()
        if "·" in text:
            parts = text.split("·")
            for part in parts:
                part = part.strip()
                # Ubicaciones típicas: "Madrid", "Barcelona, España", etc.
                if len(part) < 50 and any(c in part for c in [",", "España", "Spain", "Cataluña", "Madrid", "Barcelona", "Sevilla", "Valencia"]):
                    return part.strip()
        
        return ""

    def _extract_current_position(self, parent) -> str:
        """Extrae posición/empresa actual del resultado."""
        if not parent:
            return ""
        
        # Buscar patrón de posición actual
        text = parent.get_text()
        
        # LinkedIn suele mostrar: "Cargo en Empresa · X años"
        match = re.search(r'([^\n·]+?)\s+en\s+([^\n·]+?)(?:\s+·|\s+\d+\s+a)', text)
        if match:
            return f"{match.group(1).strip()} en {match.group(2).strip()}"
        
        # Fallback: primera línea significativa
        lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 10]
        if lines:
            return lines[0][:150]
        
        return ""

    def _name_similarity(self, name1: str, name2: str) -> float:
        """Calcula similitud entre dos nombres (0-1)."""
        n1 = set(name1.lower().split())
        n2 = set(name2.lower().split())
        
        if not n1 or not n2:
            return 0.0
        
        intersection = len(n1 & n2)
        union = len(n1 | n2)
        
        return intersection / union if union > 0 else 0.0

    def search_person(self, full_name: str, institution: str = "", orcid: str = "", debug_mode: bool = False) -> list:
        """Busca persona y devuelve lista con info completa (FILTRADO RELAJADO)."""
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
        target_words = set(full_name.lower().split())
        
        for link in all_links:
            href = link.get("href", "")
            if "/in/" not in href or "login" in href or "challenge" in href:
                continue
            
            href = href.split("?")[0]
            
            if href in seen_urls:
                continue
            seen_urls.add(href)
            
            # Extraer nombre
            name = self._extract_name_from_link(link)
            
            # FILTRADO RELAJADO: Solo excluir si el nombre está vacío o es muy corto
            if not name or len(name) < 3:
                continue
            
            # Calcular similitud básica
            name_lower = name.lower()
            name_words = set(name_lower.split())
            common_words = target_words & name_words
            
            # Extraer contexto
            parent = link.find_parent("li") or link.find_parent("div", class_=re.compile("entity-result|search-result"))
            context = self._extract_headline_from_parent(parent)
            location = self._extract_location(parent)
            current_position = self._extract_current_position(parent)
            
            # Calcular score
            score = len(common_words) * 10

            # Bonus por institución
            if institution:
                inst_lower = institution.lower()
                inst_words = [w for w in inst_lower.split() if len(w) > 3]
                for word in inst_words[:3]:
                    if word in context.lower():
                        score += 5

            # Bonus por ORCID
            if orcid and orcid in context:
                score += 20

            # Bonus por tener posición actual
            if current_position:
                score += 3

            # Bonus por tener ubicación
            if location:
                score += 2

            # FILTRADO RELAJADO: Incluir todos los que tengan nombre válido
            # Solo excluir si score < 5 (muy poca relevancia)
            if score < 5:
                continue
            
            profile_links.append({
                "href": href,
                "name": name,
                "context": context,
                "location": location,
                "current_position": current_position,
                "score": score,
            })

        self.debug_info["profile_links_found"] = len(profile_links)

        # Ordenar por score
        profile_links.sort(key=lambda x: x["score"], reverse=True)

        return profile_links

    def _clean_linkedin_text(self, text: str) -> str:
        """Limpia el texto eliminando footer, headers y ruido de LinkedIn."""
        if not text:
            return ""
        
        # Lista de patrones a eliminar
        patterns_to_remove = [
            # Footer de LinkedIn
            r"Acerca de\s+Accesibilidad\s+Talent Solutions",
            r"Pautas comunitarias\s+Empleo\s+Marketing Solutions",
            r"Privacidad y condiciones\s+Opciones de publicidad",
            r"Sales Solutions\s+Móvil\s+Pequeñas empresas",
            r"Centro de seguridad\s+LinkedIn Corporation",
            r"¿Tienes preguntas\?\s+Visita nuestro Centro de ayuda",
            r"Gestiona tu cuenta y la privacidad",
            r"Accede a tu Configuración",
            r"Transparencia de las recomendaciones",
            r"Más información sobre el contenido recomendado",
            r"Seleccionar idioma",
            r"العربية.*?한국어",  # Lista de idiomas
            # Headers y navegación
            r"Inicio\s+Mi red\s+Empleos\s+Mensajes\s+Notificaciones",
            r"Para negocios\s+Publicidad",
            # Elementos de UI
            r"Enviar mensaje\s+Enviar mensaje",
            r"Opciones de publicidad",
            r"¿Por qué estoy viendo este anuncio\?",
            r"Gestiona tus preferencias de publicidad",
            r"Ocultar o denunciar este anuncio",
            r"No quiero ver este anuncio en mi feed",
            r"No quiero ver esto",
            r"Dinos por qué no quieres ver esto",
            r"Tus comentarios nos ayudarán a mejorar",
            r"Me molesta o no me interesa",
            r"He visto el anuncio demasiadas veces",
            r"Si crees que esta publicación incumple",
            r"Denunciar este anuncio\s+Enviar",
            r"Información de contacto",
            # Ruido general
            r"·\s*1er",
            r"•\s*2º",
            r"·\s*2º",
            r"·\s*1er",
            r"·\s*3er",
            # Espacios múltiples
            r"\n\s*\n\s*\n",
        ]
        
        cleaned_text = text
        for pattern in patterns_to_remove:
            cleaned_text = re.sub(pattern, "", cleaned_text, flags=re.IGNORECASE | re.DOTALL)
        
        # Limpiar espacios en blanco múltiples
        cleaned_text = re.sub(r'\n\s*\n', '\n', cleaned_text)
        cleaned_text = cleaned_text.strip()
        
        return cleaned_text

    def extract_full_cv(self, profile_url: str, debug_mode: bool = False) -> dict | None:
        """Extrae CV completo usando múltiples estrategias y LIMPIA el ruido."""
        response = self.api.get_content(profile_url, cookies=self.cookies)

        if not response["ok"] or not response["html"]:
            if debug_mode:
                st.error(f"❌ Error: {response.get('error')}")
            return None

        html = response["html"]
        soup = BeautifulSoup(html, "html.parser")
        
        cv = {"url": profile_url, "sections": {}}

        # Nombre
        h1 = soup.select_one("h1")
        if h1:
            cv["nombre"] = h1.get_text().strip()
        else:
            title = soup.title.string if soup.title else ""
            if "|" in title:
                cv["nombre"] = title.split("|")[0].strip()
            elif "LinkedIn" in title:
                cv["nombre"] = title.replace("LinkedIn", "").strip()
            else:
                cv["nombre"] = title.strip()

        # Headline - múltiples selectores
        headline_selectors = [
            ".text-body-medium.break-words",
            ".text-body-medium",
            "div[class*='text-body-medium']",
            ".pv-top-card--list span:first-child",
        ]
        for selector in headline_selectors:
            headline = soup.select_one(selector)
            if headline:
                cv["headline"] = headline.get_text().strip()
                break
        else:
            cv["headline"] = ""

        # Ubicación
        ubicacion_selectors = [
            ".text-body-small.inline",
            ".text-body-small",
            "span[class*='text-body-small']",
        ]
        for selector in ubicacion_selectors:
            ubicacion = soup.select_one(selector)
            if ubicacion:
                cv["ubicacion"] = ubicacion.get_text().strip()
                break
        else:
            cv["ubicacion"] = ""

        # Secciones - intentar múltiples selectores
        section_ids = {
            "Acerca de": ["about", "about-section"],
            "Experiencia": ["experience", "experience-section"],
            "Educación": ["education", "education-section"],
            "Publicaciones": ["publications", "publications-section"],
            "Patentes": ["patents", "patents-section"],
            "Proyectos": ["projects", "projects-section"],
            "Idiomas": ["languages", "languages-section"],
            "Premios": ["honors", "honors-section", "awards"],
        }

        for nombre_seccion, possible_ids in section_ids.items():
            for section_id in possible_ids:
                section = soup.select_one(f"section#{section_id}") or soup.select_one(f"section[id*='{section_id}']")
                if section:
                    # LIMPIAR el texto de la sección
                    section_text = section.get_text(separator="\n", strip=True)
                    cv["sections"][nombre_seccion] = self._clean_linkedin_text(section_text)
                    break

        # ESTRATEGIA CLAVE: Extraer TODO el texto del main como fallback
        main = soup.select_one("main")
        if main:
            full_text = main.get_text(separator="\n", strip=True)
            # LIMPIAR el texto completo
            cv["texto_completo"] = self._clean_linkedin_text(full_text)
        else:
            # Fallback: todo el body
            body = soup.select_one("body")
            if body:
                full_text = body.get_text(separator="\n", strip=True)
                cv["texto_completo"] = self._clean_linkedin_text(full_text)
            else:
                cv["texto_completo"] = ""

        # Si no se encontraron secciones, intentar extraer del texto completo
        if not cv["sections"] and cv["texto_completo"]:
            # Intentar identificar secciones por patrones de texto
            text = cv["texto_completo"]
            
            # Buscar patrones de secciones comunes
            section_patterns = {
                "Acerca de": r"(?:Acerca de|About)\s*\n(.*?)(?=\n\s*(?:Experiencia|Experience|Educación|Education)|$)",
                "Experiencia": r"(?:Experiencia|Experience)\s*\n(.*?)(?=\n\s*(?:Educación|Education|Publicaciones|Patentes)|$)",
                "Educación": r"(?:Educación|Education|Formación)\s*\n(.*?)(?=\n\s*(?:Publicaciones|Patentes|Proyectos|Idiomas)|$)",
                "Publicaciones": r"(?:Publicaciones|Publications)\s*\n(.*?)(?=\n\s*(?:Patentes|Proyectos|Idiomas|Premios)|$)",
                "Patentes": r"(?:Patentes|Patents)\s*\n(.*?)(?=\n\s*(?:Proyectos|Idiomas|Premios)|$)",
            }
            
            for section_name, pattern in section_patterns.items():
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    section_text = match.group(1).strip()
                    if len(section_text) > 50:  # Solo si hay contenido significativo
                        cv["sections"][section_name] = self._clean_linkedin_text(section_text)[:3000]

        if debug_mode:
            st.info(f"📄 CV extraído: {cv['nombre']}")
            st.write(f"**Headline:** {cv['headline']}")
            st.write(f"**Secciones encontradas:** {', '.join(cv['sections'].keys())}")
            st.write(f"**Longitud texto completo:** {len(cv.get('texto_completo', ''))} chars")

        return cv
# ============================================================================
# CLASE: CV ANALYZER (OpenAI) - PROMPT MEJORADO
# ============================================================================
class CVAnalyzer:
    SYSTEM_PROMPT = """Eres un analista experto en transferencia de tecnología, spin-offs académicas y propiedad industrial en España.
Tu especialidad es identificar investigadores con actividad en sectores de INDUSTRIA, BIOTECH, MEDTECH y DEEP TECH.

Analiza el CV de un investigador y extrae:

1. **PATENTES**: Lista de patentes mencionadas (título, número si disponible, año)
2. **SPIN-OFFS**: Empresas nacidas de la universidad que haya fundado, cofundado o asesorado
3. **EMPRESAS**: Otras empresas privadas donde haya trabajado (excluyendo universidades y OPIs como CSIC)
4. **ROLES ACTUALES**: Si actualmente trabaja en 2 o más empresas, o es CEO/fundador de alguna
5. **SECTOR**: Clasifica su actividad en: Industria, Biotech, Medtech, Deep Tech, TIC, Energía, Otro

Para cada empresa/spin-off, indica:
- Si es spin-off (nacida de universidad)
- Su rol (fundador, CEO, consejero, empleado, etc.)
- Descripción breve de actividad
- Si es la posición actual

Responde SOLO en JSON con este formato exacto:
{
  "patentes": [
    {"titulo": "...", "numero": "...", "anio": "..."}
  ],
  "spin_offs": [
    {"nombre": "...", "rol": "...", "descripcion": "...", "es_actual": true/false}
  ],
  "empresas": [
    {"nombre": "...", "rol": "...", "descripcion": "...", "es_actual": true/false, "es_spinoff": false}
  ],
  "roles_actuales_multiples": true/false,
  "sector_principal": "Industria|Biotech|Medtech|Deep Tech|TIC|Energía|Otro",
  "resumen_ejecutivo": "Párrafo de 3-4 líneas resumiendo su actividad industrial, patentes y spin-offs"
}

Si no hay actividad industrial/patentes/spin-offs:
{
  "patentes": [],
  "spin_offs": [],
  "empresas": [],
  "roles_actuales_multiples": false,
  "sector_principal": "Académico",
  "resumen_ejecutivo": "Investigador principalmente académico sin actividad industrial relevante detectada."
}
"""

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def analizar_cv(self, nombre: str, cv_text: str, datos_excel: dict = None) -> dict:
        # Construir prompt con contexto adicional del Excel si está disponible
        excel_context = ""
        if datos_excel:
            excel_context = "\n\nDATOS ADICIONALES DEL EXPEDIENTE DEL INVESTIGADOR:\n"
            if datos_excel.get("patentes"):
                excel_context += f"- Patentes conocidas: {datos_excel['patentes']}\n"
            if datos_excel.get("publicaciones"):
                excel_context += f"- Publicaciones: {datos_excel['publicaciones']}\n"
            if datos_excel.get("institucion"):
                excel_context += f"- Institución: {datos_excel['institucion']}\n"
            if datos_excel.get("score"):
                excel_context += f"- Score de patentes+publicaciones: {datos_excel['score']}\n"

        prompt = f"""Investigador: {nombre}
{excel_context}

CV EXTRAÍDO DE LINKEDIN:
---
{cv_text[:15000]}
---

Analiza el CV y extrae:
1. PATENTES mencionadas
2. SPIN-OFFS fundadas o cofundadas
3. EMPRESAS donde ha trabajado
4. Si tiene múltiples roles actuales o es CEO/fundador
5. Sector principal (Industria, Biotech, Medtech, Deep Tech, etc.)

Cruza la información del CV con los datos del expediente si están disponibles."""

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
            return {
                "patentes": [],
                "spin_offs": [],
                "empresas": [],
                "roles_actuales_multiples": False,
                "sector_principal": "Error",
                "resumen_ejecutivo": f"Error en análisis: {e}"
            }


def formatear_para_excel(nombre_original: str, cv: dict, analisis: dict) -> str:
    """Formatea el resultado completo para la celda INDUSTRIAL info."""
    lineas = [f"=== {nombre_original} ===", ""]
    
    # Perfil LinkedIn
    if cv:
        lineas.append("📄 PERFIL LINKEDIN:")
        if cv.get("headline"):
            lineas.append(f"🎯 {cv['headline']}")
        if cv.get("ubicacion"):
            lineas.append(f"📍 {cv['ubicacion']}")
        if cv.get("url"):
            lineas.append(f"🔗 {cv['url']}")
        
        # Solo mostrar secciones con contenido real
        for seccion, texto in cv.get("sections", {}).items():
            if texto and len(texto) > 50:
                lineas.append(f"\n— {seccion.upper()} —")
                lineas.append(texto[:2000])
    
    # Análisis IA
    lineas.append("\n" + "=" * 70)
    lineas.append("🔬 ANÁLISIS SPIN-OFFS / PATENTES / ACTIVIDAD INDUSTRIAL:")
    lineas.append("=" * 70)
    
    # Patentes
    if analisis.get("patentes"):
        lineas.append("\n📜 PATENTES:")
        for pat in analisis["patentes"]:
            titulo = pat.get("titulo", "?")
            numero = pat.get("numero", "")
            anio = pat.get("anio", "")
            linea = f"  • {titulo}"
            if numero:
                linea += f" ({numero})"
            if anio:
                linea += f" [{anio}]"
            lineas.append(linea)
    else:
        lineas.append("\n📜 PATENTES: No detectadas")
    
    # Spin-offs
    if analisis.get("spin_offs"):
        lineas.append("\n🚀 SPIN-OFFS:")
        for spin in analisis["spin_offs"]:
            nombre = spin.get("nombre", "?")
            rol = spin.get("rol", "")
            desc = spin.get("descripcion", "")
            actual = " [ACTUAL]" if spin.get("es_actual") else ""
            lineas.append(f"\n  🚀 {nombre}{actual}")
            if rol:
                lineas.append(f"     Rol: {rol}")
            if desc:
                lineas.append(f"     Actividad: {desc}")
    else:
        lineas.append("\n🚀 SPIN-OFFS: No detectadas")
    
    # Empresas
    if analisis.get("empresas"):
        lineas.append("\n🏢 OTRAS EMPRESAS:")
        for emp in analisis["empresas"]:
            nombre = emp.get("nombre", "?")
            rol = emp.get("rol", "")
            desc = emp.get("descripcion", "")
            actual = " [ACTUAL]" if emp.get("es_actual") else ""
            lineas.append(f"\n  🏢 {nombre}{actual}")
            if rol:
                lineas.append(f"     Rol: {rol}")
            if desc:
                lineas.append(f"     Actividad: {desc}")
    
    # Roles múltiples
    if analisis.get("roles_actuales_multiples"):
        lineas.append("\n⚡ MÚLTIPLES ROLES ACTUALES: Sí")
    
    # Sector
    sector = analisis.get("sector_principal", "")
    if sector:
        lineas.append(f"\n🏭 SECTOR PRINCIPAL: {sector}")
    
    # Resumen ejecutivo
    if analisis.get("resumen_ejecutivo"):
        lineas.append(f"\n📋 RESUMEN EJECUTIVO:\n{analisis['resumen_ejecutivo']}")
    
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


def extraer_datos_excel_para_ia(row, col_map: dict) -> dict:
    """Extrae datos relevantes del Excel para pasar al LLM como contexto."""
    datos = {}
    
    # Patentes
    if "patentes" in col_map:
        datos["patentes"] = str(row.get(col_map["patentes"], ""))
    elif "Representative_Patent_Titles" in row.index:
        datos["patentes"] = str(row.get("Representative_Patent_Titles", ""))
    
    # Publicaciones
    if "publicaciones" in col_map:
        datos["publicaciones"] = str(row.get(col_map["publicaciones"], ""))
    elif "Publication_Articles_Total_Area" in row.index:
        datos["publicaciones"] = str(row.get("Publication_Articles_Total_Area", ""))
    
    # Institución
    if "institucion" in col_map:
        datos["institucion"] = str(row.get(col_map["institucion"], ""))
    
    # Score
    if "score" in col_map:
        datos["score"] = str(row.get(col_map["score"], ""))
    elif "Score_10xPatents_plus_Articles" in row.index:
        datos["score"] = str(row.get("Score_10xPatents_plus_Articles", ""))
    
    return datos


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
        debug_mode = st.checkbox("🔍 Activar modo debug", value=False)
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
            st.success("✅ Token cargado")
        else:
            token = st.text_input("Token Browserless", type="password")

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
        cookies_text = st.text_area("Pega cookies (JSON)", height=150, label_visibility="collapsed")

        if cookies_text and st.button("🔑 Cargar cookies"):
            with st.spinner("Parseando..."):
                cookies = parse_cookies_text(cookies_text)
                if cookies:
                    st.session_state.cookies = cookies
                    st.success(f"✅ {len(cookies)} cookies cargadas")

                    if st.session_state.api:
                        st.session_state.scraper = LinkedInScraper(st.session_state.api, cookies)
                        
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

        st.markdown("### 📊 Estado")
        st.write(f"🌐 Browserless: {'🟢 OK' if st.session_state.api else '🟡'}")
        st.write(f"🔗 LinkedIn: {'🟢 OK' if st.session_state.linkedin_ok else '🟡'}")
        st.write(f"🤖 OpenAI: {'🟢 OK' if st.session_state.openai_ok else '🟡'}")
        st.write(f"👥 CVs: {len(st.session_state.cvs)}")
        st.write(f"🏭 Análisis: {len(st.session_state.analisis)}")

        if st.button("🔄 Reiniciar"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    # ========================================================================
    # MAIN
    # ========================================================================
    st.markdown('<p class="big-header">🚀 Spin-off Detector</p>', unsafe_allow_html=True)
    st.markdown("Analiza investigadores y detecta **patentes**, **spin-offs** y **actividad industrial**.")

    # STEP 1: Excel
    st.markdown("### 1️⃣ Cargar Excel")
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
            elif "patent" in cl and "title" in cl:
                col_map["patentes"] = col
            elif "score" in cl and "10x" in cl:
                col_map["score"] = col
            elif "publication" in cl and "total" in cl:
                col_map["publicaciones"] = col

        c1, c2, c3 = st.columns(3)
        c1.metric("👤 Nombre", col_map.get("nombre", "❌"))
        c2.metric("🏛️ Institución", col_map.get("institucion", "❌"))
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
                                st.success(f"✅ {nombre}: {len(results)} candidatos (filtrados)")
                            else:
                                st.warning(f"❌ {nombre}: sin resultados relevantes")
                        
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
                    st.markdown(f'[🌐 Abrir Google]({google_url})')
                
                manual_url = st.text_input("URL LinkedIn", placeholder="https://www.linkedin.com/in/...")
                
                if manual_url and st.button("💾 Guardar URL"):
                    st.session_state.selected_profiles[selected_name] = manual_url
                    st.success(f"✅ URL guardada")

            # Mostrar resultados FILTRADOS con info mejorada
            if st.session_state.search_results:
                st.markdown("### 📋 Selecciona el perfil correcto")
                st.info("💡 Solo se muestran candidatos con coincidencia real de nombre. Ordenados por relevancia.")
                
                for nombre, results in st.session_state.search_results.items():
                    with st.expander(f"👤 {nombre} ({len(results)} candidatos válidos)", expanded=True):
                        inst_excel = str(df[df[col_nombre] == nombre][col_inst].iloc[0]) if col_inst else ""
                        orcid_excel = str(df[df[col_nombre] == nombre][col_orcid].iloc[0]) if col_orcid else ""
                        
                        st.markdown(f"**🏛️ Institución:** {inst_excel[:100]}")
                        if orcid_excel:
                            st.markdown(f"**🔗 ORCID:** [{orcid_excel}]({orcid_excel})")
                        
                        st.divider()
                        
                        options = []
                        for i, r in enumerate(results[:10]):
                            name = r.get('name', 'Sin nombre')
                            context = r.get('context', '')[:200]
                            location = r.get('location', '')
                            current_position = r.get('current_position', '')
                            score = r.get('score', 0)
                            
                            # Label enriquecido
                            label_parts = [f"{i+1}. {name} (score: {score})"]
                            if current_position:
                                label_parts.append(f"   💼 {current_position[:100]}")
                            if location:
                                label_parts.append(f"   📍 {location}")
                            if context and context != current_position:
                                label_parts.append(f"   {context[:150]}")
                            
                            label = "\n".join(label_parts)
                            
                            options.append({
                                "label": label,
                                "href": r['href'],
                                "name": name,
                                "score": score
                            })
                        
                        if options:
                            selected_idx = st.radio(
                                f"Selecciona el perfil de {nombre}:",
                                options=list(range(len(options))),
                                format_func=lambda i: options[i]["label"],
                                key=f"select_{nombre}"
                            )
                            
                            selected = options[selected_idx]
                            st.session_state.selected_profiles[nombre] = selected["href"]
                            
                            st.caption(f"**URL:** {selected['href']}")
                            st.markdown(
                                f'<a href="{selected["href"]}" target="_blank">'
                                f'<button style="background-color:#0073b1;color:white;padding:5px 15px;'
                                f'border:none;border-radius:5px;cursor:pointer;">'
                                f'👁️ Ver perfil en LinkedIn ↗</button></a>',
                                unsafe_allow_html=True
                            )

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
                                secciones = len(cv.get("sections", {}))
                                texto_len = len(cv.get("texto_completo", ""))
                                st.success(f"✅ {nombre}: {secciones} secciones, {texto_len} chars texto completo")
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
                    st.caption(f"📍 {cv.get('ubicacion', 'N/A')}")
                    st.caption(f"🔗 {cv.get('url', 'N/A')}")
                    
                    if cv.get("sections"):
                        for sec, txt in cv.get("sections", {}).items():
                            with st.expander(f"  • {sec} ({len(txt)} chars)", expanded=False):
                                st.text(txt[:2000])
                    
                    if cv.get("texto_completo"):
                        with st.expander(f"  • Texto completo ({len(cv['texto_completo'])} chars)", expanded=False):
                            st.text(cv["texto_completo"][:3000])
                    
                    st.divider()

        # STEP 3: Analizar con IA MEJORADO
        st.markdown("### 3️⃣ Analizar con IA (Patentes + Spin-offs + Actividad Industrial)")

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
                        # Preparar texto del CV
                        cv_text_parts = []
                        if cv.get("headline"):
                            cv_text_parts.append(f"HEADLINE: {cv['headline']}")
                        if cv.get("ubicacion"):
                            cv_text_parts.append(f"UBICACIÓN: {cv['ubicacion']}")
                        
                        for sec, txt in cv.get("sections", {}).items():
                            cv_text_parts.append(f"\n=== {sec.upper()} ===\n{txt}")
                        
                        if cv.get("texto_completo"):
                            cv_text_parts.append(f"\n=== TEXTO COMPLETO ===\n{cv['texto_completo']}")
                        
                        cv_text = "\n".join(cv_text_parts)
                        
                        # Extraer datos del Excel para contexto
                        row = df[df[col_nombre] == nombre].iloc[0] if nombre in df[col_nombre].values else None
                        datos_excel = extraer_datos_excel_para_ia(row, col_map) if row is not None else None
                        
                        analisis = analyzer.analizar_cv(nombre, cv_text, datos_excel)
                        st.session_state.analisis[nombre] = analisis
                        
                        n_pat = len(analisis.get("patentes", []))
                        n_spin = len(analisis.get("spin_offs", []))
                        n_emp = len(analisis.get("empresas", []))
                        sector = analisis.get("sector_principal", "?")
                        
                        st.success(f"✅ **{nombre}**: {n_pat} patentes, {n_spin} spin-offs, {n_emp} empresas | Sector: {sector}")
                    progress.progress((i + 1) / len(st.session_state.cvs))

                st.balloons()

        # Mostrar análisis
        if st.session_state.analisis:
            with st.expander(f"🔬 Análisis completo ({len(st.session_state.analisis)})", expanded=False):
                for nombre, analisis in st.session_state.analisis.items():
                    st.markdown(f"**👤 {nombre}**")
                    
                    # Patentes
                    if analisis.get("patentes"):
                        st.markdown(f"**📜 Patentes ({len(analisis['patentes'])}):**")
                        for pat in analisis["patletes"] if False else analisis["patentes"]:
                            st.caption(f"• {pat.get('titulo', '?')} {pat.get('numero', '')} [{pat.get('anio', '')}]")
                    
                    # Spin-offs
                    if analisis.get("spin_offs"):
                        st.markdown(f"**🚀 Spin-offs ({len(analisis['spin_offs'])}):**")
                        for spin in analisis["spin_offs"]:
                            actual = " [ACTUAL]" if spin.get("es_actual") else ""
                            st.markdown(f"- **{spin.get('nombre', '?')}**{actual} - {spin.get('rol', '')}")
                            if spin.get("descripcion"):
                                st.caption(f"  _{spin['descripcion']}_")
                    
                    # Empresas
                    if analisis.get("empresas"):
                        st.markdown(f"**🏢 Empresas ({len(analisis['empresas'])}):**")
                        for emp in analisis["empresas"]:
                            actual = " [ACTUAL]" if emp.get("es_actual") else ""
                            st.markdown(f"- {emp.get('nombre', '?')}{actual} - {emp.get('rol', '')}")
                    
                    # Roles múltiples
                    if analisis.get("roles_actuales_multiples"):
                        st.warning("⚡ Múltiples roles actuales detectados")
                    
                    # Sector
                    st.info(f"**Sector:** {analisis.get('sector_principal', '?')}")
                    
                    # Resumen
                    if analisis.get("resumen_ejecutivo"):
                        st.markdown(f"**📋 Resumen:** {analisis['resumen_ejecutivo']}")
                    
                    st.divider()

        # STEP 4: Excel
        st.markdown("### 4️⃣ Generar Excel")

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
                total_pat = sum(len(a.get("patentes", [])) for a in st.session_state.analisis.values())
                total_spin = sum(len(a.get("spin_offs", [])) for a in st.session_state.analisis.values())
                total_emp = sum(len(a.get("empresas", [])) for a in st.session_state.analisis.values())
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("👥 Investigadores", len(st.session_state.analisis))
                c2.metric("📜 Patentes", total_pat)
                c3.metric("🚀 Spin-offs", total_spin)
                c4.metric("🏢 Empresas", total_emp)

        elif st.session_state.cvs:
            st.info("👉 Pulsa 'Analizar con IA'")


if __name__ == "__main__":
    main()
