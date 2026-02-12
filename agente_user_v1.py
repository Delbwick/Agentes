# KaiBot - Generador de Contenidos LLM
# Versión centrada en el usuario

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
    page_title="Generador de Contenidos LLM | KaiBot",
    page_icon="https://kaibot.es/wp-content/uploads/2020/07/image1.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado - Tema KaiBot (Azul profesional + Gris)
st.markdown("""
    <style>
    /* Colores de marca KaiBot */
    :root {
        --kaibot-blue: #0066CC;
        --kaibot-dark: #1E293B;
        --kaibot-gray: #64748B;
        --kaibot-light: #F8FAFC;
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
    
    /* Tabs activos */
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        background-color: var(--kaibot-blue);
        color: white;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: var(--kaibot-dark);
    }
    
    [data-testid="stSidebar"] .stMarkdown {
        color: white;
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
    "validados": "documentos_validados/"
}

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
    """Lista carpetas y archivos del bucket"""
    bucket = client.bucket(bucket_name)
    blobs = list(bucket.list_blobs())
    
    folders = set()
    files = []
    
    for b in blobs:
        parts = b.name.split("/")
        if len(parts) > 1:
            folders.add(parts[0] + "/")
        files.append({
            "name": b.name,
            "size": b.size,
            "updated": b.updated,
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


def generate_smart_filename(json_data: dict, prefix: str = "contenido") -> str:
    """
    Genera nombre de archivo basado en el resumen del JSON
    
    Args:
        json_data: Diccionario con los datos
        prefix: Prefijo del archivo (default: "contenido")
    
    Returns:
        Nombre de archivo formato: palabras-clave_YYYYMMDD_HHMMSS.json
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    # Extraer resumen
    summary = json_data.get("summary", "")
    
    if summary:
        # Limpiar y acortar el resumen
        words = re.findall(r'\b\w+\b', summary.lower())
        # Filtrar palabras comunes
        stopwords = {'el', 'la', 'los', 'las', 'de', 'del', 'y', 'en', 'un', 'una', 'es', 'por', 'para', 'con', 'a', 'que', 'se', 'sobre', 'este', 'esta'}
        meaningful_words = [w for w in words if w not in stopwords and len(w) > 3]
        
        # Tomar hasta 4 palabras
        short_summary = '_'.join(meaningful_words[:4])
        
        # Limitar longitud total
        if len(short_summary) > 50:
            short_summary = short_summary[:50]
        
        filename = f"{short_summary}_{timestamp}.json"
    else:
        filename = f"{prefix}_{timestamp}.json"
    
    # Asegurar que el nombre es válido
    filename = re.sub(r'[^\w\-_.]', '_', filename)
    
    return filename


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
# HEADER
# =====================================================

col_logo, col_title = st.columns([1, 6])
with col_logo:
    st.image("https://kaibot.es/wp-content/uploads/2020/07/image1.png", width=100)
with col_title:
    st.title("Generador de Contenidos LLM")
    st.caption("Powered by KaiBot Marketing Digital B2B | Análisis inteligente con OpenAI + Perplexity")

st.markdown("---")

# =====================================================
# SIDEBAR - Configuración simplificada
# =====================================================

with st.sidebar:
    st.image("https://kaibot.es/wp-content/uploads/2020/07/image-4-300x184.png", width=200)
    st.markdown("### ⚙️ Configuración")
    
    # Configuración GCS
    with st.expander("☁️ Google Cloud Storage", expanded=False):
        bucket_name = st.text_input("Bucket GCS", value="")
        sa_json = st.text_area("Service Account JSON", height=150)
    
    # Configuración OpenAI
    with st.expander("🤖 OpenAI API", expanded=False):
        openai_key = st.text_input("API Key", type="password", key="openai_key_input")
    
    # Configuración Perplexity
    with st.expander("🔍 Perplexity API", expanded=False):
        perplexity_key = st.text_input("API Key", type="password", key="pplx_input")
        
        if perplexity_key and st.button("🧪 Probar Conexión", use_container_width=True):
            try:
                from openai import OpenAI
                test_client = OpenAI(api_key=perplexity_key, base_url="https://api.perplexity.ai")
                test_response = test_client.chat.completions.create(
                    model="sonar",
                    messages=[{"role": "user", "content": "Responde OK"}]
                )
                st.success("✅ Conexión exitosa")
            except Exception as e:
                st.error(f"❌ {str(e)}")
    
    # Botón de conectar
    st.markdown("---")
    if st.button("🔌 Conectar Servicios", type="primary", use_container_width=True):
        try:
            if bucket_name and sa_json:
                st.session_state.gcs = get_gcs_client_from_json(sa_json)
                st.session_state.bucket_name = bucket_name
            
            if openai_key:
                st.session_state.openai = OpenAI(api_key=openai_key)
            
            if perplexity_key:
                st.session_state.perplexity_key = perplexity_key
            
            st.success("✅ Servicios conectados")
            st.rerun()
        except Exception as e:
            st.error(f"❌ {str(e)}")
    
    # Estado de conexión
    st.markdown("---")
    st.markdown("**Estado:**")
    st.write("☁️ GCS:", "✅" if "gcs" in st.session_state else "❌")
    st.write("🤖 OpenAI:", "✅" if "openai" in st.session_state else "❌")
    st.write("🔍 Perplexity:", "✅" if "perplexity_key" in st.session_state else "❌")
    
    # Footer
    st.markdown("---")
    st.markdown("**[KaiBot](https://kaibot.es)**")
    st.caption("Marketing Digital B2B")

# Verificar conexión
if "gcs" not in st.session_state or "bucket_name" not in st.session_state:
    st.warning("⚠️ Configura Google Cloud Storage en el sidebar para continuar")
    st.stop()

if "openai" not in st.session_state:
    st.warning("⚠️ Configura OpenAI API en el sidebar")
    st.stop()

if "perplexity_key" not in st.session_state:
    st.warning("⚠️ Configura Perplexity API en el sidebar")
    st.stop()

client = st.session_state.gcs
bucket_name = st.session_state.bucket_name

# =====================================================
# TABS PRINCIPALES
# =====================================================

tab1, tab2 = st.tabs(["🎯 Generador de Contenidos", "📁 Gestión de Archivos"])

# =====================================================
# TAB 1 - GENERADOR DE CONTENIDOS (PRINCIPAL)
# =====================================================

with tab1:
    st.header("🎯 Generador de Contenidos con IA")
    st.markdown("**Flujo:** Consulta → OpenAI analiza → Perplexity valida → Contenido final listo")
    
    # --- CONFIGURACIÓN RÁPIDA ---
    st.subheader("1️⃣ Configuración")
    
    # Archivos opcionales
    folders, files = list_folders_and_files(client, bucket_name)
    file_names = [f["name"] for f in files]
    
    col1, col2 = st.columns([3, 1])
    with col1:
        selected_files = st.multiselect(
            "📄 Archivos de contexto (opcional)",
            options=file_names,
            help="Deja vacío para consultas generales sin documentos"
        )
    with col2:
        max_chars = st.number_input(
            "Límite chars",
            2000, 50000, 15000, 1000,
            disabled=not selected_files
        )
    
    # Modo de operación
    if selected_files:
        st.info(f"📁 Análisis con {len(selected_files)} documento(s)")
    else:
        st.info("💭 Consulta general sin documentos")
    
    # Consulta
    st.markdown("**Tu consulta:**")
    
    query_templates = {
        "Personalizada": "",
        "Análisis Estratégico": "Realiza un análisis estratégico completo identificando tendencias, oportunidades y riesgos. Proporciona recomendaciones accionables.",
        "Resumen Ejecutivo": "Genera un resumen ejecutivo profesional con los puntos clave para toma de decisiones.",
        "Plan de Acción": "Identifica los 5 puntos más importantes y crea un plan de acción priorizado.",
        "Benchmark Competitivo": "Realiza un análisis competitivo comparando con tendencias actuales del mercado.",
        "Contenido Marketing B2B": "Genera contenido de marketing B2B enfocado en generación de leads y posicionamiento industrial."
    }
    
    query_type = st.selectbox("Tipo", list(query_templates.keys()))
    
    if query_type == "Personalizada":
        user_query = st.text_area("Escribe tu consulta", height=120, placeholder="Ej: Analiza las tendencias de marketing B2B industrial para 2026 y genera recomendaciones")
    else:
        user_query = st.text_area("Consulta (editable)", value=query_templates[query_type], height=120)
    
    # --- EJECUCIÓN ---
    st.markdown("---")
    st.subheader("2️⃣ Generar Contenido")
    
    col_exec, col_clear = st.columns([4, 1])
    
    with col_exec:
        if st.button("🚀 Generar Contenido", type="primary", use_container_width=True):
            if not user_query.strip():
                st.error("❌ Escribe una consulta")
                st.stop()
            
            # PASO 1: OpenAI
            with st.spinner("🤖 OpenAI analizando..."):
                try:
                    user_message = f"CONSULTA:\n{user_query}"
                    
                    if selected_files:
                        context = load_selected_context(client, bucket_name, selected_files, max_chars)
                        user_message += f"\n\nCONTEXTO:\n{context}"
                    
                    openai_prompt = """Eres un experto en generación de contenidos corporativos B2B.

Responde en JSON con esta estructura:
{
  "summary": "Resumen ejecutivo (2-3 líneas)",
  "key_points": ["Punto 1", "Punto 2", "Punto 3"],
  "recommended_actions": ["Acción 1", "Acción 2"],
  "topics_to_validate": ["Tema 1 a validar", "Tema 2 a validar"]
}"""
                    
                    response = st.session_state.openai.chat.completions.create(
                        model="gpt-4o-mini",
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
                        "query": user_query,
                        "mode": "with_context" if selected_files else "general"
                    }
                    
                    st.session_state.openai_response = openai_data
                    
                except Exception as e:
                    st.error(f"❌ Error en OpenAI: {str(e)}")
                    st.stop()
            
            # PASO 2: Perplexity
            with st.spinner("🔍 Perplexity validando..."):
                try:
                    from openai import OpenAI
                    
                    perplexity_client = OpenAI(
                        api_key=st.session_state.perplexity_key,
                        base_url="https://api.perplexity.ai"
                    )
                    
                    perplexity_prompt = """Eres un validador experto. Valida y enriquece el análisis con información actual.

Responde SOLO en JSON:
{
  "summary": "Resumen validado",
  "key_points": ["Punto validado 1", "Punto 2", "Punto 3"],
  "recommended_actions": ["Acción 1", "Acción 2"],
  "validation_notes": "Notas de validación",
  "sources": ["URL fuente 1", "URL fuente 2"],
  "confidence_level": "alto"
}"""
                    
                    validation_prompt = f"""ANÁLISIS A VALIDAR:
{json.dumps(openai_data, indent=2, ensure_ascii=False)}

CONSULTA ORIGINAL:
{user_query}

Valida con fuentes actuales y proporciona URLs verificables."""
                    
                    response = perplexity_client.chat.completions.create(
                        model="sonar",
                        messages=[
                            {"role": "system", "content": perplexity_prompt},
                            {"role": "user", "content": validation_prompt}
                        ]
                    )
                    
                    response_text = response.choices[0].message.content
                    
                    # Limpiar markdown
                    clean_text = response_text.strip()
                    if "```json" in clean_text:
                        clean_text = clean_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in clean_text:
                        clean_text = clean_text.split("```")[1].split("```")[0].strip()
                    
                    # Parsear JSON
                    try:
                        validated_json = json.loads(clean_text)
                    except json.JSONDecodeError:
                        import re
                        json_match = re.search(r'\{.*\}', clean_text, re.DOTALL)
                        if json_match:
                            validated_json = json.loads(json_match.group())
                        else:
                            raise
                    
                    validated_json["metadata"] = {
                        "timestamp": datetime.utcnow().isoformat(),
                        "agent": "perplexity",
                        "model": "sonar",
                        "original_query": user_query
                    }
                    
                    st.session_state.perplexity_response = validated_json
                    st.success("✅ Contenido generado")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error en Perplexity: {str(e)}")
                    
                    # Mostrar respuesta de OpenAI como fallback
                    if "openai_response" in st.session_state:
                        st.warning("⚠️ Mostrando solo resultado de OpenAI")
                        st.session_state.perplexity_response = st.session_state.openai_response
                        st.rerun()
    
    with col_clear:
        if st.button("🗑️ Limpiar", use_container_width=True):
            for key in ["openai_response", "perplexity_response", "edited_response"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    # --- RESULTADOS ---
    if "perplexity_response" in st.session_state:
        st.markdown("---")
        st.subheader("3️⃣ Resultado Final")
        
        final_data = st.session_state.perplexity_response
        
        # Vista previa
        st.markdown("**📝 Resumen:**")
        st.success(final_data.get("summary", "N/A"))
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.markdown("**🎯 Puntos Clave:**")
            for i, point in enumerate(final_data.get("key_points", []), 1):
                st.markdown(f"{i}. {point}")
        
        with col_b:
            st.markdown("**✅ Acciones Recomendadas:**")
            for i, action in enumerate(final_data.get("recommended_actions", []), 1):
                st.markdown(f"{i}. {action}")
        
        if "sources" in final_data and final_data["sources"]:
            st.markdown("**🔗 Fuentes:**")
            for source in final_data["sources"]:
                if source.startswith("http"):
                    st.markdown(f"- [{source}]({source})")
                else:
                    st.markdown(f"- {source}")
        
        # Editor (comentado para simplificar - descomentar si se necesita)
        """
        with st.expander("✏️ Editar JSON"):
            if "edited_response" not in st.session_state:
                st.session_state.edited_response = json.dumps(final_data, indent=2, ensure_ascii=False)
            
            edited_json = st.text_area("JSON", st.session_state.edited_response, height=400)
            
            try:
                edited_data = json.loads(edited_json)
                st.success("✅ JSON válido")
                json_is_valid = True
            except:
                st.error("❌ JSON inválido")
                json_is_valid = False
        """
        
        # Simplificado: usar el resultado final directamente
        edited_data = final_data
        json_is_valid = True
        
        # --- GUARDAR ---
        st.markdown("---")
        st.subheader("4️⃣ Guardar Contenido")
        
        filename_preview = generate_smart_filename(edited_data)
        st.info(f"📝 Nombre: `{filename_preview}`")
        
        col_save, col_download = st.columns(2)
        
        with col_save:
            if st.button("💾 Guardar en Cloud", type="primary", use_container_width=True):
                try:
                    filename = generate_smart_filename(edited_data)
                    upload_json_to_gcs(client, bucket_name, BUCKET_FOLDERS["validados"], filename, edited_data)
                    st.success(f"✅ Guardado: {filename}")
                    st.balloons()
                except Exception as e:
                    st.error(f"❌ {str(e)}")
        
        with col_download:
            st.download_button(
                "⬇️ Descargar JSON",
                json.dumps(edited_data, indent=2, ensure_ascii=False),
                file_name=filename_preview,
                mime="application/json",
                use_container_width=True
            )

# =====================================================
# TAB 2 - GESTIÓN DE ARCHIVOS (SECUNDARIO)
# =====================================================

with tab2:
    st.header("📁 Gestión de Archivos")
    
    folders, files = list_folders_and_files(client, bucket_name)
    
    # Subir archivos
    st.subheader("📤 Subir Archivos")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        folder = st.selectbox("Carpeta", folders if folders else ["documentos/"])
        uploaded = st.file_uploader("Archivos", accept_multiple_files=True)
    with col2:
        new_folder = st.text_input("Nueva carpeta")
    
    target_folder = f"{new_folder.strip()}/" if new_folder else folder
    
    if st.button("⬆️ Subir", type="primary") and uploaded:
        progress = st.progress(0)
        for i, f in enumerate(uploaded):
            try:
                upload_file(client, bucket_name, f, target_folder)
                progress.progress((i + 1) / len(uploaded))
            except Exception as e:
                st.error(f"Error: {e}")
        st.success(f"✅ {len(uploaded)} archivo(s) subidos")
        st.rerun()
    
    # Listar archivos
    st.markdown("---")
    st.subheader("📂 Archivos en el Bucket")
    
    if files:
        df = pd.DataFrame(files)
        st.dataframe(df, use_container_width=True)
        
        to_delete = st.multiselect("Eliminar", df["name"].tolist())
        
        if st.button("🗑️ Eliminar seleccionados") and to_delete:
            bucket = client.bucket(bucket_name)
            for name in to_delete:
                try:
                    bucket.blob(name).delete()
                except Exception as e:
                    st.error(f"Error: {e}")
            st.success(f"✅ {len(to_delete)} eliminados")
            st.rerun()
    else:
        st.info("Sin archivos")
    
    # Documentación adicional (comentado - descomentar si se necesita)
    """
    st.markdown("---")
    st.subheader("🌐 Documentación Web")
    
    web = st.text_input("URL")
    linkedin = st.text_input("LinkedIn")
    
    if st.button("💾 Guardar") and (web or linkedin):
        try:
            payload = {"web": web, "linkedin": linkedin, "created_at": datetime.utcnow().isoformat()}
            upload_json_to_gcs(client, bucket_name, BUCKET_FOLDERS["adicional"], 
                             f"fuentes_{int(datetime.utcnow().timestamp())}.json", payload)
            st.success("✅ Guardado")
        except Exception as e:
            st.error(f"❌ {e}")
    """

# Footer
st.markdown("---")
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    st.markdown("**[KaiBot](https://kaibot.es)** - Marketing Digital B2B")
with col_f2:
    st.markdown("Especialistas en generación de leads industriales")
with col_f3:
    st.markdown("📧 hello@kaibot.es | ☎️ (+34) 633 69 88 32")
