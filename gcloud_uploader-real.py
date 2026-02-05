import streamlit as st
import io
import json
import random
from datetime import datetime
import pandas as pd

from google.cloud import storage
from google.oauth2 import service_account

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="KaiBot Cloud Storage Manager",
    layout="wide"
)

BUCKET_FOLDERS = {
    "agente": "Documentos_agente/",
    "adicional": "documentacion_adicional/",
    "validados": "documentos_validados/",
}

# =========================================================
# AUTH
# =========================================================

def get_gcs_client(sa_json_str):
    info = json.loads(sa_json_str)
    creds = service_account.Credentials.from_service_account_info(info)
    return storage.Client(credentials=creds, project=info["project_id"])

# =========================================================
# GCS HELPERS
# =========================================================

def upload_json_to_gcs(client, bucket_name, folder, filename, data):
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(f"{folder}{filename}")
    blob.upload_from_string(
        json.dumps(data, indent=2, ensure_ascii=False),
        content_type="application/json"
    )

def list_files(client, bucket_name, prefix=None):
    bucket = client.bucket(bucket_name)
    blobs = bucket.list_blobs(prefix=prefix)
    return [b.name for b in blobs if not b.name.endswith("/")]

def delete_file(client, bucket_name, name):
    bucket = client.bucket(bucket_name)
    bucket.blob(name).delete()

# =========================================================
# UI STYLE
# =========================================================

st.markdown("""
<style>
.stButton>button {
    background-color:#2563EB;
    color:white;
    border-radius:8px;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:
    st.image("https://kaibot.es/wp-content/uploads/2020/07/image1.png", width=120)
    st.header("⚙️ Configuración GCloud")

    bucket_name = st.text_input("Bucket GCS", key="sb_bucket")
    sa_json = st.text_area("Service Account JSON", height=200, key="sb_sa")

    connect = st.button("Conectar", key="sb_connect")

    if connect:
        try:
            st.session_state["gcs_client"] = get_gcs_client(sa_json)
            st.success("Conectado a GCloud")
        except Exception as e:
            st.error(str(e))

client = st.session_state.get("gcs_client")
if not client:
    st.stop()
    
with st.sidebar:
    st.header("🤖 OpenAI – Agente real")

    openai_api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        key="sb_openai_key"
    )

    openai_model = st.selectbox(
        "Modelo",
        ["gpt-4.1", "gpt-4o", "gpt-4o-mini"],
        key="sb_openai_model"
    )

    openai_max_tokens = st.slider(
        "Max tokens",
        min_value=256,
        max_value=4096,
        value=1024,
        step=128,
        key="sb_openai_tokens"
    )

    openai_temperature = st.slider(
        "Temperature",
        0.0, 1.0, 0.3, 0.05,
        key="sb_openai_temp"
    )

st.session_state["openai_config"] = {
    "api_key": openai_api_key,
    "model": openai_model,
    "max_tokens": openai_max_tokens,
    "temperature": openai_temperature,
}


# =========================================================
# TABS
# =========================================================

tab_data, tab_agents = st.tabs(["📁 Datos", "🤖 Agentes"])

# =========================================================
# 📁 TAB DATOS
# =========================================================

with tab_data:
    st.subheader("📤 Subida de archivos")

    uploaded = st.file_uploader(
        "Subir archivos al bucket",
        accept_multiple_files=True,
        key="data_uploader"
    )

    folder_choice = st.selectbox(
        "Carpeta destino",
        options=list(BUCKET_FOLDERS.keys()),
        key="data_folder"
    )

    if st.button("Subir archivos", key="data_upload_btn"):
        for f in uploaded:
            blob = client.bucket(bucket_name).blob(
                f"{BUCKET_FOLDERS[folder_choice]}{f.name}"
            )
            blob.upload_from_file(f)
        st.success("Archivos subidos")

    st.markdown("---")
    st.subheader("🌐 Documentación adicional (Web / LinkedIn)")

    web = st.text_input("Página web", key="data_web")
    linkedin = st.text_input("LinkedIn", key="data_linkedin")

    if st.button("Guardar documentación adicional", key="data_save_web"):
        payload = {
            "web": web,
            "linkedin": linkedin,
            "created_at": datetime.utcnow().isoformat()
        }
        upload_json_to_gcs(
            client,
            bucket_name,
            BUCKET_FOLDERS["adicional"],
            f"fuentes_{datetime.utcnow().timestamp()}.json",
            payload
        )
        st.success("Documentación guardada")

    st.markdown("---")
    st.subheader("🗑 Gestión de archivos")

    all_files = []
    for f in BUCKET_FOLDERS.values():
        all_files += list_files(client, bucket_name, f)

    to_delete = st.multiselect(
        "Selecciona archivos a eliminar",
        all_files,
        key="data_delete_select"
    )

    if st.button("Eliminar seleccionados", key="data_delete_btn"):
        for f in to_delete:
            delete_file(client, bucket_name, f)
        st.success("Archivos eliminados")

# =========================================================
# 🤖 TAB AGENTES
# =========================================================

with tab_agents:
    st.subheader("🤖 Consulta a tu agente")

    query = st.text_area(
        "Consulta",
        height=120,
        key="agent_query"
    )

    docs = []
    for folder in BUCKET_FOLDERS.values():
        docs += list_files(client, bucket_name, folder)

    selected_docs = st.multiselect(
        "Documentación a usar",
        docs,
        key="agent_docs"
    )

    col1, col2, col3 = st.columns(3)
    run_sim = col1.button("🎭 Simulado", key="agent_sim")
    run_demo = col2.button("🧪 Demo", key="agent_demo")
    run_real = col3.button("🚀 Real", key="agent_real")

    def generate_agent_json(mode):
        return {
            "mode": mode,
            "query": query,
            "summary": "Análisis generado a partir de las fuentes seleccionadas.",
            "key_points": [
                "Síntesis estructurada",
                "Contenido alineado con la consulta",
                "Uso de documentación interna"
            ],
            "sources": selected_docs,
            "created_at": datetime.utcnow().isoformat()
        }

    if run_sim or run_demo or run_real:
        result = generate_agent_json(
            "simulado" if run_sim else "demo" if run_demo else "real"
        )

        st.markdown("### 📄 Respuesta del agente")
        st.json(result)

        st.markdown("### 🔎 Validación externa (tipo Perplexity)")
        approved = random.choice([True, False])

        if approved:
            st.success("✅ APROBADO")
            if st.button("Guardar en documentos_validados", key="agent_save_valid"):
                filename = f"respuesta_{datetime.utcnow().timestamp()}.json"
                upload_json_to_gcs(
                    client,
                    bucket_name,
                    BUCKET_FOLDERS["validados"],
                    filename,
                    result
                )
                st.success("Respuesta guardada en documentos_validados/")
        else:
            st.warning("⚠️ REQUIERE AJUSTES")
            st.text_area(
                "Correcciones manuales",
                height=120,
                key="agent_corrections"
            )
