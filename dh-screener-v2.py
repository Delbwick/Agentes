# En Tab 4, sección de exportación:

with tab4:
    st.markdown('<p class="section-title">📊 Exportar resultados</p>', unsafe_allow_html=True)
    
    if not st.session_state.results:
        st.info("👉 Ejecuta un análisis primero para poder exportar")
    else:
        # 🔍 Filtro por centro antes de exportar
        centro_options = ["Todos"] + list(st.session_state.results.keys())
        selected_centro_export = st.selectbox(
            "🏢 Filtrar por centro para exportar",
            options=centro_options,
            key="tab4_centro_filter"
        )
        
        rows = []
        for centro_nombre, centro_data in st.session_state.results.items():
            # Aplicar filtro por centro si se seleccionó uno específico
            if selected_centro_export != "Todos" and centro_nombre != selected_centro_export:
                continue
                
            for entity_type in ["technologies", "papers", "companies", "people"]:
                for entity in centro_data["entities"].get(entity_type, []):
                    rows.append({
                        "Centro": centro_nombre,
                        "Región": centro_data.get("region", ""),
                        "Tipo Centro": centro_data.get("tipo", ""),
                        "Tipo Entidad": entity_type,
                        "Nombre": entity.get("nombre") or entity.get("titulo"),
                        "Vertical": entity.get("vertical") or entity.get("sector"),
                        "Descripción": entity.get("descripcion") or entity.get("relevancia_health"),
                        "Score": entity.get("score", 0),
                        "Referencia": entity.get("referencia", ""),
                        "Modelo Usado": entity.get("model_used", "N/A"),
                        "Fallback": "Sí" if entity.get("fallback_used") else "No",
                        "ORCID": entity.get("orcid", ""),
                    })
        
        if rows:
            df_export = pd.DataFrame(rows)
            
            # 📋 Vista previa agrupada por centro
            st.markdown("#### Vista previa (agrupada por centro)")
            
            # Mostrar resumen por centro
            if selected_centro_export == "Todos":
                summary_by_center = df_export.groupby("Centro").agg({
                    "Nombre": "count",
                    "Score": "mean"
                }).rename(columns={"Nombre": "Oportunidades", "Score": "Score Promedio"})
                st.dataframe(summary_by_center.round(1), use_container_width=True)
                st.caption("💡 Haz clic en un centro arriba para ver detalles o filtra arriba")
            
            # Dataframe completo con agrupación visual
            st.markdown("##### 📋 Detalle completo")
            
            # Ordenar por Centro para mejor legibilidad
            df_export_sorted = df_export.sort_values(["Centro", "Tipo Entidad", "Score"], ascending=[True, True, False])
            
            # Configuración de columnas para mejor visualización
            st.dataframe(
                df_export_sorted,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Centro": st.column_config.TextColumn("🏢 Centro", width="medium"),
                    "Tipo Entidad": st.column_config.TextColumn("📦 Tipo", width="small"),
                    "Nombre": st.column_config.TextColumn("📝 Nombre", width="large"),
                    "Score": st.column_config.NumberColumn("⭐ Score", format="%.0f", width="small"),
                    "Modelo Usado": st.column_config.TextColumn("🤖 Modelo", width="small"),
                    "Fallback": st.column_config.CheckboxColumn("🔄 Fallback", width="tiny"),
                }
            )
            
            # Botones de descarga
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                    # Hoja principal con todos los datos
                    df_export_sorted.to_excel(writer, index=False, sheet_name="Oportunidades")
                    
                    # Hoja de resumen por centro
                    if selected_centro_export == "Todos":
                        summary_by_center.to_excel(writer, sheet_name="Resumen_Centros")
                    
                    # Formato de columnas
                    worksheet = writer.sheets["Oportunidades"]
                    for i, col in enumerate(df_export_sorted.columns):
                        max_len = max(df_export_sorted[col].fillna('').astype(str).str.len().max(), len(str(col)))
                        worksheet.set_column(i, i, min(max_len + 2, 60))
                
                buffer.seek(0)
                centro_suffix = f"_{selected_centro_export}" if selected_centro_export != "Todos" else ""
                st.download_button(
                    label="📥 Descargar Excel",
                    data=buffer,
                    file_name=f"double_helix_dealflow{centro_suffix}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            with col_dl2:
                csv = df_export_sorted.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    label="📥 Descargar CSV",
                    data=csv,
                    file_name=f"double_helix_dealflow{centro_suffix}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
