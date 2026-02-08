# KaiBot Cloud Storage Manager + Content Agent (OPTIMIZADO)
import streamlit as st
from datetime import datetime
import json
import pandas as pd
from google.cloud import storage
from google.oauth2 import service_account
from openai import OpenAI

# =====================================================
# CONFIGURACIÓN
# =====================================================

BUCKET_FOLDERS = {
    "documentos": "documentos/",
    "adicional": "adicional/",
    "validados": "documentos_validados/"
}

# =====================================================
# Helpers GCP
# =====================================================

def get_gcs_client_from_json(sa_json_str: str) -> storage.Client:
    """Crea cliente GCS desde JSON de service account"""
    try:
        info = json.loads(sa_json_str)
        creds = service_account.Credentials.from_service_account_info(info)
        return storage.Client(credentials=creds, project=info.get("project_id"))
    except json.JSONDecodeError:
        raise ValueError("El JSON del Service Account no es válido")
    except Exception as e:
        raise Exception(f"Error al crear cliente GCS: {str(e)}")


def list_folders_and_files(client: storage.Client, bucket_name: str):
    """Lista carpetas y archivos del bucket"""
    bucket = client.bucket(bucket_name)
    blobs = list(bucket.list_blobs())
    
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
    
    return sorted(folders), files


def upload_file(client: storage.Client, bucket_name: str, file, folder: str):
    """Sube archivo a GCS"""
    bucket = client.bucket(bucket_name)
    path = f"{folder.rstrip('/')}/{file.name}"
    blob = bucket.blob(path)
    blob.upload_from_file(file, rewind=True)
    return path


def upload_json_to_gcs(client: storage.Client, bucket_name: str, folder: str, filename: str, data: dict):
    """Sube JSON a GCS"""
    bucket = client.bucket(bucket_name)
    path = f"{folder.rstrip('/')}/{filename}"
    blob = bucket.blob(path)
    blob.upload_from_string(json.dumps(data, indent=2, ensure_ascii=False), content_type="application/json")
    return path

# =====================================================
# Perplexity Agent
# =====================================================

def call_perplexity_agent(api_key: str, system_prompt: str, user_query: str, context: str = "") -> dict:
    """
    Llama a Perplexity API y retorna respuesta en JSON
    
    Args:
        api_key: API key de Perplexity
        system_prompt: Instrucciones del sistema
        user_query: Consulta del usuario
        context: Contexto adicional de documentos
    
    Returns:
        dict con la respuesta parseada
    """
    try:
        from openai import OpenAI
        
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.perplexity.ai"
        )
        
        # Preparar mensaje completo
        full_message = user_query
        if context:
            full_message = f"""CONTEXTO:
{context}

---

CONSULTA:
{user_query}"""
        
        # Llamar a Perplexity
        response = client.chat.completions.create(
            model="llama-3.1-sonar-small-128k-online",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_message}
            ]
        )
        
        response_text = response.choices[0].message.content
        
        # Limpiar markdown
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        return json.loads(response_text)
        
    except json.JSONDecodeError:
        raise ValueError("La respuesta de Perplexity no es un JSON válido")
    except Exception as e:
        raise Exception(f"Error al llamar a Perplexity: {str(e)}")

# =====================================================
# Context loader
# =====================================================

def load_selected_context(client: storage.Client, bucket_name: str, selected_files: list, max_chars: int) -> str:
    """Carga contexto de archivos seleccionados con límite de caracteres"""
    bucket = client.bucket(bucket_name)
    texts = []
    total_chars = 0
    
    for name in selected_files:
        try:
            blob = bucket.blob(name)
            content = blob.download_as_text()
            
            if total_chars + len(content) > max_chars:
                remaining = max_chars - total_chars
                if remaining <= 0:
                    break
                content = content[:remaining]
            
            texts.append(f"### {name}\n{content}")
            total_chars += len(content)
        except Exception as e:
            st.warning(f"Error al cargar {name}: {str(e)}")
    
    return "\n\n".join(texts)


# =====================================================
# OpenAI Agent
# =====================================================

def call_openai_agent(openai_client: OpenAI, system_prompt: str, context: str, user_query: str) -> dict:
    """Llama al agente de OpenAI y retorna respuesta JSON"""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"{system_prompt}\n\nContexto:\n{context}"},
                {"role": "user", "content": user_query}
            ],
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        raise ValueError("La respuesta de OpenAI no es un JSON válido")
    except Exception as e:
        raise Exception(f"Error al llamar a OpenAI: {str(e)}")


# =====================================================
# UI CONFIG
# =====================================================

st.set_page_config(page_title="KaiBot Cloud Agent", layout="wide")

st.markdown("""
    <style>
    body { background-color: #f8fafc; }
    h1, h2, h3 { color: #1E293B; }
    .stButton>button { width: 100%; }
    </style>
""", unsafe_allow_html=True)

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
    
    bucket_name = st.text_input("Bucket GCS", value="")
    sa_json = st.text_area("Service Account JSON", height=220)
    openai_key = st.text_input("OpenAI API Key", type="password")
    
    if st.button("🔌 Conectar"):
        try:
            st.session_state.gcs = get_gcs_client_from_json(sa_json)
            if openai_key:
                st.session_state.openai = OpenAI(api_key=openai_key)
            st.session_state.bucket_name = bucket_name
            st.success("✅ Conectado correctamente")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

if "gcs" not in st.session_state or "bucket_name" not in st.session_state:
    st.warning("⚠️ Configura la conexión en el sidebar para continuar")
    st.stop()

client = st.session_state.gcs
bucket_name = st.session_state.bucket_name

# =====================================================
# TABS
# =====================================================

tab1, tab2, tab3 = st.tabs(["📁 Gestión de Archivos", "🤖 Agentes IA", "🧪 Modo Demo"])

# =====================================================
# TAB 1 - FILE MANAGEMENT
# =====================================================

with tab1:
    folders, files = list_folders_and_files(client, bucket_name)
    
    st.subheader("📤 Subida de archivos")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        folder = st.selectbox("Carpeta destino", options=folders if folders else ["documentos/"])
        uploaded = st.file_uploader("Selecciona archivos", accept_multiple_files=True)
    with col2:
        new_folder = st.text_input("Crear nueva carpeta")
    
    target_folder = f"{new_folder.strip()}/" if new_folder else folder
    
    if st.button("⬆️ Subir archivos") and uploaded:
        progress = st.progress(0)
        for i, f in enumerate(uploaded):
            try:
                upload_file(client, bucket_name, f, target_folder)
                progress.progress((i + 1) / len(uploaded))
            except Exception as e:
                st.error(f"Error subiendo {f.name}: {str(e)}")
        st.success(f"✅ {len(uploaded)} archivo(s) subidos correctamente")
        st.rerun()
    
    st.markdown("---")
    st.subheader("🌐 Documentación adicional (Web / LinkedIn)")
    
    web = st.text_input("Página web")
    linkedin = st.text_input("LinkedIn")
    
    if st.button("💾 Guardar documentación adicional"):
        if web or linkedin:
            payload = {
                "web": web,
                "linkedin": linkedin,
                "created_at": datetime.utcnow().isoformat()
            }
            try:
                upload_json_to_gcs(
                    client, bucket_name, 
                    BUCKET_FOLDERS["adicional"],
                    f"fuentes_{int(datetime.utcnow().timestamp())}.json",
                    payload
                )
                st.success("✅ Documentación guardada")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
        else:
            st.warning("Introduce al menos un campo")
    
    st.markdown("---")
    st.subheader("📁 Contenido del bucket")
    
    if files:
        df = pd.DataFrame(files)
        st.dataframe(df, use_container_width=True)
        
        to_delete = st.multiselect("Selecciona archivos a eliminar", options=df["name"].tolist())
        
        if st.button("🗑️ Eliminar seleccionados") and to_delete:
            bucket = client.bucket(bucket_name)
            for name in to_delete:
                try:
                    bucket.blob(name).delete()
                except Exception as e:
                    st.error(f"Error eliminando {name}: {str(e)}")
            st.success(f"✅ {len(to_delete)} archivo(s) eliminados")
            st.rerun()
    else:
        st.info("ℹ️ El bucket no contiene archivos")

# =====================================================
# TAB 2 - AGENTE FINAL CON PERPLEXITY
# =====================================================

with tab2:
    st.header("🤖 Agente de Contenidos con Perplexity")
    st.caption("Consulta → Perplexity → Validación → Guardado")
    
    # Verificar API key de Perplexity
    if "perplexity_key" not in st.session_state:
        with st.expander("⚙️ Configurar Perplexity API", expanded=True):
            perplexity_key = st.text_input("Perplexity API Key", type="password", key="pplx_input")
            if st.button("Guardar API Key"):
                if perplexity_key:
                    st.session_state.perplexity_key = perplexity_key
                    st.success("✅ API Key guardada")
                    st.rerun()
    
    if "perplexity_key" not in st.session_state:
        st.warning("⚠️ Configura tu API Key de Perplexity para continuar")
        st.stop()
    
    # --- PASO 1: CONFIGURACIÓN DE LA CONSULTA ---
    st.subheader("📝 Paso 1: Configuración")
    
    system_prompt = st.text_area(
        "System prompt para Perplexity",
        value="""Eres un agente experto en análisis de contenidos corporativos y generación de insights estratégicos.

Analiza el contexto proporcionado y responde en formato JSON válido con esta estructura:
{
  "summary": "Resumen ejecutivo conciso (2-3 líneas)",
  "key_points": [
    "Punto clave 1",
    "Punto clave 2",
    "Punto clave 3"
  ],
  "recommended_actions": [
    "Acción recomendada 1",
    "Acción recomendada 2"
  ],
  "sources": [
    "Fuente 1",
    "Fuente 2"
  ]
}

Sé preciso, profesional y basa tus respuestas en datos verificables.""",
        height=200
    )
    
    # Selección de archivos de contexto
    folders, files = list_folders_and_files(client, bucket_name)
    file_names = [f["name"] for f in files]
    
    selected_files = st.multiselect(
        "📄 Selecciona archivos para contexto",
        options=file_names,
        help="Estos archivos se usarán como contexto para la consulta"
    )
    
    max_chars = st.slider(
        "Límite de caracteres de contexto",
        min_value=2000,
        max_value=30000,
        value=10000,
        step=1000,
        help="Controla cuánto contexto enviar a Perplexity"
    )
    
    # Tipo de consulta
    col1, col2 = st.columns([2, 1])
    with col1:
        query_mode = st.radio(
            "Tipo de consulta",
            ["Personalizada", "Plantilla"],
            horizontal=True
        )
    
    if query_mode == "Personalizada":
        user_query = st.text_area(
            "Tu consulta",
            placeholder="Ejemplo: Analiza las tendencias de mercado y sugiere 3 acciones estratégicas prioritarias",
            height=100
        )
    else:
        templates = {
            "Resumen Ejecutivo": "Genera un resumen ejecutivo profesional de la documentación proporcionada, destacando los puntos más relevantes para la toma de decisiones.",
            "Análisis DAFO": "Realiza un análisis DAFO (Debilidades, Amenazas, Fortalezas, Oportunidades) basado en la información del contexto.",
            "Plan de Acción": "Identifica los 5 puntos clave más importantes y proporciona un plan de acción detallado para cada uno.",
            "Detección de Riesgos": "Analiza el contexto e identifica posibles riesgos, incoherencias o puntos de mejora.",
            "Benchmark Competitivo": "Analiza la posición competitiva y genera recomendaciones estratégicas."
        }
        
        selected_template = st.selectbox("Selecciona plantilla", list(templates.keys()))
        user_query = st.text_area(
            "Consulta (editable)",
            value=templates[selected_template],
            height=100
        )
    
    # --- PASO 2: EJECUTAR CONSULTA ---
    st.markdown("---")
    st.subheader("🚀 Paso 2: Ejecutar Consulta")
    
    col_exec, col_clear = st.columns([3, 1])
    
    with col_exec:
        execute_query = st.button(
            "▶️ Consultar a Perplexity",
            type="primary",
            use_container_width=True
        )
    
    with col_clear:
        if st.button("🗑️ Limpiar", use_container_width=True):
            if "perplexity_response" in st.session_state:
                del st.session_state.perplexity_response
            if "edited_response" in st.session_state:
                del st.session_state.edited_response
            st.rerun()
    
    if execute_query:
        if not user_query.strip():
            st.error("❌ La consulta no puede estar vacía")
            st.stop()
        
        if not selected_files:
            st.warning("⚠️ No has seleccionado archivos. La consulta se hará sin contexto adicional.")
        
        with st.spinner("🔄 Consultando a Perplexity..."):
            try:
                # Cargar contexto de archivos
                context = ""
                if selected_files:
                    context = load_selected_context(client, bucket_name, selected_files, max_chars)
                
                # Preparar el prompt completo
                full_prompt = user_query
                if context:
                    full_prompt = f"""CONTEXTO DE DOCUMENTOS:
{context}

---

CONSULTA:
{user_query}"""
                
                # Llamar a Perplexity
                from openai import OpenAI
                
                perplexity_client = OpenAI(
                    api_key=st.session_state.perplexity_key,
                    base_url="https://api.perplexity.ai"
                )
                
                response = perplexity_client.chat.completions.create(
                    model="llama-3.1-sonar-small-128k-online",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": full_prompt}
                    ]
                )
                
                response_text = response.choices[0].message.content
                
                # Intentar parsear como JSON
                try:
                    # Limpiar markdown si existe
                    if "```json" in response_text:
                        response_text = response_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in response_text:
                        response_text = response_text.split("```")[1].split("```")[0].strip()
                    
                    response_json = json.loads(response_text)
                    
                    # Añadir metadata
                    response_json["metadata"] = {
                        "timestamp": datetime.utcnow().isoformat(),
                        "query": user_query,
                        "model": "llama-3.1-sonar-small-128k-online",
                        "context_files": selected_files,
                        "context_chars": len(context)
                    }
                    
                    st.session_state.perplexity_response = response_json
                    st.success("✅ Respuesta recibida de Perplexity")
                    
                except json.JSONDecodeError:
                    st.error("❌ La respuesta no está en formato JSON válido")
                    st.code(response_text)
                    st.stop()
                
            except Exception as e:
                st.error(f"❌ Error al consultar Perplexity: {str(e)}")
                st.stop()
    
    # --- PASO 3: MOSTRAR Y EDITAR RESPUESTA ---
    if "perplexity_response" in st.session_state:
        st.markdown("---")
        st.subheader("📊 Paso 3: Revisar y Editar Respuesta")
        
        # Mostrar vista previa
        with st.expander("👁️ Vista Previa Estructurada", expanded=True):
            response_data = st.session_state.perplexity_response
            
            st.markdown(f"**📝 Resumen:**")
            st.info(response_data.get("summary", "N/A"))
            
            st.markdown("**🎯 Puntos Clave:**")
            for i, point in enumerate(response_data.get("key_points", []), 1):
                st.markdown(f"{i}. {point}")
            
            st.markdown("**✅ Acciones Recomendadas:**")
            for i, action in enumerate(response_data.get("recommended_actions", []), 1):
                st.markdown(f"{i}. {action}")
            
            if "sources" in response_data and response_data["sources"]:
                st.markdown("**🔗 Fuentes:**")
                for source in response_data["sources"]:
                    st.markdown(f"- {source}")
        
        # Editor JSON
        st.markdown("**✏️ Editor JSON**")
        st.caption("Puedes editar la respuesta antes de guardarla")
        
        if "edited_response" not in st.session_state:
            st.session_state.edited_response = json.dumps(
                st.session_state.perplexity_response,
                indent=2,
                ensure_ascii=False
            )
        
        edited_json = st.text_area(
            "JSON editable",
            value=st.session_state.edited_response,
            height=400,
            key="json_editor"
        )
        
        # Validar JSON editado
        try:
            edited_data = json.loads(edited_json)
            st.success("✅ JSON válido")
            json_is_valid = True
        except json.JSONDecodeError as e:
            st.error(f"❌ JSON inválido: {str(e)}")
            json_is_valid = False
        
        # --- PASO 4: GUARDAR ---
        st.markdown("---")
        st.subheader("💾 Paso 4: Guardar Respuesta")
        
        col_save, col_download = st.columns(2)
        
        with col_save:
            if st.button("💾 Guardar en GCS (respuestas_validadas/)", use_container_width=True, disabled=not json_is_valid):
                try:
                    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                    filename = f"respuesta_validada_{timestamp}.json"
                    
                    upload_json_to_gcs(
                        client,
                        bucket_name,
                        BUCKET_FOLDERS["validados"],
                        filename,
                        edited_data
                    )
                    
                    st.success(f"✅ Guardado como: {filename}")
                    st.balloons()
                    
                    # Limpiar sesión
                    del st.session_state.perplexity_response
                    del st.session_state.edited_response
                    
                except Exception as e:
                    st.error(f"❌ Error al guardar: {str(e)}")
        
        with col_download:
            st.download_button(
                "⬇️ Descargar JSON",
                edited_json,
                file_name=f"respuesta_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True,
                disabled=not json_is_valid
            )

# =====================================================
# TAB 3 - DEMO MODE
# =====================================================

with tab3:
    st.header("🧪 Modo Demo (Sin APIs)")
    st.caption("Flujo: generación JSON → validación simulada → aprobación")
    
    if st.button("🎲 Generar JSON simulado"):
        simulated_json = {
            "summary": "Resumen ejecutivo simulado del contenido.",
            "key_points": [
                "Insight clave 1 - Análisis de mercado",
                "Insight clave 2 - Tendencias identificadas",
                "Insight clave 3 - Oportunidades detectadas"
            ],
            "recommended_actions": [
                "Implementar estrategia A",
                "Revisar proceso B"
            ],
            "meta": {
                "mode": "simulated",
                "generated_at": datetime.utcnow().isoformat()
            }
        }
        st.session_state["demo_json"] = json.dumps(simulated_json, indent=2, ensure_ascii=False)
    
    if "demo_json" in st.session_state:
        st.subheader("📄 JSON generado")
        edited_json = st.text_area(
            "Edita el JSON si es necesario",
            value=st.session_state["demo_json"],
            height=300
        )
        
        if st.button("🔍 Validar (simulado)"):
            validation_text = """VALIDACIÓN SIMULADA
----------------------------------
✅ Formato JSON válido
✅ Contenido coherente y alineado
✅ Estructura correcta
⚠️  Recomendación: validar tono antes de publicar"""
            
            st.session_state["validation_text"] = validation_text
            st.session_state["validated_json"] = edited_json
    
    if "validation_text" in st.session_state:
        st.subheader("🧠 Resultado de validación")
        st.code(st.session_state["validation_text"])
        
        col_ok, col_cancel = st.columns(2)
        
        with col_ok:
            if st.button("✅ Aprobar y guardar"):
                try:
                    bucket = client.bucket(bucket_name)
                    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                    blob = bucket.blob(f"{BUCKET_FOLDERS['validados']}resultado_{ts}.json")
                    blob.upload_from_string(
                        st.session_state["validated_json"],
                        content_type="application/json"
                    )
                    st.success("✅ Documento validado y almacenado")
                    del st.session_state["demo_json"]
                    del st.session_state["validation_text"]
                    del st.session_state["validated_json"]
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
        
        with col_cancel:
            if st.button("🔄 Reiniciar"):
                del st.session_state["demo_json"]
                del st.session_state["validation_text"]
                del st.session_state["validated_json"]
                st.rerun()
