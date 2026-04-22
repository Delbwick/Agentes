import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io
import json
import openai

# =============================================================
# 1. CONFIGURACIÓN & UX KAIBOT
# =============================================================
st.set_page_config(
    page_title="KaiBot Lead Manager Pro",
    page_icon="https://kaibot.es/wp-content/uploads/2020/07/image1.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    :root {
        --kaibot-blue: #0066CC; --kaibot-blue-hover: #0052A3; --kaibot-dark: #1E293B;
        --kaibot-gray: #64748B; --kaibot-light: #F8FAFC; --sidebar-bg: #0F172A;
        --success: #10B981; --warning: #F59E0B; --danger: #EF4444;
    }
    .main { background-color: var(--kaibot-light); }
    h1, h2, h3, h4 { color: var(--kaibot-dark); font-weight: 600; }
    .stButton > button[kind="primary"] { background-color: var(--kaibot-blue); color: white; border: none; font-weight: 500; }
    .stButton > button[kind="primary"]:hover { background-color: var(--kaibot-blue-hover); }
    .stButton > button { width: 100%; }
    .stTabs [data-baseweb="tab-list"] { background: white; border-bottom: 2px solid #E2E8F0; gap: 4px; }
    .stTabs [data-baseweb="tab-list"] button[role="tab"] { 
        background: transparent; color: var(--kaibot-gray); font-weight: 500; border-radius: 6px 6px 0 0; padding: 10px 20px; 
    }
    .stTabs [data-baseweb="tab-list"] button[role="tab"][aria-selected="true"] { 
        background: var(--kaibot-blue); color: white !important; font-weight: 600; border-bottom: 3px solid var(--kaibot-blue); 
    }
    .stTabs [data-baseweb="tab-panel"] { padding: 24px; background: white; border-radius: 0 0 8px 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
    [data-testid="stSidebar"] { background-color: var(--sidebar-bg); }
    [data-testid="stSidebar"] * { color: white !important; }
    [data-testid="stSidebar"] input, [data-testid="stSidebar"] textarea, [data-testid="stSidebar"] select {
        background: rgba(255,255,255,0.08) !important; border: 1px solid rgba(255,255,255,0.2) !important; color: white !important;
    }
    .kpi-card { background: white; padding: 16px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); text-align: center; }
    .kpi-value { font-size: 1.8rem; font-weight: 700; color: var(--kaibot-dark); margin: 4px 0; }
    .kpi-label { font-size: 0.85rem; color: var(--kaibot-gray); text-transform: uppercase; letter-spacing: 0.5px; }
    .kaibot-footer { text-align: center; color: var(--kaibot-gray); font-size: 0.85rem; margin-top: 40px; padding: 20px 0; border-top: 1px solid #E2E8F0; }
</style>
""", unsafe_allow_html=True)

# =============================================================
# 2. CONFIGURACIÓN & CONSTANTES
# =============================================================
CAMPOS_REQ = [
    "N_FORM", "FECHA_ENVIO_FORM", "NOMBRE_EMPRESA", "NOMBRE_ENVIO_MAIL", "MAIL",
    "TELÉFONO", "MENSAJE", "TIPO_FORM", "SON_CLIENTE", "ANOTACIONES",
    "VALOR_LEAD", "COSTE_DEL_LEAD", "ORIGEN_FORM_HA_FINALIZADO", "FACTURACION",
    "VERTICAL_EMPRESA", "LINKEDIN", "CARGO"
]

DEFAULT_ICP = {
    "sectores_prioritarios": ["Tecnología", "Industrial", "Salud", "Finanzas"],
    "tamano_minimo": "Pequeña (10-50)",
    "cargos_decision": ["CEO", "CMO", "Director Comercial", "Head of Growth", "CTO"],
    "facturacion_min": "1-5M€"
}

# =============================================================
# 3. FUNCIONES DE DATOS & VALORACIÓN
# =============================================================
def init_sample_data():
    np.random.seed(42)
    n = 25
    data = {
        "N_FORM": [f"FRM-{1000+i}" for i in range(n)],
        "FECHA_ENVIO_FORM": pd.date_range(start="2025-03-01", periods=n, freq="3D"),
        "NOMBRE_EMPRESA": np.random.choice(["TechCorp", "IndusLab", "MediGroup", "DataFlow", "GreenSolutions"], n),
        "NOMBRE_ENVIO_MAIL": np.random.choice(["Carlos R.", "Ana M.", "Luis P.", "Sofia T.", "Miguel A."], n),
        "MAIL": [f"user{i}@empresa.com" for i in range(n)],
        "TELÉFONO": [f"+34 600 {np.random.randint(100000, 999999)}" for i in range(n)],
        "MENSAJE": np.random.choice(["Interesados en consultoría B2B", "Solicitan demo de plataforma", "Contacto para partnership", "Consulta sobre precios enterprise"], n),
        "TIPO_FORM": np.random.choice(["Web General", "Landing Campaña", "Webinar", "Feria", "Contacto Directo"], n),
        "SON_CLIENTE": np.random.choice(["Sí", "No"], n, p=[0.3, 0.7]),
        "ANOTACIONES": np.random.choice(["Requiere follow-up", "Alta intención", "Presupuesto definido", "En evaluación"], n),
        "VALOR_LEAD": np.random.uniform(500, 15000, n),
        "COSTE_DEL_LEAD": np.random.uniform(20, 800, n),
        "ORIGEN_FORM_HA_FINALIZADO": np.random.choice(["Sí", "No", "Parcial"], n, p=[0.6, 0.2, 0.2]),
        "FACTURACION": np.random.choice(["<1M€", "1-5M€", "5-20M€", ">20M€"], n),
        "VERTICAL_EMPRESA": np.random.choice(["Industrial", "Tecnología", "Salud", "Logística", "Finanzas"], n),
        "LINKEDIN": [f"https://linkedin.com/in/user{i}" for i in range(n)],
        "CARGO": np.random.choice(["CEO", "CMO", "Director Comercial", "Head of Growth", "CTO"], n)
    }
    df = pd.DataFrame(data)
    df["VALOR_LEAD"] = df["VALOR_LEAD"].round(2)
    df["COSTE_DEL_LEAD"] = df["COSTE_DEL_LEAD"].round(2)
    return df

def calcular_valoracion(df):
    df = df.copy()
    df.columns = df.columns.str.strip()  # CRÍTICO: elimina espacios
    
    df["ROI_LEAD"] = np.where(df["COSTE_DEL_LEAD"] > 0, (df["VALOR_LEAD"] - df["COSTE_DEL_LEAD"]) / df["COSTE_DEL_LEAD"], 0).round(2)
    df["PUNTUACION"] = 0
    df.loc[df["SON_CLIENTE"] == "Sí", "PUNTUACION"] += 20
    df.loc[df["ORIGEN_FORM_HA_FINALIZADO"] == "Sí", "PUNTUACION"] += 25
    df.loc[df["VALOR_LEAD"] > df["VALOR_LEAD"].median(), "PUNTUACION"] += 20
    df.loc[df["CARGO"].isin(["CEO", "CMO", "Director Comercial"]), "PUNTUACION"] += 25
    df.loc[df["FACTURACION"].isin(["5-20M€", ">20M€"]), "PUNTUACION"] += 10
    df["PUNTUACION"] = df["PUNTUACION"].clip(0, 100)
    
    conditions = [df["PUNTUACION"] >= 75, df["PUNTUACION"] >= 50, df["PUNTUACION"] >= 25]
    choices = ["🟢 Alto Potencial", "🟡 Medio", "🔴 Bajo"]
    df["ESTADO_VALOR"] = np.select(conditions, choices, default="🔴 Bajo")
    return df

# =============================================================
# 4. FUNCIONES OPENAI ENRIQUECIDAS
# =============================================================
def buscar_contexto_empresa(nombre_empresa, api_key):
    if not api_key or not nombre_empresa: return None
    try:
        client = openai.OpenAI(api_key=api_key)
        prompt = f"""Analista de inteligencia comercial. Investiga: {nombre_empresa}.
        Devuelve SOLO JSON: {{"sector_principal": "string", "tipo_negocio": "B2B"|"B2C", "tamano_estimado": "string", "madurez_digital": "Alta"|"Media"|"Baja", "notas_clave": ["string"]}}"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Experto en inteligencia de mercado."}, {"role": "user", "content": prompt}],
            temperature=0.3, response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except: return None

def consultar_openai_enriquecido(row, api_key, icp_config=None):
    if not api_key: return None, None, "⚠️ Falta API Key OpenAI."
    
    empresa_info = buscar_contexto_empresa(row.get('NOMBRE_EMPRESA', ''), api_key) if row.get('NOMBRE_EMPRESA') else None
    contexto = f"Sector: {empresa_info.get('sector_principal', 'Desconocido') if empresa_info else 'N/A'}, Tipo: {empresa_info.get('tipo_negocio', 'N/A') if empresa_info else 'N/A'}"
    
    icp = icp_config if icp_config else DEFAULT_ICP
    
    prompt = f"""Actúa como experto en scoring B2B. Evalúa lead del 0 al 100.
    ICP: {icp['sectores_prioritarios']} | {icp['tamano_minimo']} | Cargos: {icp['cargos_decision']}
    Datos: Empresa: {row.get('NOMBRE_EMPRESA')}, Cargo: {row.get('CARGO')}, Mensaje: {row.get('MENSAJE')}
    Contexto: {contexto}
    
    Criterios: 40% Fit ICP, 30% Intención, 15% Calidad, 15% Potencial.
    Devuelve SOLO JSON: {{"score": int, "reasons": ["string"], "recommendation": "string", "fit_icp": "Alto"|"Medio"|"Bajo", "risk_factors": ["string"], "next_step_suggested": "string"}}
    """
    
    try:
        client = openai.OpenAI(api_key=api_key)
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Analista scoring B2B."}, {"role": "user", "content": prompt}],
            temperature=0.2, response_format={"type": "json_object"}, max_tokens=400
        )
        ai_data = json.loads(res.choices[0].message.content)
        ai_data["contexto_empresa"] = empresa_info
        return ai_data, prompt, None
    except Exception as e:
        return None, prompt, f"❌ Error: {e}"

# =============================================================
# 5. INICIALIZACIÓN & SIDEBAR
# =============================================================
if "leads_df" not in st.session_state:
    st.session_state.leads_df = calcular_valoracion(init_sample_data())
if "selected_lead" not in st.session_state: st.session_state.selected_lead = None
if "openai_key" not in st.session_state: st.session_state.openai_key = ""
if "ai_cache" not in st.session_state: st.session_state.ai_cache = {}
if "icp_config" not in st.session_state: st.session_state.icp_config = DEFAULT_ICP.copy()

# =============================================================
# LIMPIEZA DE DATOS (CRÍTICO PARA EVITAR ERRORES)
# =============================================================
df_raw = st.session_state.leads_df
# Elimina espacios en blanco al inicio/final de los nombres de columnas
df_raw.columns = df_raw.columns.str.strip()

with st.sidebar:
    st.markdown('![](https://kaibot.es/wp-content/uploads/2020/07/image1.png) **KaiBot Leads**', unsafe_allow_html=True)
    st.markdown("---")
    
    st.markdown("🔍 **Filtros Avanzados**")
    search = st.text_input("Buscar empresa/email/cargo", placeholder="Ej: TechCorp, CMO...")
    col1, col2 = st.columns(2)
    
    # Usamos nombres de columnas LIMPIOS (sin espacios)
    with col1:
        vertical = st.multiselect("Vertical", options=df_raw["VERTICAL_EMPRESA"].unique().tolist(), default=df_raw["VERTICAL_EMPRESA"].unique().tolist())
    with col2:
        tipo_form = st.multiselect("Tipo Formulario", options=df_raw["TIPO_FORM"].unique().tolist(), default=df_raw["TIPO_FORM"].unique().tolist())
        
    col3, col4 = st.columns(2)
    with col3:
        cliente = st.selectbox("¿Es Cliente?", ["Todos", "Sí", "No"])
    with col4:
        exito = st.selectbox("Formulario Finalizado?", ["Todos", "Sí", "No", "Parcial"])
        
    # SLIDER SEGURO: Maneja dataframes vacíos o valores no numéricos
    max_val_possible = 20000  # Valor por defecto
    if "VALOR_LEAD" in df_raw.columns:
        try:
            numeric_vals = pd.to_numeric(df_raw["VALOR_LEAD"], errors='coerce')
            if not numeric_vals.empty and not numeric_vals.isna().all():
                max_val_possible = int(numeric_vals.max())
        except:
            pass
            
    min_val, max_val = st.slider("Rango Valor Lead (€)", 0, max_val_possible, (0, max_val_possible), 100)

    # =============================================================
    # 📥 IMPORTADOR INTELIGENTE CON MAPEO
    # =============================================================
    st.markdown("---")
    st.markdown("📥 **Importar CSV**")
    
    uploaded = st.file_uploader("Cargar archivo CSV", type=["csv"], key="csv_uploader_v2")
    
    if uploaded is not None:
        try:
            df_up = pd.read_csv(uploaded, encoding='utf-8-sig')
            df_up.columns = df_up.columns.str.strip() # Limpiar columnas del CSV
            detected_cols = df_up.columns.tolist()
            
            st.success(f"✅ {len(df_up)} filas detectadas.")
            
            # Columnas que necesitamos (LIMPIAS)
            TARGET_COLS = [
                "N_FORM", "FECHA_ENVIO_FORM", "NOMBRE_EMPRESA", "NOMBRE_ENVIO_MAIL", "MAIL",
                "TELÉFONO", "MENSAJE", "TIPO_FORM", "SON_CLIENTE", "ANOTACIONES",
                "VALOR_LEAD", "COSTE_DEL_LEAD", "ORIGEN_FORM_HA_FINALIZADO", "FACTURACION",
                "VERTICAL_EMPRESA", "LINKEDIN", "CARGO"
            ]
            
            # Inicializar mapeo en sesión
            if "import_map" not in st.session_state:
                st.session_state.import_map = {}
                # Auto-mapeo básico
                for target in TARGET_COLS:
                    match = next((c for c in detected_cols if target.lower() in c.lower()), None)
                    st.session_state.import_map[target] = match

            with st.expander("⚙️ Configurar Mapeo (Revisar automático)", expanded=True):
                st.caption("🟢 Campos críticos (Empresa, Email)")
                
                for target_col in TARGET_COLS:
                    is_critical = target_col in ["NOMBRE_EMPRESA", "MAIL"]
                    icon = "🟢" if is_critical else "⚪"
                    
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.markdown(f"{icon} **{target_col}**")
                    with c2:
                        options = ["(Dejar vacío)"] + detected_cols
                        current = st.session_state.import_map.get(target_col)
                        idx = options.index(current) if current in options else 0
                        
                        selected = st.selectbox(
                            f"Map {target_col}", 
                            options=options, index=idx, 
                            key=f"map_{target_col}", label_visibility="collapsed"
                        )
                        st.session_state.import_map[target_col] = selected
                
                st.markdown("---")
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    # Validar que los campos críticos están mapeados
                    critical_ok = all([st.session_state.import_map.get(c) != "(Dejar vacío)" for c in ["NOMBRE_EMPRESA", "MAIL"]])
                    
                    if st.button("🚀 IMPORTAR", type="primary", disabled=not critical_ok, use_container_width=True):
                        # Construir dataframe final
                        data_dict = {}
                        for target_col in TARGET_COLS:
                            src_col = st.session_state.import_map.get(target_col)
                            if src_col and src_col != "(Dejar vacío)" and src_col in df_up.columns:
                                data_dict[target_col] = df_up[src_col]
                            else:
                                # Valores por defecto
                                if target_col in ["VALOR_LEAD", "COSTE_DEL_LEAD"]: data_dict[target_col] = 0.0
                                elif target_col == "FECHA_ENVIO_FORM": data_dict[target_col] = datetime.now()
                                elif target_col == "SON_CLIENTE": data_dict[target_col] = "No"
                                elif target_col == "ORIGEN_FORM_HA_FINALIZADO": data_dict[target_col] = "Sí"
                                else: data_dict[target_col] = ""
                        
                        df_new = pd.DataFrame(data_dict)
                        st.session_state.leads_df = calcular_valoracion(df_new)
                        st.success("✅ Importación exitosa")
                        st.rerun()
                        
                with col_btn2:
                    if st.button("🔄 Reset", use_container_width=True):
                        st.session_state.import_map = {}
                        st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")

# =============================================================
# APLICAR FILTROS (Con nombres de columnas LIMPIOS)
# =============================================================
df_f = df_raw.copy()
if search: df_f = df_f[df_f.apply(lambda r: search.lower() in r.astype(str).str.lower().sum(), axis=1)]
if vertical != df_raw["VERTICAL_EMPRESA"].unique().tolist(): df_f = df_f[df_f["VERTICAL_EMPRESA"].isin(vertical)]
if tipo_form != df_raw["TIPO_FORM"].unique().tolist(): df_f = df_f[df_f["TIPO_FORM"].isin(tipo_form)]
if cliente != "Todos": df_f = df_f[df_f["SON_CLIENTE"] == cliente]
if exito != "Todos": df_f = df_f[df_f["ORIGEN_FORM_HA_FINALIZADO"] == exito]
df_f = df_f[(df_f["VALOR_LEAD"] >= min_val) & (df_f["VALOR_LEAD"] <= max_val)]
df_f = df_f.sort_values("FECHA_ENVIO_FORM", ascending=False)
st.session_state.df_filtrado = df_f

# =============================================================
# 6. MAIN UI - 5 PESTAÑAS
# =============================================================
st.markdown('<div style="display:flex;align-items:center;gap:10px;"><img src="https://kaibot.es/wp-content/uploads/2020/07/image1.png" width="30"><h2 style="margin:0;">Panel de Leads & Valoración</h2></div>', unsafe_allow_html=True)
st.caption("Gestión, análisis y scoring inteligente B2B.")
st.markdown("---")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Dashboard KPIs", "📋 Lista", "🔍 Detalle", "➕ Nuevo Lead", "🤖 Batch Scoring"])

# TAB 1: KPIs
with tab1:
    c1, c2, c3, c4 = st.columns(4)
    total = len(df_f); val_t = df_f["VALOR_LEAD"].sum(); cost_t = df_f["COSTE_DEL_LEAD"].sum()
    roi = ((val_t - cost_t) / cost_t) if cost_t > 0 else 0; cli = len(df_f[df_f["SON_CLIENTE"]=="Sí"])
    def kpi_card(l, v, s=""): st.markdown(f'<div class="kpi-card"><div class="kpi-label">{l}</div><div class="kpi-value">{v}</div><div style="color:var(--kaibot-gray);font-size:0.8rem;">{s}</div></div>', unsafe_allow_html=True)
    with c1: kpi_card("Leads", total, "Filtrados")
    with c2: kpi_card("Pipeline", f"{val_t:,.0f}€", f"{cost_t:,.0f}€ invertidos")
    with c3: kpi_card("ROI", f"{roi:.2f}x", "Retorno")
    with c4: kpi_card("Clientes", f"{cli} ({cli/max(total,1)*100:.1f}%)", "Conversión")
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1: st.bar_chart(df_f.groupby("VERTICAL_EMPRESA")["VALOR_LEAD"].sum(), use_container_width=True)
    with c2: st.bar_chart(df_f.groupby("TIPO_FORM")["VALOR_LEAD"].mean(), use_container_width=True)

# TAB 2: Lista
with tab2: st.dataframe(df_f, use_container_width=True, hide_index=True)

# TAB 3: Detalle
with tab3:
    st.markdown("### 🔍 Detalle & Análisis")
    opts = df_f["N_FORM"].tolist()
    sel = st.selectbox("Selecciona lead", options=opts, index=opts.index(st.session_state.selected_lead) if st.session_state.selected_lead in opts else 0)
    if sel:
        st.session_state.selected_lead = sel
        row = df_f[df_f["N_FORM"]==sel].iloc[0]
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown(f"**{row['NOMBRE_EMPRESA']}** | {row['CARGO']} | `{row['MAIL']}`")
            st.info(row['MENSAJE'])
        with c2:
            st.metric("Valor", f"{row['VALOR_LEAD']:,.0f}€")
            st.progress(row['PUNTUACION']/100)
            st.caption(f"Score: {row['PUNTUACION']} | {row['ESTADO_VALOR']}")
        new_note = st.text_area("Anotaciones", value=str(row['ANOTACIONES']), label_visibility="collapsed")
        if st.button("💾 Guardar"):
            idx = st.session_state.leads_df.index[st.session_state.leads_df["N_FORM"]==sel][0]
            st.session_state.leads_df.at[idx, "ANOTACIONES"] = new_note
            st.rerun()
        if st.button("🤖 Consultar OpenAI"):
            ai_res, ai_prompt, err = consultar_openai_enriquecido(row.to_dict(), st.session_state.openai_key, st.session_state.icp_config)
            if err: st.error(err)
            else:
                st.session_state.ai_cache[sel] = {"response": ai_res, "prompt": ai_prompt}
                idx = st.session_state.leads_df.index[st.session_state.leads_df["N_FORM"]==sel][0]
                st.session_state.leads_df.loc[idx, "AI_SCORE"] = ai_res.get("score")
                st.session_state.leads_df.loc[idx, "AI_REASONING"] = "; ".join(ai_res.get("reasons", []))
                st.rerun()
        if sel in st.session_state.ai_cache:
            cache = st.session_state.ai_cache[sel]
            st.markdown("### 🧠 Consulta & Respuesta OpenAI")
            with st.expander("📤 Prompt Enviado", expanded=False): st.code(cache["prompt"], language="markdown")
            with st.expander("📥 Respuesta (JSON)", expanded=True): st.json(cache["response"])
            if "score" in cache["response"]:
                ai_score = cache["response"]["score"]; fit = cache["response"].get("fit_icp", "Desconocido")
                st.markdown(f"**Fit ICP:** {'🟢' if fit=='Alto' else '🟡' if fit=='Medio' else '🔴'} {fit}")
                c_a, c_b = st.columns(2)
                c_a.metric("Score IA", f"{ai_score}/100", delta=f"{ai_score - row['PUNTUACION']} vs Reglas")
                if cache["response"].get("reasons"):
                    st.markdown("**Razones:**"); [st.write(f"• {r}") for r in cache["response"]["reasons"]]

# TAB 4: Nuevo Lead
with tab4:
    st.markdown("### ➕ Añadir Lead Manual")
    with st.form("new_lead_form"):
        c1, c2, c3 = st.columns(3)
        emp = c1.text_input("NOMBRE_EMPRESA *", placeholder="TechCorp"); mail = c2.text_input("MAIL *", placeholder="email@empresa.com")
        cargo = c3.text_input("CARGO", placeholder="CTO"); vert = c1.selectbox("VERTICAL", ["Tecnología", "Industrial", "Salud", "Finanzas"])
        fact = c2.selectbox("FACTURACION", ["<1M€", "1-5M€", "5-20M€", ">20M€"]); men = c3.text_area("MENSAJE")
        val = c1.number_input("VALOR (€)", value=1000); cost = c2.number_input("COSTE (€)", value=50)
        if st.form_submit_button("💾 Guardar y Analizar"):
            if emp and mail:
                new_id = f"MAN-{datetime.now().strftime('%H%M%S')}"
                new_df = pd.DataFrame([{"N_FORM": new_id, "FECHA_ENVIO_FORM": datetime.now(), "NOMBRE_EMPRESA": emp, "MAIL": mail, "CARGO": cargo, "VERTICAL_EMPRESA": vert, "FACTURACION": fact, "MENSAJE": men, "VALOR_LEAD": val, "COSTE_DEL_LEAD": cost, "SON_CLIENTE": "No", "ORIGEN_FORM_HA_FINALIZADO": "Sí", "ANOTACIONES": "Nuevo"}])
                st.session_state.leads_df = pd.concat([st.session_state.leads_df, new_df], ignore_index=True)
                st.session_state.leads_df = calcular_valoracion(st.session_state.leads_df)
                if st.session_state.openai_key:
                    with st.spinner("🤖 Calculando IA..."):
                        ai_res, _, err = consultar_openai_enriquecido(new_df.iloc[0].to_dict(), st.session_state.openai_key, st.session_state.icp_config)
                        if not err and ai_res:
                            idx = st.session_state.leads_df.index[st.session_state.leads_df["N_FORM"]==new_id][0]
                            st.session_state.leads_df.loc[idx, "AI_SCORE"] = ai_res.get("score")
                            st.session_state.leads_df.loc[idx, "AI_REASONING"] = "; ".join(ai_res.get("reasons", []))
                st.success("✅ Lead guardado"); st.rerun()
            else: st.error("⚠️ Empresa y Email obligatorios")

# TAB 5: Batch Scoring IA (NUEVO)
with tab5:
    st.markdown("### 🤖 Batch Scoring IA")
    st.caption("Procesa múltiples leads filtrados simultáneamente con OpenAI.")
    
    if not st.session_state.openai_key:
        st.warning("⚠️ Introduce tu API Key de OpenAI en el sidebar para activar el Batch Scoring.")
    else:
        col_mode1, col_mode2 = st.columns([1, 3])
        with col_mode1:
            mode = st.radio("Modo", ["Todos los filtrados", "Seleccionar manualmente"], index=0)
        
        leads_to_process = []
        if mode == "Todos los filtrados":
            leads_to_process = st.session_state.df_filtrado.copy()
            st.info(f"📋 Se procesarán **{len(leads_to_process)}** leads según filtros actuales.")
        else:
            selected_forms = st.multiselect("Selecciona leads específicos", options=df_f["N_FORM"].tolist())
            if selected_forms:
                leads_to_process = df_f[df_f["N_FORM"].isin(selected_forms)]
                st.info(f"📋 Se procesarán **{len(leads_to_process)}** leads seleccionados.")
        
        if len(leads_to_process) > 0:
            if st.button(f"🚀 Ejecutar Scoring para {len(leads_to_process)} Leads", type="primary"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                results_log = []
                
                for i, idx in enumerate(leads_to_process.index):
                    row = leads_to_process.loc[idx]
                    progress_bar.progress((i + 1) / len(leads_to_process))
                    status_text.text(f"🔄 Analizando: {row.get('NOMBRE_EMPRESA')} ({i+1}/{len(leads_to_process)})")
                    
                    ai_res, _, err = consultar_openai_enriquecido(row.to_dict(), st.session_state.openai_key, st.session_state.icp_config)
                    if not err and ai_res:
                        global_idx = st.session_state.leads_df.index[st.session_state.leads_df["N_FORM"] == row["N_FORM"]][0]
                        st.session_state.leads_df.loc[global_idx, "AI_SCORE"] = ai_res.get("score")
                        st.session_state.leads_df.loc[global_idx, "AI_REASONING"] = "; ".join(ai_res.get("reasons", []))
                        st.session_state.leads_df.loc[global_idx, "AI_FIT_ICP"] = ai_res.get("fit_icp", "")
                        results_log.append(f"✅ {row['NOMBRE_EMPRESA']}: {ai_res.get('score')}/100 ({ai_res.get('fit_icp')})")
                    else:
                        results_log.append(f"❌ {row['NOMBRE_EMPRESA']}: {err}")
                
                status_text.text("✅ Proceso completado.")
                
                # Mostrar resumen de resultados
                with st.expander("📊 Resumen de Resultados", expanded=True):
                    for log in results_log:
                        st.caption(log)
                
                st.rerun()
        else:
            st.info("ℹ️ No hay leads para procesar. Ajusta los filtros o selecciona leads manualmente.")

st.markdown('<div class="kaibot-footer">© 2026 KaiBot. Optimizado para gestión comercial B2B.</div>', unsafe_allow_html=True)
