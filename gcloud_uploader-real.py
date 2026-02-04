# KaiBot Cloud Storage Manager
# streamlit_gcloud_uploader.py

import streamlit as st
from datetime import datetime
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
# GCloud
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
    bucket.blob(name).delete()

# -----------------------------
# Firestore
# -----------------------------

def save_history(fs_client, record):
    fs_client.collection("upload_history").add(record)


def load_history(fs_client, limit=200):
    docs = (
        fs_client.collection("upload_history")
        .order_by("uploaded_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [d.to_dict() for d in docs]

# -----------------------------
# UI
# -----------------------------

st.set_page_config(page_title="KaiBot Cloud Storage Manager", layout="wide")

# Navegación
page = st.sidebar.radio(
    "🧭 Navegación",
    ["Gestión de archivos", "Consulta a tu agente de generación de contenidos"],
)

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
    st.caption("Gestión corporativa de archivos y agente de contenidos")

st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración GCloud")
    bucket_name = st.text_input("Bucket GCS")
    sa_json = st.text_area("Service Account JSON", height=220)
    enable_history = st.checkbox("Guardar historial en Firestore", value=False)

    if st.button("Conectar"):
        try:
            gcs_client = get_gcs_client_from_json(sa_json)
            st.session_state["gcs_client"] = gcs_client
            if enable_history:
                fs_client = get_firestore_client_from_json(sa_json)
                st.session_state["fs_client"] = fs_client
            st.success("Conectado correctamente a Google Cloud")
        except Exception as e:
            st.error(f"Error de conexión: {e}")

client = st.session_state.get("gcs_client")
fs_client = st.session_state.get("fs_client")

if not client:
    st.warning("Configura el acceso a GCloud en la barra lateral para continuar.")
    st.stop()

if page == "Gestión de archivos":
    col1, col2 = st.columns((2, 3))((2, 3))

# -----------------------------
# Subida
# -----------------------------
with col1:
    st.subheader("📤 Subida de archivos")

    # Ver carpetas existentes
    iterator = client.list_blobs(bucket_name, prefix="", delimiter="/")
    _ = list(iterator)
    existing_folders = sorted([p.rstrip("/") for p in iterator.prefixes])

    folder_mode = st.radio(
        "Destino",
        ["Elegir carpeta existente", "Crear nueva carpeta"],
        horizontal=True,
    )

    if folder_mode == "Elegir carpeta existente" and existing_folders:
        selected_folder = st.selectbox("Carpeta", existing_folders)
    else:
        selected_folder = st.text_input("Nombre de la carpeta", value="raw")

    uploaded = st.file_uploader("Selecciona archivos", accept_multiple_files=True)
    tag = st.text_input("Etiqueta (tag)")

    if st.button("Subir archivos"):
        if not uploaded:
            st.warning("No hay archivos seleccionados")
        else:
            for f in uploaded:
                buf = io.BytesIO(f.read())
                meta = {"tag": tag} if tag else {}
                destination = f"{selected_folder.strip('/')}/{f.name}"
                rec = gcloud_upload_file(client, bucket_name, buf, destination, meta)
                if enable_history and fs_client:
                    save_history(fs_client, rec)
            st.success(f"{len(uploaded)} archivo(s) subidos correctamente")

    st.markdown("---")
    st.subheader("🧾 Documentación adicional")

    web_url = st.text_input("Página web")
    linkedin_url = st.text_input("LinkedIn")

    if st.button("Guardar documentación"):
        if not web_url and not linkedin_url:
            st.warning("Introduce al menos un campo")
        else:
            payload = {
                "web": web_url,
                "linkedin": linkedin_url,
                "timestamp": datetime.utcnow().isoformat(),
            }
            json_bytes = io.BytesIO(json.dumps(payload, indent=2).encode("utf-8"))
            filename = f"documentacion_adicional/info_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            gcloud_upload_file(
                client,
                bucket_name,
                json_bytes,
                filename,
                metadata={"type": "documentacion_adicional"},
            )
            st.success("Documentación guardada correctamente")

# -----------------------------
# Listado
# -----------------------------
with col2:
    st.subheader("📁 Archivos en el bucket")

    records = gcloud_list_files(client, bucket_name)
    df = pd.DataFrame(records)

    if not df.empty:
        folders_df = df[df.apply(lambda r: r["name"].endswith("/") and r["size"] == 0, axis=1)]
        files_df = df[~df.index.isin(folders_df.index)]

        st.markdown("**📁 Carpetas**")
        if not folders_df.empty:
            st.dataframe(folders_df[["name", "uploaded_at"]], use_container_width=True)
        else:
            st.caption("No hay carpetas")

        st.markdown("**📄 Archivos**")
        tag_filter = st.text_input("Filtrar por tag")
        if tag_filter:
            files_df = files_df[files_df["metadata"].astype(str).str.contains(tag_filter)]

        if not files_df.empty:
            st.dataframe(files_df[["name", "size", "uploaded_at", "metadata"]], use_container_width=True)

            to_delete = st.multiselect("Borrar archivos", options=files_df["name"].tolist())
            if st.button("Eliminar seleccionados"):
                for name in to_delete:
                    gcloud_delete_file(client, bucket_name, name)
                st.success("Archivos eliminados")
        else:
            st.caption("No hay archivos")
    else:
        st.info("El bucket está vacío")

# -----------------------------
# Historial
# -----------------------------
if page == "Gestión de archivos" means enable_history and fs_client:
    st.markdown("---")
    st.subheader("🕒 Historial de subidas")
    history = load_history(fs_client)
    if history:
        st.dataframe(pd.DataFrame(history), use_container_width=True)
    else:
        st.caption("Sin historial aún")

# -----------------------------
# Agente de generación de contenidos
# -----------------------------
if page == "Consulta a tu agente de generación de contenidos":
    import openai

    st.subheader("🤖 Consulta a tu agente de generación de contenidos")

    st.markdown(
        "Este agente utiliza la documentación almacenada en Google Cloud Storage "
        "para generar respuestas estructuradas en JSON."
    )

    openai_key = st.text_input("OpenAI API Key", type="password")

    system_prompt = st.text_area(
        "Instrucciones del agente (system prompt)",
        value=(
            "Eres un agente de generación de contenidos corporativos. "
            "Debes responder SIEMPRE en formato JSON válido siguiendo este esquema:
"
            "{
"
            "  \"summary\": string,
"
            "  \"key_points\": [string],
"
            "  \"recommended_actions\": [string]
"
            "}"
        ),
        height=180,
    )

    user_prompt = st.text_area(
        "Consulta",
        placeholder="Ej: Genera una descripción corporativa basada en la web y LinkedIn",
        height=150,
    )

    # -------- Leer documentación adicional desde GCS --------
    def load_agent_context(client, bucket_name):
        """
        Lee y agrega como contexto TODOS los archivos JSON y de texto
        de las carpetas relevantes del agente.
        """
        prefixes = [
            "Documentos_agente/",
            "documentacion_adicional/",
            "documentos_validados/",
        ]

        context = {
            "Documentos_agente": [],
            "documentacion_adicional": [],
            "documentos_validados": [],
        }

        for prefix in prefixes:
            blobs = client.list_blobs(bucket_name, prefix=prefix)
            for b in blobs:
                try:
                    # JSON
                    if b.name.endswith(".json"):
                        content = json.loads(b.download_as_text())
                    # Texto plano (txt, md)
                    elif b.name.endswith((".txt", ".md")):
                        content = b.download_as_text()
                    else:
                        continue

                    key = prefix.rstrip("/")
                    context[key].append({
                        "file": b.name,
                        "content": content,
                    })
                except Exception:
                    continue

        return context

    if st.button("Consultar agente"):
        if not openai_key or not user_prompt:
            st.warning("Introduce la API Key y una consulta")
        else:
            # Cargar contexto completo del agente
            context_data = load_agent_context(client, bucket_name)
            context_text = json.dumps(context_data, indent=2)(context_docs, indent=2)

            openai.api_key = openai_key

            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        "Contexto disponible (JSON):
"
                        f"{context_text}

"
                        "Consulta:
"
                        f"{user_prompt}"
                    ),
                },
            ]

            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.3,
                )

                raw_content = response.choices[0].message["content"]
                parsed = json.loads(raw_content)

                # Guardar respuesta en GCS
                output = {
                    "query": user_prompt,
                    "response": parsed,
                    "generated_at": datetime.utcnow().isoformat(),
                }

                out_bytes = io.BytesIO(json.dumps(output, indent=2).encode("utf-8"))
                out_name = (
                    "respuestas_agente/"
                    f"response_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
                )

                gcloud_upload_file(
                    client,
                    bucket_name,
                    out_bytes,
                    out_name,
                    metadata={"type": "agent_response"},
                )

                st.success("Respuesta generada y almacenada")
                st.json(parsed)

            except Exception as e:
                st.error(f"Error al consultar OpenAI: {e}")
