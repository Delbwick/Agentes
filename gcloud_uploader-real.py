"""
KaiBot Cloud Storage Manager
Archivo: streamlit_gcloud_uploader.py

Aplicación Streamlit corporativa para:
- Subida REAL de archivos a Google Cloud Storage
- Listado y borrado REAL desde un bucket GCS
- Historial persistente opcional (Firestore preparado)
- Filtros básicos por etiqueta y fecha

Requisitos:
- pip install streamlit pandas google-cloud-storage google-cloud-firestore

IMPORTANTE:
- Se espera un JSON de Service Account válido (pegado en la UI o vía variable de entorno)
"""

import streamlit as st
from datetime import datetime
import os
import io
import json
import pandas as pd

from google.cloud import storage
from google.cloud import firestore
from google.oauth2 import service_account

# -----------------------------
# Helpers de autenticación
# -----------------------------

def get_gcs_client_from_json(sa_json_str):
    info = json.loads(sa_json_str)
    creds = service_account.Credentials.from_service_account_info(info)
    return storage.Client(credentials=creds, project=info.get("project_id"))


def get_firestore_client_from_json(sa_json_str):
    info = json.loads(sa_json_str)
    creds = service_account.Credentials.from_service_account_info(info)
    return firestore.Client(credentials=creds, project=info.get("project_id"))

# -----------------------------
# GCloud REAL
# -----------------------------

def gcloud_upload_file(client, bucket_name, file_buffer, destination_path, metadata=None):
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_path)

    blob.metadata = metadata or {}
    blob.upload_from_file(file_buffer, rewind=True)

    blob.reload()

    return {
        "name": blob.name,
        "size": blob.size,
        "uploaded_at": blob.time_created.isoformat(),
        "metadata": blob.metadata or {},
    }


def gcloud_list_files(client, bucket_name):
    bucket = client.bucket(bucket_name)
    blobs = bucket.list_blobs()

    records = []
    for b in blobs:
        records.append({
            "name": b.name,
            "size": b.size,
            "uploaded_at": b.time_created.isoformat() if b.time_created else None,
            "metadata": b.metadata or {},
        })
    return records


def gcloud_delete_file(client, bucket_name, name):
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(name)
    blob.delete()

# -----------------------------
# Firestore (historial)
# -----------------------------

def save_history(fs_client, record):
    fs_client.collection("upload_history").add(record)


def load_history(fs_client, limit=200):
    docs = fs_client.collection("upload_history").order_by(
        "uploaded_at", direction=firestore.Query.DESCENDING
    ).limit(limit).stream()
    return [d.to_dict() for d in docs]

# -----------------------------
# UI
# -----------------------------

st.set_page_config(page_title="KaiBot GCloud Uploader", layout="wide")

st.markdown(
    """
    <style>
    body { background-color: #f8fafc; }
    h1, h2, h3, h4 { color: #1E293B; }
    .stButton>button {
        background-color: #2563EB !important;
        color: white !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Header
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image("https://kaibot.es/wp-content/uploads/2020/07/image1.png", width=90)
with col_title:
    st.title("KaiBot Cloud Storage Manager")
    st.caption("Gestión corporativa de archivos sobre Google Cloud Storage")

st.markdown("---")

# Sidebar config
with st.sidebar:
    st.header("⚙️ Configuración GCloud")

    project_id = st.text_input("GCP Project ID")
    bucket_name = st.text_input("Bucket GCS")
    sa_json = st.text_area("Service Account JSON", height=220)

    enable_history = st.checkbox("Guardar historial en Firestore", value=False)

    connect = st.button("Conectar")

    if connect:
        try:
            gcs_client = get_gcs_client_from_json(sa_json)
            st.session_state["gcs_client"] = gcs_client
            if enable_history:
                fs_client = get_firestore_client_from_json(sa_json)
                st.session_state["fs_client"] = fs_client
            st.success("Conectado correctamente a Google Cloud")
        except Exception as e:
            st.error(f"Error de conexión: {e}")

# Validación conexión
client = st.session_state.get("gcs_client")
fs_client = st.session_state.get("fs_client")

if not client:
    st.warning("Configura el acceso a GCloud en la barra lateral para continuar.")
    st.stop()

# Layout
col1, col2 = st.columns((2, 3))

with col1:
    st.subheader("📤 Subida de archivos")

    uploaded = st.file_uploader("Selecciona archivos", accept_multiple_files=True)

    st.markdown("**Destino en el bucket**")
    folder_mode = st.radio(
        "Selecciona cómo definir la carpeta destino",
        options=["Elegir carpeta existente", "Introducir nueva carpeta"],
        horizontal=True,
    )

    existing_folders = sorted({
        f.split("/")[0]
        for f in [r.get("name", "") for r in st.session_state.get("uploaded_files", [])]
        if "/" in f
    })

    if folder_mode == "Elegir carpeta existente" and existing_folders:
        selected_folder = st.selectbox("Carpeta destino", existing_folders)
    else:
        selected_folder = st.text_input("Nombre de la carpeta destino", value="raw")

    tag = st.text_input("Etiqueta (tag)")

    if st.button("Subir a GCloud"):
        if not uploaded:
            st.warning("No hay archivos seleccionados")
        else:
            for f in uploaded:
                buf = io.BytesIO(f.read())
                meta = {"tag": tag} if tag else {}

                destination_path = f"{selected_folder.strip('/')}/{f.name}"

                rec = gcloud_upload_file(
                    client,
                    bucket_name,
                    buf,
                    destination_path,
                    metadata=meta,
                )
                if enable_history and fs_client:
                    save_history(fs_client, rec)
            st.success(f"{len(uploaded)} archivo(s) subidos correctamente")

with col2:
    st.subheader("📁 Archivos en el bucket")

    files = gcloud_list_files(client, bucket_name)

    if files:
        df = pd.DataFrame(files)

        # Filtros
        tag_filter = st.text_input("Filtrar por tag")
        if tag_filter:
            df = df[df["metadata"].astype(str).str.contains(tag_filter)]

        st.dataframe(df, use_container_width=True)

        to_delete = st.multiselect("Borrar archivos", options=df["name"].tolist())
        if st.button("Eliminar seleccionados"):
            for name in to_delete:
                gcloud_delete_file(client, bucket_name, name)
            st.success("Archivos eliminados")
    else:
        st.info("El bucket no contiene archivos")

if enable_history and fs_client:
    st.markdown("---")
    st.subheader("🕒 Historial de subidas (Firestore)")
    history = load_history(fs_client)
    if history:
        st.dataframe(pd.DataFrame(history), use_container_width=True)
    else:
        st.info("Sin historial aún")
