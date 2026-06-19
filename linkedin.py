# ============================================================================
# STREAMLIT APP - SECCIÓN DE BÚSQUEDA MEJORADA (SIN FOTOS, MÁS INFO)
# ============================================================================

if st.session_state.search_results:
    st.markdown("### 📋 Selecciona el perfil correcto")
    st.info("💡 Ordenados por relevancia. Busca coincidencias en nombre e institución.")
    
    for nombre, results in st.session_state.search_results.items():
        with st.expander(f"👤 {nombre} ({len(results)} candidatos)", expanded=True):
            # Info del Excel
            inst_excel = str(df[df[col_nombre] == nombre][col_inst].iloc[0]) if col_inst else ""
            orcid_excel = str(df[df[col_nombre] == nombre][col_orcid].iloc[0]) if col_orcid else ""
            
            # Mostrar info de referencia
            col_ref1, col_ref2 = st.columns(2)
            with col_ref1:
                st.markdown(f"**🏛️ Institución:** {inst_excel[:80]}{'...' if len(inst_excel) > 80 else ''}")
            with col_ref2:
                if orcid_excel:
                    st.markdown(f"**🔗 ORCID:** [{orcid_excel[-8:]}]({orcid_excel})")
            
            st.divider()
            
            # Mostrar solo top 10 resultados ordenados
            for i, r in enumerate(results[:10]):
                name = r.get('name', 'Sin nombre')
                headline = r.get('headline', '')
                location = r.get('location', '')
                context = r.get('context', '')
                score = r.get('score', 0)
                href = r.get('href', '')
                
                # Calcular coincidencias
                name_match = nombre.lower() in name.lower()
                inst_match = False
                inst_words_found = []
                if inst_excel and context:
                    inst_words = [w for w in inst_excel.lower().split() if len(w) > 4]
                    for word in inst_words[:5]:
                        if word in context.lower():
                            inst_match = True
                            inst_words_found.append(word)
                
                # Tarjeta compacta
                with st.container():
                    col_checkbox, col_content = st.columns([0.08, 0.92])
                    
                    with col_checkbox:
                        selected = st.checkbox(
                            "",
                            key=f"select_{nombre}_{i}",
                            label_visibility="collapsed",
                            help="Marca para seleccionar"
                        )
                    
                    with col_content:
                        # Header: Nombre + Score + Badges
                        col_h1, col_h2 = st.columns([3, 1])
                        with col_h1:
                            st.markdown(f"**{name}**", unsafe_allow_html=True)
                        with col_h2:
                            if score > 10:
                                st.markdown(f"<span style='background:#28a745;color:white;padding:2px 8px;border-radius:12px;font-size:0.85rem;font-weight:bold;'>Score: {score}</span>", unsafe_allow_html=True)
                            elif score > 0:
                                st.caption(f"Score: {score}")
                        
                        # Badges de coincidencia
                        badges = []
                        if name_match:
                            badges.append("🎯 Nombre")
                        if inst_match:
                            badges.append(f"🏢 Institución ({', '.join(inst_words_found[:2])})")
                        
                        if badges:
                            badge_html = " ".join([f"<span style='background:#17a2b8;color:white;padding:2px 6px;border-radius:8px;font-size:0.8rem;margin-right:4px;'>{b}</span>" for b in badges])
                            st.markdown(badge_html, unsafe_allow_html=True)
                        
                        # Info relevante: Headline y Ubicación
                        info_parts = []
                        if headline:
                            info_parts.append(f"💼 {headline}")
                        if location:
                            info_parts.append(f"📍 {location}")
                        
                        if info_parts:
                            st.caption(" • ".join(info_parts))
                        
                        # Contexto recortado (solo si es relevante)
                        if context and len(context) > 20:
                            # Extraer solo la parte de institución/experiencia actual
                            context_preview = context[:250] + "..." if len(context) > 250 else context
                            st.markdown(f"*{context_preview}*", unsafe_allow_html=True)
                        
                        # Link y acciones
                        col_link, col_space = st.columns([2, 1])
                        with col_link:
                            if href:
                                st.markdown(f"[🔗 Ver perfil LinkedIn]({href})", unsafe_allow_html=True)
                        
                        st.markdown("---")
            
            # Botón guardar selección
            col_btn1, col_btn2 = st.columns([2, 1])
            with col_btn1:
                if st.button(f"💾 Guardar selección", key=f"save_{nombre}", type="primary", use_container_width=True):
                    seleccionado = False
                    for i, r in enumerate(results[:10]):
                        if st.session_state.get(f"select_{nombre}_{i}", False):
                            st.session_state.selected_profiles[nombre] = r['href']
                            st.success(f"✅ Seleccionado: {r.get('name', 'N/A')} (Score: {r.get('score', 0)})")
                            seleccionado = True
                            break
                    
                    if not seleccionado:
                        st.warning("⚠️ Selecciona un candidato primero")
            
            with col_btn2:
                if st.button(f"🔄 Limpiar", key=f"clear_{nombre}"):
                    for i in range(len(results[:10])):
                        key = f"select_{nombre}_{i}"
                        if key in st.session_state:
                            st.session_state[key] = False
                    st.rerun()
            
            st.markdown("<br>", unsafe_allow_html=True)
