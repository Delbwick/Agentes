
# KaiBot Cloud Storage Manager + Content Agent (OPTIMIZADO)
import streamlit as st
from datetime import datetime
import json
import pandas as pd
from google.cloud import storage
from google.oauth2 import service_account
from openai import OpenAI
import re

# =====================================================
# CONFIGURACIÓN DE PÁGINA (FAVICON Y COLOR)
# =====================================================

st.set_page_config(
    page_title="KaiBot Cloud Agent",
    page_icon="https://kaibot.es/wp-content/uploads/2020/07/image1.png",  # Favicon
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado - Tema KaiBot con pestañas en negro/gris
st.markdown("""
    <style>
    /* Colores de marca KaiBot */
    :root {
        --kaibot-blue: #0066CC;
        --kaibot-dark: #1E293B;
        --kaibot-gray: #64748B;
        --kaibot-light: #F8FAFC;
        --sidebar-bg: #475569; /* Gris azulado */
    }
    
    /* Fondo general */
    .main {
        background-color: #F8FAFC;
    }
    
    /* Títulos */
    h1, h2, h3 {
        color: var(--kaibot-dark);
        font-weight: 600;
    }
    
    /* Botones primarios */
    .stButton>button[kind="primary"] {
        background-color: var(--kaibot-blue);
        color: white;
        border: none;
        font-weight: 600;
    }
    
    .stButton>button[kind="primary"]:hover {
        background-color: #0052A3;
        border: none;
    }
    
    /* ===== TABS - Estilo Negro/Gris ===== */
    /* Contenedor de tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #1E293B;
        padding: 8px;
        border-radius: 8px 8px 0 0;
    }
    
    /* Tabs no seleccionados */
    .stTabs [data-baseweb="tab-list"] button[role="tab"] {
        background-color: #334155;
        color: #E2E8F0;
        border: none;
        border-radius: 6px 6px 0 0;
        padding: 12px 24px;
        font-weight: 500;
        font-size: 15px;
    }
    
    /* Tab hover */
    .stTabs [data-baseweb="tab-list"] button[role="tab"]:hover {
        background-color: #475569;
        color: white;
    }
    
    /* Tab seleccionado */
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        background-color: var(--kaibot-blue);
        color: white;
        font-weight: 600;
    }
    
    /* Contenido del tab */
    .stTabs [data-baseweb="tab-panel"] {
        background-color: white;
        padding: 24px;
        border-radius: 0 0 8px 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* ===== SIDEBAR - Gris azulado con todo en blanco ===== */
    [data-testid="stSidebar"] {
        background-color: var(--sidebar-bg);
    }
    
    /* Todos los textos del sidebar en blanco */
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    
    /* Títulos y markdown en blanco */
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label {
        color: white !important;
    }
    
    /* Inputs del sidebar con borde blanco y texto blanco */
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea,
    [data-testid="stSidebar"] select {
        background-color: rgba(255, 255, 255, 0.1) !important;
        border: 1px solid white !important;
        color: white !important;
    }
    
    /* Placeholder de inputs en blanco */
    [data-testid="stSidebar"] input::placeholder,
    [data-testid="stSidebar"] textarea::placeholder {
        color: rgba(255, 255, 255, 0.7) !important;
    }
    
    /* Botones del sidebar */
    [data-testid="stSidebar"] .stButton>button {
        background-color: transparent;
        border: 1px solid white;
        color: white !important;
    }
    
    [data-testid="stSidebar"] .stButton>button:hover {
        background-color: rgba(255, 255, 255, 0.1);
        border: 1px solid white;
    }
    
    /* Botones primarios del sidebar */
    [data-testid="stSidebar"] .stButton>button[kind="primary"] {
        background-color: var(--kaibot-blue);
        border: 1px solid var(--kaibot-blue);
        color: white !important;
    }
    
    [data-testid="stSidebar"] .stButton>button[kind="primary"]:hover {
        background-color: #0052A3;
        border: 1px solid #0052A3;
    }
    
    /* Expanders del sidebar */
    [data-testid="stSidebar"] .streamlit-expanderHeader {
        background-color: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.3);
        color: white !important;
    }
    
    [data-testid="stSidebar"] .streamlit-expanderHeader:hover {
        background-color: rgba(255, 255, 255, 0.15);
    }
    
    /* Contenido de expanders */
    [data-testid="stSidebar"] .streamlit-expanderContent {
        background-color: rgba(0, 0, 0, 0.1);
        border-left: 1px solid rgba(255, 255, 255, 0.3);
    }
    
    /* Divisores del sidebar */
    [data-testid="stSidebar"] hr {
        border-color: rgba(255, 255, 255, 0.3) !important;
    }
    
    /* Caption/subtítulos del sidebar */
    [data-testid="stSidebar"] .stCaption {
        color: rgba(255, 255, 255, 0.8) !important;
    }
    
    /* Info boxes */
    .stInfo {
        background-color: #EBF5FF;
        border-left: 4px solid var(--kaibot-blue);
    }
    
    /* Success boxes */
    .stSuccess {
        background-color: #ECFDF5;
        border-left: 4px solid #10B981;
    }
    
    /* Botones width completo */
    .stButton>button {
        width: 100%;
    }
    
    /* Eliminamos padding excesivo */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
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
    "prompts": "prompts/"  # Carpeta del prompt
}

# =====================================================
# Helper para generar nombres de archivo
# =====================================================

def generate_smart_filename(json_data: dict, prefix: str = "validado") -> str:
    """
    Genera nombre de archivo basado en el resumen del JSON
    
    Args:
        json_data: Diccionario con los datos
        prefix: Prefijo del archivo (default: "validado")
    
    Returns:
        Nombre de archivo formato: resumen-breve_YYYYMMDD_HHMMSS.json
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    # Extraer resumen
    summary = json_data.get("summary", "")
    
    if summary:
        # Limpiar y acortar el resumen
        # Tomar primeras 5-7 palabras significativas
        words = re.findall(r'\b\w+\b', summary.lower())
        # Filtrar palabras comunes
        stopwords = {'el', 'la', 'los', 'las', 'de', 'del', 'y', 'en', 'un', 'una', 'es', 'por', 'para', 'con', 'a', 'que', 'se'}
        meaningful_words = [w for w in words if w not in stopwords and len(w) > 3]
        
        # Tomar hasta 4 palabras
        short_summary = '_'.join(meaningful_words[:4])
        
        # Limitar longitud total
        if len(short_summary) > 50:
            short_summary = short_summary[:50]
        
        filename = f"{short_summary}_{timestamp}.json"
    else:
        filename = f"{prefix}_{timestamp}.json"
    
    # Asegurar que el nombre es válido (sin caracteres especiales problemáticos)
    filename = re.sub(r'[^\w\-_.]', '_', filename)
    
    return filename

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
# UI CONFIG
# =====================================================

st.set_page_config(page_title="KaiBot Cloud Agent", layout="wide")

st.markdown("""
    <style>
    body { background-color: #f8fafc; }
    h1, h2, h3 { color: #1E293B; }
    .stButton>button { width: 100%; }
    </style>
""", unsafe_allow_html=True)

col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image("https://kaibot.es/wp-content/uploads/2020/07/image1.png", width=90)
with col_title:
    st.title("KaiBot Cloud Storage & Content Agent")
    st.caption("Gestión documental + agente de contenidos (modo demo y real)")

st.markdown("---")

# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:
    st.header("⚙️ Configuración")
    
    bucket_name = st.text_input("Bucket GCS", value="")
    sa_json = st.text_area("Service Account JSON", height=220)
    openai_key = st.text_input("OpenAI API Key", type="password")
    
    if st.button("🔌 Conectar"):
        try:
            st.session_state.gcs = get_gcs_client_from_json(sa_json)
            if openai_key:
                st.session_state.openai = OpenAI(api_key=openai_key)
            st.session_state.bucket_name = bucket_name
            st.success("✅ Conectado correctamente")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

if "gcs" not in st.session_state or "bucket_name" not in st.session_state:
    st.warning("⚠️ Configura la conexión en el sidebar para continuar")
    st.stop()

client = st.session_state.gcs
bucket_name = st.session_state.bucket_name

# =====================================================
# TABS
# =====================================================

tab1, tab2, tab3 = st.tabs(["📁 Gestión de Archivos", "🤖 Agentes IA", "🧪 Modo Demo"])

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
# TAB 2 - AGENTE DUAL: OPENAI → PERPLEXITY (MEJORADO)
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
    
    # Selección de archivos (AHORA OPCIONAL)
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
    
    col_exec1, col_clear1 = st.columns([3, 1])
    
    with col_exec1:
        execute_openai = st.button(
            "▶️ Analizar con OpenAI",
            type="primary",
            use_container_width=True
        )
    
    with col_clear1:
        if st.button("🗑️ Limpiar Todo", use_container_width=True):
            keys_to_delete = ["openai_response", "perplexity_response", "edited_response"]
            for key in keys_to_delete:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    if execute_openai:
        if not user_query.strip():
            st.error("❌ La consulta no puede estar vacía")
            st.stop()
        
        with st.spinner("🔄 OpenAI analizando..."):
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
                
                # Llamar a OpenAI
                response = st.session_state.openai.chat.completions.create(
                    model="gpt-4o-mini",
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
                    "model": "gpt-4o-mini",
                    "query": user_query,
                    "context_files": selected_files if selected_files else [],
                    "context_chars": len(context) if context else 0,
                    "mode": "with_context" if selected_files else "general_query"
                }
                
                st.session_state.openai_response = response_json
                st.success("✅ Análisis completado por OpenAI")
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
            if mode == "with_context":
                st.success(f"📁 Análisis basado en {len(openai_data.get('metadata', {}).get('context_files', []))} documento(s)")
            else:
                st.info("💭 Análisis general sin documentos específicos")
            
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
        
        if st.button("▶️ Validar con Perplexity", type="primary", use_container_width=True):
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
                        "analysis_mode": openai_data.get("metadata", {}).get("mode", "unknown")
                    }
                    
                    st.session_state.perplexity_response = validated_json
                    st.success("✅ Validación completada por Perplexity")
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
                st.rerun()
