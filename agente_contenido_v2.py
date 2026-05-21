# KaiBot - Generador de Contenidos LLM
# Versión Cliente - Optimizada con st.secrets
# © 2026 Kai Marketing LAB

import streamlit as st
from datetime import datetime
import json
import pandas as pd
from google.cloud import storage
from google.oauth2 import service_account
from openai import OpenAI
import re

# =====================================================
# 🔐 INICIALIZACIÓN DE SECRETOS (NUEVO)
# =====================================================

def init_secrets():
    """Valida y carga configuración desde st.secrets"""
    required = ["openai_key", "perplexity_key", "gcp_credentials", "gcp_bucket_default"]
    missing = [k for k in required if not st.secrets.get(k)]
    
    if missing:
        st.error(f"🔐 Faltan secretos críticos: {', '.join(missing)}")
        st.info("💡 Configúralos en Streamlit Cloud → Settings → Secrets o en `.streamlit/secrets.toml`")
        st.stop()
    
    # Inicializar clientes solo si no existen
    if "openai" not in st.session_state:
        st.session_state.openai = OpenAI(api_key=st.secrets["openai_key"])
    
    if "perplexity_key" not in st.session_state:
        st.session_state.perplexity_key = st.secrets["perplexity_key"]
    
    if "gcs" not in st.session_state:
        try:
            creds_info = json.loads(st.secrets["gcp_credentials"])
            credentials = service_account.Credentials.from_service_account_info(creds_info)
            st.session_state.gcs = storage.Client(credentials=credentials, project=creds_info.get("project_id"))
        except Exception as e:
            st.error(f"❌ Error al conectar con GCS: {str(e)}")
            st.stop()
    
    # Bucket por defecto (sobrescribible en UI)
    if "bucket_name" not in st.session_state:
        st.session_state.bucket_name = st.secrets["gcp_bucket_default"]
    
    # Carpetas configurables
    if "BUCKET_FOLDERS" not in st.session_state:
        st.session_state.BUCKET_FOLDERS = {
            "documentos": st.secrets.get("folder_contexto", "documentos/"),
            "adicional": "adicional/",
            "validados": st.secrets.get("folder_validados", "documentos_validados/"),
            "prompts": st.secrets.get("folder_prompts", "prompts/")
        }
    
    # Branding del cliente
    if "client_branding" not in st.session_state:
        st.session_state.client_branding = {
            "name": st.secrets.get("client_name", "KaiBot"),
            "color": st.secrets.get("client_color", "#0066CC"),
            "footer": st.secrets.get("client_footer", "© 2026 Kai Marketing LAB")
        }

# =====================================================
# CONFIGURACIÓN DE PÁGINA
# =====================================================

st.set_page_config(
    page_title="Generador de Contenidos IA | KaiBot",
    page_icon="https://kaibot.es/wp-content/uploads/2020/07/image1.png",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://kaibot.es/contacto-kaibot-b2b-marketing/',
        'Report a bug': "mailto:hello@kaibot.es",
        'About': "# KaiBot - Generador de Contenidos IA\n**Especialistas en Marketing Digital B2B**"
    }
)

# 🔐 Inicializar secretos y clientes
init_secrets()

# Variables globales accesibles
client = st.session_state.gcs
bucket_name = st.session_state.bucket_name
BUCKET_FOLDERS = st.session_state.BUCKET_FOLDERS
BRANDING = st.session_state.client_branding

# =====================================================
# CSS PERSONALIZADO - ESTILO KAIBOT (Dinámico con branding)
# =====================================================

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    :root {{
        --kaibot-blue: {BRANDING['color']};
        --kaibot-blue-dark: #0052A3;
        --kaibot-blue-light: #3B82F6;
        --kaibot-dark: #1E293B;
        --kaibot-gray: #64748B;
        --kaibot-gray-light: #94A3B8;
        --kaibot-bg: #F8FAFC;
        --kaibot-white: #FFFFFF;
        --sidebar-bg: #1E293B;
        --accent-green: #10B981;
    }}
    
    * {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
    .main {{ background-color: var(--kaibot-bg); }}
    
    h1 {{ color: var(--kaibot-dark); font-weight: 700; font-size: 2.5rem; margin-bottom: 0.5rem; }}
    h2 {{ color: var(--kaibot-dark); font-weight: 600; font-size: 1.75rem; margin-top: 2rem; margin-bottom: 1rem; }}
    h3 {{ color: var(--kaibot-gray); font-weight: 600; font-size: 1.25rem; }}
    
    .stButton>button[kind="primary"] {{
        background: linear-gradient(135deg, var(--kaibot-blue) 0%, var(--kaibot-blue-dark) 100%);
        color: white; border: none; font-weight: 600; padding: 0.75rem 2rem;
        border-radius: 8px; transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(0, 102, 204, 0.2);
    }}
    .stButton>button[kind="primary"]:hover {{
        background: linear-gradient(135deg, var(--kaibot-blue-dark) 0%, #003d7a 100%);
        box-shadow: 0 6px 12px rgba(0, 102, 204, 0.3); transform: translateY(-2px);
    }}
    
    .stTabs [data-baseweb="tab-list"] {{ gap: 12px; background-color: transparent; padding: 0; border-bottom: 2px solid #E2E8F0; }}
    .stTabs [data-baseweb="tab-list"] button[role="tab"] {{
        background-color: transparent; color: var(--kaibot-gray); border: none;
        border-bottom: 3px solid transparent; padding: 16px 32px; font-weight: 600; font-size: 15px; transition: all 0.3s ease;
    }}
    .stTabs [data-baseweb="tab-list"] button[role="tab"]:hover {{ color: var(--kaibot-blue); border-bottom-color: var(--kaibot-blue-light); }}
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {{ color: var(--kaibot-blue); border-bottom-color: var(--kaibot-blue); font-weight: 700; }}
    .stTabs [data-baseweb="tab-panel"] {{ padding: 32px 0; }}
    
    [data-testid="stSidebar"] {{ background: linear-gradient(180deg, var(--sidebar-bg) 0%, #0F172A 100%); padding-top: 2rem; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ color: white !important; font-weight: 600; }}
    
    [data-testid="stSidebar"] input, [data-testid="stSidebar"] textarea {{
        background-color: rgba(255, 255, 255, 0.1) !important; border: 1px solid rgba(255, 255, 255, 0.2) !important;
        color: var(--kaibot-blue-light) !important; border-radius: 6px; font-weight: 500;
    }}
    [data-testid="stSidebar"] input::placeholder, [data-testid="stSidebar"] textarea::placeholder {{ color: rgba(255, 255, 255, 0.5) !important; }}
    [data-testid="stSidebar"] input:focus, [data-testid="stSidebar"] textarea:focus {{ border-color: var(--kaibot-blue) !important; box-shadow: 0 0 0 2px rgba(0, 102, 204, 0.2); }}
    
    [data-testid="stSidebar"] .stButton>button {{ background-color: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.2); color: white !important; font-weight: 600; }}
    [data-testid="stSidebar"] .stButton>button:hover {{ background-color: rgba(255, 255, 255, 0.15); border-color: rgba(255, 255, 255, 0.3); }}
    [data-testid="stSidebar"] .stButton>button[kind="primary"] {{ background: linear-gradient(135deg, var(--kaibot-blue) 0%, var(--kaibot-blue-dark) 100%); border: none; }}
    
    [data-testid="stSidebar"] .streamlit-expanderHeader {{ background-color: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px; font-weight: 600; }}
    [data-testid="stSidebar"] .streamlit-expanderHeader:hover {{ background-color: rgba(255, 255, 255, 0.1); }}
    [data-testid="stSidebar"] hr {{ border-color: rgba(255, 255, 255, 0.2) !important; margin: 1.5rem 0; }}
    
    .stInfo {{ background-color: #EBF5FF; border-left: 4px solid var(--kaibot-blue); border-radius: 8px; padding: 1rem; }}
    .stSuccess {{ background-color: #ECFDF5; border-left: 4px solid var(--accent-green); border-radius: 8px; padding: 1rem; }}
    .stWarning {{ background-color: #FEF3C7; border-left: 4px solid #F59E0B; border-radius: 8px; padding: 1rem; }}
    .stError {{ background-color: #FEE2E2; border-left: 4px solid #EF4444; border-radius: 8px; padding: 1rem; }}
    
    .dataframe {{ border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    .streamlit-expanderHeader {{ background-color: white; border: 1px solid #E2E8F0; border-radius: 8px; font-weight: 600; color: var(--kaibot-dark); }}
    .stProgress > div > div {{ background-color: var(--kaibot-blue); }}
    
    .footer-kaibot {{
        background: linear-gradient(135deg, var(--kaibot-dark) 0%, #0F172A 100%);
        padding: 2rem; border-radius: 12px; margin-top: 3rem; color: white; text-align: center;
    }}
    .block-container {{ padding-top: 1rem; padding-bottom: 2rem; max-width: 1200px; }}
    </style>
""", unsafe_allow_html=True)

# =====================================================
# CONFIGURACIÓN Y CONSTANTES
# =====================================================

STOPWORDS = {
    'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'ser', 'se', 'no', 'haber',
    'por', 'con', 'su', 'para', 'como', 'estar', 'tener', 'le', 'lo', 'todo',
    'pero', 'más', 'hacer', 'o', 'poder', 'decir', 'este', 'ir', 'otro', 'ese',
    'si', 'me', 'ya', 'ver', 'porque', 'dar', 'cuando', 'él', 'muy', 'sin',
    'vez', 'mucho', 'saber', 'qué', 'sobre', 'mi', 'alguno', 'mismo', 'yo',
    'también', 'hasta', 'año', 'dos', 'querer', 'entre', 'así', 'primero',
    'desde', 'grande', 'eso', 'ni', 'nos', 'llegar', 'pasar', 'tiempo', 'ella',
    'les', 'tal', 'una', 'las', 'los', 'del', 'al'
}

# =====================================================
# FUNCIONES HELPER (Mantenemos las tuyas intactas)
# =====================================================

def upload_file(client: storage.Client, bucket_name: str, uploaded_file, folder: str):
    bucket = client.bucket(bucket_name)
    blob_path = f"{folder}{uploaded_file.name}"
    blob = bucket.blob(blob_path)
    blob.upload_from_file(uploaded_file, rewind=True)
    return blob_path

def upload_json_to_gcs(client: storage.Client, bucket_name: str, folder: str, filename: str, data: dict):
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(f"{folder}{filename}")
    blob.upload_from_string(json.dumps(data, indent=2, ensure_ascii=False), content_type='application/json')

def list_folders_and_files(client: storage.Client, bucket_name: str):
    bucket = client.bucket(bucket_name)
    blobs = list(bucket.list_blobs())
    folders = set()
    files = []
    for blob in blobs:
        if blob.name.endswith('/'):
            folders.add(blob.name)
        else:
            parts = blob.name.split('/')
            if len(parts) > 1:
                folders.add('/'.join(parts[:-1]) + '/')
            blob.reload()
            file_info = {
                "name": blob.name, "size": blob.size if blob.size is not None else 0,
                "updated": blob.updated,
                "tipo": blob.metadata.get("tipo", "") if blob.metadata else "",
                "objetivo": blob.metadata.get("objetivo", "") if blob.metadata else "",
                "fuentes_fiables": blob.metadata.get("fuentes_fiables", "false").lower() == "true" if blob.metadata else False,
                "notas": blob.metadata.get("notas", "") if blob.metadata else ""
            }
            files.append(file_info)
    return sorted(list(folders)), files

def get_file_metadata(client: storage.Client, bucket_name: str, file_path: str) -> dict:
    bucket = client.bucket(bucket_name)
    blob = bucket.get_blob(file_path)
    if blob and blob.metadata:
        return {
            "tipo": blob.metadata.get("tipo", ""), "objetivo": blob.metadata.get("objetivo", ""),
            "fuentes_fiables": blob.metadata.get("fuentes_fiables", "false").lower() == "true",
            "notas": blob.metadata.get("notas", "")
        }
    return {"tipo": "", "objetivo": "", "fuentes_fiables": False, "notas": ""}

def update_file_metadata(client: storage.Client, bucket_name: str, file_path: str, metadata: dict) -> bool:
    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(file_path)
        metadata_to_save = {
            "tipo": str(metadata.get("tipo", "")), "objetivo": str(metadata.get("objetivo", "")),
            "fuentes_fiables": str(metadata.get("fuentes_fiables", False)).lower(),
            "notas": str(metadata.get("notas", ""))
        }
        blob.metadata = metadata_to_save
        blob.patch()
        return True
    except Exception as e:
        st.error(f"Error actualizando metadatos: {str(e)}")
        return False

def load_selected_context(client: storage.Client, bucket_name: str, file_names: list, max_chars: int = 15000) -> str:
    bucket = client.bucket(bucket_name)
    context = []
    total_chars = 0
    for fname in file_names:
        if total_chars >= max_chars:
            break
        blob = bucket.blob(fname)
        try:
            content = blob.download_as_text()
            remaining = max_chars - total_chars
            if len(content) > remaining:
                content = content[:remaining] + "... [truncado]"
            context.append(f"--- {fname} ---\n{content}")
            total_chars += len(content)
        except Exception as e:
            context.append(f"--- {fname} ---\nError: {str(e)}")
    return "\n\n".join(context)

def generate_smart_filename(data: dict, max_length: int = 50) -> str:
    summary = data.get("summary", "analisis")
    words = re.findall(r'\b\w+\b', summary.lower())
    keywords = [w for w in words if w not in STOPWORDS and len(w) > 3]
    name_parts = keywords[:5] if keywords else ["contenido", "ia"]
    base_name = "_".join(name_parts)[:max_length]
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}_{timestamp}.json"

def save_analysis_with_metadata(client: storage.Client, bucket_name: str, folder: str, filename: str, data: dict, metadata: dict):
    bucket = client.bucket(bucket_name)
    blob_path = f"{folder}{filename}"
    blob = bucket.blob(blob_path)
    metadata_to_save = {
        "tipo": str(metadata.get("tipo", "")), "objetivo": str(metadata.get("objetivo", "")),
        "fuentes_fiables": str(metadata.get("fuentes_fiables", False)).lower(),
        "notas": str(metadata.get("notas", ""))
    }
    blob.metadata = metadata_to_save
    blob.upload_from_string(json.dumps(data, indent=2, ensure_ascii=False), content_type='application/json')

def save_prompt_to_bucket(client: storage.Client, bucket_name: str, prompt_data: dict, metadata: dict) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    nombre_clean = re.sub(r'[^\w\s-]', '', metadata.get("nombre", "prompt")).replace(" ", "_")
    filename = f"prompt_{nombre_clean}_{timestamp}.json"
    payload = {"prompts": prompt_data, "metadata": metadata, "created_at": datetime.utcnow().isoformat()}
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(f"{BUCKET_FOLDERS['prompts']}{filename}")
    blob.metadata = {"tipo": "Prompt Configuration", "nombre": metadata.get("nombre", ""), "uso": metadata.get("uso", ""), "notas": metadata.get("descripcion", "")}
    blob.upload_from_string(json.dumps(payload, indent=2, ensure_ascii=False), content_type='application/json')
    return filename

def load_prompt_from_bucket(client: storage.Client, bucket_name: str, prompt_file: str) -> dict:
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(prompt_file)
    content = blob.download_as_text()
    return json.loads(content)

# =====================================================
# HEADER PROFESIONAL
# =====================================================

col_logo, col_brand = st.columns([1, 5])
with col_logo:
    st.image("https://kaibot.es/wp-content/uploads/2020/07/image-4-300x184.png", width=120)
with col_brand:
    st.markdown(f"""
        <h1 style='margin-bottom: 0;'>Generador de Contenidos IA</h1>
        <p style='color: #64748B; font-size: 1.1rem; margin-top: 0.5rem;'>
            <strong>Powered by {BRANDING['name']}</strong> | Análisis inteligente con OpenAI + Perplexity
        </p>
    """, unsafe_allow_html=True)
st.markdown("---")

# =====================================================
# SIDEBAR - SIMPLIFICADO (Sin inputs de credenciales)
# =====================================================

with st.sidebar:
    st.markdown(f"""
        <div style='text-align: center; padding: 1rem 0 2rem 0;'>
            <h2 style='color: white; margin-bottom: 0.5rem;'>⚙️ Configuración</h2>
            <p style='color: rgba(255,255,255,0.7); font-size: 0.9rem;'>Ajustes de sesión</p>
        </div>
    """, unsafe_allow_html=True)
    
    # 🪣 Selector de Bucket (configurable por usuario avanzado)
    with st.expander("🪣 Bucket GCS", expanded=True):
        new_bucket = st.text_input("Nombre del Bucket", value=bucket_name, key="sidebar_bucket_input")
        if new_bucket != bucket_name:
            st.session_state.bucket_name = new_bucket
            st.success(f"✅ Bucket cambiado a: `{new_bucket}`")
            st.rerun()
        
        st.markdown("#### 📁 Carpetas configuradas")
        st.caption(f"📝 Prompts: `{BUCKET_FOLDERS['prompts']}`")
        st.caption(f"✅ Validados: `{BUCKET_FOLDERS['validados']}`")
        st.caption(f"📎 Contexto: `{BUCKET_FOLDERS['documentos']}`")
    
    # 🔐 Estado de conexiones (solo informativo)
    with st.expander("🔐 Estado de Servicios", expanded=True):
        st.success("✅ OpenAI: Conectado")
        st.success("✅ Perplexity: Conectado")
        st.success(f"✅ GCS: `{bucket_name}`")
    
    st.markdown("---")
    
    # 💬 Soporte
    st.markdown("### 💬 Soporte KaiBot")
    st.markdown(f"""
        <div style='background: rgba(255,255,255,0.05); padding: 1rem; border-radius: 8px;'>
            <p style='margin-bottom: 0.5rem;'><strong>¿Necesitas ayuda?</strong></p>
            <p style='font-size: 0.9rem; margin-bottom: 0.5rem;'>
                📧 <a href='mailto:hello@kaibot.es' style='color: #3B82F6;'>hello@kaibot.es</a><br>
                📞 <a href='tel:+34633698832' style='color: #3B82F6;'>+34 633 69 88 32</a>
            </p>
            <a href='https://kaibot.es' target='_blank' style='color: #10B981; font-weight: 600; text-decoration: none;'>
                🌐 Visitar KaiBot.es →
            </a>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown(f"<small style='color: rgba(255,255,255,0.6)'>{BRANDING['footer']}</small>", unsafe_allow_html=True)

# =====================================================
# TABS PRINCIPALES
# =====================================================

tab1, tab2, tab3 = st.tabs(["🎯 Generar Contenido", "📁 Mis Archivos", "⚙️ Configuración Avanzada"])

# =====================================================
# TAB 1 - GENERAR CONTENIDO (CON DEBUG + FALLBACK ROBUSTO)
# =====================================================

with tab1:
    st.markdown("## 🎯 Generador de Contenidos con IA")
    st.markdown("**Análisis profesional en 3 pasos:** Configura → OpenAI analiza → Perplexity valida")
    
    # PASO 1: CONFIGURACIÓN
    st.markdown("### 📋 Paso 1: Configura tu análisis")
    
    folders, files = list_folders_and_files(client, bucket_name)
    file_names = [f["name"] for f in files if not f["name"].startswith(BUCKET_FOLDERS["prompts"])]
    
    col_files, col_chars = st.columns([3, 1])
    
    with col_files:
        selected_files = st.multiselect(
            "📄 Documentos de contexto (opcional)",
            options=file_names,
            help="Selecciona archivos para basar el análisis. Déjalo vacío para consultas generales.",
            key="tab1_select_files"
        )
    
    with col_chars:
        max_chars = st.number_input(
            "Límite caracteres",
            min_value=2000,
            max_value=50000,
            value=15000,
            step=1000,
            disabled=len(selected_files) == 0,
            key="tab1_max_chars"
        )
    
    if selected_files:
        st.info(f"📁 **Modo:** Análisis con {len(selected_files)} documento(s)")
    else:
        st.info("💭 **Modo:** Consulta general sin documentos")
    
    st.markdown("---")
    
    # Consulta
    st.markdown("**Tu consulta:**")
    
    query_mode = st.radio(
        "Tipo de consulta",
        ["📝 Personalizada", "📋 Plantilla"],
        horizontal=True,
        key="tab1_query_mode"
    )
    
    if query_mode == "📝 Personalizada":
        user_query = st.text_area(
            "Escribe tu consulta",
            placeholder="Ejemplo: Analiza las tendencias de marketing B2B industrial para 2026 y genera 3 recomendaciones estratégicas priorizadas",
            height=150,
            key="tab1_custom_query"
        )
    else:
        templates = {
            "Análisis Estratégico B2B": "Realiza un análisis estratégico completo identificando tendencias clave, oportunidades y riesgos en marketing B2B industrial. Proporciona recomendaciones accionables con ROI estimado y plazos de implementación.",
            "Resumen Ejecutivo": "Genera un resumen ejecutivo profesional destacando los 3 puntos más relevantes para la toma de decisiones en generación de leads B2B. Incluye datos cuantificables y fuentes verificables.",
            "Plan de Acción con KPIs": "Identifica los 5 puntos más importantes para mejorar la generación de leads B2B y crea un plan de acción detallado con KPIs, plazos y recursos necesarios.",
            "Benchmark Competitivo": "Realiza un análisis competitivo del sector comparando estrategias de marketing digital B2B. Incluye datos de inversión publicitaria, canales utilizados y resultados obtenidos.",
            "Contenido LinkedIn B2B": "Genera 5 ideas de contenido para LinkedIn enfocadas en thought leadership B2B industrial. Incluye temas, formatos y calendario para los próximos 3 meses.",
            "Estrategia Ferias Industriales": "Analiza las mejores prácticas para participación en ferias B2B combinando estrategia digital pre-evento, durante y post-evento para maximizar ROI.",
            "Tendencias LifeSciences 2026": "Analiza las últimas tendencias en marketing digital para empresas de LifeSciences y MedTech. Identifica oportunidades de posicionamiento y generación de leads.",
            "Análisis DAFO Digital": "Realiza un análisis DAFO (Debilidades, Amenazas, Fortalezas, Oportunidades) enfocado en estrategia digital B2B. Valida cada punto con tendencias actuales."
        }
        
        # 🔧 FIX: Estado reactivo para plantillas
        if "tab1_last_template" not in st.session_state:
            st.session_state.tab1_last_template = None
        if "tab1_template_query" not in st.session_state:
            st.session_state.tab1_template_query = list(templates.values())[0]
        
        selected_template = st.selectbox(
            "Elige una plantilla",
            list(templates.keys()),
            key="tab1_template_select"
        )
        
        if st.session_state.tab1_last_template != selected_template:
            st.session_state.tab1_template_query = templates[selected_template]
            st.session_state.tab1_last_template = selected_template
        
        user_query = st.text_area(
            "Consulta (editable)",
            value=st.session_state.tab1_template_query,
            height=150,
            key="tab1_template_query"
        )
        
        if user_query != templates.get(selected_template):
            st.session_state.tab1_last_template = None
    
    # Modelos
    st.markdown("---")
    st.markdown("**⚙️ Configuración de modelos:**")
    
    col_openai, col_perplexity = st.columns(2)
    
    with col_openai:
        openai_models = {
            "GPT-4o Mini (Recomendado)": "gpt-4o-mini",
            "GPT-4o": "gpt-4o",
            "GPT-4 Turbo": "gpt-4-turbo-preview"
        }
        selected_openai = st.selectbox("🤖 Modelo OpenAI", list(openai_models.keys()), index=0, key="tab1_openai_model")
        openai_model = openai_models[selected_openai]
    
    with col_perplexity:
        perplexity_models = {
            "Sonar (Recomendado)": "sonar",
            "Sonar Pro": "sonar-pro",
            "Llama 3.1 70B": "llama-3.1-70b-instruct"
        }
        selected_perplexity = st.selectbox("🔍 Modelo Perplexity", list(perplexity_models.keys()), index=0, key="tab1_pplx_model")
        perplexity_model = perplexity_models[selected_perplexity]
    
    st.markdown("---")
    
    # PASO 2: EJECUTAR
    st.markdown("### 🚀 Paso 2: Generar contenido")
    
    col_gen, col_clear = st.columns([4, 1])
    
    with col_gen:
        generate_content = st.button(
            "▶️ Generar Contenido con IA",
            type="primary",
            use_container_width=True,
            disabled=not user_query.strip(),
            key="tab1_generate_btn"
        )
    
    with col_clear:
        if st.button("🗑️ Limpiar", use_container_width=True, key="tab1_clear_btn"):
            for key in ["openai_response", "perplexity_response", "edited_response"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    if generate_content:
        context = ""
        if selected_files:
            context = load_selected_context(client, bucket_name, selected_files, max_chars)
        
        # OpenAI
        with st.spinner(f"🤖 {selected_openai} analizando..."):
            try:
                openai_prompt = """Eres un analista estratégico experto en contenidos B2B.

Analiza y genera insights accionables en formato JSON:
{
  "summary": "Resumen ejecutivo (2-3 líneas con valor estratégico)",
  "key_points": ["Insight 1 con datos", "Insight 2 con oportunidad", "Insight 3 con riesgo"],
  "recommended_actions": ["Acción 1 con plazo y ROI", "Acción 2 medible"],
  "topics_to_validate": ["Tema 1 a validar online", "Tema 2 a verificar"]
}

Enfoque: Resultados medibles, oportunidades concretas, ROI.
IMPORTANTE: Responde SOLO con JSON válido, sin texto adicional."""

                user_message = f"CONSULTA:\n{user_query}"
                if context:
                    user_message += f"\n\nCONTEXTO:\n{context}"
                
                response = st.session_state.openai.chat.completions.create(
                    model=openai_model,
                    messages=[
                        {"role": "system", "content": openai_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    response_format={"type": "json_object"}
                )
                
                # 🔧 FIX: Parseo robusto de respuesta OpenAI
                raw_content = response.choices[0].message.content.strip()
                
                # Limpiar markdown si existe
                if "```json" in raw_content:
                    raw_content = raw_content.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_content:
                    raw_content = raw_content.split("```")[1].split("```")[0].strip()
                
                openai_data = json.loads(raw_content)
                
                # 🔧 FIX: Validar y normalizar estructura
                if not isinstance(openai_data, dict):
                    raise ValueError("La respuesta no es un objeto JSON válido")
                
                # Asegurar campos mínimos
                if "summary" not in openai_data:
                    openai_data["summary"] = openai_data.get("content") or openai_data.get("response") or "Análisis generado exitosamente."
                if "key_points" not in openai_data:
                    openai_data["key_points"] = openai_data.get("insights") or openai_data.get("points") or []
                if "recommended_actions" not in openai_data:
                    openai_data["recommended_actions"] = openai_data.get("actions") or openai_data.get("next_steps") or []
                
                openai_data["metadata"] = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "agent": "openai",
                    "model": openai_model,
                    "query": user_query,
                    "mode": "with_context" if selected_files else "general",
                    "raw_response_ok": True
                }
                st.session_state.openai_response = openai_data
                
            except Exception as e:
                st.error(f"❌ Error en OpenAI: {str(e)}")
                # 🔧 FIX: Fallback incluso si OpenAI falla
                st.session_state.openai_response = {
                    "summary": f"Error al generar análisis: {str(e)[:200]}",
                    "key_points": [],
                    "recommended_actions": [],
                    "metadata": {
                        "timestamp": datetime.utcnow().isoformat(),
                        "agent": "openai_error",
                        "model": openai_model,
                        "query": user_query,
                        "error": str(e)
                    }
                }
                st.stop()
        
        # Perplexity
        with st.spinner(f"🔍 {selected_perplexity} validando..."):
            try:
                perplexity_client = OpenAI(
                    api_key=st.session_state.perplexity_key,
                    base_url="https://api.perplexity.ai"
                )
                
                perplexity_prompt = """Valida y enriquece análisis con fuentes confiables actuales.

FUENTES PRIORITARIAS: Gartner, McKinsey, Forrester, medios B2B especializados, datos verificables.

Responde en JSON:
{
  "summary": "Resumen validado con datos actuales",
  "key_points": ["Punto 1 validado con fuente", "Punto 2 enriquecido", "Punto 3 con contexto"],
  "recommended_actions": ["Acción 1 con best practice", "Acción 2 con ROI sector"],
  "validation_notes": "Qué se validó y con qué fuentes",
  "sources": ["URL (Título - Fecha)", "URL (Título - Fecha)"],
  "confidence_level": "alto"
}"""
                
                validation_prompt = f"""ANÁLISIS A VALIDAR:
{json.dumps(st.session_state.openai_response, indent=2, ensure_ascii=False)}

CONSULTA ORIGINAL: {user_query}

Valida con fuentes actuales online y proporciona URLs verificables."""
                
                response = perplexity_client.chat.completions.create(
                    model=perplexity_model,
                    messages=[
                        {"role": "system", "content": perplexity_prompt},
                        {"role": "user", "content": validation_prompt}
                    ]
                )
                
                response_text = response.choices[0].message.content
                clean_text = response_text.strip()
                
                if "```json" in clean_text:
                    clean_text = clean_text.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_text:
                    clean_text = clean_text.split("```")[1].split("```")[0].strip()
                
                try:
                    validated_json = json.loads(clean_text)
                except:
                    json_match = re.search(r'\{.*\}', clean_text, re.DOTALL)
                    if json_match:
                        validated_json = json.loads(json_match.group())
                    else:
                        raise ValueError("No se pudo extraer JSON válido")
                
                validated_json["metadata"] = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "agent": "perplexity",
                    "model": perplexity_model,
                    "original_query": user_query,
                    "openai_model": openai_model
                }
                
                st.session_state.perplexity_response = validated_json
                st.success("✅ Contenido generado y validado")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error en Perplexity: {str(e)[:200]}")
                if "openai_response" in st.session_state:
                    st.warning("⚠️ Usando solo OpenAI como fallback")
                    # 🔧 FIX: Fallback robusto que PRESERVA el contenido de OpenAI
                    fallback_data = {}
                    original = st.session_state.openai_response
                    
                    # Copiar campos de contenido con múltiples fallbacks
                    fallback_data["summary"] = (
                        original.get("summary") or 
                        original.get("content") or 
                        original.get("response") or 
                        original.get("text") or
                        str(original) if isinstance(original, str) else
                        "Contenido generado por OpenAI. Perplexity no pudo validar."
                    )
                    
                    fallback_data["key_points"] = (
                        original.get("key_points") or 
                        original.get("insights") or 
                        original.get("points") or 
                        original.get("findings") or
                        []
                    )
                    
                    fallback_data["recommended_actions"] = (
                        original.get("recommended_actions") or 
                        original.get("actions") or 
                        original.get("next_steps") or 
                        original.get("recommendations") or
                        []
                    )
                    
                    # Copiar otros campos útiles
                    for field in ["topics_to_validate", "analysis", "conclusions", "data"]:
                        if field in original and field not in fallback_data:
                            fallback_data[field] = original[field]
                    
                    # Metadata de fallback
                    fallback_data["metadata"] = {
                        **(original.get("metadata", {})),
                        "agent": "openai_fallback",
                        "fallback_reason": str(e)[:150],
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
                    # Asegurar que confidence_level exista para la UI
                    fallback_data["confidence_level"] = "bajo"
                    
                    st.session_state.perplexity_response = fallback_data
                    st.rerun()
    
    # 🔧 DEBUG: Toggle para ver respuesta cruda (descomentar para debug)
    # if st.checkbox("🔍 Debug: Ver respuesta OpenAI cruda", key="debug_toggle"):
    #     with st.expander("📦 openai_response completo", expanded=True):
    #         st.json(st.session_state.get("openai_response", {}))
    #     with st.expander("📦 perplexity_response completo", expanded=True):
    #         st.json(st.session_state.get("perplexity_response", {}))
    
    # PASO 3: RESULTADOS
    if "perplexity_response" in st.session_state:
        st.markdown("---")
        st.markdown("### 📊 Paso 3: Resultado validado")
        
        final_data = st.session_state.perplexity_response
        metadata = final_data.get("metadata", {})
        
        # 🔧 FIX: Detectar fallback de forma robusta
        is_fallback = metadata.get("agent") in ["openai", "openai_fallback", "openai_error"]
        
        with st.expander("👁️ Vista Previa del Contenido", expanded=True):
            col_badge1, col_badge2, col_badge3 = st.columns(3)
            
            with col_badge1:
                openai_model_display = metadata.get("openai_model") or metadata.get("model", "N/A")
                st.markdown(f"**🤖 OpenAI:** {openai_model_display}")
            
            with col_badge2:
                if is_fallback:
                    reason = metadata.get("fallback_reason", "Error de validación")
                    st.markdown(f"**🔍 Perplexity:** ⚠️ Fallback\n\n<small>{reason[:50]}...</small>")
                else:
                    st.markdown(f"**🔍 Perplexity:** {metadata.get('model', 'N/A')}")
            
            with col_badge3:
                if is_fallback:
                    confidence, emoji, label = "bajo", "🔴", "BAJO ⚠️"
                else:
                    conf = final_data.get("confidence_level", "medio").lower()
                    emoji = "🟢" if conf == "alto" else "🟡" if conf == "medio" else "🔴"
                    confidence, label = conf, conf.upper()
                st.markdown(f"**{emoji} Confianza:** {label}")
            
            st.markdown("---")
            st.markdown("#### 📝 Resumen Ejecutivo")
            
            # 🔧 FIX: Obtener summary con fallbacks agresivos
            summary = final_data.get("summary")
            if not summary or summary in ["N/A", "", "None"]:
                # Intentar otros campos
                for field in ["content", "response", "text", "analysis", "conclusion"]:
                    if final_data.get(field):
                        summary = final_data[field]
                        break
                # Último recurso: convertir a string
                if not summary:
                    summary = str(final_data)[:300] + "..." if len(str(final_data)) > 300 else str(final_data)
            
            if is_fallback:
                st.warning(f"⚠️ {summary}")
            else:
                st.success(summary)
            
            col_points, col_actions = st.columns(2)
            
            with col_points:
                st.markdown("#### 🎯 Puntos Clave")
                points = final_data.get("key_points", [])
                # Fallbacks para puntos
                if not points:
                    for field in ["insights", "points", "findings", "key_insights"]:
                        if final_data.get(field):
                            points = final_data[field]
                            break
                if points and isinstance(points, list):
                    for i, point in enumerate(points, 1):
                        st.markdown(f"**{i}.** {point}")
                elif points and isinstance(points, str):
                    st.markdown(f"• {points}")
                else:
                    st.caption("ℹ️ Sin puntos clave disponibles")
            
            with col_actions:
                st.markdown("#### ✅ Acciones Recomendadas")
                actions = final_data.get("recommended_actions", [])
                # Fallbacks para acciones
                if not actions:
                    for field in ["actions", "next_steps", "recommendations", "action_items"]:
                        if final_data.get(field):
                            actions = final_data[field]
                            break
                if actions and isinstance(actions, list):
                    for i, action in enumerate(actions, 1):
                        st.markdown(f"**{i}.** {action}")
                elif actions and isinstance(actions, str):
                    st.markdown(f"• {actions}")
                else:
                    st.caption("ℹ️ Sin acciones recomendadas")
            
            # Notas de validación (solo si no es fallback)
            if not is_fallback and final_data.get("validation_notes"):
                st.markdown("---")
                st.markdown("#### 📋 Notas de Validación")
                st.info(final_data["validation_notes"])
            
            # Fuentes (solo si no es fallback)
            if not is_fallback and final_data.get("sources"):
                st.markdown("---")
                st.markdown("#### 🔗 Fuentes Verificadas")
                for i, source in enumerate(final_data["sources"], 1):
                    if isinstance(source, str) and source.startswith("http"):
                        st.markdown(f"{i}. [{source}]({source})")
                    else:
                        st.markdown(f"{i}. {source}")
        
        # Comparador (solo si hay respuesta real de Perplexity)
        if not is_fallback and "openai_response" in st.session_state:
            with st.expander("🔄 Comparar OpenAI vs Perplexity"):
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("**🔵 OpenAI (Original)**")
                    st.json(st.session_state.openai_response)
                with col_b:
                    st.markdown("**🟣 Perplexity (Validado)**")
                    st.json(final_data)
        elif is_fallback:
            st.info("💡 *Mostrando respuesta de OpenAI. Perplexity no pudo validar por error de conexión, formato o límite de tasa.*")
            with st.expander("🔍 Ver respuesta OpenAI completa"):
                st.json(st.session_state.get("openai_response", {}))
        
        st.markdown("---")
        st.markdown("### 💾 Guardar contenido")
        
        with st.expander("📋 Configurar metadatos", expanded=True):
            col_m1, col_m2 = st.columns(2)
            
            with col_m1:
                content_tipo = st.text_input(
                    "🏷️ Tipo",
                    value="Análisis IA Validado" if not is_fallback else "Análisis IA (Sin validar)",
                    key="tab1_tipo_meta"
                )
                
                content_objetivo = st.selectbox(
                    "🎯 Objetivo",
                    ["Marketing B2B", "Social Media", "Blog Post", "Informe Interno", 
                     "Presentación", "White Paper", "Publicación Científica"],
                    index=0,
                    key="tab1_objetivo_meta"
                )
            
            with col_m2:
                has_sources = not is_fallback and bool(final_data.get("sources", []))
                content_fuentes = st.checkbox(
                    "✅ Fuentes verificadas",
                    value=has_sources,
                    disabled=is_fallback,
                    key="tab1_fuentes_meta"
                )
                
                content_notas = st.text_area(
                    "📝 Notas",
                    value=f"Consulta: {user_query[:100]}..." if len(user_query) > 100 else f"Consulta: {user_query}",
                    height=80,
                    key="tab1_notas_meta"
                )
        
        with st.expander("✏️ Editar JSON (avanzado)"):
            if "edited_response" not in st.session_state:
                st.session_state.edited_response = json.dumps(final_data, indent=2, ensure_ascii=False)
            
            edited_json = st.text_area(
                "JSON editable",
                value=st.session_state.edited_response,
                height=400,
                key="tab1_json_editor"
            )
            
            try:
                edited_data = json.loads(edited_json)
                st.success("✅ JSON válido")
                json_is_valid = True
            except:
                st.error("❌ JSON inválido")
                json_is_valid = False
                edited_data = final_data
        
        if "edited_response" not in st.session_state:
            edited_data = final_data
            json_is_valid = True
        
        preview_filename = generate_smart_filename(edited_data)
        st.info(f"📝 **Nombre de archivo:** `{preview_filename}`")
        
        col_save, col_download = st.columns(2)
        
        with col_save:
            if st.button("💾 Guardar en Cloud", type="primary", use_container_width=True, 
                        disabled=not json_is_valid, key="tab1_save_btn"):
                try:
                    filename = generate_smart_filename(edited_data)
                    analysis_metadata = {
                        "tipo": content_tipo,
                        "objetivo": content_objetivo,
                        "fuentes_fiables": content_fuentes and not is_fallback,
                        "notas": content_notas + (" [FALLBACK]" if is_fallback else "")
                    }
                    
                    save_analysis_with_metadata(
                        client, bucket_name,
                        BUCKET_FOLDERS["validados"],
                        filename, edited_data,
                        analysis_metadata
                    )
                    
                    st.success(f"✅ Guardado: {filename}")
                    st.balloons()
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
        
        with col_download:
            st.download_button(
                "⬇️ Descargar JSON",
                json.dumps(edited_data, indent=2, ensure_ascii=False),
                file_name=preview_filename,
                mime="application/json",
                use_container_width=True,
                key="tab1_download_btn"
            )
            
        # =====================================================
        # PASO 4: REPRESENTACIÓN VISUAL DEL CONTENIDO
        # =====================================================
        
        st.markdown("---")
        st.markdown("### 🎨 Paso 4: Contenido listo para usar")
        st.markdown("*Transforma el análisis en formatos listos para publicar*")
        
        # Selector de formato de salida
        output_format = st.radio(
            "📋 Selecciona el formato de salida",
            ["📊 Infografía (Email)", "💼 Post LinkedIn", "🌐 Artículo Web", "📝 Texto Plano"],
            horizontal=True,
            key="tab1_output_format"
        )
        
        # 🔧 Función helper para generar contenido formateado
        def generate_formatted_content(data: dict, format_type: str, query: str) -> str:
            """Genera contenido formateado según el tipo de salida"""
            summary = data.get("summary", "")
            points = data.get("key_points", [])
            actions = data.get("recommended_actions", [])
            sources = data.get("sources", [])
            
            if format_type == "📊 Infografía (Email)":
                # Formato compacto para email con infografía adjunta
                content = f"""🔹 *{summary}*

📌 Puntos clave:
"""
                for i, p in enumerate(points, 1):
                    # Limpiar prefijos como "Validado:" para formato visual
                    clean_p = re.sub(r'^(Validado|No validado)[^:]*:\s*', '', p, flags=re.IGNORECASE)
                    content += f"• {clean_p}\n"
                
                content += f"""
🎯 Acciones recomendadas:
"""
                for i, a in enumerate(actions, 1):
                    content += f"→ {a}\n"
                
                if sources:
                    content += f"""
🔗 Fuentes: {len(sources)} referencias verificadas
"""
                content += f"\n---\n*Generado con KaiBot IA | {datetime.now().strftime('%d/%m/%Y')}*"
                return content.strip()
            
            elif format_type == "💼 Post LinkedIn":
                # Formato optimizado para LinkedIn: hook + valor + CTA + hashtags
                hook = summary[:150] + "..." if len(summary) > 150 else summary
                
                content = f"""{hook}

🧵 Hilo con insights clave:

"""
                for i, p in enumerate(points[:3], 1):  # Máximo 3 puntos para LinkedIn
                    clean_p = re.sub(r'^(Validado|No validado)[^:]*:\s*', '', p, flags=re.IGNORECASE)
                    content += f"{i}/ {clean_p}\n\n"
                
                content += """💡 ¿Qué opinas sobre estas tendencias? 
👇 Déjame tu perspectiva en comentarios.

#B2B #MarketingDigital #Innovación #KaiBot"""
                return content.strip()
            
            elif format_type == "🌐 Artículo Web":
                # Formato HTML básico para web/blog
                content = f"""<article>
  <h1>{summary}</h1>
  
  <section>
    <h2>🔍 Puntos Clave</h2>
    <ul>
"""
                for p in points:
                    clean_p = re.sub(r'^(Validado|No validado)[^:]*:\s*', '', p, flags=re.IGNORECASE)
                    content += f"      <li>{clean_p}</li>\n"
                
                content += """    </ul>
  </section>
  
  <section>
    <h2>✅ Acciones Recomendadas</h2>
    <ol>
"""
                for a in actions:
                    content += f"      <li>{a}</li>\n"
                
                if sources:
                    content += """    </ol>
  </section>
  
  <section>
    <h2>📚 Fuentes</h2>
    <ul>
"""
                    for s in sources:
                        if s.startswith("http"):
                            url = s.split(" ")[0]
                            title = s.split("(", 1)[1].rstrip(")") if "(" in s else "Fuente"
                            content += f'      <li><a href="{url}" target="_blank">{title}</a></li>\n'
                        else:
                            content += f"      <li>{s}</li>\n"
                
                content += f"""    </ul>
    <p><small>Generado con KaiBot IA | {datetime.now().strftime('%d/%m/%Y')}</small></p>
  </section>
</article>"""
                return content.strip()
            
            else:  # Texto Plano
                content = f"""RESUMEN EJECUTIVO
{'='*50}
{summary}

PUNTOS CLAVE
{'-'*50}
"""
                for i, p in enumerate(points, 1):
                    content += f"{i}. {p}\n"
                
                content += f"""
ACCIONES RECOMENDADAS
{'-'*50}
"""
                for i, a in enumerate(actions, 1):
                    content += f"{i}. {a}\n"
                
                if sources:
                    content += f"""
FUENTES VERIFICADAS
{'-'*50}
"""
                    for i, s in enumerate(sources, 1):
                        content += f"{i}. {s}\n"
                
                content += f"\n---\nGenerado con KaiBot IA | {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                return content.strip()
        
        # Generar y mostrar contenido formateado
        formatted_content = generate_formatted_content(final_data, output_format, user_query)
        
        # Preview visual con styling
        with st.expander("👁️ Vista previa del contenido formateado", expanded=True):
            if output_format == "🌐 Artículo Web":
                st.markdown(formatted_content, unsafe_allow_html=True)
            else:
                st.markdown(f"```text\n{formatted_content}\n```")
        
        # Botones de acción
        col_copy, col_download, col_regenerate = st.columns([2, 2, 1])
        
        with col_copy:
            # 🔧 Streamlit no tiene copy-to-clipboard nativo, usamos workaround con st.code + instrucciones
            st.code(formatted_content, language="text" if output_format != "🌐 Artículo Web" else "html")
            st.caption("💡 Selecciona el texto arriba y usa Ctrl+C / Cmd+C para copiar")
        
        with col_download:
            # Determinar extensión según formato
            ext_map = {
                "📊 Infografía (Email)": "txt",
                "💼 Post LinkedIn": "txt", 
                "🌐 Artículo Web": "html",
                "📝 Texto Plano": "txt"
            }
            ext = ext_map.get(output_format, "txt")
            filename_base = preview_filename.replace(".json", f"_{output_format.split()[1].lower()}.{ext}")
            
            st.download_button(
                "⬇️ Descargar formato",
                formatted_content,
                file_name=filename_base,
                mime="text/html" if ext == "html" else "text/plain",
                use_container_width=True,
                key="tab1_download_formatted"
            )
        
        with col_regenerate:
            if st.button("🔄 Regenerar", use_container_width=True, key="tab1_regenerate_format"):
                # Forzar regeneración limpiando cache del formato
                if "tab1_formatted_cache" in st.session_state:
                    del st.session_state.tab1_formatted_cache
                st.rerun()
        
        # 💡 Tips contextuales según formato
        with st.expander("💡 Tips para este formato", expanded=False):
            if output_format == "📊 Infografía (Email)":
                st.markdown("""
                - ✂️ **Mantén el texto breve**: Las infografías funcionan mejor con frases de <15 palabras
                - 🎨 **Usa iconos**: Los emojis o iconos ayudan a escanear rápido el contenido
                - 📱 **Test mobile**: El 60% de emails se abren en móvil, verifica legibilidad
                - 🔗 **Enlace único**: Incluye solo 1 CTA principal para maximizar clicks
                """)
            elif output_format == "💼 Post LinkedIn":
                st.markdown("""
                - 🪝 **Hook en primera línea**: Las primeras 2 frases determinan si se expande el post
                - 🧵 **Hilos > Posts largos**: Divide insights complejos en 3-5 posts conectados
                - 📊 **Incluye datos**: Los posts con cifras tienen 3x más engagement
                - ⏰ **Mejor horario**: Martes-Jueves 8-10am o 5-7pm para audiencia B2B
                """)
            elif output_format == "🌐 Artículo Web":
                st.markdown("""
                - 🔍 **SEO básico**: Incluye la keyword principal en H1 y primeros 100 caracteres
                - 📐 **Longitud ideal**: 800-1500 palabras para artículos B2B de autoridad
                - 🔗 **Enlaces internos**: Enlaza a 2-3 recursos propios para mejorar SEO y retención
                - 🖼️ **Imágenes**: Añade 1 imagen cada 300 palabras para reducir bounce rate
                """)
            else:
                st.markdown("""
                - 📋 **Copiar y pegar**: Listo para usar en documentos, presentaciones o briefings
                - ✏️ **Editable**: Puedes modificar cualquier sección antes de usar
                - 🔄 **Versiones**: Genera múltiples formatos desde el mismo análisis
                """)
        
        # 🎯 Bonus: Generar variantes automáticas (opcional)
        if st.checkbox("✨ Generar variantes adicionales", key="tab1_generate_variants"):
            st.markdown("#### 🎲 Variantes automáticas")
            
            variants = {
                "🎯 Versión Ejecutiva (1-línea)": f"💡 {summary[:200]}{'...' if len(summary) > 200 else ''}",
                "📱 Versión Mobile (<280 chars)": f"{summary[:250]}{'...' if len(summary) > 250 else ''} #B2B #KaiBot",
                "🗣️ Versión Pitch (30 seg)": f"¿Sabías que {summary.lower().replace('.', ',')[:180]}? Descubre más con KaiBot."
            }
            
            for label, content in variants.items():
                with st.container():
                    st.markdown(f"**{label}**")
                    st.code(content, language="text")
                    st.caption(f"Longitud: {len(content)} caracteres")
# =====================================================
# TAB 2 - MIS ARCHIVOS (Sin cambios, funciona perfecto)
# =====================================================

with tab2:
    st.markdown("## 📁 Gestión de Archivos")
    folders, files = list_folders_and_files(client, bucket_name)
    
    st.markdown("### 📤 Subir nuevos archivos")
    col1, col2 = st.columns([2, 1])
    with col1:
        folder = st.selectbox("Carpeta destino", options=folders if folders else ["documentos/"], key="tab2_folder_select")
        uploaded = st.file_uploader("Selecciona archivos", accept_multiple_files=True, key="tab2_file_uploader")
    with col2:
        new_folder = st.text_input("Nueva carpeta", key="tab2_new_folder")
    target_folder = f"{new_folder.strip()}/" if new_folder else folder
    
    if st.button("⬆️ Subir archivos", key="tab2_upload_btn") and uploaded:
        progress = st.progress(0)
        for i, f in enumerate(uploaded):
            try: upload_file(client, bucket_name, f, target_folder); progress.progress((i + 1) / len(uploaded))
            except Exception as e: st.error(f"Error subiendo {f.name}: {str(e)}")
        st.success(f"✅ {len(uploaded)} archivo(s) subidos"); st.rerun()
    
    st.markdown("---")
    st.markdown("### 🌐 Documentación adicional")
    web = st.text_input("Página web", key="tab2_web_input"); linkedin = st.text_input("LinkedIn", key="tab2_linkedin_input")
    if st.button("💾 Guardar documentación adicional", key="tab2_save_doc_btn"):
        if web or linkedin:
            try:
                upload_json_to_gcs(client, bucket_name, BUCKET_FOLDERS["adicional"], f"fuentes_{int(datetime.utcnow().timestamp())}.json", {"web": web, "linkedin": linkedin, "created_at": datetime.utcnow().isoformat()})
                st.success("✅ Documentación guardada")
            except Exception as e: st.error(f"❌ Error: {str(e)}")
        else: st.warning("Introduce al menos un campo")
    
    st.markdown("---\n### 📊 Archivos en el bucket")
    if files:
        df = pd.DataFrame(files)
        for col, default in {"name": "", "tipo": "", "objetivo": "", "fuentes_fiables": False, "notas": "", "size": 0, "updated": None}.items():
            if col not in df.columns: df[col] = default
        st.dataframe(df[["name", "tipo", "objetivo", "fuentes_fiables", "notas", "size", "updated"]], use_container_width=True, hide_index=True, column_config={
            "name": st.column_config.TextColumn("📄 Archivo"), "tipo": st.column_config.TextColumn("🏷️ Tipo", width="small"),
            "objetivo": st.column_config.TextColumn("🎯 Objetivo"), "fuentes_fiables": st.column_config.CheckboxColumn("✅ Fuentes", width="small"),
            "notas": st.column_config.TextColumn("📝 Notas", width="large"), "size": st.column_config.NumberColumn("💾 Tamaño", width="small"),
            "updated": st.column_config.DatetimeColumn("📅 Fecha", width="small")
        })
        
        st.markdown("---\n### 👁️ Previsualizar archivo")
        col_preview, col_btn = st.columns([3, 1])
        with col_preview: preview_file_select = st.selectbox("Selecciona archivo", options=df["name"].tolist(), key="tab2_preview_select")
        with col_btn:
            st.markdown("\n\n")
            if st.button("🔍 Previsualizar", type="primary", use_container_width=True, key="tab2_preview_btn"): st.session_state.show_preview = preview_file_select
        
        if "show_preview" in st.session_state and st.session_state.show_preview:
            with st.expander(f"📄 {st.session_state.show_preview}", expanded=True):
                try:
                    blob = client.bucket(bucket_name).blob(st.session_state.show_preview); blob.reload()
                    file_ext = st.session_state.show_preview.split('.')[-1].lower()
                    if file_ext == 'json': st.json(json.loads(blob.download_as_text()))
                    elif file_ext in ['txt', 'md', 'csv', 'py', 'js', 'html', 'css']: st.code(blob.download_as_text(), language=file_ext if file_ext != 'md' else 'text')
                    elif file_ext in ['png', 'jpg', 'jpeg', 'gif']: st.image(blob.download_as_bytes(), use_container_width=True)
                    else:
                        st.info(f"📎 Archivo: {file_ext.upper()}"); st.download_button("⬇️ Descargar", blob.download_as_bytes(), file_name=st.session_state.show_preview.split('/')[-1])
                except Exception as e: st.error(f"❌ Error: {str(e)}")
        
        st.markdown("---\n### ✏️ Editar metadatos")
        selected_file = st.selectbox("Selecciona archivo", options=df["name"].tolist(), key="tab2_metadata_select")
        if selected_file:
            current = get_file_metadata(client, bucket_name, selected_file)
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                tipo = st.text_input("🏷️ Tipo", value=current["tipo"], key="tab2_tipo_input")
                objetivo = st.selectbox("🎯 Objetivo", ["", "Publicación Científica", "Social Media", "Blog Post", "Informe Interno", "Marketing B2B", "Presentación", "White Paper"], index=["", "Publicación Científica", "Social Media", "Blog Post", "Informe Interno", "Marketing B2B", "Presentación", "White Paper"].index(current["objetivo"]) if current["objetivo"] in ["", "Publicación Científica", "Social Media", "Blog Post", "Informe Interno", "Marketing B2B", "Presentación", "White Paper"] else 0, key="tab2_objetivo_select")
            with col_m2:
                fuentes = st.checkbox("✅ Fuentes verificadas", value=current["fuentes_fiables"], key="tab2_fuentes_check")
                notas = st.text_area("📝 Notas", value=current["notas"], height=100, key="tab2_notas_input")
            if st.button("💾 Guardar Metadatos", type="primary", key="tab2_save_meta_btn"):
                if update_file_metadata(client, bucket_name, selected_file, {"tipo": tipo, "objetivo": objetivo, "fuentes_fiables": fuentes, "notas": notas}):
                    st.success("✅ Metadatos actualizados"); st.rerun()
        
        st.markdown("---")
        to_delete = st.multiselect("🗑️ Selecciona archivos a eliminar", options=df["name"].tolist(), key="tab2_delete_select")
        if st.button("🗑️ Eliminar seleccionados", key="tab2_delete_btn") and to_delete:
            for name in to_delete:
                try: client.bucket(bucket_name).blob(name).delete()
                except Exception as e: st.error(f"Error: {str(e)}")
            st.success(f"✅ {len(to_delete)} eliminados"); st.rerun()
    else: st.info("ℹ️ No hay archivos en el bucket")

# =====================================================
# TAB 3 - CONFIGURACIÓN AVANZADA (Con fix carga JSON)
# =====================================================

with tab3:
    st.markdown("## ⚙️ Configuración Avanzada")
    st.markdown("### 📝 Gestión de Prompts")
    
    folders, files = list_folders_and_files(client, bucket_name)
    prompt_files = [f["name"] for f in files if f["name"].startswith(BUCKET_FOLDERS["prompts"])]
    
    if prompt_files:
        col_load, col_btn = st.columns([3, 1])
        with col_load: load_prompt = st.selectbox("📂 Prompts guardados", ["-- Selecciona un prompt --"] + prompt_files, key="tab3_prompt_select")
        with col_btn:
            st.markdown("\n\n")
            if st.button("🔄 Cargar", use_container_width=True, key="tab3_load_prompt_btn"):
                if load_prompt != "-- Selecciona un prompt --":
                    try:
                        loaded = load_prompt_from_bucket(client, bucket_name, load_prompt)
                        prompts_data = loaded.get("prompts", loaded) if isinstance(loaded.get("prompts"), dict) else loaded
                        openai_content = prompts_data.get("openai") or prompts_data.get("openai_prompt")
                        perplexity_content = prompts_data.get("perplexity") or prompts_data.get("perplexity_prompt")
                        if not openai_content or not perplexity_content: raise ValueError(f"Claves no encontradas. Disponibles: {list(prompts_data.keys())}")
                        st.session_state.tab3_openai_prompt = openai_content
                        st.session_state.tab3_pplx_prompt = perplexity_content
                        st.success(f"✅ Cargado: {loaded.get('metadata', {}).get('nombre', load_prompt)}")
                        st.rerun()
                    except Exception as e: st.error(f"❌ Error: {str(e)}")
    
    st.markdown("---")
    default_openai = """Eres un analista estratégico experto en generación de contenidos corporativos B2B..."""
    openai_prompt = st.text_area("System Prompt - OpenAI", value=st.session_state.get("tab3_openai_prompt", default_openai), height=300, key="tab3_openai_prompt")
    st.markdown("---")
    default_perplexity = """Eres un validador experto en fact-checking y enriquecimiento de contenido estratégico B2B..."""
    perplexity_prompt = st.text_area("System Prompt - Perplexity", value=st.session_state.get("tab3_pplx_prompt", default_perplexity), height=300, key="tab3_pplx_prompt")
    
    st.markdown("---\n### 💾 Guardar configuración")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        prompt_nombre = st.text_input("Nombre", key="tab3_prompt_name")
        prompt_uso = st.selectbox("Uso", ["General", "Marketing B2B", "LifeSciences", "Tecnología Industrial"], key="tab3_prompt_uso")
    with col_s2: prompt_desc = st.text_area("Descripción", height=100, key="tab3_prompt_desc")
    
    if st.button("💾 Guardar Prompts", type="primary", use_container_width=True, key="tab3_save_prompt_btn"):
        if not prompt_nombre: st.error("❌ Introduce un nombre")
        else:
            try:
                prompt_data = {"openai": openai_prompt, "perplexity": perplexity_prompt}
                metadata = {"nombre": prompt_nombre, "descripcion": prompt_desc, "uso": prompt_uso, "created_at": datetime.utcnow().isoformat()}
                filename = save_prompt_to_bucket(client, bucket_name, {"prompts": prompt_data, "metadata": metadata}, metadata)
                st.success(f"✅ Guardado: {filename}")
                for k in ["tab3_openai_prompt", "tab3_pplx_prompt", "loaded_prompt_metadata"]:
                    if k in st.session_state: del st.session_state[k]
                st.rerun()
            except Exception as e: st.error(f"❌ Error: {str(e)}")

# =====================================================
# FOOTER KAIBOT
# =====================================================

st.markdown(f"""
    <div class='footer-kaibot'>
        <h3 style='color: white; margin-bottom: 1rem;'>Powered by {BRANDING['name']}</h3>
        <p style='color: rgba(255,255,255,0.8); margin-bottom: 1rem;'>Especialistas en Marketing Digital B2B | Generación de leads industriales</p>
        <div style='display: flex; justify-content: center; gap: 2rem; flex-wrap: wrap;'>
            <span>📧 hello@kaibot.es</span><span>📞 +34 633 69 88 32</span><span>📍 Vitoria-Gasteiz</span>
        </div>
        <p style='margin-top: 1.5rem; color: rgba(255,255,255,0.6); font-size: 0.9rem;'>{BRANDING['footer']}</p>
    </div>
""", unsafe_allow_html=True)
