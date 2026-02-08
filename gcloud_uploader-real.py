# KaiBot Cloud Storage Manager + Content Agent (OPTIMIZADO)
import streamlit as st
from datetime import datetime
import json
import pandas as pd
from google.cloud import storage
from google.oauth2 import service_account
from openai import OpenAI

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
# TAB 1 - FILE MANAGEMENT
# =====================================================

with tab1:
    folders, files = list_folders_and_files(client, bucket_name)
    
    st.subheader("📤 Subida de archivos")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        folder = st.selectbox("Carpeta destino", options=folders if folders else ["documentos/"])
        uploaded = st.file_uploader("Selecciona archivos", accept_multiple_files=True)
    with col2:
        new_folder = st.text_input("Crear nueva carpeta")
    
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
    st.subheader("📁 Contenido del bucket")
    
    if files:
        df = pd.DataFrame(files)
        st.dataframe(df, use_container_width=True)
        
        to_delete = st.multiselect("Selecciona archivos a eliminar", options=df["name"].tolist())
        
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
# TAB 2 - AGENTS
# =====================================================

with tab2:
    st.subheader("🤖 Agente IA (OpenAI)")
    
    if "openai" not in st.session_state:
        st.warning("⚠️ Configura la API key de OpenAI en el sidebar")
        st.stop()
    
    system_prompt = st.text_area(
        "System prompt",
        value="""Eres un agente de generación de contenidos corporativos.
Debes responder SIEMPRE en formato JSON válido siguiendo este esquema:
{
  "summary": "resumen ejecutivo",
  "key_points": ["punto 1", "punto 2", "punto 3"],
  "recommended_actions": ["acción 1", "acción 2"]
}""",
        height=180
    )
    
    folders, files = list_folders_and_files(client, bucket_name)
    file_names = [f["name"] for f in files]
    
    selected_files = st.multiselect("📄 Archivos de contexto", options=file_names)
    
    col1, col2 = st.columns(2)
    with col1:
        max_chars = st.slider("Límite caracteres contexto", 1000, 20000, 8000, 500)
    with col2:
        mode = st.radio("Modo", ["Consulta personalizada", "Consultas predefinidas"])
    
    if mode == "Consulta personalizada":
        user_query = st.text_area("Tu consulta", height=100)
    else:
        user_query = st.selectbox("Consulta predefinida", [
            "Resume los puntos clave de la documentación",
            "Genera un resumen ejecutivo",
            "Detecta riesgos o incoherencias"
        ])
    
    if st.button("🚀 Ejecutar agente"):
        if not selected_files:
            st.warning("⚠️ Selecciona al menos un archivo de contexto")
            st.stop()
        
        with st.spinner("Procesando..."):
            try:
                context = load_selected_context(client, bucket_name, selected_files, max_chars)
                result = call_openai_agent(st.session_state.openai, system_prompt, context, user_query)
                
                st.success("✅ Respuesta generada")
                st.json(result)
                
                st.download_button(
                    "⬬ Descargar JSON",
                    json.dumps(result, indent=2, ensure_ascii=False),
                    f"respuesta_{int(datetime.utcnow().timestamp())}.json",
                    "application/json"
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
