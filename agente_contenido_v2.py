# KaiBot - Generador de Contenidos LLM
# Versión Cliente - Optimizada y profesional
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

# =====================================================
# CSS PERSONALIZADO - ESTILO KAIBOT
# =====================================================

st.markdown("""
    <style>
    /* Importar fuente profesional */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Variables de color KaiBot */
    :root {
        --kaibot-blue: #0066CC;
        --kaibot-blue-dark: #0052A3;
        --kaibot-blue-light: #3B82F6;
        --kaibot-dark: #1E293B;
        --kaibot-gray: #64748B;
        --kaibot-gray-light: #94A3B8;
        --kaibot-bg: #F8FAFC;
        --kaibot-white: #FFFFFF;
        --sidebar-bg: #1E293B;
        --accent-green: #10B981;
    }
    
    /* Fuente global */
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    
    /* Fondo principal */
    .main {
        background-color: var(--kaibot-bg);
    }
    
    /* Títulos profesionales */
    h1 {
        color: var(--kaibot-dark);
        font-weight: 700;
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
    }
    
    h2 {
        color: var(--kaibot-dark);
        font-weight: 600;
        font-size: 1.75rem;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    
    h3 {
        color: var(--kaibot-gray);
        font-weight: 600;
        font-size: 1.25rem;
    }
    
    /* Botones primarios KaiBot */
    .stButton>button[kind="primary"] {
        background: linear-gradient(135deg, var(--kaibot-blue) 0%, var(--kaibot-blue-dark) 100%);
        color: white;
        border: none;
        font-weight: 600;
        padding: 0.75rem 2rem;
        border-radius: 8px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(0, 102, 204, 0.2);
    }
    
    .stButton>button[kind="primary"]:hover {
        background: linear-gradient(135deg, var(--kaibot-blue-dark) 0%, #003d7a 100%);
        box-shadow: 0 6px 12px rgba(0, 102, 204, 0.3);
        transform: translateY(-2px);
    }
    
    /* Botones secundarios */
    .stButton>button {
        width: 100%;
        border-radius: 6px;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    
    /* TABS - Diseño profesional */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background-color: transparent;
        padding: 0;
        border-bottom: 2px solid #E2E8F0;
    }
    
    .stTabs [data-baseweb="tab-list"] button[role="tab"] {
        background-color: transparent;
        color: var(--kaibot-gray);
        border: none;
        border-bottom: 3px solid transparent;
        padding: 16px 32px;
        font-weight: 600;
        font-size: 15px;
        transition: all 0.3s ease;
    }
    
    .stTabs [data-baseweb="tab-list"] button[role="tab"]:hover {
        color: var(--kaibot-blue);
        border-bottom-color: var(--kaibot-blue-light);
    }
    
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        color: var(--kaibot-blue);
        border-bottom-color: var(--kaibot-blue);
        font-weight: 700;
    }
    
    .stTabs [data-baseweb="tab-panel"] {
        padding: 32px 0;
    }
    
    /* SIDEBAR - Diseño profesional oscuro */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--sidebar-bg) 0%, #0F172A 100%);
        padding-top: 2rem;
    }
    
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: white !important;
        font-weight: 600;
    }
    
    /* Inputs del sidebar */
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea {
        background-color: rgba(255, 255, 255, 0.1) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        color: var(--kaibot-blue-light) !important;
        border-radius: 6px;
        font-weight: 500;
    }
    
    [data-testid="stSidebar"] input::placeholder,
    [data-testid="stSidebar"] textarea::placeholder {
        color: rgba(255, 255, 255, 0.5) !important;
    }
    
    [data-testid="stSidebar"] input:focus,
    [data-testid="stSidebar"] textarea:focus {
        border-color: var(--kaibot-blue) !important;
        box-shadow: 0 0 0 2px rgba(0, 102, 204, 0.2);
    }
    
    /* Botones del sidebar */
    [data-testid="stSidebar"] .stButton>button {
        background-color: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        color: white !important;
        font-weight: 600;
    }
    
    [data-testid="stSidebar"] .stButton>button:hover {
        background-color: rgba(255, 255, 255, 0.15);
        border-color: rgba(255, 255, 255, 0.3);
    }
    
    [data-testid="stSidebar"] .stButton>button[kind="primary"] {
        background: linear-gradient(135deg, var(--kaibot-blue) 0%, var(--kaibot-blue-dark) 100%);
        border: none;
    }
    
    /* Expanders del sidebar */
    [data-testid="stSidebar"] .streamlit-expanderHeader {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 6px;
        font-weight: 600;
    }
    
    [data-testid="stSidebar"] .streamlit-expanderHeader:hover {
        background-color: rgba(255, 255, 255, 0.1);
    }
    
    /* Divisores */
    [data-testid="stSidebar"] hr {
        border-color: rgba(255, 255, 255, 0.2) !important;
        margin: 1.5rem 0;
    }
    
    /* Info boxes mejoradas */
    .stInfo {
        background-color: #EBF5FF;
        border-left: 4px solid var(--kaibot-blue);
        border-radius: 8px;
        padding: 1rem;
    }
    
    .stSuccess {
        background-color: #ECFDF5;
        border-left: 4px solid var(--accent-green);
        border-radius: 8px;
        padding: 1rem;
    }
    
    .stWarning {
        background-color: #FEF3C7;
        border-left: 4px solid #F59E0B;
        border-radius: 8px;
        padding: 1rem;
    }
    
    .stError {
        background-color: #FEE2E2;
        border-left: 4px solid #EF4444;
        border-radius: 8px;
        padding: 1rem;
    }
    
    /* Tablas profesionales */
    .dataframe {
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    /* Expanders mejorados */
    .streamlit-expanderHeader {
        background-color: white;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        font-weight: 600;
        color: var(--kaibot-dark);
    }
    
    /* Progress bar */
    .stProgress > div > div {
        background-color: var(--kaibot-blue);
    }
    
    /* Footer KaiBot */
    .footer-kaibot {
        background: linear-gradient(135deg, var(--kaibot-dark) 0%, #0F172A 100%);
        padding: 2rem;
        border-radius: 12px;
        margin-top: 3rem;
        color: white;
        text-align: center;
    }
    
    /* Padding optimizado */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    </style>
""", unsafe_allow_html=True)

# =====================================================
# CONFIGURACIÓN
# =====================================================

BUCKET_FOLDERS = {
    "documentos": "documentos/",
    "adicional": "adicional/",
    "validados": "documentos_validados/",
    "prompts": "prompts/"
}

# Lista de palabras vacías en español para nombres de archivo
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
# FUNCIONES HELPER
# =====================================================

def get_gcs_client_from_json(json_string: str) -> storage.Client:
    """Crea cliente GCS desde JSON de service account"""
    credentials_dict = json.loads(json_string)
    credentials = service_account.Credentials.from_service_account_info(credentials_dict)
    return storage.Client(credentials=credentials, project=credentials_dict.get('project_id'))

def upload_file(client: storage.Client, bucket_name: str, uploaded_file, folder: str):
    """Sube archivo a GCS"""
    bucket = client.bucket(bucket_name)
    blob_path = f"{folder}{uploaded_file.name}"
    blob = bucket.blob(blob_path)
    blob.upload_from_file(uploaded_file, rewind=True)
    return blob_path

def upload_json_to_gcs(client: storage.Client, bucket_name: str, folder: str, filename: str, data: dict):
    """Sube JSON a GCS"""
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(f"{folder}{filename}")
    blob.upload_from_string(json.dumps(data, indent=2, ensure_ascii=False), content_type='application/json')

def list_folders_and_files(client: storage.Client, bucket_name: str):
    """Lista carpetas y archivos con metadatos completos"""
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
            
            # Recargar blob para obtener metadata completa
            blob.reload()
            
            file_info = {
                "name": blob.name,
                "size": blob.size if blob.size is not None else 0,
                "updated": blob.updated,
                "tipo": blob.metadata.get("tipo", "") if blob.metadata else "",
                "objetivo": blob.metadata.get("objetivo", "") if blob.metadata else "",
                "fuentes_fiables": blob.metadata.get("fuentes_fiables", "false").lower() == "true" if blob.metadata else False,
                "notas": blob.metadata.get("notas", "") if blob.metadata else ""
            }
            files.append(file_info)
    
    return sorted(list(folders)), files

def get_file_metadata(client: storage.Client, bucket_name: str, file_path: str) -> dict:
    """Obtiene metadatos de un archivo"""
    bucket = client.bucket(bucket_name)
    blob = bucket.get_blob(file_path)
    
    if blob and blob.metadata:
        return {
            "tipo": blob.metadata.get("tipo", ""),
            "objetivo": blob.metadata.get("objetivo", ""),
            "fuentes_fiables": blob.metadata.get("fuentes_fiables", "false").lower() == "true",
            "notas": blob.metadata.get("notas", "")
        }
    
    return {"tipo": "", "objetivo": "", "fuentes_fiables": False, "notas": ""}

def update_file_metadata(client: storage.Client, bucket_name: str, file_path: str, metadata: dict) -> bool:
    """Actualiza metadatos de un archivo"""
    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(file_path)
        
        # Convertir bool a string para GCS metadata
        metadata_to_save = {
            "tipo": str(metadata.get("tipo", "")),
            "objetivo": str(metadata.get("objetivo", "")),
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
    """Carga contenido de archivos seleccionados"""
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
    """Genera nombre de archivo inteligente desde summary"""
    summary = data.get("summary", "analisis")
    
    # Limpiar y tokenizar
    words = re.findall(r'\b\w+\b', summary.lower())
    
    # Filtrar stopwords y palabras muy cortas
    keywords = [w for w in words if w not in STOPWORDS and len(w) > 3]
    
    # Tomar primeras palabras clave
    name_parts = keywords[:5]
    
    if not name_parts:
        name_parts = ["contenido", "ia"]
    
    base_name = "_".join(name_parts)[:max_length]
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    return f"{base_name}_{timestamp}.json"

def save_analysis_with_metadata(client: storage.Client, bucket_name: str, folder: str, 
                                filename: str, data: dict, metadata: dict):
    """Guarda análisis con metadatos en GCS"""
    bucket = client.bucket(bucket_name)
    blob_path = f"{folder}{filename}"
    blob = bucket.blob(blob_path)
    
    # Convertir metadata a strings
    metadata_to_save = {
        "tipo": str(metadata.get("tipo", "")),
        "objetivo": str(metadata.get("objetivo", "")),
        "fuentes_fiables": str(metadata.get("fuentes_fiables", False)).lower(),
        "notas": str(metadata.get("notas", ""))
    }
    
    blob.metadata = metadata_to_save
    blob.upload_from_string(
        json.dumps(data, indent=2, ensure_ascii=False),
        content_type='application/json'
    )

def save_prompt_to_bucket(client: storage.Client, bucket_name: str, 
                          prompt_data: dict, metadata: dict) -> str:
    """Guarda prompts en bucket"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    nombre_clean = re.sub(r'[^\w\s-]', '', metadata.get("nombre", "prompt")).replace(" ", "_")
    filename = f"prompt_{nombre_clean}_{timestamp}.json"
    
    payload = {
        "prompts": prompt_data,
        "metadata": metadata,
        "created_at": datetime.utcnow().isoformat()
    }
    
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(f"{BUCKET_FOLDERS['prompts']}{filename}")
    
    # Metadata para el blob
    blob.metadata = {
        "tipo": "Prompt Configuration",
        "nombre": metadata.get("nombre", ""),
        "uso": metadata.get("uso", ""),
        "notas": metadata.get("descripcion", "")
    }
    
    blob.upload_from_string(
        json.dumps(payload, indent=2, ensure_ascii=False),
        content_type='application/json'
    )
    
    return filename

def load_prompt_from_bucket(client: storage.Client, bucket_name: str, prompt_file: str) -> dict:
    """Carga prompts desde bucket"""
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
    st.markdown("""
        <h1 style='margin-bottom: 0;'>Generador de Contenidos IA</h1>
        <p style='color: #64748B; font-size: 1.1rem; margin-top: 0.5rem;'>
            <strong>Powered by KaiBot</strong> | Análisis inteligente con OpenAI + Perplexity
        </p>
    """, unsafe_allow_html=True)

st.markdown("---")

# =====================================================
# SIDEBAR - GESTIÓN DE CONEXIONES
# =====================================================

with st.sidebar:
    st.markdown("""
        <div style='text-align: center; padding: 1rem 0 2rem 0;'>
            <h2 style='color: white; margin-bottom: 0.5rem;'>⚙️ Configuración</h2>
            <p style='color: rgba(255,255,255,0.7); font-size: 0.9rem;'>Conecta tus servicios</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Estado de conexión
    connection_status = {
        "gcs": "gcs" in st.session_state and "bucket_name" in st.session_state,
        "openai": "openai" in st.session_state,
        "perplexity": "perplexity_key" in st.session_state
    }
    
    st.markdown("### 📊 Estado de Servicios")
    
    for service, connected in connection_status.items():
        status_emoji = "✅" if connected else "❌"
        status_text = "Conectado" if connected else "Desconectado"
        status_color = "#10B981" if connected else "#EF4444"
        
        service_names = {
            "gcs": "Google Cloud",
            "openai": "OpenAI",
            "perplexity": "Perplexity"
        }
        
        st.markdown(f"""
            <div style='background: rgba(255,255,255,0.05); padding: 0.75rem; border-radius: 6px; margin-bottom: 0.5rem; border-left: 3px solid {status_color};'>
                <strong>{status_emoji} {service_names[service]}</strong><br>
                <small style='color: rgba(255,255,255,0.7);'>{status_text}</small>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Google Cloud
    with st.expander("☁️ Google Cloud Storage", expanded=not connection_status["gcs"]):
        bucket_name = st.text_input(
            "Nombre del Bucket",
            value=st.session_state.get("bucket_name", ""),
            placeholder="mi-bucket-kaibot",
            key="gcs_bucket_input"
        )
        
        sa_json = st.text_area(
            "Service Account (JSON)",
            height=150,
            placeholder='{"type": "service_account", ...}',
            key="gcs_sa_input"
        )
        
        if st.button("💾 Conectar GCS", use_container_width=True, key="gcs_connect_btn"):
            try:
                st.session_state.gcs = get_gcs_client_from_json(sa_json)
                st.session_state.bucket_name = bucket_name
                st.success("✅ Google Cloud conectado")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    # OpenAI
    with st.expander("🤖 OpenAI", expanded=not connection_status["openai"]):
        openai_key = st.text_input(
            "API Key",
            type="password",
            placeholder="sk-...",
            key="openai_key_input"
        )
        
        if st.button("💾 Conectar OpenAI", use_container_width=True, key="openai_connect_btn"):
            try:
                st.session_state.openai = OpenAI(api_key=openai_key)
                st.success("✅ OpenAI conectado")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    # Perplexity
    with st.expander("🔍 Perplexity", expanded=not connection_status["perplexity"]):
        perplexity_key = st.text_input(
            "API Key",
            type="password",
            placeholder="pplx-...",
            key="pplx_key_input"
        )
        
        col_save, col_test = st.columns(2)
        
        with col_save:
            if st.button("💾 Guardar", use_container_width=True, key="pplx_save_btn"):
                st.session_state.perplexity_key = perplexity_key
                st.success("✅ Guardado")
                st.rerun()
        
        with col_test:
            if st.button("🧪 Probar", use_container_width=True, key="pplx_test_btn") and perplexity_key:
                try:
                    test_client = OpenAI(api_key=perplexity_key, base_url="https://api.perplexity.ai")
                    test_client.chat.completions.create(
                        model="sonar",
                        messages=[{"role": "user", "content": "test"}]
                    )
                    st.success("✅ Funciona")
                except Exception as e:
                    st.error(f"❌ {str(e)}")
    
    st.markdown("---")
    
    # Soporte
    st.markdown("### 💬 Soporte")
    st.markdown("""
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

# Verificar conexiones
if not all([connection_status["gcs"], connection_status["openai"], connection_status["perplexity"]]):
    st.warning("⚠️ **Configura todos los servicios** en el sidebar para comenzar")
    st.info("💡 Necesitas conectar Google Cloud Storage, OpenAI y Perplexity para usar el generador")
    st.stop()

client = st.session_state.gcs
bucket_name = st.session_state.bucket_name

# =====================================================
# TABS PRINCIPALES
# =====================================================

tab1, tab2, tab3 = st.tabs(["🎯 Generar Contenido", "📁 Mis Archivos", "⚙️ Configuración Avanzada"])

# =====================================================
# TAB 1 - GENERAR CONTENIDO
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
        
        # 🔧 FIX: Inicializar estado para tracking de plantilla
        if "tab1_last_template" not in st.session_state:
            st.session_state.tab1_last_template = None
        if "tab1_template_query" not in st.session_state:
            st.session_state.tab1_template_query = list(templates.values())[0]
        
        selected_template = st.selectbox(
            "Elige una plantilla",
            list(templates.keys()),
            key="tab1_template_select"
        )
        
        # 🔧 FIX: Detectar cambio de plantilla y actualizar query SOLO si no fue editado manualmente
        if st.session_state.tab1_last_template != selected_template:
            st.session_state.tab1_template_query = templates[selected_template]
            st.session_state.tab1_last_template = selected_template
        
        user_query = st.text_area(
            "Consulta (editable)",
            value=st.session_state.tab1_template_query,
            height=150,
            key="tab1_template_query",
            on_change=lambda: setattr(st.session_state, 'tab1_template_query', st.session_state.tab1_template_query)
        )
        
        # 🔧 FIX: Guardar cambios manuales del usuario para no sobrescribirlos
        if user_query != templates.get(selected_template):
            st.session_state.tab1_last_template = None  # Desvincular para no sobrescribir edición manual

    #Pro tip para actualizar la palntilla original
        #    if user_query != templates.get(selected_template):
          #  if st.button("🔄 Restaurar plantilla", key="tab1_restore_template"):
         #       st.session_state.tab1_template_query = templates[selected_template]
         #       st.session_state.tab1_last_template = selected_template
          #      st.rerun()
    
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

Enfoque: Resultados medibles, oportunidades concretas, ROI."""

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
                
                openai_data = json.loads(response.choices[0].message.content)
                openai_data["metadata"] = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "agent": "openai",
                    "model": openai_model,
                    "query": user_query,
                    "mode": "with_context" if selected_files else "general"
                }
                st.session_state.openai_response = openai_data
                
            except Exception as e:
                st.error(f"❌ Error en OpenAI: {str(e)}")
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
                st.error(f"❌ Error en Perplexity: {str(e)}")
                if "openai_response" in st.session_state:
                    st.warning("⚠️ Usando solo OpenAI")
                    st.session_state.perplexity_response = st.session_state.openai_response
                    st.rerun()
    
    # PASO 3: RESULTADOS
    if "perplexity_response" in st.session_state:
        st.markdown("---")
        st.markdown("### 📊 Paso 3: Resultado validado")
        
        final_data = st.session_state.perplexity_response
        
        with st.expander("👁️ Vista Previa del Contenido", expanded=True):
            col_badge1, col_badge2, col_badge3 = st.columns(3)
            with col_badge1:
                st.markdown(f"**🤖 OpenAI:** {final_data.get('metadata', {}).get('openai_model', 'N/A')}")
            with col_badge2:
                st.markdown(f"**🔍 Perplexity:** {final_data.get('metadata', {}).get('model', 'N/A')}")
            with col_badge3:
                confidence = final_data.get("confidence_level", "medio").lower()
                emoji = "🟢" if confidence == "alto" else "🟡" if confidence == "medio" else "🔴"
                st.markdown(f"**{emoji} Confianza:** {confidence.upper()}")
            
            st.markdown("---")
            st.markdown("#### 📝 Resumen Ejecutivo")
            st.success(final_data.get("summary", "N/A"))
            
            col_points, col_actions = st.columns(2)
            
            with col_points:
                st.markdown("#### 🎯 Puntos Clave")
                for i, point in enumerate(final_data.get("key_points", []), 1):
                    st.markdown(f"**{i}.** {point}")
            
            with col_actions:
                st.markdown("#### ✅ Acciones Recomendadas")
                for i, action in enumerate(final_data.get("recommended_actions", []), 1):
                    st.markdown(f"**{i}.** {action}")
            
            if "validation_notes" in final_data and final_data["validation_notes"]:
                st.markdown("---")
                st.markdown("#### 📋 Notas de Validación")
                st.info(final_data["validation_notes"])
            
            if "sources" in final_data and final_data["sources"]:
                st.markdown("---")
                st.markdown("#### 🔗 Fuentes Verificadas")
                for i, source in enumerate(final_data["sources"], 1):
                    if source.startswith("http"):
                        st.markdown(f"{i}. [{source}]({source})")
                    else:
                        st.markdown(f"{i}. {source}")
        
        with st.expander("🔄 Comparar OpenAI vs Perplexity"):
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**🔵 OpenAI (Original)**")
                st.json(st.session_state.openai_response)
            with col_b:
                st.markdown("**🟣 Perplexity (Validado)**")
                st.json(final_data)
        
        st.markdown("---")
        st.markdown("### 💾 Guardar contenido")
        
        with st.expander("📋 Configurar metadatos", expanded=True):
            col_m1, col_m2 = st.columns(2)
            
            with col_m1:
                content_tipo = st.text_input(
                    "🏷️ Tipo",
                    value="Análisis IA Validado",
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
                has_sources = bool(final_data.get("sources", []))
                content_fuentes = st.checkbox(
                    "✅ Fuentes verificadas",
                    value=has_sources,
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
            if st.button("💾 Guardar en Cloud", type="primary", use_container_width=True, key="tab1_save_btn"):
                try:
                    filename = generate_smart_filename(edited_data)
                    analysis_metadata = {
                        "tipo": content_tipo,
                        "objetivo": content_objetivo,
                        "fuentes_fiables": content_fuentes,
                        "notas": content_notas
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
# TAB 2 - MIS ARCHIVOS
# =====================================================

with tab2:
    st.markdown("## 📁 Gestión de Archivos")
    
    folders, files = list_folders_and_files(client, bucket_name)
    
    # Subida de archivos
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
            try:
                upload_file(client, bucket_name, f, target_folder)
                progress.progress((i + 1) / len(uploaded))
            except Exception as e:
                st.error(f"Error subiendo {f.name}: {str(e)}")
        st.success(f"✅ {len(uploaded)} archivo(s) subidos")
        st.rerun()
    
    st.markdown("---")
    
    # Documentación adicional
    st.markdown("### 🌐 Documentación adicional (Web / LinkedIn)")
    
    web = st.text_input("Página web", key="tab2_web_input")
    linkedin = st.text_input("LinkedIn", key="tab2_linkedin_input")
    
    if st.button("💾 Guardar documentación adicional", key="tab2_save_doc_btn"):
        if web or linkedin:
            payload = {
                "web": web,
                "linkedin": linkedin,
                "created_at": datetime.utcnow().isoformat()
            }
            try:
                upload_json_to_gcs(
                    client, bucket_name, 
                    BUCKET_FOLDERS["adicional"],
                    f"fuentes_{int(datetime.utcnow().timestamp())}.json",
                    payload
                )
                st.success("✅ Documentación guardada")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
        else:
            st.warning("Introduce al menos un campo")
    
    st.markdown("---")
    
    # Tabla de archivos
    st.markdown("### 📊 Archivos en el bucket")
    
    if files:
        df = pd.DataFrame(files)
        
        required_columns = {
            "name": "",
            "tipo": "",
            "objetivo": "",
            "fuentes_fiables": False,
            "notas": "",
            "size": 0,
            "updated": None
        }
        
        for col, default_value in required_columns.items():
            if col not in df.columns:
                df[col] = default_value
        
        column_order = ["name", "tipo", "objetivo", "fuentes_fiables", "notas", "size", "updated"]
        df = df[column_order]
        
        column_config = {
            "name": st.column_config.TextColumn("📄 Archivo", width="medium"),
            "tipo": st.column_config.TextColumn("🏷️ Tipo", width="small"),
            "objetivo": st.column_config.TextColumn("🎯 Objetivo", width="medium"),
            "fuentes_fiables": st.column_config.CheckboxColumn("✅ Fuentes", width="small"),
            "notas": st.column_config.TextColumn("📝 Notas", width="large"),
            "size": st.column_config.NumberColumn("💾 Tamaño", width="small"),
            "updated": st.column_config.DatetimeColumn("📅 Fecha", width="small")
        }
        
        st.dataframe(
            df,
            use_container_width=True,
            column_config=column_config,
            hide_index=True
        )
        
        # Previsualización
        st.markdown("---")
        st.markdown("### 👁️ Previsualizar archivo")
        
        col_preview, col_btn = st.columns([3, 1])
        
        with col_preview:
            preview_file_select = st.selectbox(
                "Selecciona archivo",
                options=df["name"].tolist(),
                key="tab2_preview_select"
            )
        
        with col_btn:
            st.markdown("")
            st.markdown("")
            if st.button("🔍 Previsualizar", type="primary", use_container_width=True, key="tab2_preview_btn"):
                st.session_state.show_preview = preview_file_select
        
        if "show_preview" in st.session_state and st.session_state.show_preview:
            with st.expander(f"📄 {st.session_state.show_preview}", expanded=True):
                try:
                    bucket = client.bucket(bucket_name)
                    blob = bucket.blob(st.session_state.show_preview)
                    blob.reload()
                    
                    file_size = blob.size if blob.size is not None else 0
                    file_size_kb = file_size / 1024 if file_size > 0 else 0
                    file_ext = st.session_state.show_preview.split('.')[-1].lower()
                    
                    if file_ext == 'json':
                        content = blob.download_as_text()
                        data = json.loads(content)
                        st.json(data)
                    elif file_ext in ['txt', 'md', 'csv', 'log']:
                        content = blob.download_as_text()
                        st.code(content, language='text')
                    elif file_ext == 'py':
                        content = blob.download_as_text()
                        st.code(content, language='python')
                    elif file_ext in ['js', 'jsx', 'ts', 'tsx']:
                        content = blob.download_as_text()
                        st.code(content, language='javascript')
                    elif file_ext in ['html', 'css']:
                        content = blob.download_as_text()
                        st.code(content, language='html')
                    elif file_ext in ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp']:
                        image_bytes = blob.download_as_bytes()
                        st.image(image_bytes, caption=st.session_state.show_preview, use_container_width=True)
                    elif file_ext == 'pdf':
                        st.info(f"📄 Archivo PDF")
                        st.write(f"**Tamaño:** {file_size_kb:.2f} KB")
                        st.warning("💡 Descarga el archivo para verlo")
                        pdf_bytes = blob.download_as_bytes()
                        st.download_button(
                            "⬇️ Descargar PDF",
                            pdf_bytes,
                            file_name=st.session_state.show_preview.split('/')[-1],
                            mime="application/pdf"
                        )
                    elif file_ext in ['docx', 'xlsx', 'pptx', 'doc', 'xls', 'ppt']:
                        st.info(f"📎 Archivo Office: {file_ext.upper()}")
                        st.write(f"**Tamaño:** {file_size_kb:.2f} KB")
                        file_bytes = blob.download_as_bytes()
                        mime_types = {
                            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                        }
                        st.download_button(
                            f"⬇️ Descargar {file_ext.upper()}",
                            file_bytes,
                            file_name=st.session_state.show_preview.split('/')[-1],
                            mime=mime_types.get(file_ext, 'application/octet-stream')
                        )
                    else:
                        st.warning(f"⚠️ Tipo no soportado: .{file_ext}")
                        st.write(f"**Tamaño:** {file_size_kb:.2f} KB")
                
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
        
        # Editor de metadatos
        st.markdown("---")
        st.markdown("### ✏️ Editar metadatos")
        
        selected_file = st.selectbox(
            "Selecciona archivo",
            options=df["name"].tolist(),
            key="tab2_metadata_select"
        )
        
        if selected_file:
            current_metadata = get_file_metadata(client, bucket_name, selected_file)
            
            col_m1, col_m2 = st.columns(2)
            
            with col_m1:
                tipo = st.text_input(
                    "🏷️ Tipo",
                    value=current_metadata["tipo"],
                    key="tab2_tipo_input"
                )
                
                objetivo_options = ["", "Publicación Científica", "Social Media", "Blog Post", 
                                   "Informe Interno", "Marketing B2B", "Presentación", "White Paper"]
                
                current_objetivo = current_metadata["objetivo"]
                objetivo_index = objetivo_options.index(current_objetivo) if current_objetivo in objetivo_options else 0
                
                objetivo = st.selectbox(
                    "🎯 Objetivo",
                    objetivo_options,
                    index=objetivo_index,
                    key="tab2_objetivo_select"
                )
            
            with col_m2:
                fuentes = st.checkbox(
                    "✅ Fuentes verificadas",
                    value=current_metadata["fuentes_fiables"],
                    key="tab2_fuentes_check"
                )
                
                notas = st.text_area(
                    "📝 Notas",
                    value=current_metadata["notas"],
                    height=100,
                    key="tab2_notas_input"
                )
            
            if st.button("💾 Guardar Metadatos", type="primary", key="tab2_save_meta_btn"):
                new_metadata = {
                    "tipo": tipo,
                    "objetivo": objetivo,
                    "fuentes_fiables": fuentes,
                    "notas": notas
                }
                
                if update_file_metadata(client, bucket_name, selected_file, new_metadata):
                    st.success(f"✅ Metadatos actualizados")
                    st.rerun()
        
        # Eliminar archivos
        st.markdown("---")
        to_delete = st.multiselect("🗑️ Selecciona archivos a eliminar", options=df["name"].tolist(), key="tab2_delete_select")
        
        if st.button("🗑️ Eliminar seleccionados", key="tab2_delete_btn") and to_delete:
            bucket = client.bucket(bucket_name)
            for name in to_delete:
                try:
                    bucket.blob(name).delete()
                except Exception as e:
                    st.error(f"Error: {str(e)}")
            st.success(f"✅ {len(to_delete)} eliminados")
            st.rerun()
    else:
        st.info("ℹ️ No hay archivos en el bucket")

# =====================================================
# TAB 3 - CONFIGURACIÓN AVANZADA
# =====================================================

with tab3:
    st.markdown("## ⚙️ Configuración Avanzada")
    
    # Gestión de prompts
    st.markdown("### 📝 Gestión de Prompts")
    
    folders, files = list_folders_and_files(client, bucket_name)
    prompt_files = [f["name"] for f in files if f["name"].startswith(BUCKET_FOLDERS["prompts"])]
    
    if prompt_files:
        col_load, col_btn = st.columns([3, 1])
        
        with col_load:
            load_prompt = st.selectbox(
                "📂 Prompts guardados",
                ["-- Selecciona un prompt --"] + prompt_files,
                key="tab3_prompt_select"
            )
        
        with col_btn:
            st.markdown("")
            st.markdown("")
            if st.button("🔄 Cargar", use_container_width=True, key="tab3_load_prompt_btn"):
                if load_prompt != "-- Selecciona un prompt --":
                    try:
                        loaded = load_prompt_from_bucket(client, bucket_name, load_prompt)
                        
                        # 🔧 FIX: Actualizar DIRECTAMENTE las claves de los widgets
                        st.session_state.tab3_openai_prompt = loaded["prompts"]["openai_prompt"]
                        st.session_state.tab3_pplx_prompt = loaded["prompts"]["perplexity_prompt"]
                        
                        # Opcional: guardar metadata para referencia
                        st.session_state.loaded_prompt_metadata = loaded.get('metadata', {})
                        
                        st.success(f"✅ Cargado: {loaded.get('metadata', {}).get('nombre', 'Sin nombre')}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
    
    st.markdown("---")
    
    # Prompts - OpenAI
    default_openai = """Eres un analista estratégico experto en generación de contenidos corporativos B2B con más de 15 años de experiencia.

**TU MISIÓN:**
Analizar información y generar insights accionables de alto valor para directivos y responsables de marketing industrial.

**ESTRUCTURA DE RESPUESTA (JSON OBLIGATORIO):**
{
  "summary": "Resumen ejecutivo de 2-3 líneas enfocado en el valor estratégico",
  "key_points": ["Punto 1: Insight con dato", "Punto 2: Oportunidad identificada", "Punto 3: Riesgo estratégico"],
  "recommended_actions": ["Acción 1: Específica con plazo", "Acción 2: Con ROI estimado"],
  "topics_to_validate": ["Dato a verificar online", "Tendencia a validar"]
}"""

    # 🔧 FIX: Usar session_state del widget directamente como fallback
    openai_prompt = st.text_area(
        "System Prompt - OpenAI",
        value=st.session_state.get("tab3_openai_prompt", default_openai),
        height=300,
        key="tab3_openai_prompt"
    )
    
    st.markdown("---")
    
    # Prompts - Perplexity
    default_perplexity = """Eres un validador experto en fact-checking y enriquecimiento de contenido estratégico B2B.

**FUENTES PRIORITARIAS:** Gartner, McKinsey, Forrester, medios B2B especializados.

**ESTRUCTURA DE RESPUESTA (JSON OBLIGATORIO):**
{
  "summary": "Resumen validado con datos actuales",
  "key_points": ["Punto 1 validado con fuente actual", "Punto 2 enriquecido", "Punto 3 con contexto"],
  "recommended_actions": ["Acción 1 con best practice", "Acción 2 con ROI"],
  "validation_notes": "Resumen de validación",
  "sources": ["URL (Título - Fecha)", "URL (Título - Fecha)"],
  "confidence_level": "alto"
}"""

    perplexity_prompt = st.text_area(
        "System Prompt - Perplexity",
        value=st.session_state.get("tab3_pplx_prompt", default_perplexity),
        height=300,
        key="tab3_pplx_prompt"
    )
    
    st.markdown("---")
    st.markdown("### 💾 Guardar configuración")
    
    col_s1, col_s2 = st.columns(2)
    
    with col_s1:
        prompt_nombre = st.text_input("Nombre", key="tab3_prompt_name")
        prompt_uso = st.selectbox(
            "Uso",
            ["General", "Marketing B2B", "LifeSciences", "Tecnología Industrial"],
            key="tab3_prompt_uso"
        )
    
    with col_s2:
        prompt_desc = st.text_area("Descripción", height=100, key="tab3_prompt_desc")
    
    if st.button("💾 Guardar Prompts", type="primary", use_container_width=True, key="tab3_save_prompt_btn"):
        if not prompt_nombre:
            st.error("❌ Introduce un nombre")
        else:
            try:
                prompt_data = {
                    "openai_prompt": openai_prompt,
                    "perplexity_prompt": perplexity_prompt
                }
                
                metadata = {
                    "nombre": prompt_nombre,
                    "descripcion": prompt_desc,
                    "uso": prompt_uso
                }
                
                filename = save_prompt_to_bucket(client, bucket_name, prompt_data, metadata)
                st.success(f"✅ Guardado: {filename}")
                
                # 🔧 FIX: Limpiar session_state de widgets para evitar conflictos en próxima carga
                # (Opcional: si quieres mantener la edición actual, comenta estas líneas)
                if "tab3_openai_prompt" in st.session_state:
                    del st.session_state.tab3_openai_prompt
                if "tab3_pplx_prompt" in st.session_state:
                    del st.session_state.tab3_pplx_prompt
                if "loaded_prompt_metadata" in st.session_state:
                    del st.session_state.loaded_prompt_metadata
                
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

# =====================================================
# FOOTER KAIBOT
# =====================================================

st.markdown("""
    <div class='footer-kaibot'>
        <h3 style='color: white; margin-bottom: 1rem;'>Powered by KaiBot</h3>
        <p style='color: rgba(255,255,255,0.8); margin-bottom: 1rem;'>
            Especialistas en Marketing Digital B2B | Generación de leads industriales
        </p>
        <div style='display: flex; justify-content: center; gap: 2rem; flex-wrap: wrap;'>
            <span>📧 hello@kaibot.es</span>
            <span>📞 +34 633 69 88 32</span>
            <span>📍 Vitoria-Gasteiz</span>
        </div>
        <p style='margin-top: 1.5rem; color: rgba(255,255,255,0.6); font-size: 0.9rem;'>
            © 2026 Kai Marketing LAB. Todos los derechos reservados.
        </p>
    </div>
""", unsafe_allow_html=True)
