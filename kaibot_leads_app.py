import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io, json, os
import openai
from google.cloud import storage
from google.oauth2.service_account import Credentials
import gspread

# =============================================================
# 1. CONFIGURACIÓN & UX KAIBOT
# =============================================================
st.set_page_config(
    page_title="KaiBot Lead Manager",
    page_icon="https://kaibot.es/wp-content/uploads/2020/07/image1.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    :root {
        --kaibot-blue: #0066CC; --kaibot-blue-hover: #0052A3; --kaibot-dark: #1E293B;
        --kaibot-gray: #64748B; --kaibot-light: #F8FAFC; --sidebar-bg: #0F172A;
    }
    .main { background-color: var(--kaibot-light); }
    h1, h2, h3, h4 { color: var(--kaibot-dark); font-weight: 600; }
    .stButton > button[kind="primary"] { background-color: var(--kaibot-blue); color: white; border: none; font-weight: 500; }
    .stButton > button[kind="primary"]:hover { background-color: var(--kaibot-blue-hover); }
    .stTabs [data-baseweb="tab-list"] { background: white; border-bottom: 2px solid #E2E8F0; gap: 4px; }
    .stTabs [data-baseweb="tab-list"] button[role="tab"] { background: transparent; color: var(--kaibot-gray); font-weight: 500; border-radius: 6px 6px 0 0; padding: 10px 20px; transition: all 0.2s; }
    .stTabs [data-baseweb="tab-list"] button[role="tab"][aria-selected="true"] { background: var(--kaibot-blue); color: white; font-weight: 600; border-bottom: 3px solid var(--kaibot-blue); }
    .stTabs [data-baseweb="tab-panel"] { padding: 24px; background: white; border-radius: 0 0 8px 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
    [data-testid="stSidebar"] { background-color: var(--sidebar-bg); }
    [data-testid="stSidebar"] * { color: white !important; }
    [data-testid="stSidebar"] input, [data-testid="stSidebar"] textarea, [data-testid="stSidebar"] select {
        background: rgba(255,255,255,0.08) !important; border: 1px solid rgba(255,255,255,0.2) !important; color: white !important;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"] { background-color: var(--kaibot-blue); border: none; }
    .kpi-card { background: white; padding: 16px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); text-align: center; }
    .kpi-value { font-size: 1.8rem; font-weight: 700; color: var(--kaibot-dark); margin: 4px 0; }
    .kpi-label { font-size: 0.85rem; color: var(--kaibot-gray); text-transform: uppercase; letter-spacing: 0.5px; }
    .kaibot-footer { text-align: center; color: var(--kaibot-gray); font-size: 0.85rem; margin-top: 40px; padding: 20px 0; border-top: 1px solid #E2E8F0; }
""", unsafe_allow_html=True)

# =============================================================
# 2. UTILIDADES CLOUD & IA
# =============================================================
def init_gcs_client():
    if "gcp_creds" not in st.session_state: return None
    return storage.Client(credentials=st.session_state.gcp_creds, project=st.session_state.gcp_creds.project_id)

def init_sheets_client(sheet_url):
    if "gcp_creds" not in st.session_state: return None
    gc = gspread.authorize(st.session_state.gcp_creds)
    return gc.open_by_url(sheet_url).sheet1

def load_from_gcs(bucket, path):
    try:
        client = init_gcs_client()
        if not client: return None
        blob = client.bucket(bucket).blob(path)
        if not blob.exists(): return None
        return pd.read_csv(io.StringIO(blob.download_as_text()))
    except Exception as e:
        st.warning(f"⚠️ GCS: {e}")
        return None

def save_to_gcs(df, bucket, path):
    try:
        client = init_gcs_client()
        if not client: return
        blob = client.bucket(bucket).blob(path)
        csv_buf = io.StringIO()
        df.to_csv(csv_buf, index=False)
        blob.upload_from_string(csv_buf.getvalue(), content_type="text/csv")
        st.success("✅ Guardado en GCS")
    except Exception as e:
        st.error(f"❌ GCS Error: {e}")

def pull_from_sheets(url, sheet_name="Leads"):
    try:
        ws = init_sheets_client(url)
        if not ws: return None
        data = ws.get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception as e:
        st.warning(f"⚠️ Sheets: {e}")
        return None

def push_to_sheets(df, url, mode="overwrite"):
    try:
        ws = init_sheets_client(url)
        if not ws: return
        if mode == "overwrite":
            ws.clear()
            ws.update([df.columns.tolist()] + df.values.tolist())
        else:
            ws.append_rows(df.values.tolist(), value_input_option="USER_ENTERED")
        st.success("✅ Sincronizado con Sheets")
    except Exception as e:
        st.error(f"❌ Sheets Error: {e}")

@st.cache_data(ttl=1800)
def apply_ai_scoring(df: pd.DataFrame, api_key: str) -> pd.DataFrame:
    if not api_key: return df
    client = openai.OpenAI(api_key=api_key)
    df = df.copy()
    for col in ["AI_SCORE", "AI_REASONS"]: df[col] = None
    
    for idx, row in df.iterrows():
        prompt = f"""Evalúa este lead B2B del 0 al 100. Devuelve SOLO JSON: {{"score": int, "reasons": ["string"]}}
        Empresa: {row.get('NOMBRE_EMPRESA','')} | Vertical: {row.get('VERTICAL_EMPRESA','')} | 
        Facturación: {row.get('FACTURACION','')} | Cargo: {row.get('CARGO','')} | Mensaje: {row.get('MENSAJE','')}"""
        try:
            res = client.chat.completions.create(
                model="gpt-4o-mini", messages=[{"role":"system","content":"Experto ventas B2B."},{"role":"user","content":prompt}],
                temperature=0.2, response_format={"type":"json_object"}
            )
            ai = json.loads(res.choices[0].message.content)
            df.at[idx, "AI_SCORE"] = ai["score"]
            df.at[idx, "AI_REASONS"] = ", ".join(ai["reasons"])
        except:
            df.at[idx, "AI_SCORE"] = 50
            df.at[idx, "AI_REASONS"] = "API fallback"
            
    if "PUNTUACION" in df.columns:
        df["PUNTUACION_FINAL"] = (df["PUNTUACION"]*0.4 + df["AI_SCORE"]*0.6).clip(0,100).round(1)
    return df

# =============================================================
# 3. MOTOR DE DATOS & VALORACIÓN
# =============================================================
def init_sample_data():
    np.random.seed(42)
    n = 25
    return pd.DataFrame({
        "N_FORM": [f"FRM-{1000+i}" for i in range(n)],
        "FECHA_ENVIO_FORM": pd.date_range(start="2025-03-01", periods=n, freq="3D"),
        "NOMBRE_EMPRESA": np.random.choice(["TechCorp","IndusLab","MediGroup","DataFlow","GreenSolutions"], n),
        "NOMBRE_ENVIO_MAIL": np.random.choice(["Carlos R.","Ana M.","Luis P.","Sofia T."], n),
        "MAIL": [f"user{i}@empresa.com" for i in range(n)],
        "TELÉFONO": [f"+34 600 {np.random.randint(100000,999999)}" for i in range(n)],
        "MENSAJE": np.random.choice(["Interesados consultoría","Solicitan demo","Contacto partnership","Consulta precios"], n),
        "TIPO_FORM": np.random.choice(["Web General","Landing Campaña","Webinar","Feria"], n),
        "SON_CLIENTE": np.random.choice(["Sí","No"], n, p=[0.3,0.7]),
        "ANOTACIONES": np.random.choice(["Requiere follow-up","Alta intención","Presupuesto definido","En evaluación"], n),
        "VALOR_LEAD": np.random.uniform(500,15000,n).round(2),
        "COSTE_DEL_LEAD": np.random.uniform(20,800,n).round(2),
        "ORIGEN_FORM_HA_FINALIZADO": np.random.choice(["Sí","No","Parcial"], n, p=[0.6,0.2,0.2]),
        "FACTURACION": np.random.choice(["<1M€","1-5M€","5-20M€",">20M€"], n),
        "VERTICAL_EMPRESA": np.random.choice(["Industrial","Tecnología","Salud","Logística","Finanzas"], n),
        "LINKEDIN": [f"https://linkedin.com/in/user{i}" for i in range(n)],
        "CARGO": np.random.choice(["CEO","CMO","Director Comercial","Head of Growth","Consultor"], n)
    })

def calcular_valoracion(df):
    df = df.copy()
    df.columns = df.columns.str.strip()
    df["ROI_LEAD"] = np.where(df["COSTE_DEL_LEAD"]>0, (df["VALOR_LEAD"]-df["COSTE_DEL_LEAD"])/df["COSTE_DEL_LEAD"], 0).round(2)
    df["PUNTUACION"] = 0
    df.loc[df["SON_CLIENTE"]=="Sí", "PUNTUACION"] += 20
    df.loc[df["ORIGEN_FORM_HA_FINALIZADO"]=="Sí", "PUNTUACION"] += 25
    df.loc[df["VALOR_LEAD"]>df["VALOR_LEAD"].median(), "PUNTUACION"] += 20
    df.loc[df["CARGO"].isin(["CEO","CMO","Director Comercial"]), "PUNTUACION"] += 25
    df.loc[df["FACTURACION"].isin(["5-20M€",">20M€"]), "PUNTUACION"] += 10
    df["PUNTUACION"] = df["PUNTUACION"].clip(0,100)
    df["ESTADO_VALOR"] = np.select([df["PUNTUACION"]>=75, df["PUNTUACION"]>=50, df["PUNTUACION"]>=25], 
                                   ["🟢 Alto Potencial","🟡 Medio","🔴 Bajo"], default="🔴 Bajo")
    return df

# =============================================================
# 4. INICIALIZACIÓN & SIDEBAR
# =============================================================
with st.sidebar:
    st.image("https://kaibot.es/wp-content/uploads/2020/07/image1.png", width=60)
    st.markdown("### KaiBot Leads")
    st.markdown("---")
    
    # CHECKBOX CREDENCIALES GOOGLE
    enable_cloud = st.checkbox("☁️ Activar Integración Cloud (GCS/Sheets)")
    if enable_cloud:
        st.markdown("🔑 **Credenciales GCP**")
        uploaded_creds = st.file_uploader("Subir JSON de Service Account", type=["json"])
        if uploaded_creds is not None:
            try:
                st.session_state.gcp_creds = Credentials.from_service_account_info(json.load(uploaded_creds))
                st.success("✅ Credenciales cargadas en memoria")
            except Exception as e:
                st.error(f"❌ JSON inválido: {e}")
                
        st.session_state.gcs_bucket = st.text_input("Bucket GCS", placeholder="kaibot-leads-prod")
        st.session_state.gcs_path = st.text_input("Path GCS", placeholder="leads/active.csv")
        st.session_state.sheet_url = st.text_input("URL Google Sheets", placeholder="https://docs.google.com/spreadsheets/d/...")
        
    st.markdown("🤖 **OpenAI Scoring**")
    st.session_state.openai_key = st.text_input("API Key OpenAI", type="password")
    
    st.markdown("---")
    st.markdown("🔍 **Filtros Avanzados**")
    search = st.text_input("Buscar empresa/email/cargo", placeholder="Ej: TechCorp, CMO...")
    col1, col2 = st.columns(2)
    with col1: vertical_sel = st.multiselect("Vertical", options=["Todas"], default=["Todas"])
    with col2: tipo_sel = st.multiselect("Tipo Form", options=["Todos"], default=["Todos"])
    cliente_sel = st.selectbox("¿Es Cliente?", ["Todos", "Sí", "No"])
    exito_sel = st.selectbox("Formulario Finalizado?", ["Todos", "Sí", "No", "Parcial"])
    min_val, max_val = st.slider("Rango Valor (€)", 0, 20000, (0, 20000), 100)
    
    st.markdown("---")
    st.markdown("📥 **Importar/Exportar**")
    uploaded = st.file_uploader("Cargar CSV", type=["csv"])
    if uploaded:
        try:
            df_up = pd.read_csv(uploaded)
            st.session_state.leads_df = calcular_valoracion(df_up)
            st.success("✅ CSV cargado")
            st.rerun()
        except Exception as e: st.error(f"❌ {e}")
        
    if enable_cloud and st.session_state.get("sheet_url") and st.session_state.get("gcp_creds"):
        if st.button("🔄 Sync Cloud", type="primary"):
            push_to_sheets(st.session_state.leads_df, st.session_state.sheet_url)
            save_to_gcs(st.session_state.leads_df, st.session_state.gcs_bucket, st.session_state.gcs_path)
            
    if st.button("📤 Exportar CSV"):
        csv = st.session_state.df_filtrado.to_csv(index=False).encode("utf-8")
        st.download_button("Descargar", csv, f"leads_{datetime.now():%Y%m%d}.csv", "text/csv")

# Carga inicial segura
if "leads_df" not in st.session_state:
    df_init = None
    if enable_cloud and st.session_state.get("gcs_bucket") and st.session_state.get("gcp_creds"):
        df_init = load_from_gcs(st.session_state.gcs_bucket, st.session_state.gcs_path)
    if df_init is None or df_init.empty and enable_cloud and st.session_state.get("sheet_url"):
        df_init = pull_from_sheets(st.session_state.sheet_url)
    if df_init is None or df_init.empty:
        df_init = init_sample_data()
    st.session_state.leads_df = calcular_valoracion(df_init)

df_raw = st.session_state.leads_df

# Preparar filtros dinámicos
if "VERTICAL_EMPRESA" in df_raw.columns:
    v_options = df_raw["VERTICAL_EMPRESA"].unique().tolist()
    if "Todas" in vertical_sel and len(v_options)>0: vertical_sel = v_options
if "TIPO_FORM" in df_raw.columns:
    t_options = df_raw["TIPO_FORM"].unique().tolist()
    if "Todos" in tipo_sel and len(t_options)>0: tipo_sel = t_options

df_f = df_raw.copy()
if search: df_f = df_f[df_f.apply(lambda r: search.lower() in r.astype(str).str.lower().sum(), axis=1)]
if "VERTICAL_EMPRESA" in df_f.columns and vertical_sel != ["Todas"]: df_f = df_f[df_f["VERTICAL_EMPRESA"].isin(vertical_sel)]
if "TIPO_FORM" in df_f.columns and tipo_sel != ["Todos"]: df_f = df_f[df_f["TIPO_FORM"].isin(tipo_sel)]
if cliente_sel!="Todos": df_f = df_f[df_f["SON_CLIENTE"]==cliente_sel]
if exito_sel!="Todos": df_f = df_f[df_f["ORIGEN_FORM_HA_FINALIZADO"]==exito_sel]
df_f = df_f[(df_f["VALOR_LEAD"]>=min_val) & (df_f["VALOR_LEAD"]<=max_val)].sort_values("FECHA_ENVIO_FORM", ascending=False)
st.session_state.df_filtrado = df_f

# =============================================================
# 5. MAIN UI
# =============================================================
st.markdown('### 📊 Panel de Leads & Valoración')
st.caption("Gestión, análisis y scoring inteligente de leads captados por formularios.")
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📈 Dashboard KPIs", "📋 Lista Interactiva", "🔍 Detalle & IA"])

with tab1:
    c1,c2,c3,c4 = st.columns(4)
    val_t = df_f["VALOR_LEAD"].sum(); cost_t = df_f["COSTE_DEL_LEAD"].sum()
    roi = ((val_t-cost_t)/cost_t) if cost_t>0 else 0
    cli = len(df_f[df_f["SON_CLIENTE"]=="Sí"])
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">Leads Activos</div><div class="kpi-value">{len(df_f)}</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">Valor Pipeline</div><div class="kpi-value">{val_t:,.0f}€</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">ROI Global</div><div class="kpi-value">{roi:.2f}x</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">Clientes</div><div class="kpi-value">{cli} ({cli/max(len(df_f),1)*100:.1f}%)</div></div>', unsafe_allow_html=True)
    c1,c2 = st.columns(2)
    if len(df_f)>0:
        c1.bar_chart(df_f.groupby("VERTICAL_EMPRESA")["VALOR_LEAD"].sum())
        c2.bar_chart(df_f.groupby("TIPO_FORM")["VALOR_LEAD"].mean())

with tab2:
    st.dataframe(df_f, use_container_width=True, hide_index=True)

with tab3:
    st.markdown("### 🔍 Análisis & Scoring IA")
    sel = st.selectbox("Lead", options=df_f["N_FORM"].tolist() if len(df_f)>0 else [])
    if sel:
        row = df_f[df_f["N_FORM"]==sel].iloc[0]
        c1,c2 = st.columns([2,1])
        with c1:
            st.markdown(f"**{row['NOMBRE_EMPRESA']}** | {row['CARGO']} | `{row['MAIL']}`")
            st.info(row['MENSAJE'])
            st.caption(f"Anotaciones: {row['ANOTACIONES']}")
        with c2:
            st.metric("Valor", f"{row['VALOR_LEAD']:,.0f}€")
            st.progress(row['PUNTUACION']/100)
            st.caption(f"Score: {row['PUNTUACION']:.0f} | {row['ESTADO_VALOR']}")
            
        new_note = st.text_area("📝 Anotaciones", value=str(row['ANOTACIONES']), label_visibility="collapsed")
        if st.button("💾 Guardar Cambios"):
            idx = st.session_state.leads_df[st.session_state.leads_df["N_FORM"]==sel].index[0]
            st.session_state.leads_df.at[idx, "ANOTACIONES"] = new_note
            st.session_state.leads_df = calcular_valoracion(st.session_state.leads_df)
            st.success("✅ Actualizado")
            if enable_cloud and st.session_state.get("sheet_url"): push_to_sheets(st.session_state.leads_df, st.session_state.sheet_url)
            st.rerun()
            
        if st.button("🤖 Recalcular con IA"):
            if not st.session_state.get("openai_key"): st.warning("Introduce API Key de OpenAI en el sidebar"); st.stop()
            with st.spinner("Analizando con GPT-4o-mini..."):
                st.session_state.leads_df = apply_ai_scoring(st.session_state.leads_df, st.session_state.openai_key)
                if "PUNTUACION_FINAL" in st.session_state.leads_df.columns:
                    st.session_state.leads_df["PUNTUACION"] = st.session_state.leads_df["PUNTUACION_FINAL"]
                st.success("✅ Scoring IA aplicado (Pesa 60% IA / 40% Reglas)")
                st.rerun()

st.markdown('<div class="kaibot-footer">© 2026 KaiBot. Optimizado para gestión comercial B2B.</div>', unsafe_allow_html=True)
