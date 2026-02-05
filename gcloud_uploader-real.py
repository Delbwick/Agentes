# KaiBot Cloud Storage Manager + Content Agent (STABLE VERSION)
# Demo + Producción controlada

import streamlit as st
from datetime import datetime
import io
import json
import pandas as pd

from google.cloud import storage
from google.oauth2 import service_account
from openai import OpenAI

# =====================================================
# Helpers GCP
# =====================================================

def get_gcs_client_from_json(sa_json_str: str) -> storage.Client:
    info = json.loads(sa_json_str)
    creds = service_account.Credentials.from_service_account_info(info)
    return storage.Client(credentials=creds, project=info.get("project_id"))


def list_folders_and_files(client: storage.Client, bucket_name: str):
    bucket = client.bucket(bucket_name)
    blobs = bucket.list_blobs()

    folders = set()
    files = []

    for b in blobs:
        parts = b.name.split("/")
        if len(parts) > 1:
            folders.add(parts[0] + "/")
        files.append(
            {
                "name": b.name,
                "size": b.size,
                "updated": b.updated,
            }
        )

    return sorted(folders), files


def upload_file(client: storage.Client, bucket_name: str, file, folder: str):
    bucket = client.bucket(bucket_name)
    path = f"{folder.rstrip('/')}/{file.name}"
    blob = bucket.blob(path)
    blob.upload_from_file(file, rewind=True)


# =====================================================
# Context loader (SAFE)
# =====================================================

def load_selected_context(client, bucket_name, selected_files, max_chars):
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

        texts.append(
            f"""### {name}
{content}"""
        )

        total_chars += len(content)

    return "\n\n".join(texts)


# =====================================================
# UI CONFIG
# =====================================================

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
    st.caption("Gestión documental + agente de contenidos (modo demo y real)")

st.markdown("---")

# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:
    st.header("⚙️ Configuración")

    bucket_name = st.text_input("Bucket GCS")
    sa_json = st.text_area("Service Account JSON", height=220)
    openai_key = st.text_input("OpenAI API Key", type="password")

    if st.button("Conectar"):
        try:
            st.session_state.gcs = get_gcs_client_from_json(sa_json)
            if openai_key:
                st.session_state.openai = OpenAI(api_key=openai_key)
            st.success("Conectado correctamente")
        except Exception as e:
            st.error(e)

if "gcs" not in st.session_state:
    st.warning("Configura la conexión para continuar")
    st.stop()

client = st.session_state.gcs

# =====================================================
# TABS
# =====================================================

tab1, tab2 = st.tabs(["📁 Gestión de Archivos", "🤖 Agentes"])

# =====================================================
# TAB 1 - FILE MANAGEMENT
# =====================================================

with tab1:
    folders, files = list_folders_and_files(client, bucket_name)

    st.subheader("📤 Subida de archivos")

    col1, col2 = st.columns([2, 1])
    with col1:
        folder = st.selectbox("Carpeta destino", options=folders)
        uploaded = st.file_uploader("Selecciona archivos", accept_multiple_files=True)
    with col2:
        new_folder = st.text_input("Crear nueva carpeta")

    target_folder = f"{new_folder.strip()}/" if new_folder else folder

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

# =====================================================
# TAB 2 - AGENTS
# =====================================================

with tab2:
    st.subheader("🤖 Agente real (OpenAI)")

    system_prompt = st.text_area(
        "System prompt",
        value="""Eres un agente de generación de contenidos corporativos.
Debes responder SIEMPRE en formato JSON válido siguiendo este esquema:
{
  "summary": string,
  "key_points": [string],
  "recommended_actions": [string]
}
No añadas texto fuera del JSON.""",
        height=180,
    )

    user_query = st.text_area("Consulta", height=100)

    folders, files = list_folders_and_files(client, bucket_name)
    file_names = [f["name"] for f in files]

    selected_files = st.multiselect("Archivos de contexto", options=file_names)

    max_chars = st.slider(
        "Límite de caracteres de contexto",
        min_value=1000,
        max_value=20000,
        value=8000,
        step=500,
    )

    if st.button("Ejecutar agente real"):
        if "openai" not in st.session_state:
            st.error("No hay API key configurada")
            st.stop()
        if not selected_files:
            st.warning("Selecciona archivos de contexto")
            st.stop()

        context = load_selected_context(
            client, bucket_name, selected_files, max_chars
        )

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

            st.json(json.loads(response.output_text))
        except Exception:
            st.error("Error al ejecutar el agente real")

    st.markdown("---")
    st.subheader("🎯 Agente demo (guiado)")

    demo_queries = [
        "Resume los puntos clave de la documentación",
        "Genera un resumen ejecutivo",
        "Detecta riesgos o incoherencias",
    ]

    demo_query = st.selectbox("Consulta demo", demo_queries)

    if st.button("Ejecutar agente demo"):
        if "openai" not in st.session_state:
            st.error("No hay API key configurada")
            st.stop()
        if not selected_files:
            st.warning("Selecciona archivos de contexto")
            st.stop()

        context = load_selected_context(
            client, bucket_name, selected_files, max_chars
        )

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

            st.json(json.loads(response.output_text))
        except Exception:
            st.error("Error al ejecutar el agente demo")

    st.markdown("---")
    st.subheader("🧪 Agente simulado (sin APIs)")

    simulated_query = st.text_input(
        "Consulta simulada",
        value="Genera un resumen ejecutivo de la documentación",
    )

    if st.button("Generar respuesta simulada"):
        simulated_response = {
            "summary": "Resumen ejecutivo simulado para demostración.",
            "key_points": [
                "Insight simulado 1",
                "Insight simulado 2",
                "Insight simulado 3",
            ],
            "recommended_actions": [
                "Acción simulada 1",
                "Acción simulada 2",
            ],
            "meta": {
                "mode": "simulated",
                "query": simulated_query,
                "generated_at": datetime.utcnow().isoformat() + "Z",
            },
        }

        st.json(simulated_response)

        st.download_button(
            "⬇️ Descargar JSON",
            json.dumps(simulated_response, indent=2),
            file_name="respuesta_agente_demo.json",
            mime="application/json",
        )


# =============================
# AGENTE SIMULADO (SIN APIs)
# =============================

st.markdown("---")
st.header("🧪 Agente DEMO / Simulación completa")
st.caption("Flujo demo: generación JSON → validación simulada tipo Perplexity → aprobación")

# --- Generación simulada del JSON
if st.button("Generar JSON (simulado)"):
    simulated_json = {
        "summary": "Resumen simulado del contenido basado en los documentos seleccionados.",
        "key_points": [
            "Punto clave 1 generado en modo demo",
            "Punto clave 2 generado en modo demo",
            "Punto clave 3 generado en modo demo",
        ],
        "recommended_actions": [
            "Acción recomendada A",
            "Acción recomendada B",
        ],
    }
    st.session_state["demo_json"] = json.dumps(simulated_json, indent=2, ensure_ascii=False)

# Mostrar / editar JSON
if "demo_json" in st.session_state:
    st.subheader("📄 JSON generado por el agente")
    edited_json = st.text_area(
        "JSON editable (puedes corregirlo antes de validar)",
        value=st.session_state["demo_json"],
        height=260,
    )

    # --- Validación simulada tipo Perplexity
    if st.button("Validar con Perplexity (simulado)"):
        validation_text = (
            "VALIDACIÓN SIMULADA (Perplexity)\n"
            "----------------------------------\n"
            "El contenido es coherente, claro y alineado con el contexto proporcionado.\n"
            "Se recomienda validar el tono final antes de publicación."
        )
        st.session_state["validation_text"] = validation_text
        st.session_state["validated_json"] = edited_json

# Mostrar validación
if "validation_text" in st.session_state:
    st.subheader("🧠 Respuesta del validador (texto)")
    st.text_area(
        "Resultado de validación",
        value=st.session_state["validation_text"],
        height=160,
    )

    # --- Aprobación final
    col_ok, col_cancel = st.columns(2)

    with col_ok:
        if st.button("✅ Aprobar y guardar en documentos_validados/"):
            bucket = client.bucket(bucket_name)
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            blob = bucket.blob(f"documentos_validados/resultado_{ts}.json")
            blob.upload_from_string(
                st.session_state["validated_json"], content_type="application/json"
            )
            st.success("Documento validado y almacenado correctamente")

    with col_cancel:
        st.info("Puedes modificar el JSON y volver a validar antes de aprobar")
