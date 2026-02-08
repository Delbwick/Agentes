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
# TAB 2 - AGENTE DUAL: OPENAI → PERPLEXITY (CORREGIDO)
# =====================================================

with tab2:
    st.header("🤖 Agente Dual: OpenAI + Perplexity")
    st.caption("Paso 1: OpenAI analiza documentos → Paso 2: Perplexity valida/enriquece")
    
    # Verificar APIs
    apis_configured = True
    
    if "openai" not in st.session_state:
        st.warning("⚠️ Configura OpenAI en el sidebar")
        apis_configured = False
    
    if "perplexity_key" not in st.session_state:
        with st.expander("⚙️ Configurar Perplexity API", expanded=not apis_configured):
            perplexity_key = st.text_input("Perplexity API Key", type="password", key="pplx_input")
            if st.button("Guardar API Key"):
                if perplexity_key:
                    st.session_state.perplexity_key = perplexity_key
                    st.success("✅ API Key guardada")
                    st.rerun()
        apis_configured = False
    
    if not apis_configured:
        st.stop()
    
    # --- PASO 1: CONFIGURACIÓN ---
    st.subheader("📝 Configuración Inicial")
    
    # System prompt para OpenAI (análisis de documentos)
    openai_prompt = st.text_area(
        "System Prompt para OpenAI (Análisis de Documentos)",
        value="""Eres un analista experto en contenidos corporativos.

Tu tarea es analizar los documentos proporcionados y responder a la consulta del usuario de forma estructurada.

IMPORTANTE: Debes responder en formato JSON válido con esta estructura:

{
  "summary": "Resumen ejecutivo respondiendo a la consulta (2-3 líneas)",
  "key_points": [
    "Punto clave 1 relacionado con la consulta",
    "Punto clave 2 relacionado con la consulta",
    "Punto clave 3 relacionado con la consulta"
  ],
  "recommended_actions": [
    "Acción recomendada 1 basada en el análisis",
    "Acción recomendada 2 basada en el análisis"
  ],
  "topics_to_validate": [
    "Tema 1 que requiere validación externa",
    "Tema 2 que requiere validación externa"
  ]
}

Basa tu análisis en los documentos proporcionados y responde específicamente a lo que el usuario pregunta.""",
        height=220,
        key="openai_system"
    )
    
    # System prompt para Perplexity (validación y enriquecimiento)
    perplexity_prompt = st.text_area(
        "System Prompt para Perplexity (Validación y Enriquecimiento)",
        value="""Eres un validador experto que verifica y enriquece análisis con información actualizada de fuentes confiables.

Recibirás un análisis previo en JSON. Tu tarea es:
1. Validar la información con fuentes actuales y confiables
2. Enriquecer con datos adicionales relevantes
3. Añadir fuentes verificables

Devuelve el resultado en este formato JSON:

{
  "summary": "Resumen validado y mejorado",
  "key_points": [
    "Punto clave validado 1",
    "Punto clave validado 2",
    "Punto clave validado 3"
  ],
  "recommended_actions": [
    "Acción recomendada validada 1",
    "Acción recomendada validada 2"
  ],
  "validation_notes": "Notas sobre la validación realizada",
  "sources": [
    "URL o referencia de fuente 1",
    "URL o referencia de fuente 2"
  ],
  "confidence_level": "alto/medio/bajo"
}

Usa únicamente fuentes confiables y actuales.""",
        height=220,
        key="perplexity_system"
    )
    
    # Selección de archivos
    folders, files = list_folders_and_files(client, bucket_name)
    file_names = [f["name"] for f in files]
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        selected_files = st.multiselect(
            "📄 Archivos para análisis",
            options=file_names,
            help="OpenAI analizará estos documentos"
        )
    
    with col2:
        max_chars = st.number_input(
            "Límite caracteres",
            min_value=2000,
            max_value=30000,
            value=10000,
            step=1000
        )
    
    # Consulta del usuario
    query_mode = st.radio(
        "Tipo de consulta",
        ["Personalizada", "Plantilla"],
        horizontal=True
    )
    
    if query_mode == "Personalizada":
        user_query = st.text_area(
            "Tu consulta",
            placeholder="Ejemplo: Analiza las tendencias principales y genera recomendaciones estratégicas",
            height=100
        )
    else:
        templates = {
            "Análisis Estratégico Completo": "Realiza un análisis estratégico completo de los documentos y proporciona recomendaciones accionables validadas con tendencias actuales del mercado.",
            "Resumen Ejecutivo Validado": "Genera un resumen ejecutivo profesional y valida los puntos clave con fuentes actuales y confiables.",
            "Análisis de Riesgos y Oportunidades": "Identifica riesgos y oportunidades en los documentos, y valida con información actual del sector.",
            "Plan de Acción Priorizado": "Extrae los puntos más importantes y crea un plan de acción validado con mejores prácticas actuales.",
            "Benchmark Competitivo": "Analiza el contenido y compara con tendencias actuales del mercado usando fuentes verificables."
        }
        
        selected_template = st.selectbox("Selecciona plantilla", list(templates.keys()))
        user_query = st.text_area(
            "Consulta (editable)",
            value=templates[selected_template],
            height=100
        )
    
    # --- PASO 2: EJECUTAR AGENTE OPENAI ---
    st.markdown("---")
    st.subheader("🔵 Paso 1: Análisis con OpenAI")
    
    col_exec1, col_clear1 = st.columns([3, 1])
    
    with col_exec1:
        execute_openai = st.button(
            "▶️ Analizar con OpenAI",
            type="primary",
            use_container_width=True
        )
    
    with col_clear1:
        if st.button("🗑️ Limpiar Todo", use_container_width=True):
            keys_to_delete = ["openai_response", "perplexity_response", "edited_response"]
            for key in keys_to_delete:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    if execute_openai:
        if not user_query.strip():
            st.error("❌ La consulta no puede estar vacía")
            st.stop()
        
        if not selected_files:
            st.error("❌ Debes seleccionar al menos un archivo para analizar")
            st.stop()
        
        with st.spinner("🔄 OpenAI analizando documentos..."):
            try:
                # Cargar contexto
                context = load_selected_context(client, bucket_name, selected_files, max_chars)
                
                # CORRECCIÓN: Ahora la consulta del usuario va en el mensaje del usuario
                response = st.session_state.openai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": openai_prompt},
                        {"role": "user", "content": f"""CONSULTA DEL USUARIO:
{user_query}

---

DOCUMENTOS DE CONTEXTO:
{context}"""}
                    ],
                    response_format={"type": "json_object"}
                )
                
                response_text = response.choices[0].message.content
                response_json = json.loads(response_text)
                
                # Añadir metadata
                response_json["metadata"] = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "agent": "openai",
                    "model": "gpt-4o-mini",
                    "query": user_query,
                    "context_files": selected_files,
                    "context_chars": len(context)
                }
                
                st.session_state.openai_response = response_json
                st.success("✅ Análisis completado por OpenAI")
                
            except Exception as e:
                st.error(f"❌ Error en OpenAI: {str(e)}")
                st.stop()
    
    # Mostrar respuesta de OpenAI
    if "openai_response" in st.session_state:
        with st.expander("📊 Resultado de OpenAI", expanded=True):
            openai_data = st.session_state.openai_response
            
            st.markdown("**📝 Resumen:**")
            st.info(openai_data.get("summary", "N/A"))
            
            st.markdown("**🎯 Puntos Clave:**")
            for i, point in enumerate(openai_data.get("key_points", []), 1):
                st.markdown(f"{i}. {point}")
            
            st.markdown("**✅ Acciones Recomendadas:**")
            for i, action in enumerate(openai_data.get("recommended_actions", []), 1):
                st.markdown(f"{i}. {action}")
            
            if "topics_to_validate" in openai_data:
                st.markdown("**🔍 Temas para Validar:**")
                for topic in openai_data["topics_to_validate"]:
                    st.markdown(f"- {topic}")
            
            # Mostrar JSON
            with st.expander("🔧 Ver JSON completo"):
                st.json(openai_data)
        
        # --- PASO 3: VALIDAR CON PERPLEXITY ---
        st.markdown("---")
        st.subheader("🟣 Paso 2: Validación con Perplexity")
        
        st.info("💡 Perplexity validará el análisis de OpenAI con fuentes online actuales")
        
        # Selector de modelo de Perplexity
        perplexity_model = st.selectbox(
            "Modelo de Perplexity",
            [
                "llama-3.1-sonar-small-128k-online",
                "llama-3.1-sonar-large-128k-online",
                "llama-3.1-sonar-huge-128k-online"
            ],
            index=0,
            help="Modelos disponibles: small (rápido), large (balanceado), huge (mejor calidad)"
        )
        
        if st.button("▶️ Validar con Perplexity", type="primary", use_container_width=True):
            with st.spinner("🔄 Perplexity validando y enriqueciendo..."):
                try:
                    from openai import OpenAI
                    
                    perplexity_client = OpenAI(
                        api_key=st.session_state.perplexity_key,
                        base_url="https://api.perplexity.ai"
                    )
                    
                    # Preparar prompt para Perplexity
                    validation_prompt = f"""ANÁLISIS PREVIO A VALIDAR:
{json.dumps(st.session_state.openai_response, indent=2, ensure_ascii=False)}

---

CONSULTA ORIGINAL DEL USUARIO:
{user_query}

---

TAREA:
Valida este análisis con fuentes actuales y confiables. Enriquece la información donde sea necesario y proporciona fuentes verificables. 
Asegúrate de que tu respuesta sea un JSON válido siguiendo la estructura especificada."""
                    
                    # CORRECCIÓN: Usar modelo válido de Perplexity
                    response = perplexity_client.chat.completions.create(
                        model=perplexity_model,
                        messages=[
                            {"role": "system", "content": perplexity_prompt},
                            {"role": "user", "content": validation_prompt}
                        ]
                    )
                    
                    response_text = response.choices[0].message.content
                    
                    # Limpiar markdown
                    if "```json" in response_text:
                        response_text = response_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in response_text:
                        response_text = response_text.split("```")[1].split("```")[0].strip()
                    
                    validated_json = json.loads(response_text)
                    
                    # Añadir metadata
                    validated_json["metadata"] = {
                        "timestamp": datetime.utcnow().isoformat(),
                        "agent": "perplexity",
                        "model": perplexity_model,
                        "original_query": user_query,
                        "openai_analysis_timestamp": openai_data.get("metadata", {}).get("timestamp", "N/A")
                    }
                    
                    st.session_state.perplexity_response = validated_json
                    st.success("✅ Validación completada por Perplexity")
                    
                except json.JSONDecodeError:
                    st.error("❌ La respuesta de Perplexity no es un JSON válido")
                    with st.expander("Ver respuesta raw"):
                        st.code(response_text)
                    st.stop()
                except Exception as e:
                    st.error(f"❌ Error en Perplexity: {str(e)}")
                    st.stop()
    
    # --- PASO 4: MOSTRAR Y EDITAR RESULTADO FINAL ---
    if "perplexity_response" in st.session_state:
        st.markdown("---")
        st.subheader("📊 Paso 3: Resultado Final Validado")
        
        # Vista previa estructurada
        with st.expander("👁️ Vista Previa Detallada", expanded=True):
            final_data = st.session_state.perplexity_response
            
            st.markdown("**📝 Resumen Validado:**")
            st.success(final_data.get("summary", "N/A"))
            
            st.markdown("**🎯 Puntos Clave Validados:**")
            for i, point in enumerate(final_data.get("key_points", []), 1):
                st.markdown(f"{i}. {point}")
            
            st.markdown("**✅ Acciones Recomendadas Validadas:**")
            for i, action in enumerate(final_data.get("recommended_actions", []), 1):
                st.markdown(f"{i}. {action}")
            
            if "validation_notes" in final_data:
                st.markdown("**📋 Notas de Validación:**")
                st.info(final_data["validation_notes"])
            
            if "confidence_level" in final_data:
                confidence = final_data["confidence_level"]
                emoji = "🟢" if confidence == "alto" else "🟡" if confidence == "medio" else "🔴"
                st.markdown(f"**{emoji} Nivel de Confianza:** {confidence.upper()}")
            
            if "sources" in final_data and final_data["sources"]:
                st.markdown("**🔗 Fuentes Verificables:**")
                for i, source in enumerate(final_data["sources"], 1):
                    st.markdown(f"{i}. {source}")
        
        # Comparación OpenAI vs Perplexity
        with st.expander("🔄 Comparar OpenAI vs Perplexity"):
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.markdown("**🔵 OpenAI (Original)**")
                st.json(st.session_state.openai_response)
            
            with col_b:
                st.markdown("**🟣 Perplexity (Validado)**")
                st.json(st.session_state.perplexity_response)
        
        # Editor JSON
        st.markdown("---")
        st.markdown("**✏️ Editor JSON Final**")
        st.caption("Puedes editar la respuesta validada antes de guardarla")
        
        if "edited_response" not in st.session_state:
            st.session_state.edited_response = json.dumps(
                st.session_state.perplexity_response,
                indent=2,
                ensure_ascii=False
            )
        
        edited_json = st.text_area(
            "JSON editable",
            value=st.session_state.edited_response,
            height=450,
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
        
        # --- PASO 5: GUARDAR ---
        st.markdown("---")
        st.subheader("💾 Paso 4: Guardar Respuesta Final")
        
        col_save, col_download, col_both = st.columns(3)
        
        with col_save:
            if st.button(
                "💾 Guardar en GCS",
                use_container_width=True,
                disabled=not json_is_valid,
                type="primary"
            ):
                try:
                    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                    filename = f"validado_{timestamp}.json"
                    
                    upload_json_to_gcs(
                        client,
                        bucket_name,
                        BUCKET_FOLDERS["validados"],
                        filename,
                        edited_data
                    )
                    
                    st.success(f"✅ Guardado: {BUCKET_FOLDERS['validados']}{filename}")
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"❌ Error al guardar: {str(e)}")
        
        with col_download:
            st.download_button(
                "⬇️ Descargar JSON",
                edited_json,
                file_name=f"validado_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True,
                disabled=not json_is_valid
            )
        
        with col_both:
            if st.button(
                "💾⬇️ Guardar y Descargar",
                use_container_width=True,
                disabled=not json_is_valid
            ):
                try:
                    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                    filename = f"validado_{timestamp}.json"
                    
                    # Guardar en GCS
                    upload_json_to_gcs(
                        client,
                        bucket_name,
                        BUCKET_FOLDERS["validados"],
                        filename,
                        edited_data
                    )
                    
                    st.success(f"✅ Guardado en GCS: {filename}")
                    
                    # Preparar descarga
                    st.download_button(
                        "⬇️ Haz clic aquí para descargar",
                        edited_json,
                        file_name=filename,
                        mime="application/json",
                        use_container_width=True
                    )
                    
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
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
