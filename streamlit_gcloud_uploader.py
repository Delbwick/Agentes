"""
Streamlit app - Interfaz para subir y supervisar archivos en una instancia de GCloud
Archivo: streamlit_gcloud_uploader.py
Descripción: Interfaz (mock) que permite subir archivos, ver la lista de archivos "subidos" y simular acciones
Nota: Las funciones de conexión con Google Cloud Storage están como stubs para que las rellenes después.

Instrucciones de uso:
1. Instala dependencias: pip install streamlit
2. Ejecuta: streamlit run streamlit_gcloud_uploader.py

El app usa session_state para mantener la lista de archivos mientras la sesión está activa.
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
    """
    Stub: subirá file_buffer a GCloud en destination_path.
    Por ahora solo devuelve un dict simulado con metadatos.
    Reemplaza por la implementación real cuando estés listo.
    """
    # Simulación: generar metadatos
    now = datetime.utcnow().isoformat() + "Z"
    return {
        "name": destination_path,
        "size": file_buffer.getbuffer().nbytes if hasattr(file_buffer, "getbuffer") else None,
        "uploaded_at": now,
        "metadata": metadata or {},
    }


def gcloud_list_files(prefix=None):
    """Stub: devolverá la lista de archivos en GCloud. Por ahora devuelve la lista local en session_state."""
    # La app centraliza la lista en session_state['uploaded_files']
    return st.session_state.get("uploaded_files", [])


def gcloud_delete_file(name):
    """Stub: borrará un archivo en GCloud. Por ahora actualiza session_state."""
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
    files.insert(0, rec)  # mostrar más reciente primero
    st.session_state["uploaded_files"] = files


# -----------------------------
# UI
# -----------------------------

st.set_page_config(page_title="GCloud Uploader - Interfaz", layout="wide")
init_session_state()

st.title("Interfaz de subida y supervisión — GCloud (mock)")
st.write("Eres experto — esta interfaz está preparada para que conectes tus funciones de GCloud cuando quieras.")

# Layout: sidebar para configuración, main para subir y supervisión
with st.sidebar:
    st.header("Configuración (placeholder)")
    project_id = st.text_input("GCP Project ID", value="tu-project-id")
    bucket_name = st.text_input("Bucket / destino", value="tu-bucket")
    service_account = st.text_area("Credenciales (JSON) — opcional", height=120)
    st.markdown("---")
    st.write("Estado de la conexión: **No conectada** (interfaz mock).")
    st.button("Probar conexión (stub)", on_click=lambda: st.info("Función de prueba aún no implementada"))

# Main columns
col1, col2 = st.columns((2, 3))

with col1:
    st.subheader("Subir archivos")

    uploaded = st.file_uploader("Selecciona archivos", accept_multiple_files=True)

    # Metadatos opcionales
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
                # leer como buffer
                file_bytes = f.read()
                buf = io.BytesIO(file_bytes)

                dest_name = f.name if preserve_name else f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{f.name}"
                dest_path = os.path.join(bucket_name, dest_name)

                # metadata
                meta = {"tag": tag} if tag else {}

                # llamar al stub
                rec = gcloud_upload_file(buf, dest_path, metadata=meta)
                add_uploaded_file_record(rec)

                progress.progress(int(i/total * 100))
            st.success(f"{total} archivo(s) procesado(s) (simulado).")
            st.session_state["last_action"] = f"Subidos {total} archivos (simulado)"

    st.markdown("---")
    st.subheader("Acciones rápidas")
    if st.button("Limpiar lista local (simulado)"):
        st.session_state["uploaded_files"] = []
        st.success("Lista local limpiada.")

with col2:
    st.subheader("Supervisión — Archivos subidos")

    files = gcloud_list_files()

    if not files:
        st.info("No hay archivos subidos todavía (modo mock). Usa 'Simular subida' para probar la UI.")
    else:
        # mostrar tabla con paginación simple
        df = pd.DataFrame([{
            "name": f["name"],
            "size_bytes": f.get("size"),
            "uploaded_at": f.get("uploaded_at"),
            "metadata": f.get("metadata"),
        } for f in files])

        st.dataframe(df)

        # seleccionable para acciones
        to_delete = st.multiselect("Selecciona archivos para borrar (simulado)", options=[f["name"] for f in files])
        if st.button("Borrar seleccionados (simulado)"):
            for name in to_delete:
                gcloud_delete_file(name)
            st.success(f"Borrados {len(to_delete)} archivo(s) (simulado).")


# Pie / estado
st.markdown("---")
st.write("Última acción:", st.session_state.get("last_action", "—"))

st.caption("Notas:\n- Esta aplicación es solo la interfaz.\n- Reemplaza los stubs gcloud_* por tus llamadas a la API de Google Cloud (google-cloud-storage, gcloud SDK, o llamadas directas).\n- Si quieres, puedo ahora:")
st.markdown("1. Añadir autenticación con `google-cloud-storage` y subir archivos reales.\n2. Implementar listado y borrado real desde un bucket.\n3. Añadir paginación, filtros por fecha/etiqueta, y un historial persistente (BigQuery / Firestore).\n")
