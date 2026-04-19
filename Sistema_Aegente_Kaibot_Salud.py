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
    
    /* Selectbox mejorado */
    .stSelectbox {
        border-radius: 6px;
    }
    
    /* Text areas */
    textarea {
        border-radius: 6px !important;
        border: 1px solid #E2E8F0 !important;
    }
    
    /* Spinner personalizado */
    .stSpinner > div {
        border-top-color: var(--kaibot-blue) !important;
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
    
    /* Progress bar */
    .stProgress > div > div {
        background-color: var(--kaibot-blue);
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

# =====================================================
# FUNCIONES HELPER (todas las que ya tienes)
# =====================================================

# ... [Aquí van todas tus funciones helper existentes: get_gcs_client_from_json, list_folders_and_files, etc.]
# Para no hacer esto demasiado largo, mantén TODAS las funciones que ya tienes

# =====================================================
# Helpers GCP
# =====================================================

def get_gcs_client_from_json(sa_json_str: str) -> storage.Client:
    """Crea cliente GCS desde JSON de service account"""
    try:
        info = json.loads(sa_json_str)
        creds = service_account.Credentials.from_service_account_info(info)
        return storage.Client(credentials=creds, project=info.get("project_id"))
    except json.JSONDecodeError:
        raise ValueError("El JSON del Service Account no es válido")
    except Exception as e:
        raise Exception(f"Error al crear cliente GCS: {str(e)}")


def list_folders_and_files(client: storage.Client, bucket_name: str):
    """Lista carpetas y archivos del bucket con metadatos enriquecidos"""
    bucket = client.bucket(bucket_name)
    blobs = list(bucket.list_blobs())
    
    folders = set()
    files = []
    
    for b in blobs:
        parts = b.name.split("/")
        if len(parts) > 1:
            folders.add(parts[0] + "/")
        
        # IMPORTANTE: Recargar el blob para obtener metadatos actualizados
        b.reload()
        
        # Obtener metadatos custom
        metadata = b.metadata or {}
        
        files.append({
            "name": b.name,
            "size": b.size,
            "updated": b.updated,
            "tipo": metadata.get("tipo", ""),
            "notas": metadata.get("notas", ""),
            "objetivo": metadata.get("objetivo", ""),
            "fuentes_fiables": metadata.get("fuentes_fiables", "").lower() == "true"
        })
    
    return sorted(folders), files


def upload_file(client: storage.Client, bucket_name: str, file, folder: str):
    """Sube archivo a GCS"""
    bucket = client.bucket(bucket_name)
    path = f"{folder.rstrip('/')}/{file.name}"
    blob = bucket.blob(path)
    blob.upload_from_file(file, rewind=True)
    return path


def upload_json_to_gcs(client: storage.Client, bucket_name: str, folder: str, filename: str, data: dict):
    """Sube JSON a GCS"""
    bucket = client.bucket(bucket_name)
    path = f"{folder.rstrip('/')}/{filename}"
    blob = bucket.blob(path)
    blob.upload_from_string(json.dumps(data, indent=2, ensure_ascii=False), content_type="application/json")
    return path
# =====================================================
# Sistema de Metadatos de Archivos
# =====================================================

def get_file_metadata(client: storage.Client, bucket_name: str, file_path: str) -> dict:
    """Obtiene metadatos personalizados de un archivo"""
    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(file_path)
        blob.reload()
        
        # Obtener metadatos custom
        metadata = blob.metadata or {}
        
        return {
            "tipo": metadata.get("tipo", ""),
            "notas": metadata.get("notas", ""),
            "objetivo": metadata.get("objetivo", ""),
            "fuentes_fiables": metadata.get("fuentes_fiables", "").lower() == "true"
        }
    except Exception:
        return {
            "tipo": "",
            "notas": "",
            "objetivo": "",
            "fuentes_fiables": False
        }


def update_file_metadata(client: storage.Client, bucket_name: str, file_path: str, metadata: dict):
    """Actualiza metadatos personalizados de un archivo"""
    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(file_path)
        blob.reload()
        
        # Preparar metadatos
        custom_metadata = {
            "tipo": metadata.get("tipo", ""),
            "notas": metadata.get("notas", ""),
            "objetivo": metadata.get("objetivo", ""),
            "fuentes_fiables": str(metadata.get("fuentes_fiables", False))
        }
        
        # Actualizar
        blob.metadata = custom_metadata
        blob.patch()
        
        return True
    except Exception as e:
        st.error(f"Error actualizando metadatos: {str(e)}")
        return False


def save_analysis_with_metadata(client: storage.Client, bucket_name: str, folder: str, 
                                filename: str, data: dict, analysis_metadata: dict):
    """Guarda JSON con metadatos enriquecidos"""
    try:
        bucket = client.bucket(bucket_name)
        path = f"{folder.rstrip('/')}/{filename}"
        blob = bucket.blob(path)
        
        # Subir contenido JSON
        blob.upload_from_string(
            json.dumps(data, indent=2, ensure_ascii=False),
            content_type="application/json"
        )
        
        # Añadir metadatos custom
        blob.metadata = {
            "tipo": analysis_metadata.get("tipo", "Análisis IA"),
            "notas": analysis_metadata.get("notas", ""),
            "objetivo": analysis_metadata.get("objetivo", ""),
            "fuentes_fiables": str(analysis_metadata.get("fuentes_fiables", True))
        }
        blob.patch()
        
        return path
    except Exception as e:
        raise Exception(f"Error al guardar con metadatos: {str(e)}")

# =====================================================
# Previsualización de archivos
# =====================================================

def preview_file(client: storage.Client, bucket_name: str, file_path: str):
    """Previsualiza el contenido de un archivo según su tipo"""
    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(file_path)
        
        # Obtener extensión del archivo
        file_ext = file_path.split('.')[-1].lower()
        
        # Archivos JSON
        if file_ext == 'json':
            content = blob.download_as_text()
            data = json.loads(content)
            st.json(data)
            return True
        
        # Archivos de texto
        elif file_ext in ['txt', 'md', 'csv', 'log']:
            content = blob.download_as_text()
            st.code(content, language='text')
            return True
        
        # Archivos Python
        elif file_ext == 'py':
            content = blob.download_as_text()
            st.code(content, language='python')
            return True
        
        # Archivos JavaScript/TypeScript
        elif file_ext in ['js', 'jsx', 'ts', 'tsx']:
            content = blob.download_as_text()
            st.code(content, language='javascript')
            return True
        
        # Archivos HTML/CSS
        elif file_ext in ['html', 'css']:
            content = blob.download_as_text()
            st.code(content, language='html')
            return True
        
        # Imágenes
        elif file_ext in ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp']:
            image_bytes = blob.download_as_bytes()
            st.image(image_bytes, caption=file_path, use_container_width=True)
            return True
        
        # PDFs (mostrar info)
        elif file_ext == 'pdf':
            st.info(f"📄 Archivo PDF: {file_path}")
            st.write(f"**Tamaño:** {blob.size / 1024:.2f} KB")
            st.warning("💡 Descarga el archivo para visualizarlo completamente")
            # Botón de descarga
            pdf_bytes = blob.download_as_bytes()
            st.download_button(
                "⬇️ Descargar PDF",
                pdf_bytes,
                file_name=file_path.split('/')[-1],
                mime="application/pdf"
            )
            return True
        
        # Archivos de Office (mostrar info)
        elif file_ext in ['docx', 'xlsx', 'pptx', 'doc', 'xls', 'ppt']:
            st.info(f"📎 Archivo de Office: {file_path}")
            st.write(f"**Tipo:** {file_ext.upper()}")
            st.write(f"**Tamaño:** {blob.size / 1024:.2f} KB")
            st.warning("💡 Descarga el archivo para visualizarlo")
            # Botón de descarga
            file_bytes = blob.download_as_bytes()
            mime_types = {
                'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                'doc': 'application/msword',
                'xls': 'application/vnd.ms-excel',
                'ppt': 'application/vnd.ms-powerpoint'
            }
            st.download_button(
                f"⬇️ Descargar {file_ext.upper()}",
                file_bytes,
                file_name=file_path.split('/')[-1],
                mime=mime_types.get(file_ext, 'application/octet-stream')
            )
            return True
        
        else:
            st.warning(f"⚠️ Tipo de archivo no soportado para previsualización: .{file_ext}")
            st.info("📊 Información del archivo:")
            st.write(f"**Nombre:** {file_path}")
            st.write(f"**Tamaño:** {blob.size / 1024:.2f} KB")
            return False
            
    except Exception as e:
        st.error(f"❌ Error al previsualizar: {str(e)}")
        return False

# =====================================================
# Sistema de Gestión de Prompts
# =====================================================

def save_prompt_to_bucket(client: storage.Client, bucket_name: str, prompt_data: dict, metadata: dict):
    """
    Guarda un prompt en el bucket con metadatos
    
    Args:
        client: Cliente GCS
        bucket_name: Nombre del bucket
        prompt_data: Diccionario con 'openai_prompt' y 'perplexity_prompt'
        metadata: Diccionario con 'nombre', 'descripcion', 'uso'
    
    Returns:
        Nombre del archivo guardado
    """
    try:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        # Crear nombre de archivo descriptivo
        nombre_limpio = re.sub(r'[^\w\-_.]', '_', metadata.get("nombre", "prompt"))
        filename = f"{nombre_limpio}_{timestamp}.json"
        
        # Preparar contenido del archivo
        content = {
            "nombre": metadata.get("nombre", ""),
            "descripcion": metadata.get("descripcion", ""),
            "uso": metadata.get("uso", ""),
            "created_at": datetime.utcnow().isoformat(),
            "prompts": {
                "openai": prompt_data.get("openai_prompt", ""),
                "perplexity": prompt_data.get("perplexity_prompt", "")
            }
        }
        
        # Guardar en bucket
        bucket = client.bucket(bucket_name)
        path = f"{BUCKET_FOLDERS['prompts']}{filename}"
        blob = bucket.blob(path)
        
        # Subir JSON
        blob.upload_from_string(
            json.dumps(content, indent=2, ensure_ascii=False),
            content_type="application/json"
        )
        
        # Añadir metadatos para la tabla
        blob.metadata = {
            "tipo": "Prompt System",
            "objetivo": metadata.get("uso", "General"),
            "fuentes_fiables": "true",
            "notas": metadata.get("descripcion", "")
        }
        blob.patch()
        
        return filename
        
    except Exception as e:
        raise Exception(f"Error al guardar prompt: {str(e)}")


def load_prompt_from_bucket(client: storage.Client, bucket_name: str, file_path: str) -> dict:
    """Carga un prompt guardado del bucket"""
    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(file_path)
        content = blob.download_as_text()
        return json.loads(content)
    except Exception as e:
        raise Exception(f"Error al cargar prompt: {str(e)}")


        
# =====================================================
# Perplexity Agent
# =====================================================

def call_perplexity_agent(api_key: str, system_prompt: str, user_query: str, context: str = "") -> dict:
    """
    Llama a Perplexity API y retorna respuesta en JSON
    
    Args:
        api_key: API key de Perplexity
        system_prompt: Instrucciones del sistema
        user_query: Consulta del usuario
        context: Contexto adicional de documentos
    
    Returns:
        dict con la respuesta parseada
    """
    try:
        from openai import OpenAI
        
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.perplexity.ai"
        )
        
        # Preparar mensaje completo
        full_message = user_query
        if context:
            full_message = f"""CONTEXTO:
{context}

---

CONSULTA:
{user_query}"""
        
        # Llamar a Perplexity
        response = client.chat.completions.create(
            model="llama-3.1-sonar-small-128k-online",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_message}
            ]
        )
        
        response_text = response.choices[0].message.content
        
        # Limpiar markdown
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        return json.loads(response_text)
        
    except json.JSONDecodeError:
        raise ValueError("La respuesta de Perplexity no es un JSON válido")
    except Exception as e:
        raise Exception(f"Error al llamar a Perplexity: {str(e)}")

# =====================================================
# Context loader
# =====================================================

def load_selected_context(client: storage.Client, bucket_name: str, selected_files: list, max_chars: int) -> str:
    """Carga contexto de archivos seleccionados con límite de caracteres"""
    bucket = client.bucket(bucket_name)
    texts = []
    total_chars = 0
    
    for name in selected_files:
        try:
            blob = bucket.blob(name)
            content = blob.download_as_text()
            
            if total_chars + len(content) > max_chars:
                remaining = max_chars - total_chars
                if remaining <= 0:
                    break
                content = content[:remaining]
            
            texts.append(f"### {name}\n{content}")
            total_chars += len(content)
        except Exception as e:
            st.warning(f"Error al cargar {name}: {str(e)}")
    
    return "\n\n".join(texts)


# =====================================================
# OpenAI Agent
# =====================================================

def call_openai_agent(openai_client: OpenAI, system_prompt: str, context: str, user_query: str) -> dict:
    """Llama al agente de OpenAI y retorna respuesta JSON"""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"{system_prompt}\n\nContexto:\n{context}"},
                {"role": "user", "content": user_query}
            ],
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        raise ValueError("La respuesta de OpenAI no es un JSON válido")
    except Exception as e:
        raise Exception(f"Error al llamar a OpenAI: {str(e)}")

# =====================================================
# HEADER PROFESIONAL
# =====================================================

# Logo y branding
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
    # Branding en sidebar
    st.markdown("""
        <div style='text-align: center; padding: 1rem 0 2rem 0;'>
            <h2 style='color: white; margin-bottom: 0.5rem;'>⚙️ Configuración</h2>
            <p style='color: rgba(255,255,255,0.7); font-size: 0.9rem;'>Conecta tus servicios</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Estado de conexión visual
    connection_status = {
        "gcs": "gcs" in st.session_state and "bucket_name" in st.session_state,
        "openai": "openai" in st.session_state,
        "perplexity": "perplexity_key" in st.session_state
    }
    
    # Dashboard de estado
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
    
    # Configuración Google Cloud
    with st.expander("☁️ Google Cloud Storage", expanded=not connection_status["gcs"]):
        bucket_name = st.text_input(
            "Nombre del Bucket",
            value=st.session_state.get("bucket_name", ""),
            placeholder="mi-bucket-kaibot"
        )
        
        sa_json = st.text_area(
            "Service Account (JSON)",
            height=150,
            placeholder='{"type": "service_account", ...}'
        )
        
        if st.button("💾 Conectar GCS", use_container_width=True):
            try:
                st.session_state.gcs = get_gcs_client_from_json(sa_json)
                st.session_state.bucket_name = bucket_name
                st.success("✅ Google Cloud conectado")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    # Configuración OpenAI
    with st.expander("🤖 OpenAI", expanded=not connection_status["openai"]):
        openai_key = st.text_input(
            "API Key",
            type="password",
            placeholder="sk-..."
        )
        
        if st.button("💾 Conectar OpenAI", use_container_width=True):
            try:
                st.session_state.openai = OpenAI(api_key=openai_key)
                st.success("✅ OpenAI conectado")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    # Configuración Perplexity
    with st.expander("🔍 Perplexity", expanded=not connection_status["perplexity"]):
        perplexity_key = st.text_input(
            "API Key",
            type="password",
            placeholder="pplx-..."
        )
        
        col_save, col_test = st.columns(2)
        
        with col_save:
            if st.button("💾 Guardar", use_container_width=True):
                st.session_state.perplexity_key = perplexity_key
                st.success("✅ Guardado")
                st.rerun()
        
        with col_test:
            if st.button("🧪 Probar", use_container_width=True) and perplexity_key:
                try:
                    from openai import OpenAI
                    test_client = OpenAI(api_key=perplexity_key, base_url="https://api.perplexity.ai")
                    test_client.chat.completions.create(
                        model="sonar",
                        messages=[{"role": "user", "content": "test"}]
                    )
                    st.success("✅ Funciona")
                except Exception as e:
                    st.error(f"❌ {str(e)}")
    
    st.markdown("---")
    
    # Ayuda y soporte
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

# Verificar conexiones mínimas
if not all([connection_status["gcs"], connection_status["openai"], connection_status["perplexity"]]):
    st.warning("⚠️ **Configura todos los servicios** en el sidebar para comenzar")
    st.info("💡 Necesitas conectar Google Cloud Storage, OpenAI y Perplexity para usar el generador de contenidos")
    st.stop()

client = st.session_state.gcs
bucket_name = st.session_state.bucket_name

# =====================================================
# TABS PRINCIPALES
# =====================================================

tab1, tab2, tab3 = st.tabs(["🎯 Generar Contenido", "📁 Mis Archivos", "⚙️ Configuración Avanzada"])

# =====================================================
# TABS
# =====================================================

#tab1, tab2, tab3 = st.tabs(["📁 Gestión de Archivos", "🤖 Agentes IA", "🧪 Modo Demo"])

# =====================================================
# TAB 1 - FILE MANAGEMENT CON METADATOS
# =====================================================
# =====================================================
# TAB 1 - FILE MANAGEMENT CON METADATOS
# =====================================================

with tab1:
    folders, files = list_folders_and_files(client, bucket_name)
    
    st.subheader("📤 Subida de archivos")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        folder = st.selectbox("Carpeta destino", options=folders if folders else ["documentos/"])
        uploaded = st.file_uploader("Selecciona archivos", accept_multiple_files=True)
    with col2:
        new_folder = st.text_input("Nueva carpeta")
    
    target_folder = f"{new_folder.strip()}/" if new_folder else folder
    
    if st.button("⬆️ Subir archivos") and uploaded:
        progress = st.progress(0)
        for i, f in enumerate(uploaded):
            try:
                upload_file(client, bucket_name, f, target_folder)
                progress.progress((i + 1) / len(uploaded))
            except Exception as e:
                st.error(f"Error subiendo {f.name}: {str(e)}")
        st.success(f"✅ {len(uploaded)} archivo(s) subidos correctamente")
        st.rerun()
    
    st.markdown("---")
    st.subheader("🌐 Documentación adicional (Web / LinkedIn)")
    
    web = st.text_input("Página web")
    linkedin = st.text_input("LinkedIn")
    
    if st.button("💾 Guardar documentación adicional"):
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
    st.subheader("📁 Contenido del bucket con Metadatos")
    
    if files:
        # Crear DataFrame asegurando que todas las columnas existen
        df = pd.DataFrame(files)
        
        # Asegurar que todas las columnas necesarias existan (aunque estén vacías)
        required_columns = {
            "name": "",
            "tipo": "",
            "objetivo": "",
            "fuentes_fiables": False,
            "notas": "",
            "size": 0,
            "updated": None
        }
        
        # Añadir columnas faltantes con valores por defecto
        for col, default_value in required_columns.items():
            if col not in df.columns:
                df[col] = default_value
        
        # Reordenar columnas para mejor visualización
        column_order = ["name", "tipo", "objetivo", "fuentes_fiables", "notas", "size", "updated"]
        df = df[column_order]
        
        # Configurar formato de columnas
        column_config = {
            "name": st.column_config.TextColumn("📄 Archivo", width="medium"),
            "tipo": st.column_config.TextColumn("🏷️ Tipo", width="small"),
            "objetivo": st.column_config.TextColumn("🎯 Objetivo", width="medium"),
            "fuentes_fiables": st.column_config.CheckboxColumn("✅ Fuentes Fiables", width="small"),
            "notas": st.column_config.TextColumn("📝 Notas", width="large"),
            "size": st.column_config.NumberColumn("💾 Tamaño (bytes)", width="small"),
            "updated": st.column_config.DatetimeColumn("📅 Actualizado", width="small")
        }
        
        # Mostrar tabla editable
        st.dataframe(
            df,
            use_container_width=True,
            column_config=column_config,
            hide_index=True
        )
        
        # PREVISUALIZACIÓN DE ARCHIVOS
        st.markdown("---")
        st.subheader("👁️ Previsualizar Archivo")
        
        col_preview, col_download = st.columns([3, 1])
        
        with col_preview:
            preview_file_select = st.selectbox(
                "Selecciona archivo para previsualizar",
                options=df["name"].tolist(),
                key="preview_file_select"
            )
        
        with col_download:
            st.markdown("")  # Espaciado
            st.markdown("")  # Espaciado
            if st.button("🔍 Previsualizar", type="primary", use_container_width=True):
                st.session_state.show_preview = preview_file_select
        
        # Mostrar previsualización
        if "show_preview" in st.session_state and st.session_state.show_preview:
            with st.expander(f"📄 {st.session_state.show_preview}", expanded=True):
                # Previsualización inline
                try:
                    bucket = client.bucket(bucket_name)
                    blob = bucket.blob(st.session_state.show_preview)
                    blob.reload()
                    
                    file_size = blob.size if blob.size is not None else 0
                    file_size_kb = file_size / 1024 if file_size > 0 else 0
                    file_ext = st.session_state.show_preview.split('.')[-1].lower()
                    
                    # JSON
                    if file_ext == 'json':
                        content = blob.download_as_text()
                        data = json.loads(content)
                        st.json(data)
                    
                    # Texto
                    elif file_ext in ['txt', 'md', 'csv', 'log']:
                        content = blob.download_as_text()
                        st.code(content, language='text')
                    
                    # Python
                    elif file_ext == 'py':
                        content = blob.download_as_text()
                        st.code(content, language='python')
                    
                    # JavaScript/TypeScript
                    elif file_ext in ['js', 'jsx', 'ts', 'tsx']:
                        content = blob.download_as_text()
                        st.code(content, language='javascript')
                    
                    # HTML/CSS
                    elif file_ext in ['html', 'css']:
                        content = blob.download_as_text()
                        st.code(content, language='html')
                    
                    # Imágenes
                    elif file_ext in ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp']:
                        image_bytes = blob.download_as_bytes()
                        st.image(image_bytes, caption=st.session_state.show_preview, use_container_width=True)
                    
                    # PDFs
                    elif file_ext == 'pdf':
                        st.info(f"📄 Archivo PDF")
                        st.write(f"**Tamaño:** {file_size_kb:.2f} KB")
                        st.warning("💡 Descarga el archivo para visualizarlo completamente")
                        pdf_bytes = blob.download_as_bytes()
                        st.download_button(
                            "⬇️ Descargar PDF",
                            pdf_bytes,
                            file_name=st.session_state.show_preview.split('/')[-1],
                            mime="application/pdf"
                        )
                    
                    # Office
                    elif file_ext in ['docx', 'xlsx', 'pptx', 'doc', 'xls', 'ppt']:
                        st.info(f"📎 Archivo de Office: {file_ext.upper()}")
                        st.write(f"**Tamaño:** {file_size_kb:.2f} KB")
                        st.warning("💡 Descarga el archivo para visualizarlo")
                        file_bytes = blob.download_as_bytes()
                        mime_types = {
                            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                            'doc': 'application/msword',
                            'xls': 'application/vnd.ms-excel',
                            'ppt': 'application/vnd.ms-powerpoint'
                        }
                        st.download_button(
                            f"⬇️ Descargar {file_ext.upper()}",
                            file_bytes,
                            file_name=st.session_state.show_preview.split('/')[-1],
                            mime=mime_types.get(file_ext, 'application/octet-stream')
                        )
                    
                    else:
                        st.warning(f"⚠️ Tipo de archivo no soportado para previsualización: .{file_ext}")
                        st.info("📊 Información del archivo:")
                        st.write(f"**Nombre:** {st.session_state.show_preview}")
                        st.write(f"**Tamaño:** {file_size_kb:.2f} KB")
                
                except Exception as e:
                    st.error(f"❌ Error al previsualizar: {str(e)}")
        
        # Editor de metadatos
        st.markdown("---")
        st.subheader("✏️ Editar Metadatos de Archivo")
        
        selected_file = st.selectbox(
            "Selecciona archivo para editar metadatos",
            options=df["name"].tolist(),
            key="metadata_editor_select"
        )
        
        if selected_file:
            # Obtener metadatos actuales
            current_metadata = get_file_metadata(client, bucket_name, selected_file)
            
            col_meta1, col_meta2 = st.columns(2)
            
            with col_meta1:
                tipo = st.text_input(
                    "🏷️ Tipo de contenido",
                    value=current_metadata["tipo"],
                    placeholder="Ej: Análisis IA, Documento técnico, Informe..."
                )
                
                objetivo_options = ["", "Publicación Científica", "Social Media", "Blog Post", "Informe Interno", 
                                   "Marketing B2B", "Presentación", "White Paper", "Caso de Estudio"]
                
                # Determinar índice actual
                current_objetivo = current_metadata["objetivo"]
                if current_objetivo in objetivo_options:
                    objetivo_index = objetivo_options.index(current_objetivo)
                else:
                    objetivo_index = 0
                
                objetivo = st.selectbox(
                    "🎯 Objetivo del contenido",
                    objetivo_options,
                    index=objetivo_index
                )
            
            with col_meta2:
                fuentes_fiables = st.checkbox(
                    "✅ Fuentes fiables verificadas",
                    value=current_metadata["fuentes_fiables"]
                )
                
                notas = st.text_area(
                    "📝 Notas importantes",
                    value=current_metadata["notas"],
                    height=100,
                    placeholder="Añade notas, contexto o información relevante sobre este archivo..."
                )
            
            if st.button("💾 Guardar Metadatos", type="primary"):
                new_metadata = {
                    "tipo": tipo,
                    "objetivo": objetivo,
                    "fuentes_fiables": fuentes_fiables,
                    "notas": notas
                }
                
                if update_file_metadata(client, bucket_name, selected_file, new_metadata):
                    st.success(f"✅ Metadatos actualizados para {selected_file}")
                    st.rerun()
        
        # Eliminar archivos
        st.markdown("---")
        to_delete = st.multiselect("🗑️ Selecciona archivos a eliminar", options=df["name"].tolist())
        
        if st.button("🗑️ Eliminar seleccionados") and to_delete:
            bucket = client.bucket(bucket_name)
            for name in to_delete:
                try:
                    bucket.blob(name).delete()
                except Exception as e:
                    st.error(f"Error eliminando {name}: {str(e)}")
            st.success(f"✅ {len(to_delete)} archivo(s) eliminados")
            st.rerun()
    else:
        st.info("ℹ️ El bucket no contiene archivos")
        
# =====================================================
# TAB 2 - AGENTE DUAL: OPENAI → PERPLEXITY (OPTIMIZADO)
# =====================================================

with tab2:
    st.header("🤖 Agente Dual: OpenAI + Perplexity")
    st.caption("Paso 1: OpenAI analiza documentos (opcional) → Paso 2: Perplexity valida/enriquece")
    
    # Verificar APIs
    apis_configured = True
    
    if "openai" not in st.session_state:
        st.warning("⚠️ Configura OpenAI en el sidebar")
        apis_configured = False
    
    if "perplexity_key" not in st.session_state:
        with st.expander("⚙️ Configurar Perplexity API", expanded=not apis_configured):
            perplexity_key = st.text_input("Perplexity API Key", type="password", key="pplx_input")
            
            col_save, col_test = st.columns(2)
            with col_save:
                if st.button("💾 Guardar API Key", use_container_width=True):
                    if perplexity_key:
                        st.session_state.perplexity_key = perplexity_key
                        st.success("✅ API Key guardada")
                        st.rerun()
                    else:
                        st.error("❌ Introduce una API Key válida")
            
            with col_test:
                if st.button("🔍 Probar Conexión", use_container_width=True) and perplexity_key:
                    try:
                        from openai import OpenAI
                        
                        test_client = OpenAI(
                            api_key=perplexity_key,
                            base_url="https://api.perplexity.ai"
                        )
                        
                        test_response = test_client.chat.completions.create(
                            model="sonar",
                            messages=[{"role": "user", "content": "Responde solo: OK"}]
                        )
                        
                        st.success(f"✅ Conexión exitosa!")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
        
        apis_configured = False
    
    if not apis_configured:
        st.stop()
    
    # --- PASO 1: CONFIGURACIÓN ---
    st.subheader("📝 Paso 1: Configuración")
    
    with st.expander("⚙️ Configuración de Prompts", expanded=False):
        st.markdown("### 📝 Gestión de Prompts")
        
        # Cargar prompts guardados (opcional)
        folders, files = list_folders_and_files(client, bucket_name)
        prompt_files = [f["name"] for f in files if f["name"].startswith(BUCKET_FOLDERS["prompts"])]
        
        if prompt_files:
            col_load, col_new = st.columns([3, 1])
            
            with col_load:
                load_prompt = st.selectbox(
                    "📂 Cargar prompt guardado",
                    ["-- Usar prompts por defecto --"] + prompt_files,
                    key="load_prompt_select"
                )
            
            with col_new:
                if st.button("🔄 Cargar", use_container_width=True):
                    if load_prompt != "-- Usar prompts por defecto --":
                        try:
                            loaded = load_prompt_from_bucket(client, bucket_name, load_prompt)
                            st.session_state.loaded_openai_prompt = loaded["prompts"]["openai"]
                            st.session_state.loaded_perplexity_prompt = loaded["prompts"]["perplexity"]
                            st.success(f"✅ Prompt cargado: {loaded.get('nombre', 'Sin nombre')}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al cargar: {str(e)}")
        
        st.markdown("---")
        
        # System prompt para OpenAI (MEJORADO Y ROBUSTO)
        default_openai_prompt = """Eres un analista estratégico experto en generación de contenidos corporativos B2B con más de 15 años de experiencia.

**TU MISIÓN:**
Analizar información y generar insights accionables de alto valor para directivos y responsables de marketing industrial.

**CONTEXTO DE TRABAJO:**
- Audiencia: Directores de marketing, CEOs de empresas B2B industriales
- Sector: Marketing digital B2B, tecnología industrial, LifeSciences, MedTech
- Objetivo: Generar contenido que impulse generación de leads y posicionamiento de marca

**INSTRUCCIONES DE ANÁLISIS:**
1. Si se proporcionan documentos, PRIORIZA la información contenida en ellos
2. Si NO hay documentos, utiliza tu conocimiento actualizado sobre tendencias B2B
3. Enfócate en RESULTADOS MEDIBLES y ROI
4. Identifica OPORTUNIDADES CONCRETAS, no generalidades
5. Proporciona DATOS Y CIFRAS cuando sea posible

**ESTRUCTURA DE RESPUESTA (JSON OBLIGATORIO):**
{
  "summary": "Resumen ejecutivo de 2-3 líneas enfocado en el valor estratégico y oportunidades identificadas",
  "key_points": [
    "Punto 1: Insight específico con dato cuantificable o tendencia clara",
    "Punto 2: Oportunidad de mercado o ventaja competitiva identificada",
    "Punto 3: Riesgo o barrera que requiere atención estratégica"
  ],
  "recommended_actions": [
    "Acción 1: Específica, medible y con plazo sugerido (ej: implementar en Q2 2026)",
    "Acción 2: Con ROI estimado o KPI de éxito asociado"
  ],
  "topics_to_validate": [
    "Dato o tendencia que requiere validación con fuentes externas actuales",
    "Regulación o cambio de mercado que debe verificarse online"
  ]
}

**ESTILO DE COMUNICACIÓN:**
- Directo y orientado a la acción
- Lenguaje profesional B2B, evita jerga innecesaria
- Enfoque en impacto de negocio y generación de oportunidades
- Tono: Consultor estratégico experimentado

**IMPORTANTE:**
- Responde EXCLUSIVAMENTE en formato JSON válido
- NO añadas texto antes o después del JSON
- Si hay documentos: basar el 80% del análisis en ellos
- Si NO hay documentos: usar conocimiento general actualizado de marketing B2B"""

        openai_prompt = st.text_area(
            "System Prompt - OpenAI (Análisis Estratégico)",
            value=st.session_state.get("loaded_openai_prompt", default_openai_prompt),
            height=250,
            key="openai_system",
            help="Este prompt define cómo OpenAI analiza y estructura la información"
        )
        
        st.markdown("---")
        
        # System prompt para Perplexity (MEJORADO Y ROBUSTO)
        default_perplexity_prompt = """Eres un validador experto en fact-checking y enriquecimiento de contenido estratégico B2B con acceso a información online en tiempo real.

**TU MISIÓN:**
Validar, contrastar y enriquecer análisis estratégicos utilizando ÚNICAMENTE fuentes confiables y actuales de internet.

**FUENTES PRIORITARIAS (en orden de preferencia):**
1. **Fuentes primarias oficiales:**
   - Sitios web corporativos de empresas mencionadas
   - Informes oficiales de consultoras (Gartner, McKinsey, Forrester, BCG)
   - Publicaciones de organismos gubernamentales y reguladores
   
2. **Medios especializados B2B:**
   - Marketing directo / Marketing B2B
   - TechCrunch, VentureBeat (para tecnología)
   - MedTech Dive, FierceBiotech (para LifeSciences)
   - Industry-specific journals

3. **Fuentes de datos verificables:**
   - Statista, eMarketer
   - Google Trends, SimilarWeb
   - Estudios de mercado publicados

**FUENTES A EVITAR:**
- Blogs personales sin autoridad demostrable
- Foros y sitios de opinión (Reddit, Quora)
- Contenido generado por IA sin verificación
- Fuentes sin fecha de publicación o anteriores a 2024

**PROCESO DE VALIDACIÓN:**
1. **Contrastar cada key_point del análisis:**
   - Buscar 2-3 fuentes independientes que confirmen o refuten
   - Si hay discrepancia, indicarlo en validation_notes
   
2. **Enriquecer con datos actuales:**
   - Añadir cifras, porcentajes, fechas concretas
   - Incluir tendencias de los últimos 6-12 meses
   - Mencionar regulaciones o cambios recientes relevantes

3. **Validar recommended_actions:**
   - Verificar viabilidad con casos de éxito recientes
   - Contrastar con mejores prácticas actuales del sector

**NIVEL DE CONFIANZA:**
- **Alto:** 3+ fuentes fiables coinciden, datos recientes (últimos 6 meses)
- **Medio:** 2 fuentes fiables, o datos de hace 6-12 meses
- **Bajo:** 1 fuente o datos mayores de 12 meses

**ESTRUCTURA DE RESPUESTA (JSON OBLIGATORIO):**
{
  "summary": "Resumen validado con datos actualizados y fuentes verificadas",
  "key_points": [
    "Punto validado 1 con dato específico de fuente actual (incluir fecha si es relevante)",
    "Punto validado 2 con contexto de mercado actualizado",
    "Punto validado 3 con comparativa o benchmark reciente"
  ],
  "recommended_actions": [
    "Acción validada 1 con caso de éxito o best practice documentado",
    "Acción validada 2 con ROI o métrica de referencia del sector"
  ],
  "validation_notes": "Resumen de qué se validó, qué discrepancias se encontraron (si las hay), y qué información se enriqueció. Mencionar si algún dato del análisis original NO pudo ser verificado.",
  "sources": [
    "https://url-completa-fuente-1.com (Título del artículo o recurso - Fecha)",
    "https://url-completa-fuente-2.com (Título del artículo o recurso - Fecha)",
    "https://url-completa-fuente-3.com (Título del artículo o recurso - Fecha)"
  ],
  "confidence_level": "alto"
}

**FORMATO DE FUENTES:**
Cada URL debe incluir:
- URL completa y funcional
- Título descriptivo del recurso
- Fecha de publicación (si está disponible)
Ejemplo: "https://www.gartner.com/report-2026 (Top Marketing Trends 2026 - Enero 2026)"

**IMPORTANTE:**
- Responde EXCLUSIVAMENTE en formato JSON válido
- NO añadas texto markdown, preambles o explicaciones fuera del JSON
- SIEMPRE incluir mínimo 3 fuentes verificables (URLs completas)
- Si no puedes validar algo, indícalo explícitamente en validation_notes
- Prioriza fuentes de 2025-2026 sobre anteriores"""

        perplexity_prompt = st.text_area(
            "System Prompt - Perplexity (Validación con Fuentes Online)",
            value=st.session_state.get("loaded_perplexity_prompt", default_perplexity_prompt),
            height=250,
            key="perplexity_system",
            help="Este prompt define cómo Perplexity valida con fuentes online"
        )
        
        # --- GUARDAR PROMPTS ---
        st.markdown("---")
        st.markdown("### 💾 Guardar Configuración de Prompts")
        
        col_save1, col_save2 = st.columns(2)
        
        with col_save1:
            prompt_nombre = st.text_input(
                "Nombre del prompt",
                placeholder="Ej: Marketing B2B Industrial",
                key="prompt_name"
            )
            
            prompt_uso = st.selectbox(
                "Uso principal",
                ["General", "Marketing B2B", "LifeSciences", "Tecnología Industrial", 
                 "Análisis Competitivo", "Contenido Científico", "Social Media"],
                key="prompt_usage"
            )
        
        with col_save2:
            prompt_descripcion = st.text_area(
                "Descripción",
                placeholder="Describe para qué casos usar este prompt...",
                height=100,
                key="prompt_description"
            )
        
        if st.button("💾 Guardar Prompts en Bucket", type="primary", use_container_width=True):
            if not prompt_nombre:
                st.error("❌ Debes dar un nombre al prompt")
            else:
                try:
                    prompt_data = {
                        "openai_prompt": openai_prompt,
                        "perplexity_prompt": perplexity_prompt
                    }
                    
                    metadata = {
                        "nombre": prompt_nombre,
                        "descripcion": prompt_descripcion,
                        "uso": prompt_uso
                    }
                    
                    filename = save_prompt_to_bucket(client, bucket_name, prompt_data, metadata)
                    
                    st.success(f"✅ Prompts guardados: {filename}")
                    st.info("📁 Podrás verlos y editarlos en el TAB 'Gestión de Archivos'")
                    
                    # Limpiar estados de carga
                    if "loaded_openai_prompt" in st.session_state:
                        del st.session_state.loaded_openai_prompt
                    if "loaded_perplexity_prompt" in st.session_state:
                        del st.session_state.loaded_perplexity_prompt
                    
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error al guardar: {str(e)}")
    
    # Selección de archivos (AHORA OPCIONAL) - Filtrar prompts
    folders, files = list_folders_and_files(client, bucket_name)
    file_names = [f["name"] for f in files if not f["name"].startswith(BUCKET_FOLDERS["prompts"])]
    
    st.markdown("**📄 Archivos de Contexto (Opcional)**")
    st.caption("Puedes seleccionar archivos para análisis o dejar vacío para consultas generales")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        selected_files = st.multiselect(
            "Selecciona archivos (opcional)",
            options=file_names,
            help="Si no seleccionas archivos, OpenAI responderá basándose en conocimiento general"
        )
    
    with col2:
        max_chars = st.number_input(
            "Límite caracteres",
            min_value=2000,
            max_value=50000,
            value=15000,
            step=1000,
            disabled=len(selected_files) == 0
        )
    
    # Indicador de modo
    if selected_files:
        st.info(f"📁 Modo: Análisis con {len(selected_files)} archivo(s)")
    else:
        st.info("💭 Modo: Consulta general sin documentos")
    
    # Consulta del usuario
    st.markdown("**Consulta**")
    
    query_mode = st.radio(
        "Tipo de consulta",
        ["Plantilla", "Personalizada"],
        horizontal=True
    )
    
    if query_mode == "Personalizada":
        user_query = st.text_area(
            "Escribe tu consulta",
            placeholder="Ejemplo: Analiza las tendencias de marketing B2B industrial para 2026 y genera 3 recomendaciones estratégicas priorizadas",
            height=120,
            key="custom_query"
        )
    else:
        # Plantillas adaptadas para funcionar con y sin archivos
        templates = {
            "Análisis Estratégico Completo": "Realiza un análisis estratégico completo identificando tendencias clave, oportunidades y riesgos en marketing B2B industrial. Proporciona recomendaciones accionables con ROI estimado y plazos de implementación.",
            "Resumen Ejecutivo": "Genera un resumen ejecutivo profesional destacando los 3 puntos más relevantes para la toma de decisiones en generación de leads B2B. Incluye datos cuantificables y fuentes verificables.",
            "Análisis DAFO": "Realiza un análisis DAFO (Debilidades, Amenazas, Fortalezas, Oportunidades) enfocado en estrategia digital B2B. Valida cada punto con tendencias actuales del sector industrial.",
            "Plan de Acción Priorizado": "Identifica los 5 puntos más importantes para mejorar la generación de leads B2B y crea un plan de acción detallado con KPIs, plazos y recursos necesarios.",
            "Benchmark Competitivo": "Realiza un análisis competitivo del sector comparando estrategias de marketing digital B2B. Incluye datos de inversión publicitaria, canales utilizados y resultados obtenidos por competidores.",
            "Contenido para LinkedIn": "Genera ideas de contenido para LinkedIn enfocadas en thought leadership B2B industrial. Incluye temas, formatos y calendario sugerido para los próximos 3 meses.",
            "Estrategia Ferias B2B": "Analiza las mejores prácticas para participación en ferias industriales B2B combinando estrategia digital pre-evento, durante y post-evento para maximizar ROI.",
            "Tendencias LifeSciences 2026": "Analiza las últimas tendencias en marketing digital para empresas de LifeSciences y MedTech. Identifica oportunidades de posicionamiento y generación de leads especializados."
        }
        
        selected_template = st.selectbox(
            "Selecciona una plantilla",
            list(templates.keys()),
            key="template_select"
        )
        
        user_query = st.text_area(
            "Consulta (editable)",
            value=templates[selected_template],
            height=120,
            key="template_query"
        )
    
    # --- PASO 2: EJECUTAR AGENTE OPENAI ---
    st.markdown("---")
    st.subheader("🔵 Paso 2: Análisis con OpenAI")
    
    # Selector de modelo de OpenAI
    col_model_openai, col_exec1, col_clear1 = st.columns([2, 2, 1])
    
    with col_model_openai:
        openai_models = {
            "GPT-4o Mini (Recomendado - Rápido)": "gpt-4o-mini",
            "GPT-4o (Avanzado)": "gpt-4o",
            "GPT-4 Turbo": "gpt-4-turbo-preview",
            "GPT-3.5 Turbo": "gpt-3.5-turbo"
        }
        
        selected_openai_model_name = st.selectbox(
            "Modelo OpenAI",
            list(openai_models.keys()),
            index=0,
            help="GPT-4o Mini es ideal para análisis B2B con excelente relación calidad-precio"
        )
        
        openai_model = openai_models[selected_openai_model_name]
    
    with col_exec1:
        execute_openai = st.button(
            "▶️ Analizar con OpenAI",
            type="primary",
            use_container_width=True
        )
    
    with col_clear1:
        if st.button("🗑️ Limpiar", use_container_width=True):
            keys_to_delete = ["openai_response", "perplexity_response", "edited_response"]
            for key in keys_to_delete:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    if execute_openai:
        if not user_query.strip():
            st.error("❌ La consulta no puede estar vacía")
            st.stop()
        
        with st.spinner(f"🔄 OpenAI ({openai_model}) analizando..."):
            try:
                # Preparar mensaje base
                user_message = f"CONSULTA DEL USUARIO:\n{user_query}"
                
                # Cargar contexto solo si hay archivos seleccionados
                context = ""
                if selected_files:
                    context = load_selected_context(client, bucket_name, selected_files, max_chars)
                    user_message += f"\n\n---\n\nDOCUMENTOS DE CONTEXTO:\n{context}"
                else:
                    user_message += "\n\n---\n\nNOTA: No se proporcionaron documentos de contexto. Responde basándote en conocimiento general y datos actuales."
                
                # Llamar a OpenAI con el modelo seleccionado
                response = st.session_state.openai.chat.completions.create(
                    model=openai_model,
                    messages=[
                        {"role": "system", "content": openai_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    response_format={"type": "json_object"}
                )
                
                response_text = response.choices[0].message.content
                response_json = json.loads(response_text)
                
                # Añadir metadata
                response_json["metadata"] = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "agent": "openai",
                    "model": openai_model,
                    "query": user_query,
                    "context_files": selected_files if selected_files else [],
                    "context_chars": len(context) if context else 0,
                    "mode": "with_context" if selected_files else "general_query"
                }
                
                st.session_state.openai_response = response_json
                st.success(f"✅ Análisis completado por OpenAI ({openai_model})")
                st.rerun()
                
            except json.JSONDecodeError as je:
                st.error(f"❌ Error al parsear JSON de OpenAI: {str(je)}")
                with st.expander("Ver respuesta raw"):
                    st.code(response_text)
            except Exception as e:
                st.error(f"❌ Error en OpenAI: {str(e)}")
    
    # Mostrar respuesta de OpenAI
    if "openai_response" in st.session_state:
        st.markdown("---")
        with st.expander("📊 Resultado de OpenAI", expanded=True):
            openai_data = st.session_state.openai_response
            
            # Mostrar modo de operación
            mode = openai_data.get("metadata", {}).get("mode", "unknown")
            model_used = openai_data.get("metadata", {}).get("model", "N/A")
            
            if mode == "with_context":
                st.success(f"📁 Análisis con {len(openai_data.get('metadata', {}).get('context_files', []))} documento(s) | Modelo: {model_used}")
            else:
                st.info(f"💭 Análisis general sin documentos | Modelo: {model_used}")
            
            st.markdown("**📝 Resumen:**")
            st.info(openai_data.get("summary", "N/A"))
            
            st.markdown("**🎯 Puntos Clave:**")
            for i, point in enumerate(openai_data.get("key_points", []), 1):
                st.markdown(f"{i}. {point}")
            
            st.markdown("**✅ Acciones Recomendadas:**")
            for i, action in enumerate(openai_data.get("recommended_actions", []), 1):
                st.markdown(f"{i}. {action}")
            
            if "topics_to_validate" in openai_data and openai_data["topics_to_validate"]:
                st.markdown("**🔍 Temas para Validar con Perplexity:**")
                for topic in openai_data["topics_to_validate"]:
                    st.markdown(f"- {topic}")
            
            # Mostrar JSON
            with st.expander("🔧 Ver JSON completo de OpenAI"):
                st.json(openai_data)
        
        # --- PASO 3: VALIDAR CON PERPLEXITY ---
        st.markdown("---")
        st.subheader("🟣 Paso 3: Validación con Perplexity")
        
        st.info("💡 Perplexity validará el análisis de OpenAI con fuentes online actuales y verificables")
        
        # Selector de modelo de Perplexity
        col_model_perplexity, col_exec_perplexity = st.columns([2, 2])
        
        with col_model_perplexity:
            perplexity_models = {
                "Sonar (Recomendado - Online)": "sonar",
                "Sonar Pro (Avanzado - Online)": "sonar-pro",
                "Llama 3.1 8B": "llama-3.1-8b-instruct",
                "Llama 3.1 70B": "llama-3.1-70b-instruct"
            }
            
            selected_model_name = st.selectbox(
                "Modelo de Perplexity",
                list(perplexity_models.keys()),
                index=0,
                help="Los modelos 'Sonar' tienen acceso a búsqueda web en tiempo real"
            )
            
            perplexity_model = perplexity_models[selected_model_name]
        
        with col_exec_perplexity:
            st.markdown("")  # Espaciado
            st.markdown("")  # Espaciado
            execute_perplexity = st.button("▶️ Validar con Perplexity", type="primary", use_container_width=True)
        
        if execute_perplexity:
            with st.spinner(f"🔄 Perplexity ({perplexity_model}) validando y enriqueciendo..."):
                try:
                    from openai import OpenAI
                    
                    perplexity_client = OpenAI(
                        api_key=st.session_state.perplexity_key,
                        base_url="https://api.perplexity.ai"
                    )
                    
                    # Preparar prompt para Perplexity
                    validation_prompt = f"""ANÁLISIS PREVIO A VALIDAR (generado por OpenAI):

{json.dumps(st.session_state.openai_response, indent=2, ensure_ascii=False)}

---

CONSULTA ORIGINAL DEL USUARIO:
{user_query}

---

INSTRUCCIONES:
1. Valida cada punto del análisis con fuentes actuales online
2. Enriquece la información con datos relevantes y recientes
3. Proporciona URLs de fuentes verificables con título y fecha
4. Indica el nivel de confianza de la validación

Responde SOLO con un JSON válido, sin texto adicional."""
                    
                    # Llamar a Perplexity
                    response = perplexity_client.chat.completions.create(
                        model=perplexity_model,
                        messages=[
                            {"role": "system", "content": perplexity_prompt},
                            {"role": "user", "content": validation_prompt}
                        ]
                    )
                    
                    response_text = response.choices[0].message.content
                    
                    # Limpiar markdown si existe
                    clean_text = response_text.strip()
                    if "```json" in clean_text:
                        clean_text = clean_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in clean_text:
                        clean_text = clean_text.split("```")[1].split("```")[0].strip()
                    
                    # Intentar parsear JSON
                    try:
                        validated_json = json.loads(clean_text)
                    except json.JSONDecodeError:
                        # Intentar extraer JSON con regex
                        json_match = re.search(r'\{.*\}', clean_text, re.DOTALL)
                        if json_match:
                            validated_json = json.loads(json_match.group())
                        else:
                            raise json.JSONDecodeError("No se encontró JSON válido en la respuesta", clean_text, 0)
                    
                    # Añadir metadata
                    validated_json["metadata"] = {
                        "timestamp": datetime.utcnow().isoformat(),
                        "agent": "perplexity",
                        "model": perplexity_model,
                        "original_query": user_query,
                        "openai_analysis_timestamp": openai_data.get("metadata", {}).get("timestamp", "N/A"),
                        "openai_model": openai_data.get("metadata", {}).get("model", "N/A"),
                        "analysis_mode": openai_data.get("metadata", {}).get("mode", "unknown")
                    }
                    
                    st.session_state.perplexity_response = validated_json
                    st.success(f"✅ Validación completada por Perplexity ({perplexity_model})")
                    st.rerun()
                    
                except json.JSONDecodeError as je:
                    st.error("❌ La respuesta de Perplexity no es un JSON válido")
                    with st.expander("📄 Ver respuesta raw de Perplexity"):
                        st.code(response_text)
                    st.warning("💡 Intenta con otro modelo o ajusta el system prompt")
                except Exception as e:
                    st.error(f"❌ Error en Perplexity: {str(e)}")
                    
                    # Información de debug
                    with st.expander("🔍 Información de debug"):
                        st.write(f"**Modelo usado:** {perplexity_model}")
                        st.write(f"**API Key configurada:** {'Sí' if 'perplexity_key' in st.session_state else 'No'}")
                        st.write(f"**Error completo:** {str(e)}")
    
    # --- PASO 4: MOSTRAR Y EDITAR RESULTADO FINAL ---
    if "perplexity_response" in st.session_state:
        st.markdown("---")
        st.subheader("📊 Paso 4: Resultado Final Validado")
        
        # Vista previa estructurada
        with st.expander("👁️ Vista Previa Detallada", expanded=True):
            final_data = st.session_state.perplexity_response
            
            # Mostrar modelos usados
            openai_model_used = final_data.get("metadata", {}).get("openai_model", "N/A")
            perplexity_model_used = final_data.get("metadata", {}).get("model", "N/A")
            st.caption(f"🤖 OpenAI: {openai_model_used} | 🔍 Perplexity: {perplexity_model_used}")
            
            st.markdown("**📝 Resumen Validado:**")
            st.success(final_data.get("summary", "N/A"))
            
            st.markdown("**🎯 Puntos Clave Validados:**")
            for i, point in enumerate(final_data.get("key_points", []), 1):
                st.markdown(f"{i}. {point}")
            
            st.markdown("**✅ Acciones Recomendadas Validadas:**")
            for i, action in enumerate(final_data.get("recommended_actions", []), 1):
                st.markdown(f"{i}. {action}")
            
            if "validation_notes" in final_data and final_data["validation_notes"]:
                st.markdown("**📋 Notas de Validación:**")
                st.info(final_data["validation_notes"])
            
            if "confidence_level" in final_data:
                confidence = final_data["confidence_level"].lower()
                if confidence == "alto":
                    emoji = "🟢"
                elif confidence == "medio":
                    emoji = "🟡"
                else:
                    emoji = "🔴"
                
                st.markdown(f"**{emoji} Nivel de Confianza:** {confidence.upper()}")
            
            if "sources" in final_data and final_data["sources"]:
                st.markdown("**🔗 Fuentes Verificables:**")
                for i, source in enumerate(final_data["sources"], 1):
                    if source.startswith("http"):
                        st.markdown(f"{i}. [{source}]({source})")
                    else:
                        st.markdown(f"{i}. {source}")
        
        # Comparación OpenAI vs Perplexity
        with st.expander("🔄 Comparar: OpenAI vs Perplexity"):
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.markdown("**🔵 OpenAI (Análisis Original)**")
                st.json(st.session_state.openai_response)
            
            with col_b:
                st.markdown("**🟣 Perplexity (Validado + Enriquecido)**")
                st.json(st.session_state.perplexity_response)
        
        # Editor JSON
        st.markdown("---")
        st.markdown("**✏️ Editor JSON Final**")
        st.caption("Puedes editar la respuesta validada antes de guardarla")
        
        if "edited_response" not in st.session_state:
            st.session_state.edited_response = json.dumps(
                st.session_state.perplexity_response,
                indent=2,
                ensure_ascii=False
            )
        
        edited_json = st.text_area(
            "JSON editable",
            value=st.session_state.edited_response,
            height=450,
            key="json_editor",
            help="Edita el JSON si necesitas hacer ajustes antes de guardar"
        )
        
        # Actualizar el estado cuando se edita
        if edited_json != st.session_state.edited_response:
            st.session_state.edited_response = edited_json
        
        # Validar JSON editado
        try:
            edited_data = json.loads(edited_json)
            st.success("✅ JSON válido")
            json_is_valid = True
        except json.JSONDecodeError as e:
            st.error(f"❌ JSON inválido: {str(e)}")
            json_is_valid = False
        
        # --- PASO 5: GUARDAR CON METADATOS ---
        st.markdown("---")
        st.subheader("💾 Paso 5: Configurar y Guardar")
        
        # Formulario de metadatos
        with st.expander("📋 Metadatos del contenido", expanded=True):
            col_m1, col_m2 = st.columns(2)
            
            with col_m1:
                content_tipo = st.text_input(
                    "🏷️ Tipo",
                    value="Análisis IA Validado",
                    placeholder="Análisis IA, Informe..."
                )
                
                content_objetivo = st.selectbox(
                    "🎯 Objetivo",
                    ["Publicación Científica", "Social Media", "Blog Post", "Informe Interno", 
                     "Marketing B2B", "Presentación", "White Paper", "Caso de Estudio"],
                    index=4  # Marketing B2B por defecto
                )
            
            with col_m2:
                # Determinar si hay fuentes fiables
                has_sources = bool(final_data.get("sources", []))
                content_fuentes = st.checkbox(
                    "✅ Fuentes fiables verificadas",
                    value=has_sources,
                    help="Perplexity ha validado con fuentes online" if has_sources else "Sin validación de fuentes"
                )
                
                content_notas = st.text_area(
                    "📝 Notas",
                    value=f"Consulta: {user_query[:100]}..." if len(user_query) > 100 else f"Consulta: {user_query}",
                    height=100
                )
        
        # Preview del nombre de archivo
        if json_is_valid:
            preview_filename = generate_smart_filename(edited_data)
            st.info(f"📝 Nombre de archivo: `{preview_filename}`")
        
        col_save, col_download, col_both = st.columns(3)
        
        with col_save:
            if st.button(
                "💾 Guardar en GCS",
                use_container_width=True,
                disabled=not json_is_valid,
                type="primary"
            ):
                try:
                    # Generar nombre inteligente basado en el resumen
                    filename = generate_smart_filename(edited_data)
                    
                    # Preparar metadatos
                    analysis_metadata = {
                        "tipo": content_tipo,
                        "objetivo": content_objetivo,
                        "fuentes_fiables": content_fuentes,
                        "notas": content_notas
                    }
                    
                    # Guardar con metadatos
                    save_analysis_with_metadata(
                        client,
                        bucket_name,
                        BUCKET_FOLDERS["validados"],
                        filename,
                        edited_data,
                        analysis_metadata
                    )
                    
                    st.success(f"✅ Guardado correctamente con metadatos")
                    st.info(f"📁 Ruta: {BUCKET_FOLDERS['validados']}{filename}")
                    st.balloons()
                    
                    # Botón para nueva consulta
                    if st.button("🔄 Nueva consulta"):
                        for key in ["openai_response", "perplexity_response", "edited_response"]:
                            if key in st.session_state:
                                del st.session_state[key]
                        st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error al guardar en GCS: {str(e)}")
        
        with col_download:
            download_filename = generate_smart_filename(edited_data) if json_is_valid else f"validado_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            
            st.download_button(
                "⬇️ Descargar JSON",
                edited_json,
                file_name=download_filename,
                mime="application/json",
                use_container_width=True,
                disabled=not json_is_valid
            )
        
        with col_both:
            if st.button(
                "💾⬇️ Guardar y Descargar",
                use_container_width=True,
                disabled=not json_is_valid
            ):
                try:
                    # Generar nombre inteligente
                    filename = generate_smart_filename(edited_data)
                    
                    # Preparar metadatos
                    analysis_metadata = {
                        "tipo": content_tipo,
                        "objetivo": content_objetivo,
                        "fuentes_fiables": content_fuentes,
                        "notas": content_notas
                    }
                    
                    # Guardar en GCS con metadatos
                    save_analysis_with_metadata(
                        client,
                        bucket_name,
                        BUCKET_FOLDERS["validados"],
                        filename,
                        edited_data,
                        analysis_metadata
                    )
                    
                    st.success(f"✅ Guardado en GCS con metadatos")
                    st.info(f"📁 {BUCKET_FOLDERS['validados']}{filename}")
                    
                    # Trigger de descarga
                    st.download_button(
                        "⬇️ Haz clic aquí para descargar",
                        edited_json,
                        file_name=filename,
                        mime="application/json",
                        use_container_width=True,
                        key="download_after_save"
                    )
                    
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    
# =====================================================
# TAB 3 - DEMO MODE
# =====================================================

with tab3:
    st.header("🧪 Modo Demo (Sin APIs)")
    st.caption("Flujo: generación JSON → validación simulada → aprobación")
    
    if st.button("🎲 Generar JSON simulado"):
        simulated_json = {
            "summary": "Resumen ejecutivo simulado del contenido.",
            "key_points": [
                "Insight clave 1 - Análisis de mercado",
                "Insight clave 2 - Tendencias identificadas",
                "Insight clave 3 - Oportunidades detectadas"
            ],
            "recommended_actions": [
                "Implementar estrategia A",
                "Revisar proceso B"
            ],
            "meta": {
                "mode": "simulated",
                "generated_at": datetime.utcnow().isoformat()
            }
        }
        st.session_state["demo_json"] = json.dumps(simulated_json, indent=2, ensure_ascii=False)
    
    if "demo_json" in st.session_state:
        st.subheader("📄 JSON generado")
        edited_json = st.text_area(
            "Edita el JSON si es necesario",
            value=st.session_state["demo_json"],
            height=300
        )
        
        if st.button("🔍 Validar (simulado)"):
            validation_text = """VALIDACIÓN SIMULADA
----------------------------------
✅ Formato JSON válido
✅ Contenido coherente y alineado
✅ Estructura correcta
⚠️  Recomendación: validar tono antes de publicar"""
            
            st.session_state["validation_text"] = validation_text
            st.session_state["validated_json"] = edited_json
    
    if "validation_text" in st.session_state:
        st.subheader("🧠 Resultado de validación")
        st.code(st.session_state["validation_text"])
        
        col_ok, col_cancel = st.columns(2)
        
        with col_ok:
            if st.button("✅ Aprobar y guardar"):
                try:
                    bucket = client.bucket(bucket_name)
                    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                    blob = bucket.blob(f"{BUCKET_FOLDERS['validados']}resultado_{ts}.json")
                    blob.upload_from_string(
                        st.session_state["validated_json"],
                        content_type="application/json"
                    )
                    st.success("✅ Documento validado y almacenado")
                    del st.session_state["demo_json"]
                    del st.session_state["validation_text"]
                    del st.session_state["validated_json"]
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
        
        with col_cancel:
            if st.button("🔄 Reiniciar"):
                del st.session_state["demo_json"]
                del st.session_state["validation_text"]
                del st.session_state["validated_json"]
                st.rerun()# ... [Aquí irían los contenidos de cada tab, que te envío en el siguiente mensaje]

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
