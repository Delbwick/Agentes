# KaiBot Cloud Storage Manager + Content Agent
# Archivo: gcloud_uploader_real.py

import streamlit as st
from datetime import datetime
import io
import json
import pandas as pd
import os

from google.cloud import storage
from google.oauth2 import service_account
from openai import OpenAI

# =============================
# Helpers GCP
# =============================

def get_gcs_client_from_json(sa_json_str):
    info = json.loads(sa_json_str)
    creds = service_account.Credentials.from_service_account_info(info)
    return storage.Client(credentials=creds, project=info.get("project_id"))


def list_folders_and_files(client, bucket_name):
    bucket = client.bucket(bucket_name)
    blobs = bucket.list_blobs()

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

    return sorted(list(folders)), files


def upload_file(client, bucket_name, file, folder):
    bucket = client.bucket(bucket_name)
    path = f"{folder.rstrip('/')}/{file.name}"
    blob = bucket.blob(path)
    blob.upload_from_file(file, rewind=True)


def read_folder_texts(client, bucket_name, folder):
    bucket = client.bucket(bucket_name)
    blobs = bucket.list_blobs(prefix=folder)
    texts = []
    for b in blobs:
        if b.name.endswith("/"):
            continue
        content = b.download_as_text()
        texts.append(f"### {b.name}\n{content}")
    return "\n\n".join(texts)

# =============================
# UI Config
# =============================

st.set_page_config(page_title="KaiBot Cloud Agent", layout="wide")

st.markdown(
    """
    <style>
    body { background-color: #f8fafc; }
    h1, h2, h3 { color: #1E293B; }
    </style>
    """,
    unsafe_allow_html=True,
)

col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image("https://kaibot.es/wp-content/uploads/2020/07/image1.png", width=90)
with col_title:
    st.title("KaiBot Cloud Storage & Content Agent")
    st.caption("Gestión de archivos y agente de generación de contenidos")

st.markdown("---")

# =============================
# Sidebar
# =============================

with st.sidebar:
    st.header("⚙️ Configuración")
    bucket_name = st.text_input("Bucket GCS")
    sa_json = st.text_area("Service Account JSON", height=220)
    openai_key = st.text_input("OpenAI API Key", type="password")

    if st.button("Conectar"):
        try:
            st.session_state.gcs = get_gcs_client_from_json(sa_json)
            st.session_state.openai = OpenAI(api_key=openai_key)
            st.success("Conectado correctamente")
        except Exception as e:
            st.error(e)

if "gcs" not in st.session_state:
    st.warning("Configura la conexión para continuar")
    st.stop()

client = st.session_state.gcs

# =============================
# Tabs
# =============================

tab1, tab2 = st.tabs(["📁 Gestión de Archivos", "🤖 Consulta al Agente"])

# =============================
# TAB 1 - FILES
# =============================

with tab1:
    folders, files = list_folders_and_files(client, bucket_name)

    st.subheader("Subir archivos")
    folder = st.selectbox("Carpeta destino", options=folders)
    uploaded = st.file_uploader("Selecciona archivos", accept_multiple_files=True)

    if st.button("Subir") and uploaded:
        for f in uploaded:
            upload_file(client, bucket_name, f, folder)
        st.success("Archivos subidos correctamente")

    st.subheader("Contenido del bucket")
    if files:
        st.dataframe(pd.DataFrame(files), use_container_width=True)

# =============================
# TAB 2 - AGENT
# =============================

with tab2:
    st.subheader("Consulta a tu agente de generación de contenidos")

    system_prompt = st.text_area(
        "Instrucciones del agente (system prompt)",
        value="""Eres un agente de generación de contenidos corporativos.
Debes responder SIEMPRE en formato JSON válido siguiendo exactamente este esquema:
{
  "summary": string,
  "key_points": [string],
  "recommended_actions": [string]
}
No añadas texto fuera del JSON.""",
        height=180,
    )

    user_query = st.text_area("Consulta", height=120)

    if st.button("Ejecutar consulta"):
        context = ""
        for folder in [
            "Documentos_agente/",
            "documentacion_adicional/",
            "documentos_validados/",
        ]:
            context += read_folder_texts(client, bucket_name, folder)

        response = st.session_state.openai.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "system",
                    "content": system_prompt + "\n\n" + context,
                },
                {"role": "user", "content": user_query},
            ],
        )

        output = response.output_text
        st.json(json.loads(output))
