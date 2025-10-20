"""
Streamlit app - Interfaz corporativa KaiBot para GCloud
Archivo: streamlit_gcloud_uploader.py
Descripción: Interfaz (mock) que permite subir archivos, ver la lista de archivos "subidos" y simular acciones.
Incluye branding corporativo, colores y estilo KaiBot.
"""

import streamlit as st
from datetime import datetime
import os
import io
import pandas as pd

# -----------------------------
# Stubs para integración con GCloud (rellenar más tarde)
# -----------------------------

def gcloud_upload_file(file_buffer, destination_path, metadata=None):
    now = datetime.utcnow().isoformat() + "Z"
    return {
        "name": destination_path,
        "size": file_buffer.getbuffer().nbytes if hasattr(file_buffer, "getbuffer") else None,
        "uploaded_at": now,
        "metadata": metadata or {},
    }


def gcloud_list_files(prefix=None):
    return st.session_state.get("uploaded_files", [])


def gcloud_delete_file(name):
    files = st.session_state.get("uploaded_files", [])
    files = [f for f in files if f["name"] != name]
    st.session_state["uploaded_files"] = files
    return True

# -----------------------------
# Helpers
# -----------------------------

def init_session_state():
    if "uploaded_files" not in st.session_state:
        st.session_state["uploaded_files"] = []
    if "last_action" not in st.session_state:
        st.session_state["last_action"] = None


def add_uploaded_file_record(rec):
    files = st.session_state.get("uploaded_files", [])
    files.insert(0, rec)
    st.session_state["uploaded_files"] = files

# -----------------------------
# UI
# -----------------------------

st.set_page_config(page_title="KaiBot GCloud Uploader", layout="wide")
init_session_state()

# Estilo corporativo CSS
st.markdown(
    """
    <style>
    body {
        background-color: #f8fafc;
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    h1, h2, h3, h4 {
        color: #1E293B;
        font-family: 'Inter', sans-serif;
    }
    .stButton>button {
        background-color: #2563EB !important;
        color: white !important;
        border-radius: 10px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 600 !important;
        border: none !important;
    }
    .stButton>button:hover {
        background-color: #1D4ED8 !important;
    }
    .css-1v0mbdj, .css-18e3th9, .stTextInput>div>div>input, .stTextArea textarea {
        border-radius: 8px !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Encabezado corporativo
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image("https://kaibot.es/wp-content/uploads/2020/07/image1.png", width=100)
with col_title:
    st.title("KaiBot Cloud Storage Manager")
    st.markdown(
        "<h4 style='color:#334155;'>Plataforma corporativa para gestión, subida y supervisión de archivos en Google Cloud</h4>",
        unsafe_allow_html=True
    )

st.markdown("---")

# Layout principal
with st.sidebar:
    st.header("⚙️ Configuración")
    project_id = st.text_input("GCP Project ID", value="tu-project-id")
    bucket_name = st.text_input("Bucket / destino", value="tu-bucket")
    service_account = st.text_area("Credenciales (JSON) — opcional", height=120)
    st.markdown("---")
    st.write("Estado de la conexión: **No conectada** (modo mock).")
    st.button("Probar conexión (stub)", on_click=lambda: st.info("Función de prueba aún no implementada"))

col1, col2 = st.columns((2, 3))

with col1:
    st.subheader("📤 Subida de archivos")

    uploaded = st.file_uploader("Selecciona archivos", accept_multiple_files=True)

    st.markdown("**Metadatos opcionales**")
    tag = st.text_input("Tag / etiqueta (opcional)")
    preserve_name = st.checkbox("Preservar nombre de archivo al subir", value=True)

    if st.button("Simular subida"):
        if not uploaded:
            st.warning("No has seleccionado archivos.")
        else:
            progress = st.progress(0)
            total = len(uploaded)
            for i, f in enumerate(uploaded, start=1):
                file_bytes = f.read()
                buf = io.BytesIO(file_bytes)
                dest_name = f.name if preserve_name else f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{f.name}"
                dest_path = os.path.join(bucket_name, dest_name)
                meta = {"tag": tag} if tag else {}
                rec = gcloud_upload_file(buf, dest_path, metadata=meta)
                add_uploaded_file_record(rec)
                progress.progress(int(i/total * 100))
            st.success(f"{total} archivo(s) procesado(s) (simulado).")
            st.session_state["last_action"] = f"Subidos {total} archivos (simulado)"

    st.markdown("---")
    st.subheader("⚡ Acciones rápidas")
    if st.button("Limpiar lista local (simulado)"):
        st.session_state["uploaded_files"] = []
        st.success("Lista local limpiada.")

with col2:
    st.subheader("📁 Supervisión de archivos")

    files = gcloud_list_files()

    if not files:
        st.info("No hay archivos subidos todavía (modo mock). Usa 'Simular subida' para probar la UI.")
    else:
        df = pd.DataFrame([{
            "name": f["name"],
            "size_bytes": f.get("size"),
            "uploaded_at": f.get("uploaded_at"),
            "metadata": f.get("metadata"),
        } for f in files])

        st.dataframe(df, use_container_width=True)

        to_delete = st.multiselect("Selecciona archivos para borrar (simulado)", options=[f["name"] for f in files])
        if st.button("Borrar seleccionados (simulado)"):
            for name in to_delete:
                gcloud_delete_file(name)
            st.success(f"Borrados {len(to_delete)} archivo(s) (simulado).")

st.markdown("---")
st.write("Última acción:", st.session_state.get("last_action", "—"))

st.caption(
    "KaiBot Cloud Storage Manager — Versión mock para pruebas de interfaz.\n"
    "Sustituye las funciones gcloud_* por implementaciones reales con google-cloud-storage."
)
