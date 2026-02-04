# KaiBot Cloud Storage Manager
# streamlit_gcloud_uploader.py

import streamlit as st
from datetime import datetime
import io
import json
import pandas as pd
import traceback

from google.cloud import storage
from google.cloud import firestore
from google.oauth2 import service_account

# -----------------------------
# Helpers de autenticación
# -----------------------------

def get_gcs_client_from_json(sa_json_str):
    """Crea cliente de Google Cloud Storage desde JSON de service account"""
    try:
        info = json.loads(sa_json_str)
        creds = service_account.Credentials.from_service_account_info(info)
        return storage.Client(credentials=creds, project=info.get("project_id"))
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON inválido: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error al crear cliente GCS: {str(e)}")


def get_firestore_client_from_json(sa_json_str):
    """Crea cliente de Firestore desde JSON de service account"""
    try:
        info = json.loads(sa_json_str)
        creds = service_account.Credentials.from_service_account_info(info)
        return firestore.Client(credentials=creds, project=info.get("project_id"))
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON inválido: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error al crear cliente Firestore: {str(e)}")

# -----------------------------
# GCloud Operations
# -----------------------------

def gcloud_upload_file(client, bucket_name, file_buffer, destination_path, metadata=None):
    """Sube un archivo a Google Cloud Storage"""
    try:
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
    except Exception as e:
        raise Exception(f"Error al subir archivo {destination_path}: {str(e)}")


def gcloud_list_files(client, bucket_name):
    """Lista todos los archivos en el bucket"""
    try:
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
    except Exception as e:
        raise Exception(f"Error al listar archivos: {str(e)}")


def gcloud_delete_file(client, bucket_name, name):
    """Elimina un archivo del bucket"""
    try:
        bucket = client.bucket(bucket_name)
        bucket.blob(name).delete()
    except Exception as e:
        raise Exception(f"Error al eliminar {name}: {str(e)}")


def get_existing_folders(client, bucket_name):
    """Obtiene las carpetas existentes en el bucket"""
    try:
        iterator = client.list_blobs(bucket_name, prefix="", delimiter="/")
        _ = list(iterator)
        return sorted([p.rstrip("/") for p in iterator.prefixes])
    except Exception as e:
        st.warning(f"No se pudieron obtener carpetas: {str(e)}")
        return []

# -----------------------------
# Firestore Operations
# -----------------------------

def save_history(fs_client, record):
    """Guarda registro en historial de Firestore"""
    try:
        fs_client.collection("upload_history").add(record)
    except Exception as e:
        st.warning(f"No se pudo guardar en historial: {str(e)}")


def load_history(fs_client, limit=200):
    """Carga historial desde Firestore"""
    try:
        docs = (
            fs_client.collection("upload_history")
            .order_by("uploaded_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [d.to_dict() for d in docs]
    except Exception as e:
        st.warning(f"Error al cargar historial: {str(e)}")
        return []

# -----------------------------
# UI Configuration
# -----------------------------

st.set_page_config(page_title="KaiBot Cloud Storage Manager", layout="wide")

# Custom CSS
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

# Navegación
page = st.sidebar.radio(
    "🧭 Navegación",
    ["Gestión de archivos", "Consulta a tu agente de generación de contenidos"],
)

# -----------------------------
# Sidebar - Configuración
# -----------------------------

with st.sidebar:
    st.header("⚙️ Configuración GCloud")
    bucket_name = st.text_input("Bucket GCS", help="Nombre del bucket de Google Cloud Storage")
    sa_json = st.text_area(
        "Service Account JSON", 
        height=220,
        help="Pega aquí el JSON completo de tu service account"
    )
    enable_history = st.checkbox("Guardar historial en Firestore", value=False)

    if st.button("Conectar"):
        if not bucket_name:
            st.error("⚠️ Debes especificar un nombre de bucket")
        elif not sa_json:
            st.error("⚠️ Debes proporcionar las credenciales del service account")
        else:
            try:
                gcs_client = get_gcs_client_from_json(sa_json)
                st.session_state["gcs_client"] = gcs_client
                st.session_state["bucket_name"] = bucket_name
                
                if enable_history:
                    fs_client = get_firestore_client_from_json(sa_json)
                    st.session_state["fs_client"] = fs_client
                    st.session_state["enable_history"] = True
                else:
                    st.session_state["enable_history"] = False
                
                st.success("✅ Conectado correctamente a Google Cloud")
            except Exception as e:
                st.error(f"❌ Error de conexión: {e}")

# Obtener clientes de session_state
client = st.session_state.get("gcs_client")
bucket_name = st.session_state.get("bucket_name", bucket_name)
fs_client = st.session_state.get("fs_client")
enable_history = st.session_state.get("enable_history", False)

if not client:
    st.warning("⚠️ Configura el acceso a GCloud en la barra lateral para continuar.")
    st.stop()

# -----------------------------
# PÁGINA: Gestión de archivos
# -----------------------------

if page == "Gestión de archivos":
    col1, col2 = st.columns((2, 3))

    # -----------------------------
    # Subida de archivos
    # -----------------------------
    with col1:
        st.subheader("📤 Subida de archivos")

        # Ver carpetas existentes
        existing_folders = get_existing_folders(client, bucket_name)

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
        tag = st.text_input("Etiqueta (tag)", help="Opcional: añade una etiqueta para clasificar")

        if st.button("Subir archivos"):
            if not uploaded:
                st.warning("⚠️ No hay archivos seleccionados")
            else:
                success_count = 0
                error_count = 0
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for idx, f in enumerate(uploaded):
                    try:
                        status_text.text(f"Subiendo {f.name}...")
                        buf = io.BytesIO(f.read())
                        meta = {"tag": tag} if tag else {}
                        destination = f"{selected_folder.strip('/')}/{f.name}"
                        
                        rec = gcloud_upload_file(client, bucket_name, buf, destination, meta)
                        
                        if enable_history and fs_client:
                            save_history(fs_client, rec)
                        
                        success_count += 1
                    except Exception as e:
                        st.error(f"❌ Error al subir {f.name}: {str(e)}")
                        error_count += 1
                    
                    progress_bar.progress((idx + 1) / len(uploaded))
                
                status_text.empty()
                progress_bar.empty()
                
                if success_count > 0:
                    st.success(f"✅ {success_count} archivo(s) subidos correctamente")
                if error_count > 0:
                    st.error(f"❌ {error_count} archivo(s) fallaron")

        st.markdown("---")
        st.subheader("🧾 Documentación adicional")

        web_url = st.text_input("Página web", placeholder="https://example.com")
        linkedin_url = st.text_input("LinkedIn", placeholder="https://linkedin.com/company/...")

        if st.button("Guardar documentación"):
            if not web_url and not linkedin_url:
                st.warning("⚠️ Introduce al menos un campo")
            else:
                try:
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
                    st.success("✅ Documentación guardada correctamente")
                except Exception as e:
                    st.error(f"❌ Error al guardar documentación: {str(e)}")

    # -----------------------------
    # Listado de archivos
    # -----------------------------
    with col2:
        st.subheader("📁 Archivos en el bucket")

        try:
            records = gcloud_list_files(client, bucket_name)
            df = pd.DataFrame(records)

            if not df.empty:
                # Separar carpetas de archivos
                folders_df = df[df.apply(lambda r: r["name"].endswith("/") and r["size"] == 0, axis=1)]
                files_df = df[~df.index.isin(folders_df.index)]

                st.markdown("**📁 Carpetas**")
                if not folders_df.empty:
                    st.dataframe(folders_df[["name", "uploaded_at"]], use_container_width=True)
                else:
                    st.caption("No hay carpetas")

                st.markdown("**📄 Archivos**")
                tag_filter = st.text_input("🔍 Filtrar por tag")
                
                if tag_filter:
                    files_df = files_df[files_df["metadata"].astype(str).str.contains(tag_filter, case=False)]

                if not files_df.empty:
                    st.dataframe(
                        files_df[["name", "size", "uploaded_at", "metadata"]], 
                        use_container_width=True
                    )

                    to_delete = st.multiselect("🗑️ Borrar archivos", options=files_df["name"].tolist())
                    
                    if st.button("Eliminar seleccionados"):
                        if to_delete:
                            success_count = 0
                            error_count = 0
                            
                            for name in to_delete:
                                try:
                                    gcloud_delete_file(client, bucket_name, name)
                                    success_count += 1
                                except Exception as e:
                                    st.error(f"Error al eliminar {name}: {str(e)}")
                                    error_count += 1
                            
                            if success_count > 0:
                                st.success(f"✅ {success_count} archivo(s) eliminados")
                            if error_count > 0:
                                st.error(f"❌ {error_count} archivo(s) no se pudieron eliminar")
                            st.rerun()
                        else:
                            st.warning("⚠️ No hay archivos seleccionados")
                else:
                    st.caption("No hay archivos que coincidan con el filtro")
            else:
                st.info("ℹ️ El bucket está vacío")
        
        except Exception as e:
            st.error(f"❌ Error al listar archivos: {str(e)}")

    # -----------------------------
    # Historial (dentro de Gestión de archivos)
    # -----------------------------
    if enable_history and fs_client:
        st.markdown("---")
        st.subheader("🕒 Historial de subidas")
        
        try:
            history = load_history(fs_client)
            if history:
                history_df = pd.DataFrame(history)
                st.dataframe(history_df, use_container_width=True)
            else:
                st.caption("Sin historial aún")
        except Exception as e:
            st.error(f"❌ Error al cargar historial: {str(e)}")

# -----------------------------
# PÁGINA: Agente de generación de contenidos
# -----------------------------

elif page == "Consulta a tu agente de generación de contenidos":
    st.subheader("🤖 Consulta a tu agente de generación de contenidos")

    st.markdown(
        """
        Este agente utiliza la información almacenada en Google Cloud Storage 
        (documentación adicional, archivos y contexto) para generar respuestas estructuradas.
        
        **Nota:** Esta es una versión de demostración. Para implementar la funcionalidad completa,
        necesitarás integrar con la API de OpenAI o Claude.
        """
    )

    # Configuración del agente
    with st.expander("⚙️ Configuración del agente", expanded=True):
        openai_key = st.text_input(
            "OpenAI API Key", 
            type="password",
            help="Tu clave de API de OpenAI"
        )
        
        system_prompt = st.text_area(
            "Instrucciones del agente (system prompt)",
            value="Eres un agente de generación de contenidos corporativos. Responde siempre en formato JSON con los campos: summary, key_points, y next_steps.",
            height=120,
        )

    # Consulta
    user_prompt = st.text_area(
        "Consulta",
        placeholder="Ej: Genera una descripción corporativa basada en la web y LinkedIn almacenados",
        height=150,
    )

    # Opciones avanzadas
    with st.expander("🔧 Opciones avanzadas"):
        include_files = st.checkbox("Incluir contexto de archivos almacenados", value=True)
        max_tokens = st.slider("Máximo de tokens", 100, 4000, 1000)
        temperature = st.slider("Temperatura", 0.0, 1.0, 0.7, 0.1)

    if st.button("Consultar agente", type="primary"):
        if not openai_key:
            st.error("⚠️ Debes proporcionar una API Key de OpenAI")
        elif not user_prompt:
            st.warning("⚠️ Introduce una consulta")
        else:
            with st.spinner("🤖 Generando respuesta..."):
                try:
                    # TODO: Aquí deberías implementar la llamada real a OpenAI
                    # Por ahora, mostramos una respuesta de ejemplo
                    
                    response = {
                        "query": user_prompt,
                        "status": "ok",
                        "generated_at": datetime.utcnow().isoformat(),
                        "config": {
                            "max_tokens": max_tokens,
                            "temperature": temperature,
                            "system_prompt": system_prompt[:100] + "..."
                        },
                        "result": {
                            "summary": "Esta es una respuesta de demostración. Para obtener respuestas reales, implementa la integración con OpenAI API usando el código comentado en el archivo.",
                            "key_points": [
                                "Configuración correcta del sistema",
                                "Validación de credenciales exitosa",
                                "Listo para integración con LLM"
                            ],
                            "next_steps": [
                                "Implementar llamada a OpenAI API",
                                "Cargar contexto desde GCS",
                                "Validar y formatear respuesta",
                                "Guardar resultado en Firestore (opcional)"
                            ],
                        },
                    }

                    st.success("✅ Respuesta generada")
                    
                    # Mostrar respuesta en formato legible
                    st.json(response)
                    
                    # Opción para descargar
                    json_str = json.dumps(response, indent=2, ensure_ascii=False)
                    st.download_button(
                        label="📥 Descargar respuesta JSON",
                        data=json_str,
                        file_name=f"agent_response_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )
                    
                except Exception as e:
                    st.error(f"❌ Error al consultar agente: {str(e)}")
                    st.code(traceback.format_exc())

    # Instrucciones para implementar
    with st.expander("💡 Cómo implementar la integración real con OpenAI"):
        st.markdown("""
        ```python
        import openai
        
        # Configurar cliente
        openai.api_key = openai_key
        
        # Obtener contexto de GCS (opcional)
        context = ""
        if include_files:
            # Cargar archivos relevantes desde GCS
            docs = load_documentation_from_gcs(client, bucket_name)
            context = "\\n".join([doc['content'] for doc in docs])
        
        # Llamada a OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{context}\\n\\n{user_prompt}"}
            ],
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        result = response.choices[0].message.content
        ```
        """)
