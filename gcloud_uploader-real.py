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

    st.subheader("📤 Subir archivos")

    col_up1, col_up2 = st.columns([2, 1])
    with col_up1:
        folder = st.selectbox("Carpeta destino", options=folders)
        uploaded = st.file_uploader("Selecciona archivos", accept_multiple_files=True)
    with col_up2:
        new_folder = st.text_input("Crear nueva carpeta")

    target_folder = new_folder.strip() + "/" if new_folder else folder

    if st.button("Subir archivos") and uploaded:
        for f in uploaded:
            upload_file(client, bucket_name, f, target_folder)
        st.success(f"{len(uploaded)} archivo(s) subidos correctamente")

    st.markdown("---")
    st.subheader("📁 Contenido del bucket")

    if files:
        df = pd.DataFrame(files)
        st.dataframe(df, use_container_width=True)

        to_delete = st.multiselect(
            "Selecciona archivos a eliminar",
            options=df["name"].tolist(),
        )

        if st.button("Eliminar seleccionados") and to_delete:
            bucket = client.bucket(bucket_name)
            for name in to_delete:
                bucket.blob(name).delete()
            st.success("Archivos eliminados correctamente")
    else:
        st.info("El bucket no contiene archivos")

# =============================
# TAB 2 - AGENT
# =============================

with tab2:
    st.subheader("🤖 Consulta a tu agente de generación de contenidos")

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

    st.markdown("---")
    st.subheader("📂 Contexto documental a usar")

    folders, files = list_folders_and_files(client, bucket_name)
    file_names = [f["name"] for f in files]

    selected_files = st.multiselect(
        "Selecciona los archivos que el agente puede leer",
        options=file_names,
    )

    st.markdown("---")
    st.subheader("⚙️ Opciones avanzadas")

    max_chars = st.slider(
        "Límite máximo de caracteres de contexto",
        min_value=1000,
        max_value=20000,
        value=8000,
        step=500,
    )

    def load_selected_context():
        bucket = client.bucket(bucket_name)
        texts = []
        total_chars = 0

        for name in selected_files:
            blob = bucket.blob(name)
            content = blob.download_as_text()
            if total_chars + len(content) > max_chars:
                remaining = max_chars - total_chars
                if remaining <= 0:
                    break
                content = content[:remaining]
            texts.append(f"### {name}\n{content}")
            total_chars += len(content)

        return "\n\n".join(texts)

    if st.button("Ejecutar consulta"):
        if not selected_files:
            st.warning("Selecciona al menos un archivo como contexto")
            st.stop()

        context = load_selected_context()

        try:
            response = st.session_state.openai.responses.create(
                model="gpt-4o-mini",
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

        except Exception:
            st.error("⚠️ Error al consultar el agente. Revisa el límite de tokens o el billing.")

    st.markdown("---")
    st.subheader("🎯 Agente demo")
    st.caption("Consultas de ejemplo para mostrar el funcionamiento del agente en modo demo")

    demo_queries = [
        "Resume los puntos clave de la documentación seleccionada",
        "Extrae oportunidades de mejora a partir de los documentos",
        "Genera un resumen ejecutivo para dirección",
        "Detecta incoherencias o riesgos en la información",
    ]

    demo_query = st.selectbox("Selecciona una consulta demo", demo_queries)

    if st.button("Ejecutar consulta demo"):
        if not selected_files:
            st.warning("Selecciona al menos un archivo como contexto")
            st.stop()

        context = load_selected_context()

        try:
            response = st.session_state.openai.responses.create(
                model="gpt-4o-mini",
                input=[
                    {
                        "role": "system",
                        "content": system_prompt + "\n\n" + context,
                    },
                    {"role": "user", "content": demo_query},
                ],
            )

            output = response.output_text
            st.json(json.loads(output))

        except Exception:
            st.error("⚠️ Error al ejecutar la consulta demo.")
