# KaiBot Cloud Storage Manager — DEMO SIN BILLING
# --------------------------------------------------
# Aplicación Streamlit corporativa para gestión de archivos en GCS
# y simulación avanzada de agentes de generación y validación de contenidos

import streamlit as st
from datetime import datetime
import io
import json
import pandas as pd

from google.cloud import storage
from google.oauth2 import service_account

# =============================
# CONFIG STREAMLIT
# =============================

st.set_page_config(page_title="KaiBot Cloud Storage Manager", layout="wide")

st.markdown(
    """
    <style>
    body { background-color: #f8fafc; }
    h1, h2, h3 { color: #1E293B; }
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

# =============================
# HELPERS GCS
# =============================

def get_gcs_client_from_json(sa_json_str):
    info = json.loads(sa_json_str)
    creds = service_account.Credentials.from_service_account_info(info)
    return storage.Client(credentials=creds, project=info.get("project_id"))


def list_folders_and_files(client, bucket_name):
    bucket = client.bucket(bucket_name)
    blobs = bucket.list_blobs()

    records = []
    for b in blobs:
        records.append({
            "path": b.name,
            "size": b.size,
            "created": b.time_created,
        })
    return records


def upload_file(client, bucket_name, buffer, destination):
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination)
    blob.upload_from_file(buffer, rewind=True)


def delete_file(client, bucket_name, path):
    bucket = client.bucket(bucket_name)
    bucket.blob(path).delete()


def load_additional_documentation(client, bucket_name):
    bucket = client.bucket(bucket_name)
    blobs = bucket.list_blobs(prefix="documentacion_adicional/")

    sources = []
    for blob in blobs:
        if blob.name.endswith(".json"):
            data = json.loads(blob.download_as_text())
            if data.get("web"):
                sources.append({"type": "web", "url": data["web"]})
            if data.get("linkedin"):
                sources.append({"type": "linkedin", "url": data["linkedin"]})
    return sources

# =============================
# HEADER
# =============================

col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image("https://kaibot.es/wp-content/uploads/2020/07/image1.png", width=90)
with col_title:
    st.title("KaiBot Cloud Storage Manager")
    st.caption("Demo corporativa sin billing — flujo completo de agente IA")

st.markdown("---")

# =============================
# SIDEBAR CONFIG (SIN CAMBIAR FLUJO ORIGINAL)
# =============================

with st.sidebar:
    st.header("⚙️ Configuración")

    st.subheader("Google Cloud")
    bucket_name = st.text_input("Bucket GCS")
    sa_json = st.text_area("Service Account JSON", height=180)

    st.markdown("---")
    st.subheader("OpenAI (agente real)")
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    model_name = st.text_input("Modelo", value="gpt-4.1-mini")
    max_tokens = st.slider("Max tokens", 256, 4096, 1024)

    if st.button("Conectar"):
        try:
            st.session_state["gcs_client"] = get_gcs_client_from_json(sa_json)
            st.session_state["openai_api_key"] = openai_api_key
            st.success("Configuración cargada")
        except Exception as e:
            st.error(f"Error de conexión: {e}")

client = st.session_state.get("gcs_client")
if not client:
    st.warning("Configura GCloud en la barra lateral")
    st.stop()

# =============================
# LAYOUT PRINCIPAL
# =============================

col1, col2 = st.columns((2, 3))

# -----------------------------
# SUBIDA DE ARCHIVOS
# -----------------------------

with col1:
    st.subheader("📤 Subida de archivos")

    uploaded = st.file_uploader("Selecciona archivos", accept_multiple_files=True)
    folder = st.text_input("Carpeta destino (opcional)")

    if st.button("Subir archivos"):
        if not uploaded:
            st.warning("No hay archivos")
        else:
            for f in uploaded:
                buf = io.BytesIO(f.read())
                path = f"{folder}/{f.name}" if folder else f.name
                upload_file(client, bucket_name, buf, path)
            st.success("Archivos subidos correctamente")

    st.markdown("---")
    st.subheader("🌐 Documentación adicional")

    web_url = st.text_input("URL Web")
    linkedin_url = st.text_input("URL LinkedIn")

    if st.button("Guardar documentación adicional"):
        if not web_url and not linkedin_url:
            st.warning("Introduce al menos una URL")
        else:
            payload = {
                "web": web_url,
                "linkedin": linkedin_url,
                "created_at": datetime.utcnow().isoformat(),
            }
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            blob = client.bucket(bucket_name).blob(
                f"documentacion_adicional/info_{ts}.json"
            )
            blob.upload_from_string(
                json.dumps(payload, indent=2, ensure_ascii=False),
                content_type="application/json",
            )
            st.success("Documentación guardada")

# -----------------------------
# EXPLORADOR
# -----------------------------

with col2:
    st.subheader("📁 Explorador del bucket")

    records = list_folders_and_files(client, bucket_name)
    if records:
        df = pd.DataFrame(records)
        st.dataframe(df, use_container_width=True)

        to_delete = st.multiselect("Eliminar archivos", df["path"].tolist())
        if st.button("Eliminar seleccionados"):
            for p in to_delete:
                delete_file(client, bucket_name, p)
            st.success("Archivos eliminados")
    else:
        st.info("Bucket vacío")

# =============================
# AGENTE SIMULADO AVANZADO
# =============================

st.markdown("---")
st.header("🧪 Agente DEMO — Generación y validación")

files_for_agent = [r["path"] for r in records]
selected_files = st.multiselect("Archivos de contexto", files_for_agent)

if st.button("Generar JSON (simulado)"):
    sources = load_additional_documentation(client, bucket_name)

    simulated = {
        "agent": "content_generation_agent",
        "mode": "demo",
        "created_at": datetime.utcnow().isoformat(),
        "analysis": {
            "documents_used": selected_files,
            "external_sources": sources,
        },
        "output": {
            "summary": "Resumen simulado coherente basado en documentos internos y fuentes externas.",
            "key_insights": [
                "Coherencia entre documentación interna y web corporativa.",
                "LinkedIn refuerza la credibilidad institucional.",
            ],
            "recommendations": [
                "Unificar tono corporativo.",
                "Ampliar casos de uso públicos.",
            ],
        },
        "sources_cited": sources,
    }

    st.session_state["demo_json"] = json.dumps(simulated, indent=2, ensure_ascii=False)

if "demo_json" in st.session_state:
    st.subheader("📄 JSON del agente")
    edited_json = st.text_area("JSON editable", st.session_state["demo_json"], height=260)

    if st.button("Validar con Perplexity (simulado)"):
        validation = """
VALIDACIÓN EXTERNA — SIMULACIÓN TIPO PERPLEXITY
----------------------------------------------
El contenido es coherente con las fuentes citadas.
No se detectan contradicciones relevantes.
Se recomienda validación editorial final.

Nivel de confianza: ALTO
"""
        st.session_state["validation_text"] = validation
        st.session_state["validated_json"] = edited_json

if "validation_text" in st.session_state:
    st.subheader("🧠 Resultado del validador")
    st.text_area("Respuesta", st.session_state["validation_text"], height=180)

    if st.button("✅ Aprobar y guardar"):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        blob = client.bucket(bucket_name).blob(
            f"documentos_validados/resultado_{ts}.json"
        )
        blob.upload_from_string(
            st.session_state["validated_json"], content_type="application/json"
        )
        st.success("Documento validado y almacenado")
