import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io
import json
import openai

# =============================================================
# 1. CONFIGURACIÓN & UX
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
# 2. CONSTANTES & DATOS (SIN ESPACIOS OCULTOS)
# =============================================================
CAMPOS_REQ = [
    "N_FORM", "FECHA_ENVIO_FORM", "NOMBRE_EMPRESA", "NOMBRE_ENVIO_MAIL", "MAIL",
    "TELÉFONO", "MENSAJE", "TIPO_FORM", "SON_CLIENTE", "ANOTACIONES",
    "VALOR_LEAD", "COSTE_DEL_LEAD", "ORIGEN_FORM_HA_FINALIZADO", "FACTURACION",
    "VERTICAL_EMPRESA", "LINKEDIN", "CARGO"
]

def init_sample_data():
    np.random.seed(42)
    n = 20
    data = {
        "N_FORM": [f"FRM-{1000+i}" for i in range(n)],
        "FECHA_ENVIO_FORM": pd.date_range(start="2025-03-01", periods=n, freq="3D"),
        "NOMBRE_EMPRESA": np.random.choice(["TechCorp", "IndusLab", "MediGroup", "DataFlow"], n),
        "NOMBRE_ENVIO_MAIL": np.random.choice(["Carlos R.", "Ana M.", "Luis P."], n),
        "MAIL": [f"user{i}@empresa.com" for i in range(n)],
        "TELÉFONO": [f"+34 600 {np.random.randint(100000, 999999)}" for i in range(n)],
        "MENSAJE": np.random.choice(["Interesados consultoría", "Solicitan demo", "Partnership", "Precios"], n),
        "TIPO_FORM": np.random.choice(["Web", "Landing", "Webinar", "Feria"], n),
        "SON_CLIENTE": np.random.choice(["Sí", "No"], n, p=[0.3, 0.7]),
        "ANOTACIONES": np.random.choice(["Follow-up", "Alta intención", "Presupuesto", "Evaluación"], n),
        "VALOR_LEAD": np.random.uniform(500, 15000, n),
        "COSTE_DEL_LEAD": np.random.uniform(20, 800, n),
        "ORIGEN_FORM_HA_FINALIZADO": np.random.choice(["Sí", "No", "Parcial"], n, p=[0.6, 0.2, 0.2]),
        "FACTURACION": np.random.choice(["<1M€", "1-5M€", "5-20M€", ">20M€"], n),
        "VERTICAL_EMPRESA": np.random.choice(["Industrial", "Tecnología", "Salud", "Finanzas"], n),
        "LINKEDIN": [f"https://linkedin.com/in/user{i}" for i in range(n)],
        "CARGO": np.random.choice(["CEO", "CMO", "Director Comercial", "CTO"], n)
    }
    df = pd.DataFrame(data)
    df["VALOR_LEAD"] = df["VALOR_LEAD"].round(2)
    df["COSTE_DEL_LEAD"] = df["COSTE_DEL_LEAD"].round(2)
    return df

def calcular_valoracion(df):
    df = df.copy()
    df.columns = df.columns.str.strip()  # Limpieza crítica
    df["ROI_LEAD"] = np.where(df["COSTE_DEL_LEAD"] > 0, (df["VALOR_LEAD"] - df["COSTE_DEL_LEAD"]) / df["COSTE_DEL_LEAD"], 0).round(2)
    df["PUNTUACION"] = 0
    df.loc[df["SON_CLIENTE"] == "Sí", "PUNTUACION"] += 20
    df.loc[df["ORIGEN_FORM_HA_FINALIZADO"] == "Sí", "PUNTUACION"] += 25
    df.loc[df["VALOR_LEAD"] > df["VALOR_LEAD"].median(), "PUNTUACION"] += 20
    df.loc[df["CARGO"].isin(["CEO", "CMO", "Director Comercial"]), "PUNTUACION"] += 25
    df.loc[df["FACTURACION"].isin(["5-20M€", ">20M€"]), "PUNTUACION"] += 10
    df["PUNTUACION"] = df["PUNTUACION"].clip(0, 100)
    conditions = [df["PUNTUACION"] >= 75, df["PUNTUACION"] >= 50, df["PUNTUACION"] >= 25]
    df["ESTADO_VALOR"] = np.select(conditions, ["🟢 Alto", "🟡 Medio", "🔴 Bajo"], default="🔴 Bajo")
    return df

# =============================================================
# 3. FUNCIONES OPENAI
# =============================================================
def consultar_openai_enriquecido(row, api_key, icp_config=None):
    if not api_key: return None, None, "⚠️ Falta API Key OpenAI."
    try:
        icp = icp_config or {"sectores_prioritarios": ["Tecnología", "Industrial", "Salud", "Finanzas"], "tamano_minimo": "Pequeña (10-50)", "cargos_decision": ["CEO", "CMO", "Director Comercial"], "facturacion_min": "1-5M€"}
        prompt = f"""Experto scoring B2B. Evalúa lead 0-100.
        ICP: {icp['sectores_prioritarios']} | {icp['tamano_minimo']} | {icp['cargos_decision']}
        Datos: Empresa: {row.get('NOMBRE_EMPRESA')}, Cargo: {row.get('CARGO')}, Mensaje: {row.get('MENSAJE')}
        Devuelve SOLO JSON: {{"score": int, "reasons": ["string"], "recommendation": "string", "fit_icp": "Alto"|"Medio"|"Bajo", "next_step_suggested": "string"}}"""
        client = openai.OpenAI(api_key=api_key)
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":"Analista scoring B2B."},{"role":"user","content":prompt}],
            temperature=0.2, response_format={"type":"json_object"}, max_tokens=400
        )
        return json.loads(res.choices[0].message.content), prompt, None
    except Exception as e:
        return None, prompt, f"❌ Error: {e}"

# =============================================================
# 4. INICIALIZACIÓN & SIDEBAR
# =============================================================
if "leads_df" not in st.session_state:
    st.session_state.leads_df = calcular_valoracion(init_sample_data())
if "df_filtrado" not in st.session_state: st.session_state.df_filtrado = st.session_state.leads_df.copy()
if "selected_lead" not in st.session_state: st.session_state.selected_lead = None
if "openai_key" not in st.session_state: st.session_state.openai_key = ""
if "ai_cache" not in st.session_state: st.session_state.ai_cache = {}
if "icp_config" not in st.session_state: st.session_state.icp_config = {"sectores_prioritarios": ["Tecnología", "Industrial", "Salud", "Finanzas"], "tamano_minimo": "Pequeña (10-50)", "cargos_decision": ["CEO", "CMO", "Director Comercial"], "facturacion_min": "1-5M€"}

df_raw = st.session_state.leads_df
df_raw.columns = df_raw.columns.str.strip()  # BLINDAJE ANTI-ESPACIOS

with st.sidebar:
    st.markdown('![](https://kaibot.es/wp-content/uploads/2020/07/image1.png) **KaiBot Leads**', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("🤖 **Configuración IA**")
    st.session_state.openai_key = st.text_input("API Key OpenAI", type="password", value=st.session_state.openai_key, placeholder="sk-proj-...")
    
    st.markdown("🎯 **ICP (Perfil Cliente)**")
    with st.expander("⚙️ Ajustar criterios"):
        icp_sect = st.multiselect("Sectores", ["Tecnología", "Industrial", "Salud", "Finanzas", "Retail"], default=st.session_state.icp_config["sectores_prioritarios"])
        icp_tam = st.selectbox("Tamaño mín", ["Micro (<10)", "Pequeña (10-50)", "Mediana (50-250)", "Grande (250+)"], index=["Micro (<10)", "Pequeña (10-50)", "Mediana (50-250)", "Grande (250+)"].index(st.session_state.icp_config["tamano_minimo"]))
        icp_car = st.multiselect("Cargos", ["CEO", "CMO", "Director Comercial", "Head of Growth", "CTO"], default=st.session_state.icp_config["cargos_decision"])
        icp_fac = st.selectbox("Facturación mín", ["<1M€", "1-5M€", "5-20M€", ">20M€"], index=["<1M€", "1-5M€", "5-20M€", ">20M€"].index(st.session_state.icp_config["facturacion_min"]))
        if st.button("Guardar ICP"):
            st.session_state.icp_config = {"sectores_prioritarios": icp_sect, "tamano_minimo": icp_tam, "cargos_decision": icp_car, "facturacion_min": icp_fac}
            st.success("✅ ICP actualizado")

    st.markdown("---")
    st.markdown("🔍 **Filtros**")
    search = st.text_input("Buscar", placeholder="Empresa, email...")
    c1, c2 = st.columns(2)
    with c1: vertical = st.multiselect("Vertical", options=df_raw["VERTICAL_EMPRESA"].unique().tolist(), default=df_raw["VERTICAL_EMPRESA"].unique().tolist())
    with c2: tipo_form = st.multiselect("Tipo", options=df_raw["TIPO_FORM"].unique().tolist(), default=df_raw["TIPO_FORM"].unique().tolist())
    c3, c4 = st.columns(2)
    with c3: cliente = st.selectbox("¿Cliente?", ["Todos", "Sí", "No"])
    with c4: exito = st.selectbox("Finalizado?", ["Todos", "Sí", "No", "Parcial"])
    
    # ✅ SLIDER BLINDADO
    safe_max = 10000
    if "VALOR_LEAD" in df_raw.columns:
        try:
            nums = pd.to_numeric(df_raw["VALOR_LEAD"], errors="coerce").dropna()
            if len(nums) > 0: safe_max = int(nums.max())
            if safe_max < 100: safe_max = 1000
        except: pass
        
    min_val, max_val = st.slider("Rango Valor (€)", 0, safe_max, (0, safe_max), step=100)

    # 📥 IMPORTADOR INTELIGENTE
    st.markdown("---")
    st.markdown("📥 **Importar CSV**")
    uploaded = st.file_uploader("Cargar CSV", type=["csv"], key="csv_uploader_v2")
    if uploaded:
        try:
            df_up = pd.read_csv(uploaded, encoding='utf-8-sig')
            df_up.columns = df_up.columns.str.strip()
            detected = df_up.columns.tolist()
            st.success(f"✅ {len(df_up)} filas detectadas.")
            
            if "import_map" not in st.session_state:
                st.session_state.import_map = {}
                for req in CAMPOS_REQ:
                    match = next((c for c in detected if req.lower() in c.lower()), None)
                    st.session_state.import_map[req] = match
                    
            with st.expander("⚙️ Mapeo de Columnas", expanded=True):
                st.caption("🟢 Críticos: Empresa, Email | El resto se rellena vacío si no se asigna.")
                for req in CAMPOS_REQ:
                    is_crit = req in ["NOMBRE_EMPRESA", "MAIL"]
                    icon = "🟢" if is_crit else "⚪"
                    col1, col2 = st.columns([2, 1])
                    with col1: st.markdown(f"{icon} **{req}**")
                    with col2:
                        opts = ["(Dejar vacío)"] + detected
                        cur = st.session_state.import_map.get(req)
                        sel = st.selectbox(f"Map {req}", options=opts, index=opts.index(cur) if cur in opts else 0, key=f"map_{req}", label_visibility="collapsed")
                        st.session_state.import_map[req] = sel
                        
                st.markdown("---")
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    crit_ok = all([st.session_state.import_map.get(c) != "(Dejar vacío)" for c in ["NOMBRE_EMPRESA", "MAIL"]])
                    if st.button("🚀 IMPORTAR", type="primary", disabled=not crit_ok, use_container_width=True):
                        data_dict = {}
                        for req in CAMPOS_REQ:
                            src = st.session_state.import_map.get(req)
                            if src and src != "(Dejar vacío)" and src in df_up.columns:
                                data_dict[req] = df_up[src]
                            else:
                                if req in ["VALOR_LEAD", "COSTE_DEL_LEAD"]: data_dict[req] = 0.0
                                elif req == "FECHA_ENVIO_FORM": data_dict[req] = datetime.now()
                                elif req == "SON_CLIENTE": data_dict[req] = "No"
                                elif req == "ORIGEN_FORM_HA_FINALIZADO": data_dict[req] = "Sí"
                                else: data_dict[req] = ""
                        st.session_state.leads_df = calcular_valoracion(pd.DataFrame(data_dict))
                        st.success("✅ Importación exitosa")
                        st.rerun()
                with col_btn2:
                    if st.button("🔄 Reset", use_container_width=True):
                        st.session_state.import_map = {}
                        st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

# Aplicar filtros
df_f = df_raw.copy()
if search: df_f = df_f[df_f.apply(lambda r: search.lower() in r.astype(str).str.lower().sum(), axis=1)]
if vertical != df_raw["VERTICAL_EMPRESA"].unique().tolist(): df_f = df_f[df_f["VERTICAL_EMPRESA"].isin(vertical)]
if tipo_form != df_raw["TIPO_FORM"].unique().tolist(): df_f = df_f[df_f["TIPO_FORM"].isin(tipo_form)]
if cliente != "Todos": df_f = df_f[df_f["SON_CLIENTE"] == cliente]
if exito != "Todos": df_f = df_f[df_f["ORIGEN_FORM_HA_FINALIZADO"] == exito]
df_f = df_f[(df_f["VALOR_LEAD"] >= min_val) & (df_f["VALOR_LEAD"] <= max_val)].sort_values("FECHA_ENVIO_FORM", ascending=False)
st.session_state.df_filtrado = df_f

# =============================================================
# 5. MAIN UI - 5 PESTAÑAS
# =============================================================
st.markdown('![](https://kaibot.es/wp-content/uploads/2020/07/image1.png) **Panel de Leads & Valoración**', unsafe_allow_html=True)
st.caption("Gestión, análisis y scoring inteligente B2B.")
st.markdown("---")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 KPIs", "📋 Lista", "🔍 Detalle", "➕ Nuevo", "🤖 Batch"])

with tab1:
    c1, c2, c3, c4 = st.columns(4)
    total = len(df_f); val_t = df_f["VALOR_LEAD"].sum(); cost_t = df_f["COSTE_DEL_LEAD"].sum()
    roi = ((val_t - cost_t) / cost_t) if cost_t > 0 else 0; cli = len(df_f[df_f["SON_CLIENTE"]=="Sí"])
    def kpi(l, v, s=""): st.markdown(f'<div class="kpi-card"><div class="kpi-label">{l}</div><div class="kpi-value">{v}</div><div style="color:var(--kaibot-gray);font-size:0.8rem;">{s}</div></div>', unsafe_allow_html=True)
    with c1: kpi("Leads", total, "Filtrados")
    with c2: kpi("Pipeline", f"{val_t:,.0f}€", f"{cost_t:,.0f}€ inv.")
    with c3: kpi("ROI", f"{roi:.2f}x", "Retorno")
    with c4: kpi("Clientes", f"{cli} ({cli/max(total,1)*100:.1f}%)", "Conversión")
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1: st.bar_chart(df_f.groupby("VERTICAL_EMPRESA")["VALOR_LEAD"].sum(), use_container_width=True)
    with c2: st.bar_chart(df_f.groupby("TIPO_FORM")["VALOR_LEAD"].mean(), use_container_width=True)

with tab2: st.dataframe(df_f, use_container_width=True, hide_index=True)

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
        if st.button("🤖 Consultar OpenAI"):
            ai_res, _, err = consultar_openai_enriquecido(row.to_dict(), st.session_state.openai_key, st.session_state.icp_config)
            if err: st.error(err)
            else:
                st.session_state.ai_cache[sel] = {"response": ai_res}
                idx = st.session_state.leads_df.index[st.session_state.leads_df["N_FORM"]==sel][0]
                st.session_state.leads_df.loc[idx, "AI_SCORE"] = ai_res.get("score")
                st.session_state.leads_df.loc[idx, "AI_REASONING"] = "; ".join(ai_res.get("reasons", []))
                st.rerun()
        if sel in st.session_state.ai_cache:
            cache = st.session_state.ai_cache[sel]
            st.markdown("### 🧠 Resultado IA")
            with st.expander("📥 JSON Respuesta", expanded=True): st.json(cache["response"])
            if "score" in cache["response"]:
                st.metric("Score IA", f"{cache['response']['score']}/100", delta=f"{cache['response']['score'] - row['PUNTUACION']}")
                st.markdown(f"**Fit ICP:** {cache['response'].get('fit_icp', 'N/A')}")
                if cache["response"].get("reasons"): st.markdown("**Razones:** " + "; ".join(cache["response"]["reasons"]))

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

with tab5:
    st.markdown("### 🤖 Batch Scoring IA")
    st.caption("Procesa múltiples leads filtrados simultáneamente.")
    if not st.session_state.openai_key:
        st.warning("⚠️ Introduce API Key OpenAI en el sidebar.")
    else:
        mode = st.radio("Modo", ["Todos los filtrados", "Seleccionar manualmente"], index=0, horizontal=True)
        leads_to_process = st.session_state.df_filtrado.copy() if mode == "Todos los filtrados" else df_f[df_f["N_FORM"].isin(st.multiselect("Selecciona leads", df_f["N_FORM"].tolist()))]
        
        if len(leads_to_process) > 0 and st.button(f"🚀 Ejecutar Scoring ({len(leads_to_process)} leads)", type="primary"):
            progress = st.progress(0); status = st.empty(); logs = []
            for i, idx in enumerate(leads_to_process.index):
                row = leads_to_process.loc[idx]
                progress.progress((i+1)/len(leads_to_process))
                status.text(f"🔄 {row.get('NOMBRE_EMPRESA')} ({i+1}/{len(leads_to_process)})")
                ai_res, _, err = consultar_openai_enriquecido(row.to_dict(), st.session_state.openai_key, st.session_state.icp_config)
                if not err and ai_res:
                    g_idx = st.session_state.leads_df.index[st.session_state.leads_df["N_FORM"] == row["N_FORM"]][0]
                    st.session_state.leads_df.loc[g_idx, "AI_SCORE"] = ai_res.get("score")
                    st.session_state.leads_df.loc[g_idx, "AI_REASONING"] = "; ".join(ai_res.get("reasons", []))
                    logs.append(f"✅ {row['NOMBRE_EMPRESA']}: {ai_res.get('score')}/100")
                else:
                    logs.append(f"❌ {row['NOMBRE_EMPRESA']}: {err}")
            status.text("✅ Completado.")
            with st.expander("📊 Resultados", expanded=True):
                for l in logs: st.caption(l)
            st.rerun()
        else:
            st.info("ℹ️ No hay leads para procesar.")

st.markdown('<div class="kaibot-footer">© 2026 KaiBot. Optimizado para gestión comercial B2B.</div>', unsafe_allow_html=True)
