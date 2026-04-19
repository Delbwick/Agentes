import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io

# =============================================================
# 1. CONFIGURACIÓN & UX
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
        --kaibot-blue: #0066CC; --kaibot-blue-hover: #0052A3; --kaibot-dark: #1E293B;
        --kaibot-gray: #64748B; --kaibot-light: #F8FAFC; --sidebar-bg: #0F172A;
        --success: #10B981; --warning: #F59E0B; --danger: #EF4444;
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
    
    .kpi-card { 
        background: white; padding: 14px 8px; border-radius: 8px; 
        box-shadow: 0 2px 6px rgba(0,0,0,0.05); text-align: center; 
        display: flex; flex-direction: column; justify-content: center; align-items: center;
    }
    .kpi-value { font-size: 1.6rem; font-weight: 700; color: var(--kaibot-dark); margin: 2px 0; }
    .kpi-label { font-size: 0.8rem; color: var(--kaibot-gray); text-transform: uppercase; letter-spacing: 0.5px; }
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
        "MENSAJE": np.random.choice(["Interesados consultoría", "Solicitan demo", "Contacto partnership", "Consulta precios"], n),
        "TIPO_FORM": np.random.choice(["Web General", "Landing Campaña", "Webinar", "Feria"], n),
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
    df.columns = df.columns.str.strip()  # Limpia espacios ocultos automáticamente
    
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
# 3. INICIALIZACIÓN & SIDEBAR
# =============================================================
if "leads_df" not in st.session_state:
    st.session_state.leads_df = calcular_valoracion(init_sample_data())
if "df_filtrado" not in st.session_state:
    st.session_state.df_filtrado = st.session_state.leads_df.copy()

df_raw = st.session_state.leads_df

with st.sidebar:
    st.markdown("### 🤖 KaiBot Leads")
    st.markdown("---")
    st.markdown("🔍 **Filtros**")
    search = st.text_input("Buscar empresa/email/cargo", placeholder="Ej: TechCorp, CMO...")
    c1, c2 = st.columns(2)
    with c1:
        vertical = st.multiselect("Vertical", options=df_raw["VERTICAL_EMPRESA"].unique().tolist(), default=df_raw["VERTICAL_EMPRESA"].unique().tolist())
    with c2:
        tipo_form = st.multiselect("Tipo Formulario", options=df_raw["TIPO_FORM"].unique().tolist(), default=df_raw["TIPO_FORM"].unique().tolist())
    cliente = st.selectbox("¿Es Cliente?", ["Todos", "Sí", "No"])
    exito = st.selectbox("Formulario Finalizado?", ["Todos", "Sí", "No", "Parcial"])
    min_val, max_val = st.slider("Rango Valor Lead (€)", 0, int(df_raw["VALOR_LEAD"].max()), (0, int(df_raw["VALOR_LEAD"].max())), 100)
    
    st.markdown("---")
    st.markdown("📥 **Importar/Exportar**")
    uploaded = st.file_uploader("Cargar CSV", type=["csv"])
    if uploaded:
        try:
            df_up = pd.read_csv(uploaded)
            st.session_state.leads_df = calcular_valoracion(df_up)
            st.success("✅ CSV cargado")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {e}")
            
    if st.button("📤 Exportar Filtrado"):
        csv = st.session_state.df_filtrado.to_csv(index=False).encode("utf-8")
        st.download_button("Descargar CSV", csv, "leads_kaiobot.csv", "text/csv")

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
# 4. MAIN UI
# =============================================================
st.markdown("### 📊 Panel de Leads & Valoración")
st.caption("Gestión, análisis y scoring inteligente de leads B2B.")
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📈 Dashboard KPIs", "📋 Lista Interactiva", "🔍 Detalle & Análisis"])

with tab1:
    # Métricas horizontales compactas
    k1, k2, k3, k4 = st.columns(4)
    val_t = df_f["VALOR_LEAD"].sum()
    cost_t = df_f["COSTE_DEL_LEAD"].sum()
    roi = ((val_t - cost_t) / cost_t) if cost_t > 0 else 0
    cli = len(df_f[df_f["SON_CLIENTE"] == "Sí"])
    
    k1.markdown(f'<div class="kpi-card"><div class="kpi-label">Leads</div><div class="kpi-value">{len(df_f)}</div></div>', unsafe_allow_html=True)
    k2.markdown(f'<div class="kpi-card"><div class="kpi-label">Pipeline</div><div class="kpi-value">{val_t:,.0f}€</div></div>', unsafe_allow_html=True)
    k3.markdown(f'<div class="kpi-card"><div class="kpi-label">ROI</div><div class="kpi-value">{roi:.2f}x</div></div>', unsafe_allow_html=True)
    k4.markdown(f'<div class="kpi-card"><div class="kpi-label">Clientes</div><div class="kpi-value">{cli} ({cli/max(len(df_f),1)*100:.1f}%)</div></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1: st.bar_chart(df_f.groupby("VERTICAL_EMPRESA")["VALOR_LEAD"].sum(), use_container_width=True)
    with c2: st.bar_chart(df_f.groupby("TIPO_FORM")["VALOR_LEAD"].mean(), use_container_width=True)

with tab2:
    st.dataframe(df_f, use_container_width=True, hide_index=True)

with tab3:
    st.markdown("### 🔍 Detalle Lead")
    opts = df_f["N_FORM"].tolist() if len(df_f) > 0 else []
    sel = st.selectbox("Selecciona un lead", options=opts)
    
    if sel:
        row = df_f[df_f["N_FORM"] == sel].iloc[0]
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown(f"**{row['NOMBRE_EMPRESA']}** | {row['CARGO']} | `{row['MAIL']}`")
            st.info(row['MENSAJE'])
        with c2:
            st.metric("Valor", f"{row['VALOR_LEAD']:,.0f}€")
            st.progress(row['PUNTUACION']/100)
            st.caption(f"Score: {row['PUNTUACION']:.0f} | {row['ESTADO_VALOR']}")
            
        new_note = st.text_area("📝 Anotaciones", value=str(row['ANOTACIONES']), label_visibility="collapsed")
        if st.button("💾 Guardar Cambios"):
            idx = st.session_state.leads_df[st.session_state.leads_df["N_FORM"] == sel].index[0]
            st.session_state.leads_df.at[idx, "ANOTACIONES"] = new_note
            st.session_state.leads_df = calcular_valoracion(st.session_state.leads_df)
            st.success("✅ Actualizado y sincronizado")
            st.rerun()

st.markdown('<div class="kaibot-footer">© 2026 KaiBot. Optimizado para gestión comercial B2B.</div>', unsafe_allow_html=True)
