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
