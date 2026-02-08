
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
# TAB 2 - AGENTE DUAL: OPENAI → PERPLEXITY
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
            
            col_save, col_test = st.columns(2)
            with col_save:
                if st.button("💾 Guardar API Key", use_container_width=True):
                    if perplexity_key:
                        st.session_state.perplexity_key = perplexity_key
                        st.success("✅ API Key guardada")
                        st.rerun()
                    else:
                        st.error("❌ Introduce una API Key válida")
            
            with col_test:
                if st.button("🔍 Probar Conexión", use_container_width=True) and perplexity_key:
                    try:
                        from openai import OpenAI
                        
                        test_client = OpenAI(
                            api_key=perplexity_key,
                            base_url="https://api.perplexity.ai"
                        )
                        
                        test_response = test_client.chat.completions.create(
                            model="sonar",
                            messages=[{"role": "user", "content": "Responde solo: OK"}]
                        )
                        
                        st.success(f"✅ Conexión exitosa!")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
        
        apis_configured = False
    
    if not apis_configured:
        st.stop()
    
    # --- PASO 1: CONFIGURACIÓN ---
    st.subheader("📝 Paso 1: Configuración")
    
    with st.expander("⚙️ Configuración de Prompts", expanded=False):
        # System prompt para OpenAI
        openai_prompt = st.text_area(
            "System Prompt - OpenAI (Análisis de Documentos)",
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

Basa tu análisis ÚNICAMENTE en los documentos proporcionados y responde específicamente a lo que el usuario pregunta.""",
            height=180,
            key="openai_system"
        )
        
        # System prompt para Perplexity
        perplexity_prompt = st.text_area(
            "System Prompt - Perplexity (Validación y Enriquecimiento)",
            value="""Eres un validador experto que verifica y enriquece análisis con información actualizada de fuentes confiables.

Recibirás un análisis previo en JSON. Tu tarea es:
1. Validar la información con fuentes actuales y confiables online
2. Enriquecer con datos adicionales relevantes
3. Añadir fuentes verificables (URLs)

IMPORTANTE: Devuelve SOLO un JSON válido con esta estructura exacta:

{
  "summary": "Resumen validado y mejorado con información actual",
  "key_points": [
    "Punto clave validado 1 con información actualizada",
    "Punto clave validado 2 con información actualizada",
    "Punto clave validado 3 con información actualizada"
  ],
  "recommended_actions": [
    "Acción recomendada validada 1 con contexto actual",
    "Acción recomendada validada 2 con contexto actual"
  ],
  "validation_notes": "Notas sobre qué se validó y qué se encontró en las fuentes",
  "sources": [
    "URL completa de fuente verificable 1",
    "URL completa de fuente verificable 2"
  ],
  "confidence_level": "alto"
}

NO incluyas texto antes o después del JSON. Solo responde con el objeto JSON.""",
            height=180,
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
            max_value=50000,
            value=15000,
            step=1000
        )
    
    # Consulta del usuario
    st.markdown("**Consulta**")
    
    query_mode = st.radio(
        "Tipo de consulta",
        ["Plantilla", "Personalizada"],
        horizontal=True
    )
    
    if query_mode == "Personalizada":
        user_query = st.text_area(
            "Escribe tu consulta",
            placeholder="Ejemplo: Analiza las tendencias principales de mercado y genera 3 recomendaciones estratégicas priorizadas",
            height=120,
            key="custom_query"
        )
    else:
        templates = {
            "Análisis Estratégico Completo": "Realiza un análisis estratégico completo de los documentos identificando tendencias clave, oportunidades y riesgos. Proporciona recomendaciones accionables validadas con información actual del mercado.",
            "Resumen Ejecutivo para Dirección": "Genera un resumen ejecutivo profesional destacando los puntos más relevantes para la toma de decisiones. Valida los datos con fuentes actuales y confiables del sector.",
            "Análisis DAFO Validado": "Realiza un análisis DAFO (Debilidades, Amenazas, Fortalezas, Oportunidades) basado en los documentos. Valida cada punto con tendencias actuales y fuentes verificables.",
            "Plan de Acción Priorizado": "Identifica los 5 puntos más importantes y crea un plan de acción detallado y priorizado. Valida con mejores prácticas actuales del sector.",
            "Benchmark Competitivo": "Analiza el contenido y realiza un benchmark competitivo comparando con tendencias actuales del mercado. Incluye fuentes verificables.",
            "Detección de Riesgos y Oportunidades": "Identifica riesgos potenciales y oportunidades de mejora en la documentación. Valida con información actual del sector y regulaciones vigentes."
        }
        
        selected_template = st.selectbox(
            "Selecciona una plantilla",
            list(templates.keys()),
            key="template_select"
        )
        
        user_query = st.text_area(
            "Consulta (editable)",
            value=templates[selected_template],
            height=120,
            key="template_query"
        )
    
    # --- PASO 2: EJECUTAR AGENTE OPENAI ---
    st.markdown("---")
    st.subheader("🔵 Paso 2: Análisis con OpenAI")
    
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
                
                # Llamar a OpenAI
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
                st.rerun()
                
            except json.JSONDecodeError as je:
                st.error(f"❌ Error al parsear JSON de OpenAI: {str(je)}")
                with st.expander("Ver respuesta raw"):
                    st.code(response_text)
            except Exception as e:
                st.error(f"❌ Error en OpenAI: {str(e)}")
    
    # Mostrar respuesta de OpenAI
    if "openai_response" in st.session_state:
        st.markdown("---")
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
            
            if "topics_to_validate" in openai_data and openai_data["topics_to_validate"]:
                st.markdown("**🔍 Temas para Validar con Perplexity:**")
                for topic in openai_data["topics_to_validate"]:
                    st.markdown(f"- {topic}")
            
            # Mostrar JSON
            with st.expander("🔧 Ver JSON completo de OpenAI"):
                st.json(openai_data)
        
        # --- PASO 3: VALIDAR CON PERPLEXITY ---
        st.markdown("---")
        st.subheader("🟣 Paso 3: Validación con Perplexity")
        
        st.info("💡 Perplexity validará el análisis de OpenAI con fuentes online actuales y verificables")
        
        # Selector de modelo de Perplexity
        perplexity_models = {
            "Sonar (Recomendado - Online)": "sonar",
            "Sonar Pro (Avanzado - Online)": "sonar-pro",
            "Llama 3.1 8B": "llama-3.1-8b-instruct",
            "Llama 3.1 70B": "llama-3.1-70b-instruct"
        }
        
        selected_model_name = st.selectbox(
            "Modelo de Perplexity",
            list(perplexity_models.keys()),
            index=0,
            help="Los modelos 'Sonar' tienen acceso a búsqueda web en tiempo real"
        )
        
        perplexity_model = perplexity_models[selected_model_name]
        
        if st.button("▶️ Validar con Perplexity", type="primary", use_container_width=True):
            with st.spinner(f"🔄 Perplexity ({perplexity_model}) validando y enriqueciendo..."):
                try:
                    from openai import OpenAI
                    
                    perplexity_client = OpenAI(
                        api_key=st.session_state.perplexity_key,
                        base_url="https://api.perplexity.ai"
                    )
                    
                    # Preparar prompt para Perplexity
                    validation_prompt = f"""ANÁLISIS PREVIO A VALIDAR (generado por OpenAI):

{json.dumps(st.session_state.openai_response, indent=2, ensure_ascii=False)}

---

CONSULTA ORIGINAL DEL USUARIO:
{user_query}

---

INSTRUCCIONES:
1. Valida cada punto del análisis con fuentes actuales online
2. Enriquece la información con datos relevantes y recientes
3. Proporciona URLs de fuentes verificables
4. Indica el nivel de confianza de la validación

Responde SOLO con un JSON válido, sin texto adicional."""
                    
                    # Llamar a Perplexity
                    response = perplexity_client.chat.completions.create(
                        model=perplexity_model,
                        messages=[
                            {"role": "system", "content": perplexity_prompt},
                            {"role": "user", "content": validation_prompt}
                        ]
                    )
                    
                    response_text = response.choices[0].message.content
                    
                    # Limpiar markdown si existe
                    clean_text = response_text.strip()
                    if "```json" in clean_text:
                        clean_text = clean_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in clean_text:
                        clean_text = clean_text.split("```")[1].split("```")[0].strip()
                    
                    # Intentar parsear JSON
                    try:
                        validated_json = json.loads(clean_text)
                    except json.JSONDecodeError:
                        # Intentar extraer JSON con regex
                        import re
                        json_match = re.search(r'\{.*\}', clean_text, re.DOTALL)
                        if json_match:
                            validated_json = json.loads(json_match.group())
                        else:
                            raise json.JSONDecodeError("No se encontró JSON válido en la respuesta", clean_text, 0)
                    
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
                    st.rerun()
                    
                except json.JSONDecodeError as je:
                    st.error("❌ La respuesta de Perplexity no es un JSON válido")
                    with st.expander("📄 Ver respuesta raw de Perplexity"):
                        st.code(response_text)
                    st.warning("💡 Intenta con otro modelo o ajusta el system prompt")
                except Exception as e:
                    st.error(f"❌ Error en Perplexity: {str(e)}")
                    
                    # Información de debug
                    with st.expander("🔍 Información de debug"):
                        st.write(f"**Modelo usado:** {perplexity_model}")
                        st.write(f"**API Key configurada:** {'Sí' if 'perplexity_key' in st.session_state else 'No'}")
                        st.write(f"**Error completo:** {str(e)}")
    
    # --- PASO 4: MOSTRAR Y EDITAR RESULTADO FINAL ---
    if "perplexity_response" in st.session_state:
        st.markdown("---")
        st.subheader("📊 Paso 4: Resultado Final Validado")
        
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
            
            if "validation_notes" in final_data and final_data["validation_notes"]:
                st.markdown("**📋 Notas de Validación:**")
                st.info(final_data["validation_notes"])
            
            if "confidence_level" in final_data:
                confidence = final_data["confidence_level"].lower()
                if confidence == "alto":
                    emoji = "🟢"
                    color = "success"
                elif confidence == "medio":
                    emoji = "🟡"
                    color = "warning"
                else:
                    emoji = "🔴"
                    color = "error"
                
                st.markdown(f"**{emoji} Nivel de Confianza:** {confidence.upper()}")
            
            if "sources" in final_data and final_data["sources"]:
                st.markdown("**🔗 Fuentes Verificables:**")
                for i, source in enumerate(final_data["sources"], 1):
                    st.markdown(f"{i}. [{source}]({source})")
        
        # Comparación OpenAI vs Perplexity
        with st.expander("🔄 Comparar: OpenAI vs Perplexity"):
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.markdown("**🔵 OpenAI (Análisis Original)**")
                st.json(st.session_state.openai_response)
            
            with col_b:
                st.markdown("**🟣 Perplexity (Validado + Enriquecido)**")
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
            key="json_editor",
            help="Edita el JSON si necesitas hacer ajustes antes de guardar"
        )
        
        # Actualizar el estado cuando se edita
        if edited_json != st.session_state.edited_response:
            st.session_state.edited_response = edited_json
        
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
        st.subheader("💾 Paso 5: Guardar Respuesta Final")
        
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
                    
                    st.success(f"✅ Guardado correctamente")
                    st.info(f"📁 Ruta: {BUCKET_FOLDERS['validados']}{filename}")
                    st.balloons()
                    
                    # Limpiar sesión después de guardar
                    if st.button("🔄 Nueva consulta"):
                        for key in ["openai_response", "perplexity_response", "edited_response"]:
                            if key in st.session_state:
                                del st.session_state[key]
                        st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error al guardar en GCS: {str(e)}")
        
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
                    
                    st.success(f"✅ Guardado en GCS")
                    st.info(f"📁 {BUCKET_FOLDERS['validados']}{filename}")
                    
                    # Trigger de descarga
                    st.download_button(
                        "⬇️ Haz clic aquí para descargar",
                        edited_json,
                        file_name=filename,
                        mime="application/json",
                        use_container_width=True,
                        key="download_after_save"
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
