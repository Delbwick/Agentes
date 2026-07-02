"""
LinkedIn CV Analyzer - Spin-off Detector
Versión final equilibrada: búsqueda funcional + selectbox + filtrado suave
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
    .round-badge {
        background: #0073b1;
        color: white;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 0.8rem;
        margin-right: 5px;
    }
    div[data-testid="stSelectbox"] {
        margin-bottom: 1rem;
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

    def test_connection(self) -> tuple:
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
# CLASE: LINKEDIN SCRAPER
# ============================================================================
class LinkedInScraper:
    def __init__(self, api: BrowserlessAPI, cookies: list):
        self.api = api
        self.cookies = cookies if cookies else []
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
        
        if not self.cookies:
            for cookie_name in critical:
                found[cookie_name] = 0
            return found
        
        for cookie_name in critical:
            cookie = next((c for c in self.cookies if c.get("name") == cookie_name), None)
            if cookie:
                found[cookie_name] = len(cookie.get("value", ""))
            else:
                found[cookie_name] = 0
        
        return found

    def _normalize_name(self, name: str) -> str:
        """Normaliza un nombre para comparación."""
        normalized = name.lower()
        normalized = normalized.replace('ı́', 'i').replace('í', 'i').replace('á', 'a')
        normalized = normalized.replace('é', 'e').replace('ó', 'o').replace('ú', 'u')
        normalized = normalized.replace('ñ', 'n').replace('ç', 'c').replace('ü', 'u')
        normalized = re.sub(r'[^a-z\s]', ' ', normalized)
        normalized = ' '.join(normalized.split())
        return normalized

    def _prepare_search_query(self, full_name: str) -> str:
        """Prepara el nombre para búsqueda: elimina iniciales, normaliza caracteres."""
        search_name = full_name
        search_name = search_name.replace('ı́', 'i').replace('í', 'i').replace('á', 'a')
        search_name = search_name.replace('é', 'e').replace('ó', 'o').replace('ú', 'u')
        search_name = search_name.replace('ñ', 'n').replace('ç', 'c').replace('ü', 'u')
        search_name = re.sub(r'\b[A-Z]\.\s*', '', search_name)
        search_name = re.sub(r'[^a-zA-Z\s]', ' ', search_name)
        search_name = ' '.join(search_name.split())
        return search_name

    def _extract_name_from_link(self, link) -> str:
        name = ""
        
        aria_label = link.get("aria-label", "")
        if aria_label and len(aria_label) > 2:
            name = aria_label.strip()
        
        if not name:
            name_span = link.select_one("span[aria-hidden='true']")
            if name_span:
                name = name_span.get_text().strip()
        
        if not name:
            spans = link.select("span")
            for span in spans:
                text = span.get_text().strip()
                if text and len(text) > 2 and not text.startswith("Ver"):
                    name = text
                    break
        
        if not name:
            text = link.get_text().strip()
            if text and len(text) > 2 and len(text) < 100:
                name = text
        
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

    def _extract_location(self, parent) -> str:
        if not parent:
            return ""
        text = parent.get_text()
        if "·" in text:
            parts = text.split("·")
            for part in parts:
                part = part.strip()
                if len(part) < 50 and any(c in part for c in [",", "España", "Spain", "Cataluña", "Madrid", "Barcelona", "Sevilla", "Valencia"]):
                    return part.strip()
        return ""

    def _extract_current_position(self, parent) -> str:
        if not parent:
            return ""
        text = parent.get_text()
        match = re.search(r'([^\n·]+?)\s+en\s+([^\n·]+?)(?:\s+·|\s+\d+\s+a)', text)
        if match:
            return f"{match.group(1).strip()} en {match.group(2).strip()}"
        lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 10]
        if lines:
            return lines[0][:150]
        return ""

    def _clean_linkedin_text(self, text: str) -> str:
        """Limpia el texto eliminando footer, headers y ruido de LinkedIn."""
        if not text:
            return ""
        
        patterns_to_remove = [
            r"Acerca de\s+Accesibilidad\s+Talent Solutions.*?LinkedIn Corporation.*?20\d{2}",
            r"Pautas comunitarias.*?Empleo.*?Marketing Solutions",
            r"Privacidad y condiciones.*?Opciones de publicidad",
            r"Sales Solutions.*?Móvil.*?Pequeñas empresas",
            r"Centro de seguridad",
            r"¿Tienes preguntas\?.*?Centro de ayuda",
            r"Gestiona tu cuenta y la privacidad",
            r"Accede a tu Configuración",
            r"Transparencia de las recomendaciones",
            r"Más información sobre el contenido recomendado",
            r"(?:العربية|বাংলা|Čeština|Dansk|Deutsch|Ελληνικά|English|Español|Suomi|Français|हिंदी|Magyar|Bahasa Indonesia|Italiano|עברית|日本語|한국어|मराठी|Bahasa Malaysia|Nederlands|Norsk|Polski|Português|Română|Русский|Svenska|Tagalog|ภาษาไทย|Türkçe|Українська|Tiếng Việt|简体中文|繁體中文)",
            r"Seleccionar idioma",
            r"Inicio\s+Mi red\s+Empleos\s+Mensajes\s+Notificaciones",
            r"Para negocios.*?Publicidad",
            r"Enviar mensaje\s+Enviar mensaje",
            r"Opciones de publicidad",
            r"¿Por qué estoy viendo este anuncio\?.*?Dinos por qué no quieres ver esto",
            r"Gestiona tus preferencias de publicidad",
            r"Ocultar o denunciar este anuncio",
            r"No quiero ver este anuncio en mi feed",
            r"No quiero ver esto",
            r"Tus comentarios nos ayudarán a mejorar",
            r"Me molesta o no me interesa",
            r"He visto el anuncio demasiadas veces",
            r"Si crees que esta publicación incumple.*?Denunciar este anuncio\s+Enviar",
            r"Información de contacto",
            r"Más de \d+\s+contactos",
            r"·\s*\d+(?:er|º|ª)",
            r"•\s*\d+(?:er|º|ª)",
            r"¿Por qué estoy viendo este anuncio\?",
        ]
        
        cleaned_text = text
        for pattern in patterns_to_remove:
            cleaned_text = re.sub(pattern, "", cleaned_text, flags=re.IGNORECASE | re.DOTALL)
        
        cleaned_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned_text)
        cleaned_text = re.sub(r'\n\s+', '\n', cleaned_text)
        cleaned_text = cleaned_text.strip()
        
        if len(cleaned_text) < 100 and len(text) > 500:
            lines = text.split('\n')
            useful_lines = []
            skip_patterns = [
                r"(acerca de|accesibilidad|talent solutions|pautas comunitarias|empleo|marketing)",
                r"(privacidad|condiciones|opciones de publicidad|sales solutions|móvil)",
                r"(pequeñas empresas|centro de seguridad|linkedin corporation)",
                r"(¿tienes preguntas|centro de ayuda|gestiona tu cuenta)",
                r"(seleccionar idioma|العربية|বাংলা|čeština|dansk|deutsch)",
                r"(enviar mensaje|opciones de publicidad|información de contacto)",
                r"(más de \d+ contactos|denunciar este anuncio)",
            ]
            for line in lines:
                line_clean = line.strip()
                if not line_clean:
                    continue
                if any(re.search(p, line_clean, re.IGNORECASE) for p in skip_patterns):
                    continue
                useful_lines.append(line_clean)
            cleaned_text = '\n'.join(useful_lines)
        
        return cleaned_text

    def _search_single_query(self, query: str, target_words: set, institution: str = "", orcid: str = "") -> list:
        """Ejecuta una búsqueda individual y devuelve resultados con score."""
        search_url = (
            f"https://www.linkedin.com/search/results/people/"
            f"?keywords={requests.utils.quote(query)}&origin=GLOBAL_SEARCH_HEADER"
        )

        response = self.api.get_content(search_url, cookies=self.cookies)
        
        if not response["ok"] or not response["html"]:
            return []

        html = response["html"]

        if "signin" in html.lower()[:1000] or "login" in html.lower()[:1000]:
            return []

        soup = BeautifulSoup(html, "html.parser")
        all_links = soup.select("a[href*='/in/']")

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
            parent = link.find_parent("li") or link.find_parent("div", class_=re.compile("entity-result|search-result"))
            context = self._extract_headline_from_context(parent)
            location = self._extract_location(parent)
            current_position = self._extract_current_position(parent)
            
            img = link.select_one("img")
            avatar_url = img.get("src", "") if img else ""
            
            # Calcular score (sistema simple que funcionaba)
            name_normalized = self._normalize_name(name)
            name_words = set(name_normalized.split())
            common_words = target_words & name_words
            score = len(common_words) * 10
            
            if institution:
                inst_lower = institution.lower()
                inst_words = [w for w in inst_lower.split() if len(w) > 3]
                for word in inst_words[:3]:
                    if word in context.lower():
                        score += 5
            
            if orcid and orcid in context:
                score += 20
            
            if current_position:
                score += 3
            
            if location:
                score += 2
            
            # FILTRADO SUAVE: Solo descartar los que no tienen NINGUNA coincidencia
            if score < 5:
                continue
            
            profile_links.append({
                "href": href,
                "name": name,
                "context": context,
                "location": location,
                "current_position": current_position,
                "avatar_url": avatar_url,
                "score": score,
                "common_words": common_words,
            })

        return profile_links

    def search_person_multi_round(self, full_name: str, institution: str = "", orcid: str = "", 
                                   debug_mode: bool = False, progress_callback=None) -> list:
        """Búsqueda en múltiples rondas."""
        self.debug_info = {"rounds": []}
        
        search_name = self._prepare_search_query(full_name)
        target_words = set(self._normalize_name(full_name).split())
        
        all_results = []
        seen_urls = set()
        
        # RONDA 1: Solo nombre
        if progress_callback:
            progress_callback(f"🔍 Ronda 1: Buscando '{search_name}'...")
        
        round1_results = self._search_single_query(search_name, target_words, institution, orcid)
        
        self.debug_info["rounds"].append({
            "round": 1,
            "query": search_name,
            "found": len(round1_results)
        })
        
        for r in round1_results:
            if r["href"] not in seen_urls:
                r["round"] = 1
                all_results.append(r)
                seen_urls.add(r["href"])
        
        if debug_mode:
            st.info(f"**Ronda 1:** {len(round1_results)} resultados con '{search_name}'")
        
        # RONDA 2: Nombre + Institución
        if len(all_results) < 3 and institution:
            inst_clean = re.sub(r'[;|,()\[\]]', ' ', institution)
            inst_words = [w for w in inst_clean.split() if len(w) > 3]
            
            if inst_words:
                query2 = f"{search_name} {' '.join(inst_words[:2])}"
                
                if progress_callback:
                    progress_callback(f"🔍 Ronda 2: Buscando '{query2}'...")
                
                round2_results = self._search_single_query(query2, target_words, institution, orcid)
                
                self.debug_info["rounds"].append({
                    "round": 2,
                    "query": query2,
                    "found": len(round2_results)
                })
                
                new_count = 0
                for r in round2_results:
                    if r["href"] not in seen_urls:
                        r["round"] = 2
                        r["score"] += 5
                        all_results.append(r)
                        seen_urls.add(r["href"])
                        new_count += 1
                
                if debug_mode:
                    st.info(f"**Ronda 2:** {len(round2_results)} resultados ({new_count} nuevos)")
        
        # RONDA 3: Nombre + ORCID
        if len(all_results) < 3 and orcid:
            orcid_id = orcid.split("/")[-1] if "/" in orcid else orcid
            query3 = f"{search_name} {orcid_id}"
            
            if progress_callback:
                progress_callback(f"🔍 Ronda 3: Buscando con ORCID...")
            
            round3_results = self._search_single_query(query3, target_words, institution, orcid)
            
            self.debug_info["rounds"].append({
                "round": 3,
                "query": query3,
                "found": len(round3_results)
            })
            
            new_count = 0
            for r in round3_results:
                if r["href"] not in seen_urls:
                    r["round"] = 3
                    r["score"] += 10
                    all_results.append(r)
                    seen_urls.add(r["href"])
                    new_count += 1
            
            if debug_mode:
                st.info(f"**Ronda 3:** {len(round3_results)} resultados ({new_count} nuevos)")
        
        all_results.sort(key=lambda x: x["score"], reverse=True)
        
        self.debug_info["total_found"] = len(all_results)
        
        if debug_mode:
            st.success(f"✅ Total combinado: {len(all_results)} candidatos únicos")
        
        return all_results

    def search_person(self, full_name: str, institution: str = "", orcid: str = "", debug_mode: bool = False) -> list:
        return self.search_person_multi_round(full_name, institution, orcid, debug_mode)

    def extract_full_cv(self, profile_url: str, debug_mode: bool = False) -> dict:
        """Extrae CV completo con limpieza de ruido."""
        response = self.api.get_content(profile_url, cookies=self.cookies)

        if not response["ok"] or not response["html"]:
            if debug_mode:
                st.error(f"❌ Error: {response.get('error')}")
            return None

        html = response["html"]
        soup = BeautifulSoup(html, "html.parser")
        
        cv = {"url": profile_url, "sections": {}}

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

        headline_selectors = [
            ".text-body-medium.break-words",
            ".text-body-medium",
            "div[class*='text-body-medium']",
        ]
        for selector in headline_selectors:
            headline = soup.select_one(selector)
            if headline:
                cv["headline"] = headline.get_text().strip()
                break
        else:
            cv["headline"] = ""

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
                    section_text = section.get_text(separator="\n", strip=True)
                    cv["sections"][nombre_seccion] = self._clean_linkedin_text(section_text)
                    break

        main = soup.select_one("main")
        if main:
            full_text = main.get_text(separator="\n", strip=True)
            cv["texto_completo"] = self._clean_linkedin_text(full_text)
        else:
            body = soup.select_one("body")
            if body:
                full_text = body.get_text(separator="\n", strip=True)
                cv["texto_completo"] = self._clean_linkedin_text(full_text)
            else:
                cv["texto_completo"] = ""

        if not cv["sections"] and cv["texto_completo"]:
            text = cv["texto_completo"]
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
                    if len(section_text) > 50:
                        cv["sections"][section_name] = self._clean_linkedin_text(section_text)[:3000]

        if debug_mode:
            st.info(f"📄 CV extraído: {cv['nombre']}")
            st.write(f"**Headline:** {cv['headline']}")
            st.write(f"**Secciones:** {', '.join(cv['sections'].keys())}")

        return cv


# ============================================================================
# CLASE: CV ANALYZER (OpenAI)
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
    lineas = [f"=== {nombre_original} ===", ""]
    
    if cv:
        lineas.append("📄 PERFIL LINKEDIN:")
        if cv.get("headline"):
            lineas.append(f"🎯 {cv['headline']}")
        if cv.get("ubicacion"):
            lineas.append(f"📍 {cv['ubicacion']}")
        if cv.get("url"):
            lineas.append(f"🔗 {cv['url']}")
        
        for seccion, texto in cv.get("sections", {}).items():
            if texto and len(texto) > 50:
                lineas.append(f"\n— {seccion.upper()} —")
                lineas.append(texto[:500])
    
    lineas.append("\n" + "=" * 70)
    lineas.append("🔬 ANÁLISIS SPIN-OFFS / PATENTES / ACTIVIDAD INDUSTRIAL:")
    lineas.append("=" * 70)
    
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
    
    if analisis.get("roles_actuales_multiples"):
        lineas.append("\n⚡ MÚLTIPLES ROLES ACTUALES: Sí")
    
    sector = analisis.get("sector_principal", "")
    if sector:
        lineas.append(f"\n🏭 SECTOR PRINCIPAL: {sector}")
    
    if analisis.get("resumen_ejecutivo"):
        lineas.append(f"\n📋 RESUMEN EJECUTIVO:\n{analisis['resumen_ejecutivo']}")
    
    return "\n".join(lineas)


# ============================================================================
# HELPERS
# ============================================================================
def parse_cookies_text(cookies_text: str) -> list:
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
            return normalized if normalized else []
    except json.JSONDecodeError:
        pass
    return []


def _cv_cache_path(nombre: str) -> Path:
    safe = re.sub(r'[^\w\-]', '_', nombre)
    return CACHE_DIR / f"{safe}.json"


def get_cached_cv(nombre: str) -> dict:
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
    datos = {}
    
    if "patentes" in col_map and col_map["patentes"]:
        val = row.get(col_map["patentes"], "")
        if pd.notna(val):
            datos["patentes"] = str(val)
    elif "Representative_Patent_Titles" in row.index:
        val = row.get("Representative_Patent_Titles", "")
        if pd.notna(val):
            datos["patentes"] = str(val)
    
    if "publicaciones" in col_map and col_map["publicaciones"]:
        val = row.get(col_map["publicaciones"], "")
        if pd.notna(val):
            datos["publicaciones"] = str(val)
    elif "Publication_Articles_Total_Area" in row.index:
        val = row.get("Publication_Articles_Total_Area", "")
        if pd.notna(val):
            datos["publicaciones"] = str(val)
    
    if "institucion" in col_map and col_map["institucion"]:
        val = row.get(col_map["institucion"], "")
        if pd.notna(val):
            datos["institucion"] = str(val)
    
    if "score" in col_map and col_map["score"]:
        val = row.get(col_map["score"], "")
        if pd.notna(val):
            datos["score"] = str(val)
    elif "Score_10xPatents_plus_Articles" in row.index:
        val = row.get("Score_10xPatents_plus_Articles", "")
        if pd.notna(val):
            datos["score"] = str(val)
    
    return datos


# ============================================================================
# STREAMLIT APP
# ============================================================================
def main():
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
    if "search_debug" not in st.session_state:
        st.session_state.search_debug = {}
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
                        
                        try:
                            critical = st.session_state.scraper.check_critical_cookies()
                            if critical is None:
                                critical = {}
                            st.write("**Cookies críticas:**")
                            for name, length in critical.items():
                                if length > 0:
                                    st.success(f"✅ {name}: {length} chars")
                                else:
                                    st.error(f"❌ {name}: FALTA")
                        except Exception as e:
                            st.warning(f"No se pudo verificar cookies: {e}")
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
        if st.session_state.api:
            st.write(f"💳 Créditos: {st.session_state.api.credits_used}")

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
            elif "patent" in cl and "title" in cl:
                col_map["patentes"] = col
            elif "score" in cl and "10x" in cl:
                col_map["score"] = col
            elif "publication" in cl and "total" in cl:
                col_map["publicaciones"] = col

        col_nombre = col_map.get("nombre")
        col_inst = col_map.get("institucion")
        col_orcid = col_map.get("orcid")
        col_industrial = col_map.get("industrial")
        col_score = col_map.get("score")
        col_patentes = col_map.get("patentes")
        col_publicaciones = col_map.get("publicaciones")

        st.markdown("#### 📊 Vista previa del dataset")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("👥 Investigadores", len(df))
        
        if col_inst and col_inst in df.columns:
            c2.metric("🏛️ Con institución", int(df[col_inst].notna().sum()))
        else:
            c2.metric("🏛️ Con institución", 0)
        
        if col_orcid and col_orcid in df.columns:
            c3.metric("🆔 Con ORCID", int(df[col_orcid].notna().sum()))
        else:
            c3.metric("🆔 Con ORCID", 0)
        
        if col_industrial and col_industrial in df.columns:
            c4.metric("🏭 Con info industrial", int(df[col_industrial].notna().sum()))
        else:
            c4.metric("🏭 Con info industrial", 0)
        
        with st.expander("🔍 Columnas detectadas", expanded=False):
            if col_map:
                col_list = []
                for key, col in col_map.items():
                    col_list.append(f"**{key}**: `{col}`")
                st.markdown("\n".join(col_list))
            else:
                st.warning("No se detectó ninguna columna conocida")
            
            missing = []
            if not col_nombre:
                missing.append("❌ Nombre")
            if not col_inst:
                missing.append("⚠️ Institución")
            if not col_orcid:
                missing.append("⚠️ ORCID")
            if not col_industrial:
                missing.append("ℹ️ INDUSTRIAL info (se creará)")
            if missing:
                st.warning("Columnas faltantes: " + ", ".join(missing))
        
        with st.expander("📋 Ver dataset completo", expanded=False):
            display_cols = []
            if col_nombre and col_nombre in df.columns:
                display_cols.append(col_nombre)
            if col_inst and col_inst in df.columns:
                display_cols.append(col_inst)
            if col_orcid and col_orcid in df.columns:
                display_cols.append(col_orcid)
            if col_score and col_score in df.columns:
                display_cols.append(col_score)
            if col_patentes and col_patentes in df.columns:
                display_cols.append(col_patentes)
            if col_industrial and col_industrial in df.columns:
                display_cols.append(col_industrial)
            
            if display_cols:
                st.dataframe(df[display_cols], use_container_width=True, height=400)
            else:
                st.dataframe(df, use_container_width=True, height=400)
        
        if col_inst and col_inst in df.columns:
            with st.expander("📈 Distribución por institución", expanded=False):
                try:
                    inst_counts = df[col_inst].value_counts().head(10)
                    if len(inst_counts) > 0:
                        st.bar_chart(inst_counts)
                    else:
                        st.info("No hay datos de institución para mostrar")
                except Exception as e:
                    st.warning(f"No se pudo generar el gráfico: {e}")

        if not col_nombre or col_nombre not in df.columns:
            st.error("❌ No se detectó columna de nombres.")
            st.stop()

        # STEP 2: Buscar CVs
        st.markdown("### 2️⃣ Buscar CVs en LinkedIn")

        if not st.session_state.linkedin_ok:
            st.warning("⚠️ Primero verifica sesión LinkedIn")
        else:
            tab1, tab2 = st.tabs(["🔍 Búsqueda automática (multi-ronda)", "🔗 URL manual"])
            
            with tab1:
                st.info("""
💡 **Búsqueda en 3 rondas automáticas:**
1. **Ronda 1**: Solo nombre
2. **Ronda 2**: Nombre + institución (si hay < 3 resultados)
3. **Ronda 3**: Nombre + ORCID (si hay < 3 resultados)

Los resultados se combinan y ordenan por relevancia.
""")
                seleccion = st.multiselect(
                    "Selecciona investigadores",
                    df[col_nombre].tolist(),
                    default=df[col_nombre].tolist()[:1]
                )

                if st.button("🔍 Buscar candidatos (multi-ronda)", type="primary", use_container_width=True):
                    progress = st.progress(0)
                    status_container = st.container()
                    
                    for i, nombre in enumerate(seleccion):
                        row_match = df[df[col_nombre] == nombre]
                        if len(row_match) == 0:
                            continue
                        
                        row = row_match.iloc[0]
                        inst = str(row.get(col_inst, "")) if col_inst and col_inst in df.columns and pd.notna(row.get(col_inst, "")) else ""
                        orcid = str(row.get(col_orcid, "")) if col_orcid and col_orcid in df.columns and pd.notna(row.get(col_orcid, "")) else ""

                        with status_container:
                            with st.spinner(f"🔍 {nombre}..."):
                                def update_progress(msg):
                                    st.caption(msg)
                                
                                results = st.session_state.scraper.search_person_multi_round(
                                    str(nombre), str(inst), str(orcid), 
                                    debug_mode=st.session_state.debug_mode,
                                    progress_callback=update_progress
                                )
                                
                                if results:
                                    st.session_state.search_results[str(nombre)] = results
                                    st.session_state.search_debug[str(nombre)] = {
                                        "institution": inst,
                                        "orcid": orcid,
                                        "rounds": st.session_state.scraper.debug_info.get("rounds", []),
                                        "total": len(results)
                                    }
                                    
                                    rounds_info = st.session_state.scraper.debug_info.get("rounds", [])
                                    rounds_summary = " | ".join([f"R{r['round']}: {r['found']}" for r in rounds_info])
                                    st.success(f"✅ {nombre}: {len(results)} candidatos ({rounds_summary})")
                                else:
                                    st.warning(f"❌ {nombre}: sin candidatos válidos")
                        
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

            # Mostrar resultados con SELECTBOX
            if st.session_state.search_results:
                st.markdown("### 📋 Selecciona el perfil correcto")
                st.info("💡 Usa el desplegable para seleccionar el perfil. Verifica la URL antes de confirmar.")
                
                for nombre, results in st.session_state.search_results.items():
                    debug_info = st.session_state.search_debug.get(nombre, {})
                    rounds = debug_info.get("rounds", [])
                    
                    with st.expander(f"👤 {nombre} ({len(results)} candidatos)", expanded=True):
                        row_match = df[df[col_nombre] == nombre]
                        if len(row_match) > 0:
                            row = row_match.iloc[0]
                            inst_excel = str(row.get(col_inst, "")) if col_inst and col_inst in df.columns and pd.notna(row.get(col_inst, "")) else ""
                            orcid_excel = str(row.get(col_orcid, "")) if col_orcid and col_orcid in df.columns and pd.notna(row.get(col_orcid, "")) else ""
                        else:
                            inst_excel = ""
                            orcid_excel = ""
                        
                        col_info1, col_info2 = st.columns(2)
                        with col_info1:
                            if inst_excel:
                                st.markdown(f"**🏛️ Institución:** {inst_excel[:100]}")
                            else:
                                st.markdown("**🏛️ Institución:** No disponible")
                        with col_info2:
                            if orcid_excel:
                                st.markdown(f"**🔗 ORCID:** [{orcid_excel}]({orcid_excel})")
                            else:
                                st.markdown("**🔗 ORCID:** No disponible")
                        
                        if rounds:
                            st.markdown("**🔄 Resumen de búsquedas:**")
                            cols = st.columns(min(len(rounds), 3))
                            for idx, r in enumerate(rounds):
                                if idx < len(cols):
                                    with cols[idx]:
                                        st.metric(f"Ronda {r['round']}", f"{r['found']} resultados")
                                        st.caption(f"`{r['query'][:40]}`")
                        
                        st.divider()
                        
                        # Construir opciones para el selectbox
                        options = []
                        option_map = {}
                        
                        for i, r in enumerate(results[:15]):
                            name = r.get('name', 'Sin nombre')
                            context = r.get('context', '')[:100]
                            location = r.get('location', '')
                            current_position = r.get('current_position', '')
                            score = r.get('score', 0)
                            round_num = r.get('round', 1)
                            common_words = r.get('common_words', set())
                            
                            round_badge = f"[R{round_num}]"
                            
                            # Construir label del selectbox
                            label_parts = [f"{i+1}. {name} {round_badge} (score: {score})"]
                            if common_words:
                                label_parts.append(f" | Coincide: {', '.join(list(common_words)[:3])}")
                            if current_position:
                                label_parts.append(f" | {current_position[:80]}")
                            if location:
                                label_parts.append(f" | 📍 {location}")
                            if context and context != current_position:
                                label_parts.append(f" | {context[:100]}")
                            
                            label = "".join(label_parts)
                            options.append(label)
                            option_map[label] = r
                        
                        if options:
                            # SELECTBOX en lugar de radio buttons
                            selected_label = st.selectbox(
                                f"Selecciona el perfil de **{nombre}**:",
                                options=options,
                                key=f"select_{nombre}",
                                index=0
                            )
                            
                            # Obtener resultado seleccionado
                            selected = option_map[selected_label]
                            
                            # Guardar automáticamente
                            st.session_state.selected_profiles[nombre] = selected["href"]
                            
                            # Mostrar URL para verificar
                            st.caption(f"**🔗 URL seleccionada:** {selected['href']}")
                            
                            # Botón para abrir en nueva pestaña
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
            st.write(f"**Perfiles seleccionados:** {len(st.session_state.selected_profiles)}")
            
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
                                st.success(f"✅ {nombre}: {secciones} secciones, {texto_len} chars")
                            else:
                                st.warning(f"⚠️ {nombre}: no se pudo extraer")
                    
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

        # STEP 3: Analizar con IA
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
                        
                        row_match = df[df[col_nombre] == nombre]
                        if len(row_match) > 0:
                            row = row_match.iloc[0]
                            datos_excel = extraer_datos_excel_para_ia(row, col_map)
                        else:
                            datos_excel = None
                        
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
                    
                    if analisis.get("patentes"):
                        st.markdown(f"**📜 Patentes ({len(analisis['patentes'])}):**")
                        for pat in analisis["patentes"]:
                            st.caption(f"• {pat.get('titulo', '?')} {pat.get('numero', '')} [{pat.get('anio', '')}]")
                    
                    if analisis.get("spin_offs"):
                        st.markdown(f"**🚀 Spin-offs ({len(analisis['spin_offs'])}):**")
                        for spin in analisis["spin_offs"]:
                            actual = " [ACTUAL]" if spin.get("es_actual") else ""
                            st.markdown(f"- **{spin.get('nombre', '?')}**{actual} - {spin.get('rol', '')}")
                            if spin.get("descripcion"):
                                st.caption(f"  _{spin['descripcion']}_")
                    
                    if analisis.get("empresas"):
                        st.markdown(f"**🏢 Empresas ({len(analisis['empresas'])}):**")
                        for emp in analisis["empresas"]:
                            actual = " [ACTUAL]" if emp.get("es_actual") else ""
                            st.markdown(f"- {emp.get('nombre', '?')}{actual} - {emp.get('rol', '')}")
                    
                    if analisis.get("roles_actuales_multiples"):
                        st.warning("⚡ Múltiples roles actuales detectados")
                    
                    st.info(f"**Sector:** {analisis.get('sector_principal', '?')}")
                    
                    if analisis.get("resumen_ejecutivo"):
                        st.markdown(f"**📋 Resumen:** {analisis['resumen_ejecutivo']}")
                    
                    st.divider()

        # STEP 4: Excel (CORREGIDO con .loc)
        st.markdown("### 4️⃣ Generar Excel")

        if st.session_state.analisis:
            if st.button("📊 Generar Excel", type="primary", use_container_width=True):
                df_out = df.copy()
                col_industrial_out = col_map.get("industrial", "INDUSTRIAL info")
                
                # CORRECCIÓN: Usar .loc en lugar de .at para evitar TypeError
                if col_industrial_out not in df_out.columns:
                    df_out[col_industrial_out] = [""] * len(df_out)
                
                # Forzar tipo object para aceptar strings largos
                df_out[col_industrial_out] = df_out[col_industrial_out].astype(object)

                for idx, row in df_out.iterrows():
                    nombre = row[col_nombre]
                    cv = st.session_state.cvs.get(nombre, {})
                    analisis = st.session_state.analisis.get(nombre, {})
                    if cv or analisis:
                        texto = formatear_para_excel(str(nombre), cv, analisis)
                        # USAR .loc en vez de .at
                        df_out.loc[idx, col_industrial_out] = texto

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
                    if col_industrial_out in df_out.columns:
                        text_format = workbook.add_format({'text_wrap': True, 'valign': 'top'})
                        col_idx = df_out.columns.get_loc(col_industrial_out)
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
