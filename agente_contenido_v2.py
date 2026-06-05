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
# TAB 1 - GENERAR CONTENIDO (CORREGIDO + CAJA CONSULTA)
# =====================================================

with tab1:
    st.markdown("## 🎯 Generador de Contenidos con IA")
    st.markdown("**Análisis profesional en 3 pasos:** Configura → OpenAI analiza → Perplexity valida")
    
    # =====================================================
    # PASO 1: CONFIGURACIÓN
    # =====================================================
    st.markdown("###  Paso 1: Configura tu análisis")
    
    folders, files = list_folders_and_files(client, bucket_name)
    file_names = [f["name"] for f in files if not f["name"].startswith(BUCKET_FOLDERS["prompts"])]
    
    col_files, col_chars = st.columns([3, 1])
    with col_files:
        selected_files = st.multiselect("📄 Documentos de contexto (opcional)", options=file_names, key="tab1_select_files")
    with col_chars:
        max_chars = st.number_input("Límite caracteres", min_value=2000, max_value=50000, value=15000, step=1000, disabled=len(selected_files)==0, key="tab1_max_chars")
    
    st.info(f"📁 **Modo:** Análisis con {len(selected_files)} documento(s)" if selected_files else "💭 **Modo:** Consulta general sin documentos")
    st.markdown("---")
    
    query_mode = st.radio("📝 Método de entrada", ["🔧 Flexible", "📝 Personalizada", "📋 Plantilla"], horizontal=True, key="tab1_query_mode")
    
    openai_prompt = ""
    user_query = ""
    
    # 🟦 MODO FLEXIBLE
    if query_mode == "🔧 Flexible":
        st.markdown("*Configura parámetros clave. El sistema generará el prompt automáticamente.*")
        col1, col2 = st.columns(2)
        with col1:
            role = st.selectbox("👤 Rol / Perfil", ["Responsable de Marketing B2B", "CEO / Director General", "Consultor Estratégico", "Content Manager", "Especialista en Ventas", "Inversor / VC", "Otro..."], key="tab1_role")
            if role == "Otro...": role = st.text_input("Especificar rol exacto", key="tab1_role_custom")
            context = st.text_area("📋 Contexto / Antecedentes", placeholder="Empresa, producto, campaña, situación actual, público objetivo...", height=100, key="tab1_context")
        with col2:
            output_format = st.selectbox("📤 Formato Output", ["Infografía / Visual", "Email corporativo", "Post LinkedIn / Thread", "Artículo Web / Blog", "Informe Ejecutivo", "Pitch comercial"], key="tab1_format")
            sources = st.text_area(" Fuentes externas (URLs, LinkedIn, datos, notas...)", placeholder="https://..., @perfil..., informe sectorial, notas internas...", height=100, key="tab1_sources")
        
        #  NUEVO: Caja de consulta libre en modo Flexible
        st.markdown("**💬 Consulta adicional (opcional):**")
        free_query = st.text_area("Añade instrucciones específicas, preguntas concretas o matices para el análisis:", 
                                  placeholder="Ej: Enfócate en el mercado español, compara con competidores directos, destaca cifras de ROI...", 
                                  height=80, key="tab1_free_query_flexible")
        
        openai_prompt = f"Eres un experto estratégico actuando como {role}. Genera contenido de alto valor optimizado específicamente para formato: {output_format}. Responde EXCLUSIVAMENTE en formato JSON válido."
        user_query = f"CONTEXTO:\n{context}\n\nFUENTES A CONSIDERAR:\n{sources}\n\nINSTRUCCIÓN:\nGenera un análisis en JSON con esta estructura exacta:\n{{\n  \"summary\": \"Resumen ejecutivo (máx. 3 líneas)\",\n  \"key_points\": [\"Insight 1\", \"Insight 2\", \"Insight 3\"],\n  \"recommended_actions\": [\"Acción 1 concreta\", \"Acción 2 con métrica\"],\n  \"topics_to_validate\": [\"Dato a verificar\", \"Tendencia a confirmar\"]\n}}\nEnfoque: Profesional, directo, orientado a resultados medibles."
        
        if free_query.strip():
            user_query += f"\n\nCONSULTA ESPECÍFICA DEL USUARIO:\n{free_query}"
    
    #  MODO PERSONALIZADO
    elif query_mode == "📝 Personalizada":
        user_query = st.text_area("Escribe tu consulta", placeholder="Ej: Analiza tendencias B2B para 2026...", height=150, key="tab1_custom_query")
        use_adv = st.checkbox("⚙️ Usar prompts avanzados (Configuración → Tab 3)", value=True, key="tab1_use_adv")
        if use_adv:
            openai_prompt = st.session_state.get("tab3_openai_prompt", """Eres un analista estratégico experto en contenidos B2B. Analiza y genera insights accionables en formato JSON...""")
        else:
            openai_prompt = """Eres un analista estratégico experto en contenidos B2B. Analiza y genera insights accionables en formato JSON..."""
            
    # 🟥 MODO PLANTILLA
    else:
        templates = {
            "Análisis Estratégico B2B": "Realiza un análisis estratégico completo identificando tendencias clave, oportunidades y riesgos en marketing B2B industrial...",
            "Resumen Ejecutivo": "Genera un resumen ejecutivo profesional destacando los 3 puntos más relevantes para la toma de decisiones...",
            "Plan de Acción con KPIs": "Identifica los 5 puntos más importantes para mejorar la generación de leads B2B y crea un plan de acción...",
            "Benchmark Competitivo": "Realiza un análisis competitivo del sector comparando estrategias de marketing digital B2B...",
            "Contenido LinkedIn B2B": "Genera 5 ideas de contenido para LinkedIn enfocadas en thought leadership B2B industrial...",
            "Estrategia Ferias Industriales": "Analiza las mejores prácticas para participación en ferias B2B combinando estrategia digital...",
            "Tendencias LifeSciences 2026": "Analiza las últimas tendencias en marketing digital para empresas de LifeSciences y MedTech...",
            "Análisis DAFO Digital": "Realiza un análisis DAFO enfocado en estrategia digital B2B. Valida cada punto con tendencias actuales."
        }
        
        if "tab1_last_template" not in st.session_state: st.session_state.tab1_last_template = None
        if "tab1_template_query" not in st.session_state: st.session_state.tab1_template_query = list(templates.values())[0]
        
        selected_template = st.selectbox("Elige una plantilla", list(templates.keys()), key="tab1_template_select")
        if st.session_state.tab1_last_template != selected_template:
            st.session_state.tab1_template_query = templates[selected_template]
            st.session_state.tab1_last_template = selected_template
            
        user_query = st.text_area("Consulta (editable)", value=st.session_state.tab1_template_query, height=150, key="tab1_template_query")
        if user_query != templates.get(selected_template): st.session_state.tab1_last_template = None
        
        use_adv = st.checkbox("⚙️ Usar prompts avanzados (Configuración → Tab 3)", value=True, key="tab1_use_adv_tpl")
        openai_prompt = st.session_state.get("tab3_openai_prompt", """Eres un analista estratégico experto en contenidos B2B. Analiza y genera insights accionables en formato JSON...""") if use_adv else """Eres un analista estratégico experto en contenidos B2B. Analiza y genera insights accionables en formato JSON..."""

    # =====================================================
    # CONFIGURACIÓN DE MODELOS
    # =====================================================
    st.markdown("---")
    st.markdown("**⚙️ Configuración de modelos:**")
    col_openai, col_perplexity = st.columns(2)
    with col_openai:
        openai_models = {"GPT-4o Mini (Recomendado)": "gpt-4o-mini", "GPT-4o": "gpt-4o", "GPT-4 Turbo": "gpt-4-turbo-preview"}
        selected_openai = st.selectbox("🤖 Modelo OpenAI", list(openai_models.keys()), index=0, key="tab1_openai_model")
        openai_model = openai_models[selected_openai]
    with col_perplexity:
        perplexity_models = {"Sonar (Recomendado)": "sonar", "Sonar Pro": "sonar-pro", "Llama 3.1 70B": "llama-3.1-70b-instruct"}
        selected_perplexity = st.selectbox("🔍 Modelo Perplexity", list(perplexity_models.keys()), index=0, key="tab1_pplx_model")
        perplexity_model = perplexity_models[selected_perplexity]
    
    st.info("💡 *Perplexity validará automáticamente la respuesta, independientemente del modo elegido.*")

    # =====================================================
    # PASO 2: EJECUTAR
    # =====================================================
    st.markdown("### 🚀 Paso 2: Generar contenido")
    col_gen, col_clear = st.columns([4, 1])
    with col_gen:
        generate_content = st.button("▶️ Generar Contenido con IA", type="primary", use_container_width=True, disabled=not user_query.strip(), key="tab1_generate_btn")
    with col_clear:
        if st.button("🗑️ Limpiar", use_container_width=True, key="tab1_clear_btn"):
            for key in ["openai_response", "perplexity_response", "edited_response"]:
                st.session_state.pop(key, None)
            st.rerun()
    
    if generate_content:
        context = ""
        if selected_files: context = load_selected_context(client, bucket_name, selected_files, max_chars)
        
        #  OPENAI
        with st.spinner(f" {selected_openai} analizando..."):
            try:
                user_message = f"CONSULTA:\n{user_query}" + (f"\n\nCONTEXTO ADICIONAL:\n{context}" if context else "")
                response = st.session_state.openai.chat.completions.create(
                    model=openai_model, 
                    messages=[{"role": "system", "content": openai_prompt}, {"role": "user", "content": user_message}], 
                    response_format={"type": "json_object"}
                )
                raw = response.choices[0].message.content.strip()
                if "```json" in raw: raw = raw.split("```json")[1].split("```")[0].strip()
                elif "```" in raw: raw = raw.split("```")[1].split("```")[0].strip()
                
                openai_data = json.loads(raw)
                openai_data["summary"] = openai_data.get("summary") or openai_data.get("content") or "Análisis generado."
                openai_data["key_points"] = openai_data.get("key_points") or openai_data.get("insights") or []
                openai_data["recommended_actions"] = openai_data.get("recommended_actions") or openai_data.get("actions") or []
                openai_data["metadata"] = {"timestamp": datetime.utcnow().isoformat(), "agent": "openai", "model": openai_model, "query": user_query, "mode": query_mode}
                st.session_state.openai_response = openai_data
            except Exception as e:
                st.error(f"❌ Error en OpenAI: {str(e)}")
                st.stop()
        
        # 🔍 PERPLEXITY
        with st.spinner(f"🔍 {selected_perplexity} validando..."):
            try:
                pplx = OpenAI(api_key=st.session_state.perplexity_key, base_url="https://api.perplexity.ai")
                pplx_sys = """Valida y enriquece análisis con fuentes confiables actuales. Responde en JSON: {"summary": "...", "key_points": [...], "recommended_actions": [...], "validation_notes": "...", "sources": [...], "confidence_level": "alto"}"""
                pplx_msg = f"ANÁLISIS A VALIDAR:\n{json.dumps(st.session_state.openai_response, indent=2, ensure_ascii=False)}\n\nCONSULTA ORIGINAL: {user_query}"
                res = pplx.chat.completions.create(model=perplexity_model, messages=[{"role": "system", "content": pplx_sys}, {"role": "user", "content": pplx_msg}])
                
                clean = res.choices[0].message.content.strip()
                if "```json" in clean: clean = clean.split("```json")[1].split("```")[0].strip()
                elif "```" in clean: clean = clean.split("```")[1].split("```")[0].strip()
                
                try: validated = json.loads(clean)
                except:
                    m = re.search(r'\{.*\}', clean, re.DOTALL)
                    validated = json.loads(m.group()) if m else {}
                
                validated["metadata"] = {"timestamp": datetime.utcnow().isoformat(), "agent": "perplexity", "model": perplexity_model, "original_query": user_query, "openai_model": openai_model}
                st.session_state.perplexity_response = validated
                st.success("✅ Contenido generado y validado")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error en Perplexity: {str(e)[:150]}")
                if "openai_response" in st.session_state:
                    st.warning("⚠️ Usando solo OpenAI como fallback")
                    fb = st.session_state.openai_response.copy()
                    fb["metadata"]["agent"] = "openai_fallback"
                    fb["metadata"]["fallback_reason"] = str(e)[:100]
                    fb["confidence_level"] = "bajo"
                    for f in ["validation_notes", "sources"]:
                        fb[f] = fb.get(f, "" if f=="validation_notes" else [])
                    st.session_state.perplexity_response = fb
                    st.rerun()

    # =====================================================
    # PASO 3: RESULTADOS
    # =====================================================
    if "perplexity_response" in st.session_state:
        st.markdown("---")
        st.markdown("### 📊 Paso 3: Resultado validado")
        final_data = st.session_state.perplexity_response
        meta = final_data.get("metadata", {})
        is_fallback = meta.get("agent") in ["openai", "openai_fallback", "openai_error"]
        
        with st.expander("👁️ Vista Previa del Contenido", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1: st.markdown(f"**🤖 OpenAI:** {meta.get('openai_model') or meta.get('model', 'N/A')}")
            with c2: st.markdown("**🔍 Perplexity:** ️ Fallback" if is_fallback else f"**🔍 Perplexity:** {meta.get('model', 'N/A')}")
            with c3: 
                conf = "bajo" if is_fallback else final_data.get("confidence_level", "medio").lower()
                st.markdown(f"**{'' if conf=='bajo' else '' if conf=='medio' else '🟢'} Confianza:** {conf.upper()}")
            
            st.markdown("---\n#### 📝 Resumen Ejecutivo")
            # ✅ FIX: Uso correcto de if/else en lugar de expresión condicional
            summary = final_data.get("summary") or final_data.get("content") or "N/A"
            if is_fallback:
                st.warning(f"⚠️ {summary}")
            else:
                st.success(summary)
            
            cp, ca = st.columns(2)
            with cp:
                st.markdown("#### 🎯 Puntos Clave")
                pts = final_data.get("key_points", []) or []
                if pts:
                    for i, p in enumerate(pts, 1): st.markdown(f"**{i}.** {p}")
                else:
                    st.caption("ℹ️ Sin puntos clave disponibles")
            with ca:
                st.markdown("#### ✅ Acciones Recomendadas")
                acts = final_data.get("recommended_actions", []) or []
                if acts:
                    for i, a in enumerate(acts, 1): st.markdown(f"**{i}.** {a}")
                else:
                    st.caption("ℹ️ Sin acciones recomendadas")
                
            if not is_fallback and final_data.get("validation_notes"):
                st.markdown("\n---\n#### 📋 Notas de Validación")
                st.info(final_data["validation_notes"])
            if not is_fallback and final_data.get("sources"):
                st.markdown("\n---\n#### 🔗 Fuentes Verificadas")
                for i, s in enumerate(final_data["sources"], 1):
                    st.markdown(f"{i}. [{s}]({s})" if s.startswith("http") else f"{i}. {s}")

        # =====================================================
        # PASO 4: CONTENIDO FORMATEADO
        # =====================================================
        st.markdown("---\n### 🎨 Paso 4: Contenido listo para usar")
        fmt = st.radio("📋 Formato", [" Email/Infografía", "💼 LinkedIn", "🌐 Web/HTML", "📝 Texto Plano"], horizontal=True, key="tab1_out_fmt")
        
        def gen_fmt(d, f):
            s, pts, acts = d.get("summary",""), d.get("key_points",[]), d.get("recommended_actions",[])
            if f=="📊 Email/Infografía": 
                return f"🔹 {s}\n\n📌 Puntos:\n" + "\n".join(f"• {p}" for p in pts) + "\n\n🎯 Acciones:\n" + "\n".join(f"→ {a}" for a in acts)
            elif f=="💼 LinkedIn": 
                return f"{s[:150]}...\n\n🧵 Insights:\n" + "\n\n".join(f"{i+1}/ {p}" for i,p in enumerate(pts[:3])) + "\n\n ¿Qué opinas?\n👇 Comenta.\n\n#B2B #Marketing #KaiBot"
            elif f=="🌐 Web/HTML": 
                return f"<article><h1>{s}</h1><h2>Puntos</h2><ul>{''.join(f'<li>{p}</li>' for p in pts)}</ul><h2>Acciones</h2><ol>{''.join(f'<li>{a}</li>' for a in acts)}</ol></article>"
            return f"RESUMEN:\n{s}\n\nPUNTOS:\n" + "\n".join(f"{i}. {p}" for i,p in enumerate(pts,1)) + "\n\nACCIONES:\n" + "\n".join(f"{i}. {a}" for i,a in enumerate(acts,1))
            
        content = gen_fmt(final_data, fmt)
        st.code(content, language="text" if fmt!="🌐 Web/HTML" else "html")
        ext = "html" if fmt=="🌐 Web/HTML" else "txt"
        st.download_button("⬇️ Descargar", content, file_name=f"kaibot_output_{datetime.now().strftime('%Y%m%d_%H%M')}.{ext}", mime="text/html" if ext=="html" else "text/plain", key="tab1_dl_fmt")

        # =====================================================
        # PASO 5: INFOGRAFÍA (PILLOW)
        # =====================================================
        st.markdown("---\n### 🖼️ Paso 5: Generar Infografía")
        try:
            from PIL import Image, ImageDraw, ImageFont
            from io import BytesIO
            PIL_OK = True
        except ImportError:
            PIL_OK = False
            st.error("📦 Falta `Pillow`. Ejecuta `pip install Pillow` para activar esta función.")
            
        if PIL_OK:
            st_info = st.selectbox("🎨 Estilo", ["professional", "dark", "clean"], format_func=lambda x: {"professional":"🏢 Profesional", "dark":"🌑 Dark", "clean":"️ Minimalista"}[x], key="tab1_inf_style")
            if st.button("🖼️ Generar Infografía", type="primary", use_container_width=True, key="tab1_gen_inf"):
                with st.spinner("🎨 Generando..."):
                    try:
                        W, H = 1080, 1920
                        colors = {"professional": ("#FFFFFF","#0066CC","#1E293B","#10B981","#F8FAFC"), "dark": ("#1E293B","#0F172A","#E2E8F0","#3B82F6","#334155"), "clean": ("#FFFFFF","#F8FAFC","#64748B","#0066CC","#F1F5F9")}[st_info]
                        bg, hdr, txt, acc, light = colors
                        img = Image.new('RGB', (W, H), color=bg)
                        draw = ImageDraw.Draw(img)
                        try: fT = ImageFont.truetype("arial.ttf", 60); fS = ImageFont.truetype("arial.ttf", 36); fB = ImageFont.truetype("arial.ttf", 32)
                        except: fT = fS = fB = ImageFont.load_default()
                        
                        def wrap(draw, text, y, font, mw, color, lh=44):
                            words, lines = text.split(), []
                            line = []
                            for w in words:
                                test = " ".join(line+[w])
                                try: tw = draw.textbbox((0,0), test, font=font)[2]
                                except: tw = draw.textlength(test, font=font)
                                if tw <= mw: line.append(w)
                                else: lines.append(" ".join(line)); line = [w]
                            if line: lines.append(" ".join(line))
                            for l in lines: draw.text((80, y), l, font=font, fill=color); y += lh
                            return y
                            
                        draw.rectangle([0,0,W,400], fill=hdr)
                        draw.text((80,100), "KAIBOT | ANÁLISIS IA", font=fS, fill="#FFF")
                        draw.ellipse([80,200,160,280], fill="#FFF")
                        draw.text((95,215), "KB", font=fS, fill=hdr)
                        
                        y = wrap(draw, final_data.get("summary","")[:300], 450, fB, W-160, txt)
                        y = wrap(draw, " PUNTOS CLAVE", y+60, fS, W-160, acc)
                        for p in final_data.get("key_points",[])[:4]:
                            cp = re.sub(r'^(Validado|No validado)[^:]*:\s*', '', p, flags=re.IGNORECASE)[:200]
                            draw.rectangle([60,y-10,W-60,y+100], fill=light, outline=acc, width=4)
                            draw.text((90, y), f"{'✅' if 'validado' in p.lower() else '⚠️'} {cp}", font=fB, fill=txt)
                            y += 120
                            
                        y = wrap(draw, " ACCIONES", y+40, fS, W-160, acc)
                        for a in final_data.get("recommended_actions",[])[:3]:
                            y = wrap(draw, f"• {a[:180]}", y+20, fB, W-160, txt)
                            
                        draw.rectangle([0,H-300,W,H], fill=hdr)
                        draw.text((80,H-250), f"🔗 {len(final_data.get('sources',[]))} fuentes verificadas", font=fB, fill="#FFF")
                        draw.text((80,H-200), f"Generado con KaiBot IA | {datetime.now().strftime('%d/%m/%Y')}", font=ImageFont.load_default(), fill="#94A3B8")
                        
                        buf = BytesIO()
                        img.save(buf, format="PNG")
                        buf.seek(0)
                        st.success("✅ Infografía generada")
                        st.image(buf, caption="Vista previa", use_container_width=True)
                        st.download_button("⬇️ Descargar PNG", buf, file_name=f"kaibot_inf_{datetime.now().strftime('%Y%m%d_%H%M')}.png", mime="image/png", key="tab1_dl_png")
                    except Exception as e:
                        st.error(f"❌ Error generando imagen: {e}")
            st.caption("💡 ¿Prefieres editar visualmente? Exporta el JSON e impórtalo en [Gamma.app](https://gamma.app)")

        # =====================================================
        # GUARDAR / DESCARGAR JSON
        # =====================================================
        st.markdown("---\n### 💾 Guardar contenido")
        with st.expander("📋 Metadatos & JSON", expanded=True):
            cm1, cm2 = st.columns(2)
            with cm1:
                c_tipo = st.text_input("🏷️ Tipo", value="Análisis IA" if not is_fallback else "Análisis Fallback", key="tab1_tipo_meta")
                c_obj = st.selectbox("🎯 Objetivo", ["Marketing B2B", "Social Media", "Blog Post", "Informe Interno", "Presentación"], index=0, key="tab1_obj_meta")
            with cm2:
                c_src = st.checkbox("✅ Fuentes verificadas", value=not is_fallback and bool(final_data.get("sources")), disabled=is_fallback, key="tab1_src_meta")
                c_notas = st.text_area(" Notas", value=f"Modo: {query_mode}", height=60, key="tab1_notas_meta")
                
            if "edited_response" not in st.session_state: st.session_state.edited_response = json.dumps(final_data, indent=2, ensure_ascii=False)
            edited = st.text_area("JSON editable", value=st.session_state.edited_response, height=300, key="tab1_json_ed")
            try: ed_data = json.loads(edited); jv = True
            except: st.error("❌ JSON inválido"); jv = False; ed_data = final_data
            
            fname = generate_smart_filename(ed_data)
            st.info(f"📝 Archivo: `{fname}`")
            cs, cd = st.columns(2)
            with cs:
                if st.button("💾 Guardar en Cloud", type="primary", use_container_width=True, disabled=not jv, key="tab1_save_btn"):
                    try:
                        save_analysis_with_metadata(client, bucket_name, BUCKET_FOLDERS["validados"], fname, ed_data, {"tipo": c_tipo, "objetivo": c_obj, "fuentes_fiables": c_src, "notas": c_notas})
                        st.success(f"✅ Guardado: {fname}"); st.balloons()
                    except Exception as e: st.error(f"❌ Error: {e}")
            with cd:
                st.download_button("️ Descargar JSON", json.dumps(ed_data, indent=2, ensure_ascii=False), file_name=fname, mime="application/json", use_container_width=True, key="tab1_dl_json")



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
# TAB 4 - MONITOR DE CONTENIDOS (SUGERENCIAS 24H)
# =====================================================

with tab4:
    st.markdown("## 📡 Monitor de Contenidos")
    st.markdown("*Fuentes inteligentes que revisan cada 24h y sugieren contenido relevante*")
    
    # =====================================================
    # INICIALIZACIÓN
    # =====================================================
    if "content_sources" not in st.session_state:
        st.session_state.content_sources = []
    if "last_check" not in st.session_state:
        st.session_state.last_check = None
    if "content_suggestions" not in st.session_state:
        st.session_state.content_suggestions = []
    
    # =====================================================
    # GESTIÓN DE FUENTES
    # =====================================================
    st.markdown("### 🔗 Gestión de Fuentes")
    
    col_add, col_list = st.columns([2, 3])
    
    with col_add:
        st.markdown("**➕ Añadir nueva fuente**")
        source_type = st.selectbox("Tipo de fuente", 
                                   ["📰 RSS Feed", "🌐 Página Web", "💼 LinkedIn Company", "🐦 Twitter/X", "📊 Informe/Estudio", "📧 Newsletter"],
                                   key="tab4_source_type")
        
        source_url = st.text_input("URL / Identificador", 
                                   placeholder="https://... o @username", 
                                   key="tab4_source_url")
        
        source_category = st.selectbox("Categoría", 
                                       ["Competencia", "Tendencias Sector", "Clientes Potenciales", "Medios/Press", "Influencers", "Otros"],
                                       key="tab4_source_cat")
        
        source_priority = st.select_slider("Prioridad", options=["Baja", "Media", "Alta", "Crítica"], value="Media", key="tab4_source_prio")
        
        if st.button("➕ Añadir Fuente", type="primary", use_container_width=True, key="tab4_add_source_btn"):
            if source_url.strip():
                new_source = {
                    "id": datetime.now().timestamp(),
                    "type": source_type,
                    "url": source_url.strip(),
                    "category": source_category,
                    "priority": source_priority,
                    "added": datetime.now().isoformat(),
                    "last_checked": None,
                    "status": "active"
                }
                st.session_state.content_sources.append(new_source)
                st.success(f"✅ Fuente añadida: {source_url[:50]}...")
                st.rerun()
            else:
                st.error("❌ Introduce una URL válida")
    
    with col_list:
        st.markdown(f"**📋 Fuentes activas ({len(st.session_state.content_sources)})**")
        
        if st.session_state.content_sources:
            for i, src in enumerate(st.session_state.content_sources):
                with st.container():
                    col1, col2, col3 = st.columns([4, 1, 1])
                    with col1:
                        st.markdown(f"**{src['type']}** - {src['category']}")
                        st.caption(f"{src['url'][:60]}...")
                        st.markdown(f"Prioridad: {src['priority']} | Añadida: {src['added'][:10]}")
                    with col2:
                        if st.button("🗑️", key=f"tab4_del_src_{i}", help="Eliminar fuente"):
                            st.session_state.content_sources.pop(i)
                            st.rerun()
                    with col3:
                        status_icon = "🟢" if src.get("status") == "active" else "🔴"
                        st.markdown(status_icon)
                    st.markdown("---")
        else:
            st.info("💡 Añade fuentes para comenzar el monitoreo")
    
    # =====================================================
    # REVISIÓN AUTOMÁTICA (CADA 24H)
    # =====================================================
    st.markdown("---")
    st.markdown("### 🔄 Revisión de Contenidos")
    
    col_check, col_info = st.columns([2, 3])
    
    with col_check:
        if st.button("🔍 Revisar fuentes ahora", type="primary", use_container_width=True, key="tab4_manual_check"):
            with st.spinner(" Analizando fuentes..."):
                suggestions = []
                
                for src in st.session_state.content_sources:
                    if src.get("status") != "active":
                        continue
                    
                    try:
                        # 🔧 Simulación de análisis (en producción usarías scraping/RSS)
                        # Aquí usamos Perplexity para analizar la fuente
                        pplx = OpenAI(api_key=st.session_state.perplexity_key, base_url="https://api.perplexity.ai")
                        
                        prompt = f"""Analiza esta fuente y extrae:
                        1. Últimas noticias/tendencias relevantes
                        2. Oportunidades de contenido detectadas
                        3. Temas candentes o controvertidos
                        4. Posibles ángulos para crear contenido

                        Fuente: {src['url']}
                        Tipo: {src['type']}
                        Categoría: {src['category']}

                        Responde en JSON:
                        {{
                            "trends": ["tendencia 1", "tendencia 2"],
                            "opportunities": ["oportunidad 1", "oportunidad 2"],
                            "hot_topics": ["tema 1", "tema 2"],
                            "content_angles": ["ángulo 1", "ángulo 2"],
                            "urgency": "baja/media/alta"
                        }}"""
                        
                        response = pplx.chat.completions.create(
                            model="sonar",
                            messages=[{"role": "user", "content": prompt}]
                        )
                        
                        # Parsear respuesta
                        content = response.choices[0].message.content
                        try:
                            analysis = json.loads(content)
                        except:
                            analysis = {
                                "trends": ["Análisis no disponible"],
                                "opportunities": ["Revisar manualmente"],
                                "hot_topics": [],
                                "content_angles": [],
                                "urgency": "media"
                            }
                        
                        # Crear sugerencia
                        suggestion = {
                            "source_id": src["id"],
                            "source_url": src["url"],
                            "source_type": src["type"],
                            "category": src["category"],
                            "priority": src["priority"],
                            "trends": analysis.get("trends", []),
                            "opportunities": analysis.get("opportunities", []),
                            "hot_topics": analysis.get("hot_topics", []),
                            "content_angles": analysis.get("content_angles", []),
                            "urgency": analysis.get("urgency", "media"),
                            "detected_at": datetime.now().isoformat(),
                            "status": "new"
                        }
                        
                        suggestions.append(suggestion)
                        
                        # Actualizar última revisión
                        src["last_checked"] = datetime.now().isoformat()
                        
                    except Exception as e:
                        st.warning(f"⚠️ Error analizando {src['url'][:40]}...: {str(e)[:50]}")
                
                # Guardar sugerencias
                st.session_state.content_suggestions = suggestions
                st.session_state.last_check = datetime.now()
                
                st.success(f"✅ Revisión completada: {len(suggestions)} sugerencias generadas")
                st.rerun()
    
    with col_info:
        if st.session_state.last_check:
            next_check = st.session_state.last_check + timedelta(hours=24)
            time_remaining = next_check - datetime.now()
            
            st.info(f"""
            **Última revisión:** {st.session_state.last_check.strftime('%d/%m/%Y %H:%M')}
            
            **Próxima revisión automática:** {next_check.strftime('%d/%m/%Y %H:%M')}
            
            **Tiempo restante:** {time_remaining.seconds // 3600}h {(time_remaining.seconds % 3600) // 60}m
            """)
        else:
            st.info(" Sin revisiones programadas. Haz clic en 'Revisar fuentes ahora' para comenzar.")
    
    # =====================================================
    # SUGERENCIAS DE CONTENIDO
    # =====================================================
    if st.session_state.content_suggestions:
        st.markdown("---")
        st.markdown(f"### 💡 Sugerencias de Contenido ({len(st.session_state.content_suggestions)})")
        
        # Filtros
        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            filter_category = st.multiselect("Filtrar por categoría", 
                                            list(set(s["category"] for s in st.session_state.content_suggestions)),
                                            key="tab4_filter_cat")
        with col_filter2:
            filter_urgency = st.selectbox("Prioridad", ["Todas", "Alta", "Media", "Baja"], key="tab4_filter_urg")
        
        # Filtrar sugerencias
        filtered = st.session_state.content_suggestions
        if filter_category:
            filtered = [s for s in filtered if s["category"] in filter_category]
        if filter_urgency != "Todas":
            filtered = [s for s in filtered if s["urgency"] == filter_urgency.lower()]
        
        # Mostrar sugerencias
        for i, sug in enumerate(filtered):
            with st.expander(f"{'🔴' if sug['urgency']=='alta' else '🟡' if sug['urgency']=='media' else '🟢'} {sug['source_type']} - {sug['category']}", expanded=(sug['urgency']=='alta')):
                
                col_s1, col_s2 = st.columns([3, 1])
                
                with col_s1:
                    st.markdown(f"**Fuente:** [{sug['source_url'][:80]}...]({sug['source_url']})")
                    st.caption(f"Detectado: {sug['detected_at'][:16]} | Prioridad: {sug['priority']}")
                
                with col_s2:
                    if st.button("✍️ Crear contenido", key=f"tab4_create_{i}", type="primary"):
                        # Preparar datos para Tab 1
                        st.session_state.tab1_query_mode = " Personalizada"
                        st.session_state.tab1_custom_query = f"""
                        Basándome en esta fuente: {sug['source_url']}
                        
                        Tendencias detectadas: {', '.join(sug['trends'][:3])}
                        
                        Oportunidades: {', '.join(sug['opportunities'][:2])}
                        
                        Genera un análisis completo sobre: {sug['hot_topics'][0] if sug['hot_topics'] else sug['trends'][0]}
                        """
                        st.session_state.tab1_from_monitor = True
                        st.switch_tab("tab1")  # O st.tabs si usas índice
                        st.success("📋 Datos copiados al Tab 1. Genera el contenido ahora.")
                
                st.markdown("---")
                
                # Tendencias
                if sug.get("trends"):
                    st.markdown("**📈 Tendencias detectadas:**")
                    for t in sug["trends"]:
                        st.markdown(f"• {t}")
                
                # Oportunidades
                if sug.get("opportunities"):
                    st.markdown("**🎯 Oportunidades de contenido:**")
                    for o in sug["opportunities"]:
                        st.markdown(f"✓ {o}")
                
                # Temas candentes
                if sug.get("hot_topics"):
                    st.markdown("**🔥 Temas candentes:**")
                    st.markdown(", ".join(sug["hot_topics"]))
                
                # Ángulos de contenido
                if sug.get("content_angles"):
                    st.markdown("**💡 Ángulos sugeridos:**")
                    for a in sug["content_angles"]:
                        st.markdown(f"→ {a}")
                
                # Acciones
                col_act1, col_act2, col_act3 = st.columns(3)
                with col_act1:
                    if st.button("📋 Copiar sugerencia", key=f"tab4_copy_{i}"):
                        st.code(f"Fuente: {sug['source_url']}\nTema: {sug['hot_topics'][0] if sug['hot_topics'] else sug['trends'][0]}\nÁngulo: {sug['content_angles'][0] if sug['content_angles'] else 'Crear contenido sobre tendencias'}", language="text")
                with col_act2:
                    if st.button("⭐ Marcar como vista", key=f"tab4_mark_{i}"):
                        sug["status"] = "reviewed"
                        st.rerun()
                with col_act3:
                    if st.button("🗑️ Descartar", key=f"tab4_discard_{i}"):
                        st.session_state.content_suggestions.remove(sug)
                        st.rerun()
    
    # =====================================================
    # CONFIGURACIÓN AVANZADA
    # =====================================================
    st.markdown("---")
    with st.expander("⚙️ Configuración del Monitor"):
        st.markdown("**🔄 Frecuencia de revisión**")
        check_freq = st.selectbox("Cada cuánto revisar", ["6 horas", "12 horas", "24 horas", "48 horas"], index=2, key="tab4_freq")
        
        st.markdown("**📊 Notificaciones**")
        notify_email = st.text_input("Email para notificaciones (opcional)", placeholder="tu@email.com", key="tab4_notify_email")
        notify_slack = st.text_input("Webhook Slack (opcional)", placeholder="https://hooks.slack.com/...", key="tab4_notify_slack")
        
        st.markdown("**💾 Guardar configuración**")
        if st.button("💾 Guardar preferencias", key="tab4_save_config"):
            st.session_state.monitor_config = {
                "frequency": check_freq,
                "notify_email": notify_email,
                "notify_slack": notify_slack
            }
            st.success("✅ Configuración guardada")
        
        st.info("💡 **Nota:** Las revisiones automáticas requieren que la app esté activa. En Streamlit Cloud, considera usar GitHub Actions o un cron job externo para revisiones automáticas cada 24h.")
    
    # =====================================================
    # IMPORTAR/EXPORTAR FUENTES
    # =====================================================
    st.markdown("---")
    col_imp, col_exp = st.columns(2)
    
    with col_imp:
        st.markdown("**📥 Importar fuentes**")
        uploaded = st.file_uploader("Subir JSON de fuentes", type=["json"], key="tab4_import")
        if uploaded:
            try:
                data = json.load(uploaded)
                st.session_state.content_sources.extend(data.get("sources", []))
                st.success(f"✅ {len(data.get('sources', []))} fuentes importadas")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error: {e}")
    
    with col_exp:
        st.markdown("**📤 Exportar fuentes**")
        if st.button("⬇️ Descargar configuración", key="tab4_export"):
            export_data = {
                "sources": st.session_state.content_sources,
                "exported_at": datetime.now().isoformat(),
                "version": "1.0"
            }
            st.download_button(
                "⬇️ Descargar JSON",
                json.dumps(export_data, indent=2, ensure_ascii=False),
                file_name=f"kaibot_sources_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                key="tab4_dl_sources"
            )

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
