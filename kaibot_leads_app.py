import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io
import json
import openai
from google.cloud import storage

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
    }
    .main { background-color: var(--kaibot-light); }
    h1, h2, h3, h4 { color: var(--kaibot-dark); font-weight: 600; }
    
    .stButton > button[kind="primary"] { background-color: var(--kaibot-blue); color: white; border: none; font-weight: 500; }
    .stButton > button[kind="primary"]:hover { background-color: var(--kaibot-blue-hover); }
    
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
    
    .kpi-card { background: white; padding: 14px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); text-align: center; }
    .kpi-value { font-size: 1.6rem; font-weight: 700; color: var(--kaibot-dark); margin: 2px 0; }
    .kpi-label { font-size: 0.8rem; color: var(--kaibot-gray); text-transform: uppercase; letter-spacing: 0.5px; }
</style>
""", unsafe_allow_html=True)

# =============================================================
# 2. MOTOR DE DATOS & VALORACIÓN (REGLAS + IA)
# =============================================================
CAMPOS_REQ = [
    "N_FORM", "FECHA_ENVIO_FORM", "NOMBRE_EMPRESA", "NOMBRE_ENVIO_MAIL", "MAIL",
    "TELÉFONO", "MENSAJE", "TIPO_FORM", "SON_CLIENTE", "ANOTACIONES",
    "VALOR_LEAD", "COSTE_DEL_LEAD", "ORIGEN_FORM_HA_FINALIZADO", "FACTURACION",
    "VERTICAL_EMPRESA", "LINKEDIN", "CARGO"
]

def init_sample_data():
    np.random.seed(42)
    n = 15
    data = {
        "N_FORM": [f"FRM-{1000+i}" for i in range(n)],
        "FECHA_ENVIO_FORM": pd.date_range(start="2026-03-01", periods=n, freq="3D"),
        "NOMBRE_EMPRESA": np.random.choice(["TechCorp", "IndusLab", "MediGroup", "DataFlow"], n),
        "NOMBRE_ENVIO_MAIL": np.random.choice(["Carlos R.", "Ana M.", "Luis P."], n),
        "MAIL": [f"user{i}@empresa.com" for i in range(n)],
        "TELÉFONO": [f"+34 600 {np.random.randint(100000, 999999)}" for i in range(n)],
        "MENSAJE": np.random.choice(["Interesados consultoría", "Solicitan demo", "Contacto partnership"], n),
        "TIPO_FORM": np.random.choice(["Web General", "Landing Campaña", "Webinar"], n),
        "SON_CLIENTE": np.random.choice(["Sí", "No"], n, p=[0.3, 0.7]),
        "ANOTACIONES": np.random.choice(["Requiere follow-up", "Alta intención", "Presupuesto definido"], n),
        "VALOR_LEAD": np.random.uniform(500, 15000, n),
        "COSTE_DEL_LEAD": np.random.uniform(20, 800, n),
        "ORIGEN_FORM_HA_FINALIZADO": np.random.choice(["Sí", "No", "Parcial"], n, p=[0.6, 0.2, 0.2]),
        "FACTURACION": np.random.choice(["<1M€", "1-5M€", "5-20M€", ">20M€"], n),
        "VERTICAL_EMPRESA": np.random.choice(["Industrial", "Tecnología", "Salud", "Finanzas"], n),
        "LINKEDIN": [f"https://linkedin.com/in/user{i}" for i in range(n)],
        "CARGO": np.random.choice(["CEO", "CMO", "Director Comercial", "Head of Growth"], n)
    }
    return pd.DataFrame(data)

def calcular_valoracion(df):
    """Aplica reglas de negocio para puntuación"""
    df = df.copy()
    df.columns = df.columns.str.strip() # Limpieza crítica de espacios
    
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

def aplicar_scoring_ia(row, api_key):
    """Consulta a OpenAI para scoring predictivo"""
    if not api_key:
        return {"score": 0, "reasoning": "API Key no configurada", "probability": 0.0}
    
    try:
        client = openai.OpenAI(api_key=api_key)
        prompt = f"""
        Actúa como experto en ventas B2B. Evalúa este lead (0-100) y probabilidad de cierre (0.0-1.0).
        Devuelve SOLO JSON: {{"score": int, "reasoning": "string", "probability": float}}
        
        Datos: Empresa: {row.get('NOMBRE_EMPRESA','')}, Cargo: {row.get('CARGO','')}, 
        Vertical: {row.get('VERTICAL_EMPRESA','')}, Mensaje: {row.get('MENSAJE','')},
        Facturación: {row.get('FACTURACION','')}, Anotaciones: {row.get('ANOTACIONES','')}
        """
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Eres un analista de datos B2B experto."},
                      {"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"score": 0, "reasoning": f"Error API: {str(e)}", "probability": 0.0}

# Funciones GCS
def upload_df_to_gcs(df, bucket_name, blob_name, credentials_json=None):
    try:
        if credentials_json:
            client = storage.Client.from_service_account_info(credentials_json)
        else:
            client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        csv_data = df.to_csv(index=False)
        blob.upload_from_string(csv_data, content_type='text/csv')
        return True
    except Exception as e:
        st.error(f"Error GCS Upload: {e}")
        return False

def download_df_from_gcs(bucket_name, blob_name, credentials_json=None):
    try:
        if credentials_json:
            client = storage.Client.from_service_account_info(credentials_json)
        else:
            client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        if not blob.exists(): return None
        csv_data = blob.download_as_text()
        return pd.read_csv(io.StringIO(csv_data))
    except Exception as e:
        st.error(f"Error GCS Download: {e}")
        return None

# =============================================================
# 3. INICIALIZACIÓN & SESSION STATE
# =============================================================
if "leads_df" not in st.session_state:
    st.session_state.leads_df = calcular_valoracion(init_sample_data())
if "gcs_creds" not in st.session_state: st.session_state.gcs_creds = None
if "openai_key" not in st.session_state: st.session_state.openai_key = ""

df_raw = st.session_state.leads_df

# =============================================================
# 4. SIDEBAR (CONFIGURACIÓN & FILTROS)
# =============================================================
with st.sidebar:
    st.markdown("### 🤖 KaiBot Leads")
    st.markdown("---")
    
    st.markdown("☁️ **Configuración GCS**")
    bucket_name = st.text_input("Nombre Bucket", placeholder="kaibot-leads")
    creds_file = st.file_uploader("Credenciales JSON", type=["json"], label_visibility="collapsed")
    
    if creds_file:
        try:
            st.session_state.gcs_creds = json.load(creds_file)
            st.success("✅ Credenciales cargadas")
        except: st.error("❌ JSON inválido")
        
    col_gcs1, col_gcs2 = st.columns(2)
    with col_gcs1:
        if st.button(" Cargar GCS", use_container_width=True):
            if bucket_name and st.session_state.gcs_creds:
                with st.spinner("Descargando..."):
                    df_cloud = download_df_from_gcs(bucket_name, "leads_export.csv", st.session_state.gcs_creds)
                    if df_cloud is not None:
                        st.session_state.leads_df = calcular_valoracion(df_cloud)
                        st.success("✅ Datos cargados desde Cloud")
                        st.rerun()
    with col_gcs2:
        if st.button("💾 Guardar GCS", use_container_width=True):
            if bucket_name and st.session_state.gcs_creds:
                with st.spinner("Subiendo..."):
                    if upload_df_to_gcs(st.session_state.leads_df, bucket_name, "leads_export.csv", st.session_state.gcs_creds):
                        st.success("✅ Guardado en Cloud")

    st.markdown("---")
    st.markdown(" **Filtros**")
    search = st.text_input("Buscar empresa/email...", placeholder="Ej: TechCorp")
    cliente = st.selectbox("¿Es Cliente?", ["Todos", "Sí", "No"])
    min_val, max_val = st.slider("Rango Valor (€)", 0, int(df_raw["VALOR_LEAD"].max()), (0, int(df_raw["VALOR_LEAD"].max())), 100)

    st.markdown("---")
    st.markdown("🤖 **OpenAI API Key**")
    st.session_state.openai_key = st.text_input("sk-...", type="password", value=st.session_state.openai_key)

# Aplicar filtros
df_f = df_raw.copy()
if search: df_f = df_f[df_f.apply(lambda r: search.lower() in r.astype(str).str.lower().sum(), axis=1)]
if cliente != "Todos": df_f = df_f[df_f["SON_CLIENTE"] == cliente]
df_f = df_f[(df_f["VALOR_LEAD"] >= min_val) & (df_f["VALOR_LEAD"] <= max_val)].sort_values("FECHA_ENVIO_FORM", ascending=False)

# =============================================================
# 5. MAIN UI
# =============================================================
st.markdown("### 📊 Panel de Leads & Valoración")
st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["📈 KPIs", "📋 Lista", "🔍 Detalle IA", "➕ Nuevo Lead"])

with tab1:
    c1, c2, c3, c4 = st.columns(4)
    val_t = df_f["VALOR_LEAD"].sum()
    roi = ((val_t - df_f["COSTE_DEL_LEAD"].sum()) / df_f["COSTE_DEL_LEAD"].sum()) if df_f["COSTE_DEL_LEAD"].sum() > 0 else 0
    
    c1.markdown(f'<div class="kpi-card"><div class="kpi-label">Leads</div><div class="kpi-value">{len(df_f)}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="kpi-card"><div class="kpi-label">Pipeline</div><div class="kpi-value">{val_t:,.0f}€</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="kpi-card"><div class="kpi-label">ROI</div><div class="kpi-value">{roi:.2f}x</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="kpi-card"><div class="kpi-label">Clientes</div><div class="kpi-value">{len(df_f[df_f["SON_CLIENTE"]=="Sí"])}</div></div>', unsafe_allow_html=True)

with tab2:
    st.dataframe(df_f, use_container_width=True, hide_index=True)

with tab3:
    st.markdown("### 🔍 Detalle & Scoring IA")
    if len(df_f) > 0:
        sel = st.selectbox("Seleccionar Lead", df_f["N_FORM"].tolist())
        row = df_f[df_f["N_FORM"] == sel].iloc[0]
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown(f"**{row['NOMBRE_EMPRESA']}** | {row['CARGO']}")
            st.caption(f"{row['MAIL']} | {row['VERTICAL_EMPRESA']}")
            st.info(row['MENSAJE'])
        with c2:
            st.metric("Valor", f"{row['VALOR_LEAD']:,.0f}€")
            st.metric("Score Reglas", f"{row['PUNTUACION']}/100")
            if "AI_SCORE" in row and pd.notna(row.get("AI_SCORE")):
                st.metric("Score IA", f"{row['AI_SCORE']}/100", delta=f"{row['AI_SCORE'] - row['PUNTUACION']}")
                if "AI_REASONING" in row: st.caption(f"💡 {row['AI_REASONING']}")
            else:
                if st.button("🤖 Calcular con IA", key="btn_calc_ai"):
                    with st.spinner("Consultando OpenAI..."):
                        ai_res = aplicar_scoring_ia(row, st.session_state.openai_key)
                        idx = st.session_state.leads_df.index[st.session_state.leads_df["N_FORM"] == sel]
                        st.session_state.leads_df.loc[idx, "AI_SCORE"] = ai_res["score"]
                        st.session_state.leads_df.loc[idx, "AI_REASONING"] = ai_res["reasoning"]
                        st.session_state.leads_df.loc[idx, "AI_PROB"] = ai_res["probability"]
                        st.rerun()

with tab4:
    st.markdown("### ➕ Añadir Nuevo Lead")
    with st.form("new_lead_form"):
        c1, c2 = st.columns(2)
        empresa = c1.text_input("Empresa *")
        email = c2.text_input("Email *")
        cargo = c1.text_input("Cargo")
        vertical = c2.selectbox("Vertical", ["Industrial", "Tecnología", "Salud", "Finanzas", "Otro"])
        mensaje = st.text_area("Mensaje / Interés")
        valor = st.number_input("Valor Estimado (€)", value=1000)
        
        submitted = st.form_submit_button("💾 Guardar y Analizar", type="primary")
        
        if submitted and empresa and email:
            new_id = f"MANUAL-{datetime.now().strftime('%H%M%S')}"
            new_row = pd.DataFrame([{
                "N_FORM": new_id, "FECHA_ENVIO_FORM": datetime.now(),
                "NOMBRE_EMPRESA": empresa, "MAIL": email, "CARGO": cargo,
                "VERTICAL_EMPRESA": vertical, "MENSAJE": mensaje, "VALOR_LEAD": valor,
                "COSTE_DEL_LEAD": 50, "SON_CLIENTE": "No", "ORIGEN_FORM_HA_FINALIZADO": "Sí",
                "FACTURACION": "1-5M€", "ANOTACIONES": "Creado manualmente"
            }])
            
            # 1. Guardar datos base
            st.session_state.leads_df = pd.concat([st.session_state.leads_df, new_row], ignore_index=True)
            st.session_state.leads_df = calcular_valoracion(st.session_state.leads_df)
            
            # 2. Scoring IA Automático si está configurado
            if st.session_state.openai_key:
                with st.spinner(" Calculando Scoring IA para el nuevo lead..."):
                    ai_res = aplicar_scoring_ia(new_row.iloc[0], st.session_state.openai_key)
                    idx = st.session_state.leads_df.index[st.session_state.leads_df["N_FORM"] == new_id]
                    st.session_state.leads_df.loc[idx, "AI_SCORE"] = ai_res["score"]
                    st.session_df.loc[idx, "AI_REASONING"] = ai_res["reasoning"]
            
            st.success(f"✅ Lead {empresa} añadido y analizado correctamente.")
            st.rerun()
        elif submitted:
            st.error("⚠️ Empresa y Email son obligatorios")
