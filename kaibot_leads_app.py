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
# 0. INICIALIZACIÓN SEGURA DE SESSION_STATE (Evita AttributeErrors)
# =============================================================
if "gcp_creds" not in st.session_state: st.session_state.gcp_creds = None
if "gcs_bucket" not in st.session_state: st.session_state.gcs_bucket = ""
if "gcs_path" not in st.session_state: st.session_state.gcs_path = ""
if "sheet_url" not in st.session_state: st.session_state.sheet_url = ""
if "openai_key" not in st.session_state: st.session_state.openai_key = ""
if "enable_cloud" not in st.session_state: st.session_state.enable_cloud = False

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
<style>
    :root {
        --kaibot-blue: #0066CC;
        --kaibot-blue-hover: #0052A3;
        --kaibot-dark: #1E293B;
        --kaibot-gray: #64748B;
        --kaibot-light: #F8FAFC;
        --sidebar-bg: #0F172A;
        --success: #10B981;
        --warning: #F59E0B;
        --danger: #EF4444;
    }
    
    .main { background-color: var(--kaibot-light); }
    h1, h2, h3, h4 { color: var(--kaibot-dark); font-weight: 600; }
    
    /* SIDEBAR OSCURO - ESTILO ORIGINAL */
    [data-testid="stSidebar"] { background-color: var(--sidebar-bg); }
    [data-testid="stSidebar"] * { color: white !important; }
    [data-testid="stSidebar"] input, [data-testid="stSidebar"] textarea, [data-testid="stSidebar"] select {
        background: rgba(255,255,255,0.08) !important; 
        border: 1px solid rgba(255,255,255,0.2) !important; 
        color: white !important;
    }
    
    /* TARJETAS KPI */
    .kpi-card { 
        background: white; 
        padding: 16px; 
        border-radius: 8px; 
        box-shadow: 0 2px 6px rgba(0,0,0,0.05); 
        text-align: center; 
    }
    .kpi-value { font-size: 1.8rem; font-weight: 700; color: var(--kaibot-dark); margin: 4px 0; }
    .kpi-label { font-size: 0.85rem; color: var(--kaibot-gray); text-transform: uppercase; letter-spacing: 0.5px; }
    
    /* FOOTER */
    .kaibot-footer { 
        text-align: center; 
        color: var(--kaibot-gray); 
        font-size: 0.85rem; 
        margin-top: 40px; 
        padding: 20px 0; 
        border-top: 1px solid #E2E8F0; 
    }
</style>
""", unsafe_allow_html=True)
# =============================================================
# 2. UTILIDADES CLOUD & IA (Blindadas con .get())
# =============================================================
def init_gcs_client():
    if not st.session_state.gcp_creds: return None
    return storage.Client(credentials=st.session_state.gcp_creds, project=st.session_state.gcp_creds.project_id)

def init_sheets_client(sheet_url):
    if not st.session_state.gcp_creds: return None
    try:
        gc = gspread.authorize(st.session_state.gcp_creds)
        return gc.open_by_url(sheet_url).sheet1
    except: return None

def load_from_gcs():
    try:
        client = init_gcs_client()
        if not client: return None
        blob = client.bucket(st.session_state.gcs_bucket).blob(st.session_state.gcs_path)
        if not blob.exists(): return None
        return pd.read_csv(io.StringIO(blob.download_as_text()))
    except Exception as e:
        st.warning(f"⚠️ GCS Load: {e}")
        return None

def save_to_gcs(df):
    try:
        client = init_gcs_client()
        if not client: return
        blob = client.bucket(st.session_state.gcs_bucket).blob(st.session_state.gcs_path)
        csv_buf = io.StringIO()
        df.to_csv(csv_buf, index=False)
        blob.upload_from_string(csv_buf.getvalue(), content_type="text/csv")
        st.success("✅ Guardado en GCS")
    except Exception as e: st.error(f"❌ GCS Error: {e}")

def pull_from_sheets():
    try:
        ws = init_sheets_client(st.session_state.sheet_url)
        if not ws: return None
        data = ws.get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception as e:
        st.warning(f"⚠️ Sheets: {e}")
        return None

def push_to_sheets(df):
    try:
        ws = init_sheets_client(st.session_state.sheet_url)
        if not ws: return
        ws.clear()
        ws.update([df.columns.tolist()] + df.values.tolist())
        st.success("✅ Sincronizado con Sheets")
    except Exception as e: st.error(f"❌ Sheets Error: {e}")

@st.cache_data(ttl=1800)
def apply_ai_scoring(df: pd.DataFrame, api_key: str) -> pd.DataFrame:
    if not api_key: return df
    try:
        client = openai.OpenAI(api_key=api_key)
        df = df.copy()
        df["AI_SCORE"], df["AI_REASONS"] = None, None
        for idx, row in df.iterrows():
            prompt = f"""Evalúa este lead B2B del 0 al 100. Devuelve SOLO JSON: {{"score": int, "reasons": ["string"]}}
            Empresa: {row.get('NOMBRE_EMPRESA','')} | Vertical: {row.get('VERTICAL_EMPRESA','')} | 
            Facturación: {row.get('FACTURACION','')} | Cargo: {row.get('CARGO','')} | Mensaje: {row.get('MENSAJE','')}"""
            res = client.chat.completions.create(
                model="gpt-4o-mini", messages=[{"role":"system","content":"Experto ventas B2B."},{"role":"user","content":prompt}],
                temperature=0.2, response_format={"type":"json_object"}
            )
            ai = json.loads(res.choices[0].message.content)
            df.at[idx, "AI_SCORE"] = ai["score"]
            df.at[idx, "AI_REASONS"] = ", ".join(ai["reasons"])
        if "PUNTUACION" in df.columns:
            df["PUNTUACION_FINAL"] = (df["PUNTUACION"]*0.4 + df["AI_SCORE"]*0.6).clip(0,100).round(1)
        return df
    except Exception as e:
        st.error(f"❌ AI Scoring: {e}")
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
        "NOMBRE_ENVIO_MAIL": np.random.choice(["Carlos R.","Ana M.","Luis P.","Sofia T.","Miguel A."], n),
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
        "CARGO": np.random.choice(["CEO","CMO","Director Comercial","Head of Growth","Consultor","CTO"], n)
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
# 4. SIDEBAR & CARGA INICIAL (Blindada)
# =============================================================
with st.sidebar:
    st.image("https://kaibot.es/wp-content/uploads/2020/07/image1.png", width=60)
    st.markdown("### KaiBot Leads")
    st.markdown("---")
    
    st.session_state.enable_cloud = st.checkbox("☁️ Activar Integración Cloud", value=st.session_state.enable_cloud)
    
    if st.session_state.enable_cloud:
        st.markdown("🔑 **Credenciales GCP**")
        uploaded_creds = st.file_uploader("Subir JSON SA", type=["json"], key="creds_uploader")
        if uploaded_creds is not None:
            try:
                st.session_state.gcp_creds = Credentials.from_service_account_info(json.load(uploaded_creds))
                st.success("✅ Credenciales en memoria")
            except Exception as e: st.error(f"❌ JSON inválido: {e}")
            
        st.session_state.gcs_bucket = st.text_input("Bucket GCS", value=st.session_state.gcs_bucket, placeholder="kaibot-leads")
        st.session_state.gcs_path = st.text_input("Path GCS", value=st.session_state.gcs_path, placeholder="leads/active.csv")
        st.session_state.sheet_url = st.text_input("URL Google Sheets", value=st.session_state.sheet_url, placeholder="https://docs.google.com/spreadsheets/d/...")
        
    st.session_state.openai_key = st.text_input("🤖 API Key OpenAI", type="password", value=st.session_state.openai_key)
    
    st.markdown("---")
    st.markdown("🔍 **Filtros**")
    search = st.text_input("Buscar", placeholder="Empresa, email...")
    col1, col2 = st.columns(2)
    with col1: vertical = st.multiselect("Vertical", options=["Todas"], default=["Todas"])
    with col2: tipo_form = st.multiselect("Tipo Form", options=["Todos"], default=["Todos"])
    cliente = st.selectbox("¿Es Cliente?", ["Todos", "Sí", "No"])
    exito = st.selectbox("Finalizado?", ["Todos", "Sí", "No", "Parcial"])
    min_val, max_val = st.slider("Rango Valor (€)", 0, 20000, (0, 20000), 100)
    
    st.markdown("---")
    st.markdown("📥 **Importar**")
    uploaded = st.file_uploader("Cargar CSV", type=["csv"])
    if uploaded:
        try:
            df_up = pd.read_csv(uploaded)
            st.session_state.leads_df = calcular_valoracion(df_up)
            st.success("✅ CSV cargado")
            st.rerun()
        except Exception as e: st.error(f"❌ {e}")
        
    if st.session_state.enable_cloud and st.button("🔄 Sync Cloud", type="primary"):
        push_to_sheets(st.session_state.leads_df)
        save_to_gcs(st.session_state.leads_df)
        
    if st.button("📤 Exportar CSV"):
        csv = st.session_state.df_filtrado.to_csv(index=False).encode("utf-8")
        st.download_button("Descargar", csv, f"leads_{datetime.now():%Y%m%d}.csv", "text/csv")

# Carga inicial segura (Evita AttributeError)
if "leads_df" not in st.session_state:
    df_init = None
    if st.session_state.enable_cloud and st.session_state.gcs_bucket and st.session_state.gcs_path:
        df_init = load_from_gcs()
    if (df_init is None or df_init.empty) and st.session_state.enable_cloud and st.session_state.sheet_url:
        df_init = pull_from_sheets()
    if df_init is None or df_init.empty:
        df_init = init_sample_data()
    st.session_state.leads_df = calcular_valoracion(df_init)

df_raw = st.session_state.leads_df

# Filtros dinámicos
if "VERTICAL_EMPRESA" in df_raw.columns:
    v_opts = df_raw["VERTICAL_EMPRESA"].unique().tolist()
    if "Todas" in vertical and v_opts: vertical = v_opts
if "TIPO_FORM" in df_raw.columns:
    t_opts = df_raw["TIPO_FORM"].unique().tolist()
    if "Todos" in tipo_form and t_opts: tipo_form = t_opts

df_f = df_raw.copy()
if search: df_f = df_f[df_f.apply(lambda r: search.lower() in r.astype(str).str.lower().sum(), axis=1)]
if "VERTICAL_EMPRESA" in df_f.columns and vertical != ["Todas"]: df_f = df_f[df_f["VERTICAL_EMPRESA"].isin(vertical)]
if "TIPO_FORM" in df_f.columns and tipo_form != ["Todos"]: df_f = df_f[df_f["TIPO_FORM"].isin(tipo_form)]
if cliente!="Todos": df_f = df_f[df_f["SON_CLIENTE"]==cliente]
if exito!="Todos": df_f = df_f[df_f["ORIGEN_FORM_HA_FINALIZADO"]==exito]
df_f = df_f[(df_f["VALOR_LEAD"]>=min_val) & (df_f["VALOR_LEAD"]<=max_val)].sort_values("FECHA_ENVIO_FORM", ascending=False)
st.session_state.df_filtrado = df_f

# =============================================================
# 5. MAIN UI
# =============================================================
st.markdown('### 📊 Panel de Leads & Valoración')
st.caption("Gestión, análisis y scoring inteligente de leads B2B.")
st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard KPIs", "📋 Lista Interactiva", "🔍 Detalle & Análisis", "➕ Nuevo Lead"])

# ================= LÓGICA TAB 4: NUEVO LEAD =================
with tab4:
    st.markdown("### ➕ Añadir Lead Manual")
    st.caption("Introduce los datos del contacto para valorarlo automáticamente.")
    
    with st.form("form_nuevo_lead", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            in_empresa = st.text_input("NOMBRE_EMPRESA", placeholder="Ej: TechCorp")
            in_email = st.text_input("MAIL", placeholder="contacto@empresa.com")
            in_cargo = st.text_input("CARGO", placeholder="Ej: CTO")
            in_vertical = st.selectbox("VERTICAL_EMPRESA", ["Industrial", "Tecnología", "Salud", "Logística", "Finanzas", "Otro"])
        
        with c2:
            in_telefono = st.text_input("TELÉFONO", placeholder="+34 600...")
            in_nombre_contacto = st.text_input("NOMBRE_ENVIO_MAIL", placeholder="Juan Pérez")
            in_facturacion = st.selectbox("FACTURACION", ["<1M€", "1-5M€", "5-20M€", ">20M€"])
            in_son_cliente = st.selectbox("SON_CLIENTE", ["No", "Sí"])
            
        with c3:
            in_valor = st.number_input("VALOR_LEAD (€)", min_value=0.0, value=1000.0)
            in_coste = st.number_input("COSTE_DEL_LEAD (€)", min_value=0.0, value=50.0)
            in_mensaje = st.text_area("MENSAJE", height=120)
            in_tipo_form = st.selectbox("TIPO_FORM", ["Manual", "Webinar", "Contacto Directo", "Web General"])

        btn_guardar = st.form_submit_button("💾 Guardar y Valorar Lead", type="primary")

        if btn_guardar:
            if not in_empresa or not in_email:
                st.error("⚠️ La Empresa y el Email son obligatorios.")
            else:
                # 1. Crear el nuevo registro
                nuevo_registro = {
                    "N_FORM": f"MANUAL-{datetime.now().strftime('%H%M%S')}",
                    "FECHA_ENVIO_FORM": datetime.now(),
                    "NOMBRE_EMPRESA": in_empresa,
                    "NOMBRE_ENVIO_MAIL": in_nombre_contacto,
                    "MAIL": in_email,
                    "TELÉFONO": in_telefono,
                    "MENSAJE": in_mensaje,
                    "TIPO_FORM": in_tipo_form,
                    "SON_CLIENTE": in_son_cliente,
                    "ANOTACIONES": "Añadido manualmente",
                    "VALOR_LEAD": in_valor,
                    "COSTE_DEL_LEAD": in_coste,
                    "ORIGEN_FORM_HA_FINALIZADO": "Sí",
                    "FACTURACION": in_facturacion,
                    "VERTICAL_EMPRESA": in_vertical,
                    "LINKEDIN": "",
                    "CARGO": in_cargo
                }
                
                # 2. Añadir al DataFrame principal
                new_df = pd.DataFrame([nuevo_registro])
                st.session_state.leads_df = pd.concat([st.session_state.leads_df, new_df], ignore_index=True)
                
                # 3. Recalcular valoraciones (ROI, Puntuación)
                st.session_state.leads_df = calcular_valoracion(st.session_state.leads_df)
                
                st.success(f"✅ Lead **{in_empresa}** añadido y valorado correctamente.")
                st.rerun()

# ================= LÓGICA TAB 1, 2, 3 (EXISTENTE) =================
with tab1:
    c1,c2,c3,c4 = st.columns(4)
    val_t = df_f["VALOR_LEAD"].sum(); cost_t = df_f["COSTE_DEL_LEAD"].sum()
    roi = ((val_t-cost_t)/cost_t) if cost_t>0 else 0
    cli = len(df_f[df_f["SON_CLIENTE"]=="Sí"])
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">Leads</div><div class="kpi-value">{len(df_f)}</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">Pipeline</div><div class="kpi-value">{val_t:,.0f}€</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">ROI</div><div class="kpi-value">{roi:.2f}x</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">Clientes</div><div class="kpi-value">{cli}</div></div>', unsafe_allow_html=True)
    if len(df_f)>0:
        st.bar_chart(df_f.groupby("VERTICAL_EMPRESA")["VALOR_LEAD"].sum())

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
            if st.session_state.enable_cloud and st.session_state.sheet_url: push_to_sheets(st.session_state.leads_df)
            st.success("✅ Actualizado")
            st.rerun()
            
        if st.button("🤖 Recalcular con IA"):
            if not st.session_state.openai_key: st.warning("Introduce API Key OpenAI en el sidebar"); st.stop()
            with st.spinner("Analizando con GPT-4o-mini..."):
                st.session_state.leads_df = apply_ai_scoring(st.session_state.leads_df, st.session_state.openai_key)
                if "PUNTUACION_FINAL" in st.session_state.leads_df.columns:
                    st.session_state.leads_df["PUNTUACION"] = st.session_state.leads_df["PUNTUACION_FINAL"]
                st.success("✅ Scoring IA aplicado (60% IA / 40% Reglas)")
                st.rerun()

st.markdown('<div class="kaibot-footer">© 2026 KaiBot. Optimizado para gestión comercial B2B.</div>', unsafe_allow_html=True)
