import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io
import json
import openai
from google.cloud import storage

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
# 2. MOTOR DE DATOS & VALORACIÓN
# =============================================================
CAMPOS_REQ = [
    "N_FORM", "FECHA_ENVIO_FORM", "NOMBRE_EMPRESA", "NOMBRE_ENVIO_MAIL", "MAIL",
    "TELÉFONO", "MENSAJE", "TIPO_FORM", "SON_CLIENTE", "ANOTACIONES",
    "VALOR_LEAD", "COSTE_DEL_LEAD", "ORIGEN_FORM_HA_FINALIZADO", "FACTURACION",
    "VERTICAL_EMPRESA", "LINKEDIN", "CARGO"
]

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
        "MENSAJE": np.random.choice(["Interesados en consultoría B2B", "Solicitan demo de plataforma", "Contacto para partnership", "Consulta sobre precios enterprise", "Interés en whitepaper sector"], n),
        "TIPO_FORM": np.random.choice(["Web General", "Landing Campaña", "Webinar", "Feria", "Contacto Directo"], n),
        "SON_CLIENTE": np.random.choice(["Sí", "No"], n, p=[0.3, 0.7]),
        "ANOTACIONES": np.random.choice(["Requiere follow-up", "Alta intención", "Presupuesto definido", "En evaluación", "Sin respuesta"], n),
        "VALOR_LEAD": np.random.uniform(500, 15000, n),
        "COSTE_DEL_LEAD": np.random.uniform(20, 800, n),
        "ORIGEN_FORM_HA_FINALIZADO": np.random.choice(["Sí", "No", "Parcial"], n, p=[0.6, 0.2, 0.2]),
        "FACTURACION": np.random.choice(["<1M€", "1-5M€", "5-20M€", ">20M€"], n),
        "VERTICAL_EMPRESA": np.random.choice(["Industrial", "Tecnología", "Salud", "Logística", "Finanzas"], n),
        "LINKEDIN": [f"https://linkedin.com/in/user{i}" for i in range(n)],
        "CARGO": np.random.choice(["CEO", "CMO", "Director Comercial", "Head of Growth", "Consultor", "CTO"], n)
    }
    df = pd.DataFrame(data)
    df["VALOR_LEAD"] = df["VALOR_LEAD"].round(2)
    df["COSTE_DEL_LEAD"] = df["COSTE_DEL_LEAD"].round(2)
    return df

def calcular_valoracion(df):
    df = df.copy()
    df.columns = df.columns.str.strip()
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

def consultar_openai(row, api_key):
    if not api_key:
        return None, None, "⚠️ Introduce tu API Key de OpenAI en el sidebar."
    prompt = f"""Actúa como experto en ventas B2B. Evalúa este lead del 0 al 100.
Devuelve SOLO JSON válido: {{"score": int, "reasons": ["string"], "recommendation": "string"}}
Datos del lead:
- Empresa: {row.get('NOMBRE_EMPRESA','N/A')}
- Vertical: {row.get('VERTICAL_EMPRESA','N/A')}
- Facturación: {row.get('FACTURACION','N/A')}
- Cargo contacto: {row.get('CARGO','N/A')}
- Mensaje recibido: {row.get('MENSAJE','N/A')}
- ¿Es cliente actual?: {row.get('SON_CLIENTE','N/A')}
"""
    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Eres un analista comercial experto en scoring predictivo B2B."},
                      {"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        ai_data = json.loads(response.choices[0].message.content)
        return ai_data, prompt, None
    except Exception as e:
        return None, prompt, f"❌ Error OpenAI: {str(e)}"

# =============================================================
# 3. FUNCIONES GOOGLE CLOUD STORAGE
# =============================================================
def upload_to_gcs(df, bucket_name, blob_name, credentials_info=None):
    """Sube DataFrame a GCS como CSV"""
    try:
        if credentials_info:
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_info(credentials_info)
            client = storage.Client(credentials=creds)
        else:
            client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        csv_data = df.to_csv(index=False)
        blob.upload_from_string(csv_data, content_type='text/csv')
        return True, None
    except Exception as e:
        return False, str(e)

def download_from_gcs(bucket_name, blob_name, credentials_info=None):
    """Descarga CSV desde GCS"""
    try:
        if credentials_info:
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_info(credentials_info)
            client = storage.Client(credentials=creds)
        else:
            client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        if not blob.exists():
            return None, "⚠️ El archivo no existe en el bucket"
        csv_data = blob.download_as_text()
        df = pd.read_csv(io.StringIO(csv_data))
        return df, None
    except Exception as e:
        return None, str(e)

def list_gcs_files(bucket_name, prefix="", credentials_info=None):
    """Lista archivos en el bucket"""
    try:
        if credentials_info:
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_info(credentials_info)
            client = storage.Client(credentials=creds)
        else:
            client = storage.Client()
        bucket = client.bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=prefix)
        return [b.name for b in blobs], None
    except Exception as e:
        return [], str(e)

# =============================================================
# 4. INICIALIZACIÓN & SESSION STATE
# =============================================================
if "leads_df" not in st.session_state:
    st.session_state.leads_df = calcular_valoracion(init_sample_data())
st.session_state.leads_df.columns = st.session_state.leads_df.columns.str.strip()

if "df_filtrado" not in st.session_state:
    st.session_state.df_filtrado = st.session_state.leads_df.copy()
if "selected_lead" not in st.session_state:
    st.session_state.selected_lead = None
if "openai_key" not in st.session_state:
    st.session_state.openai_key = ""
if "ai_cache" not in st.session_state:
    st.session_state.ai_cache = {}
if "gcs_creds" not in st.session_state:
    st.session_state.gcs_creds = None
if "gcs_bucket" not in st.session_state:
    st.session_state.gcs_bucket = ""

df_raw = st.session_state.leads_df

# =============================================================
# 5. SIDEBAR
# =============================================================
with st.sidebar:
    st.markdown('<div style="text-align:center;"><img src="https://kaibot.es/wp-content/uploads/2020/07/image1.png" width="50"><h3 style="color:white;margin:10px 0;">KaiBot Leads</h3></div>', unsafe_allow_html=True)
    st.markdown("---")
    
    # 🤖 OpenAI Config
    st.markdown("🤖 **Configuración IA**")
    st.session_state.openai_key = st.text_input("API Key OpenAI", type="password", value=st.session_state.openai_key, placeholder="sk-proj-...")
    
    # ☁️ Google Cloud Storage
    st.markdown("---")
    st.markdown("☁️ **Google Cloud Storage**")
    st.session_state.gcs_bucket = st.text_input("Bucket Name", value=st.session_state.gcs_bucket, placeholder="kaibot-leads-prod")
    
    creds_upload = st.file_uploader("Service Account JSON", type=["json"], key="gcs_creds_uploader")
    if creds_upload is not None:
        try:
            st.session_state.gcs_creds = json.load(creds_upload)
            st.success("✅ Credenciales cargadas")
        except Exception as e:
            st.error(f"❌ JSON inválido: {e}")
    
    # Operaciones GCS
    col_gcs1, col_gcs2 = st.columns(2)
    with col_gcs1:
        if st.button("💾 Guardar en GCS", use_container_width=True):
            if st.session_state.gcs_bucket and st.session_state.gcs_creds:
                with st.spinner("Subiendo a Cloud..."):
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    blob_name = f"leads/leads_{timestamp}.csv"
                    ok, err = upload_to_gcs(st.session_state.leads_df, st.session_state.gcs_bucket, blob_name, st.session_state.gcs_creds)
                    if ok:
                        st.success(f"✅ Guardado: {blob_name}")
                    else:
                        st.error(f"❌ Error: {err}")
            else:
                st.warning("⚠️ Configura Bucket y credenciales primero")
    
    with col_gcs2:
        if st.button("📥 Cargar desde GCS", use_container_width=True):
            if st.session_state.gcs_bucket and st.session_state.gcs_creds:
                files, err = list_gcs_files(st.session_state.gcs_bucket, "leads/", st.session_state.gcs_creds)
                if err:
                    st.error(err)
                elif files:
                    selected_file = st.selectbox("Selecciona archivo", files, key="gcs_file_select")
                    if st.button("Confirmar carga", key="gcs_load_confirm"):
                        with st.spinner("Descargando..."):
                            df_loaded, err = download_from_gcs(st.session_state.gcs_bucket, selected_file, st.session_state.gcs_creds)
                            if df_loaded is not None:
                                st.session_state.leads_df = calcular_valoracion(df_loaded)
                                st.success("✅ Datos cargados desde Cloud")
                                st.rerun()
                            else:
                                st.error(err)
                else:
                    st.caption("📭 No hay archivos en 'leads/'")
            else:
                st.warning("⚠️ Configura Bucket y credenciales primero")
    
    # 🔍 Filtros
    st.markdown("---")
    st.markdown("🔍 **Filtros Avanzados**")
    search = st.text_input("Buscar empresa/email/cargo", placeholder="Ej: TechCorp, CMO...")
    col1, col2 = st.columns(2)
    with col1:
        vertical = st.multiselect("Vertical", options=df_raw["VERTICAL_EMPRESA"].unique().tolist(), default=df_raw["VERTICAL_EMPRESA"].unique().tolist())
    with col2:
        tipo_form = st.multiselect("Tipo Formulario", options=df_raw["TIPO_FORM"].unique().tolist(), default=df_raw["TIPO_FORM"].unique().tolist())
    col3, col4 = st.columns(2)
    with col3:
        cliente = st.selectbox("¿Es Cliente?", ["Todos", "Sí", "No"])
    with col4:
        exito = st.selectbox("Formulario Finalizado?", ["Todos", "Sí", "No", "Parcial"])
    min_val, max_val = st.slider("Rango Valor Lead (€)", 0, int(df_raw["VALOR_LEAD"].max()), (0, int(df_raw["VALOR_LEAD"].max())), 100)
    
    # 📥 Import/Export local
    st.markdown("---")
    st.markdown("📥 **Importar/Exportar Local**")
    uploaded = st.file_uploader("Cargar CSV", type=["csv"])
    if uploaded:
        try:
            df_up = pd.read_csv(uploaded)
            df_up.columns = df_up.columns.str.strip()
            missing = [c for c in CAMPOS_REQ if c not in df_up.columns]
            if not missing:
                st.session_state.leads_df = calcular_valoracion(df_up)
                st.success("✅ CSV cargado")
                st.rerun()
            else:
                st.error(f"❌ Faltan columnas: {', '.join(missing)}")
        except Exception as e:
            st.error(f"❌ Error: {e}")
            
    if st.button("📤 Exportar Filtrado", type="primary"):
        csv = st.session_state.df_filtrado.to_csv(index=False).encode("utf-8")
        st.download_button("Descargar CSV", csv, "leads_kaiobot.csv", "text/csv")

# Aplicar filtros
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
# 6. MAIN UI - 4 PESTAÑAS
# =============================================================
st.markdown('<div style="display:flex;align-items:center;gap:10px;"><img src="https://kaibot.es/wp-content/uploads/2020/07/image1.png" width="30"><h2 style="margin:0;">Panel de Leads & Valoración</h2></div>', unsafe_allow_html=True)
st.caption("Gestión, análisis y scoring inteligente de leads B2B. Con integración Cloud e IA.")
st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard KPIs", "📋 Lista Interactiva", "🔍 Detalle & Análisis IA", "➕ Nuevo Lead"])

# TAB 1: KPIs Horizontales
with tab1:
    c1, c2, c3, c4 = st.columns(4)
    total_leads = len(df_f)
    valor_total = df_f["VALOR_LEAD"].sum()
    coste_total = df_f["COSTE_DEL_LEAD"].sum()
    roi_global = ((valor_total - coste_total) / coste_total) if coste_total > 0 else 0
    clientes = len(df_f[df_f["SON_CLIENTE"]=="Sí"])
    
    def kpi_card(label, value, sub=""):
        st.markdown(f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div><div style="color:var(--kaibot-gray);font-size:0.8rem;">{sub}</div></div>', unsafe_allow_html=True)
    kpi_card("Leads Activos", total_leads, "Filtrados")
    kpi_card("Valor Pipeline", f"{valor_total:,.0f}€", f"{coste_total:,.0f}€ invertidos")
    kpi_card("ROI Global", f"{roi_global:.2f}x", "Retorno")
    kpi_card("Clientes Reales", f"{clientes} ({clientes/max(total_leads,1)*100:.1f}%)", "Conversión")
    
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1: st.bar_chart(df_f.groupby("VERTICAL_EMPRESA")["VALOR_LEAD"].sum().rename("Valor por Vertical"), use_container_width=True)
    with c2: st.bar_chart(df_f.groupby("TIPO_FORM")["VALOR_LEAD"].mean().rename("Valor Medio por Formulario"), use_container_width=True)

# TAB 2: Lista Interactiva
with tab2:
    st.markdown("### 📋 Registro de Leads")
    col_config = {
        "N_FORM": st.column_config.TextColumn("N. Form"),
        "FECHA_ENVIO_FORM": st.column_config.DateColumn("Fecha"),
        "NOMBRE_EMPRESA": st.column_config.TextColumn("Empresa"),
        "MAIL": st.column_config.TextColumn("Email"),
        "CARGO": st.column_config.TextColumn("Cargo"),
        "VERTICAL_EMPRESA": st.column_config.TextColumn("Vertical"),
        "FACTURACION": st.column_config.TextColumn("Facturación"),
        "PUNTUACION": st.column_config.NumberColumn("Score", format="%d/100"),
        "ESTADO_VALOR": st.column_config.TextColumn("Estado"),
        "VALOR_LEAD": st.column_config.NumberColumn("Valor (€)", format="%.2f")
    }
    st.dataframe(df_f, use_container_width=True, column_config=col_config, hide_index=True)

# TAB 3: Detalle & Análisis IA
with tab3:
    st.markdown("### 🔍 Detalle & Análisis de Lead")
    options = df_f["N_FORM"].tolist() if len(df_f) > 0 else []
    default_idx = options.index(st.session_state.selected_lead) if st.session_state.selected_lead in options else 0
    sel_lead = st.selectbox("Selecciona un lead para análisis profundo", options=options, index=default_idx if options else 0)
    
    if sel_lead:
        st.session_state.selected_lead = sel_lead
        row = df_f[df_f["N_FORM"] == sel_lead].iloc[0]
        c1, c2 = st.columns([2,1])
        with c1:
            st.markdown(f"**Empresa:** {row['NOMBRE_EMPRESA']} | **Cargo:** {row['CARGO']}")
            st.markdown(f"**Email:** `{row['MAIL']}` | **Tel:** {row['TELÉFONO']}")
            st.markdown(f"**Vertical:** `{row['VERTICAL_EMPRESA']}` | **Facturación:** `{row['FACTURACION']}`")
            st.markdown(f"**Mensaje:** *{row['MENSAJE']}*")
            st.caption(f"Anotaciones: {row['ANOTACIONES']}")
        with c2:
            st.metric("Valor Lead", f"{row['VALOR_LEAD']:,.2f}€")
            st.metric("Coste Lead", f"{row['COSTE_DEL_LEAD']:,.2f}€")
            st.metric("ROI", f"{row['ROI_LEAD']:.2f}x")
            st.progress(row['PUNTUACION']/100)
            st.caption(f"Puntuación Reglas: **{row['PUNTUACION']}/100** | {row['ESTADO_VALOR']}")
            if "AI_SCORE" in row and pd.notna(row.get("AI_SCORE")):
                st.metric("Score IA", f"{row['AI_SCORE']}/100", delta=f"{row['AI_SCORE'] - row['PUNTUACION']}")
                
        st.markdown("---")
        st.markdown("📝 **Actualizar Anotaciones**")
        new_notes = st.text_area("", value=str(row["ANOTACIONES"]), label_visibility="collapsed")
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("💾 Guardar Cambios"):
                idx = st.session_state.leads_df[st.session_state.leads_df["N_FORM"]==sel_lead].index[0]
                st.session_state.leads_df.at[idx, "ANOTACIONES"] = new_notes
                st.session_state.leads_df = calcular_valoracion(st.session_state.leads_df)
                st.success("✅ Actualizado")
                st.rerun()
        with col_btn2:
            if st.button("🤖 Consultar OpenAI"):
                ai_res, ai_prompt, err = consultar_openai(row.to_dict(), st.session_state.openai_key)
                if err:
                    st.error(err)
                else:
                    idx = st.session_state.leads_df.index[st.session_state.leads_df["N_FORM"]==sel_lead]
                    st.session_state.leads_df.loc[idx, "AI_SCORE"] = ai_res.get("score")
                    st.session_state.leads_df.loc[idx, "AI_REASONING"] = ", ".join(ai_res.get("reasons", []))
                    st.session_state.ai_cache[sel_lead] = {"response": ai_res, "prompt": ai_prompt}
                    st.success("✅ Análisis IA generado")
                st.rerun()
                
        # Mostrar Prompt y Respuesta OpenAI
        if sel_lead in st.session_state.ai_cache:
            cache = st.session_state.ai_cache[sel_lead]
            st.markdown("### 🧠 Consulta & Respuesta OpenAI")
            with st.expander("📤 Prompt Enviado a OpenAI", expanded=False):
                st.code(cache["prompt"], language="markdown")
            with st.expander("📥 Respuesta Recibida (JSON)", expanded=True):
                st.json(cache["response"])
            if "score" in cache["response"]:
                c_a, c_b = st.columns(2)
                c_a.metric("Score IA", f"{cache['response']['score']}/100")
                c_b.markdown(f"**Recomendación:** {cache['response'].get('recommendation', '')}")
                if cache["response"].get("reasons"):
                    st.markdown("**Razones clave:**")
                    for r in cache["response"]["reasons"]:
                        st.write(f"• {r}")

# TAB 4: Nuevo Lead (con scoring IA automático)
with tab4:
    st.markdown("### ➕ Añadir Lead Manual")
    st.caption("Introduce los datos. El sistema calculará ROI, puntuación y (si hay API Key) scoring con IA.")
    
    with st.form("form_nuevo_lead", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            in_empresa = st.text_input("NOMBRE_EMPRESA *", placeholder="Ej: TechCorp")
            in_email = st.text_input("MAIL *", placeholder="contacto@empresa.com")
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
            in_mensaje = st.text_area("MENSAJE", height=100)
            in_tipo_form = st.selectbox("TIPO_FORM", ["Manual", "Webinar", "Contacto Directo", "Web General"])

        btn_guardar = st.form_submit_button("💾 Guardar y Valorar Lead", type="primary")

        if btn_guardar:
            if not in_empresa or not in_email:
                st.error("⚠️ La Empresa y el Email son obligatorios.")
            else:
                new_id = f"MANUAL-{datetime.now().strftime('%H%M%S')}"
                nuevo_registro = {
                    "N_FORM": new_id, "FECHA_ENVIO_FORM": datetime.now(),
                    "NOMBRE_EMPRESA": in_empresa, "NOMBRE_ENVIO_MAIL": in_nombre_contacto,
                    "MAIL": in_email, "TELÉFONO": in_telefono, "MENSAJE": in_mensaje,
                    "TIPO_FORM": in_tipo_form, "SON_CLIENTE": in_son_cliente,
                    "ANOTACIONES": "Añadido manualmente", "VALOR_LEAD": in_valor,
                    "COSTE_DEL_LEAD": in_coste, "ORIGEN_FORM_HA_FINALIZADO": "Sí",
                    "FACTURACION": in_facturacion, "VERTICAL_EMPRESA": in_vertical,
                    "LINKEDIN": "", "CARGO": in_cargo
                }
                
                # 1. Añadir y calcular reglas
                new_df = pd.DataFrame([nuevo_registro])
                st.session_state.leads_df = pd.concat([st.session_state.leads_df, new_df], ignore_index=True)
                st.session_state.leads_df = calcular_valoracion(st.session_state.leads_df)
                
                # 2. Scoring IA automático si hay API Key
                if st.session_state.openai_key:
                    with st.spinner("🤖 Calculando scoring con IA..."):
                        ai_res, _, err = consultar_openai(nuevo_registro, st.session_state.openai_key)
                        if not err and ai_res:
                            idx = st.session_state.leads_df.index[st.session_state.leads_df["N_FORM"]==new_id]
                            st.session_state.leads_df.loc[idx, "AI_SCORE"] = ai_res.get("score")
                            st.session_state.leads_df.loc[idx, "AI_REASONING"] = ", ".join(ai_res.get("reasons", []))
                            st.session_state.ai_cache[new_id] = {"response": ai_res}
                
                # 3. Auto-seleccionar en Tab 3
                st.session_state.selected_lead = new_id
                
                st.success(f"✅ Lead **{in_empresa}** guardado y valorado.")
                st.info("👉 Ve a **🔍 Detalle & Análisis IA** para ver el scoring completo.")
                st.rerun()

st.markdown('<div class="kaibot-footer">© 2026 KaiBot. Todos los derechos reservados. | Optimizado para gestión comercial B2B.</div>', unsafe_allow_html=True)
