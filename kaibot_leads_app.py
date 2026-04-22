import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io
import json

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
    
    .stButton > button[kind="primary"] { background-color: var(--kaibot-blue); color: white; border: none; font-weight: 500; }
    .stButton > button[kind="primary"]:hover { background-color: var(--kaibot-blue-hover); }
    .stButton > button { width: 100%; }
    
    .stTabs [data-baseweb="tab-list"] { background: white; border-bottom: 2px solid #E2E8F0; gap: 4px; }
    .stTabs [data-baseweb="tab-list"] button[role="tab"] { 
        background: transparent; color: var(--kaibot-gray); font-weight: 500; border-radius: 6px 6px 0 0; 
        padding: 10px 20px; transition: all 0.2s;
    }
    .stTabs [data-baseweb="tab-list"] button[role="tab"][aria-selected="true"] { 
        background: var(--kaibot-blue); color: white; font-weight: 600; border-bottom: 3px solid var(--kaibot-blue); 
    }
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
    .status-badge { display: inline-block; padding: 4px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

# =============================================================
# 2. CONFIGURACIÓN & CONSTANTES (SIN ESPACIOS)
# =============================================================
CAMPOS_REQ = [
    "N_FORM", "FECHA_ENVIO_FORM", "NOMBRE_EMPRESA", "NOMBRE_ENVIO_MAIL", "MAIL",
    "TELÉFONO", "MENSAJE", "TIPO_FORM", "SON_CLIENTE", "ANOTACIONES",
    "VALOR_LEAD", "COSTE_DEL_LEAD", "ORIGEN_FORM_HA_FINALIZADO", "FACTURACION",
    "VERTICAL_EMPRESA", "LINKEDIN", "CARGO"
]

# =============================================================
# 3. FUNCIONES DE DATOS & VALORACIÓN
# =============================================================
def init_sample_data():
    """Genera datos de ejemplo para demostración inmediata"""
    np.random.seed(42)
    n = 25
    data = {
        "N_FORM": [f"FRM-{1000+i}" for i in range(n)],
        "FECHA_ENVIO_FORM": pd.date_range(start="2025-03-01", periods=n, freq="3D"),
        "NOMBRE_EMPRESA": np.random.choice(["TechCorp", "IndusLab", "MediGroup", "DataFlow", "GreenSolutions"], n),
        "NOMBRE_ENVIO_MAIL": np.random.choice(["Carlos R.", "Ana M.", "Luis P.", "Sofia T.", "Miguel A."], n),
        "MAIL": [f"user{i}@empresa.com" for i in range(n)],
        "TELÉFONO": [f"+34 600 {np.random.randint(100000, 999999)}" for i in range(n)],
        "MENSAJE": np.random.choice([
            "Interesados en consultoría B2B", "Solicitan demo de plataforma", "Contacto para partnership",
            "Consulta sobre precios enterprise", "Interés en whitepaper sector"
        ], n),
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
    """Añade métricas automáticas: ROI, Puntuación, Estado"""
    df = df.copy()
    df.columns = df.columns.str.strip()  # Limpieza crítica de espacios
    
    df["ROI_LEAD"] = np.where(df["COSTE_DEL_LEAD"] > 0, (df["VALOR_LEAD"] - df["COSTE_DEL_LEAD"]) / df["COSTE_DEL_LEAD"], 0)
    df["ROI_LEAD"] = df["ROI_LEAD"].round(2)
    
    # Puntuación 0-100
    df["PUNTUACION"] = 0
    df.loc[df["SON_CLIENTE"] == "Sí", "PUNTUACION"] += 20
    df.loc[df["ORIGEN_FORM_HA_FINALIZADO"] == "Sí", "PUNTUACION"] += 25
    df.loc[df["VALOR_LEAD"] > df["VALOR_LEAD"].median(), "PUNTUACION"] += 20
    df.loc[df["CARGO"].isin(["CEO", "CMO", "Director Comercial"]), "PUNTUACION"] += 25
    df.loc[df["FACTURACION"].isin(["5-20M€", ">20M€"]), "PUNTUACION"] += 10
    df["PUNTUACION"] = df["PUNTUACION"].clip(0, 100)
    
    # Estado cualitativo
    conditions = [df["PUNTUACION"] >= 75, df["PUNTUACION"] >= 50, df["PUNTUACION"] >= 25]
    choices = ["🟢 Alto Potencial", "🟡 Medio", "🔴 Bajo"]
    df["ESTADO_VALOR"] = np.select(conditions, choices, default="🔴 Bajo")
    return df

# =============================================================
# 4. INICIALIZACIÓN & SIDEBAR
# =============================================================
if "leads_df" not in st.session_state:
    st.session_state.leads_df = calcular_valoracion(init_sample_data())

df_raw = st.session_state.leads_df
df_raw.columns = df_raw.columns.str.strip()  # Blindaje anti-espacios

with st.sidebar:
    st.markdown('<div style="text-align:center;"><img src="https://kaibot.es/wp-content/uploads/2020/07/image1.png" width="50"><h3 style="color:white;margin:10px 0;">KaiBot Leads</h3></div>', unsafe_allow_html=True)
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
    
    # Slider robusto: evita crash con datos vacíos
    safe_max = 10000
    if "VALOR_LEAD" in df_raw.columns:
        try:
            nums = pd.to_numeric(df_raw["VALOR_LEAD"], errors="coerce").dropna()
            if len(nums) > 0:
                safe_max = max(int(nums.max()), 1000)
        except:
            pass
    min_val, max_val = st.slider("Rango Valor Lead (€)", 0, safe_max, (0, safe_max), step=100)
    
    st.markdown("---")
    st.markdown("📥 **Importar/Exportar**")
    uploaded = st.file_uploader("Cargar CSV de Formularios", type=["csv"])
    
    if uploaded:
        try:
            df_up = pd.read_csv(uploaded, encoding='utf-8-sig')
            df_up.columns = df_up.columns.str.strip()  # Limpieza de columnas del CSV
            
            # Verificar columnas requeridas
            missing = [c for c in CAMPOS_REQ if c not in df_up.columns]
            if not missing:
                st.session_state.leads_df = calcular_valoracion(df_up)
                st.success("✅ Datos cargados correctamente")
                st.rerun()
            else:
                st.error(f"❌ Faltan columnas: {', '.join(missing)}")
        except Exception as e:
            st.error(f"❌ Error al leer CSV: {e}")
    
    if st.button("📤 Exportar Filtrado", type="primary"):
        csv = st.session_state.df_filtrado.to_csv(index=False).encode("utf-8")
        st.download_button("Descargar CSV", csv, "leads_kaiobot.csv", "text/csv")
        st.success("✅ Descarga iniciada")

# =============================================================
# 5. APLICAR FILTROS
# =============================================================
df_f = df_raw.copy()

if search:
    df_f = df_f[df_f.apply(lambda r: search.lower() in r.astype(str).str.lower().sum(), axis=1)]

if vertical != df_raw["VERTICAL_EMPRESA"].unique().tolist():
    df_f = df_f[df_f["VERTICAL_EMPRESA"].isin(vertical)]

if tipo_form != df_raw["TIPO_FORM"].unique().tolist():
    df_f = df_f[df_f["TIPO_FORM"].isin(tipo_form)]

if cliente != "Todos":
    df_f = df_f[df_f["SON_CLIENTE"] == cliente]

if exito != "Todos":
    df_f = df_f[df_f["ORIGEN_FORM_HA_FINALIZADO"] == exito]

df_f = df_f[(df_f["VALOR_LEAD"] >= min_val) & (df_f["VALOR_LEAD"] <= max_val)]
df_f = df_f.sort_values("FECHA_ENVIO_FORM", ascending=False)
st.session_state.df_filtrado = df_f

# =============================================================
# 6. MAIN UI - 3 PESTAÑAS
# =============================================================
st.markdown('<div style="display:flex;align-items:center;gap:10px;"><img src="https://kaibot.es/wp-content/uploads/2020/07/image1.png" width="30"><h2 style="margin:0;">Panel de Leads & Valoración</h2></div>', unsafe_allow_html=True)
st.caption("Gestión, análisis y scoring inteligente de leads captados por formularios. Optimizado para equipos comerciales y marketing B2B.")
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📊 Dashboard KPIs", "📋 Lista Interactiva", "🔍 Detalle & Análisis"])

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
    
    kpi_card("Leads Activos", total_leads, "Filtrados actualmente")
    kpi_card("Valor Pipeline", f"{valor_total:,.0f}€", f"{coste_total:,.0f}€ invertidos")
    kpi_card("ROI Global", f"{roi_global:.2f}x", "Retorno sobre inversión")
    kpi_card("Clientes Reales", f"{clientes} ({clientes/total_leads*100:.1f}%)", "Tasa de conversión")
    
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.bar_chart(df_f.groupby("VERTICAL_EMPRESA")["VALOR_LEAD"].sum().rename("Valor por Vertical"), use_container_width=True)
    with c2:
        st.bar_chart(df_f.groupby("TIPO_FORM")["VALOR_LEAD"].mean().rename("Valor Medio por Formulario"), use_container_width=True)

# TAB 2: Lista Interactiva
with tab2:
    st.markdown("### 📋 Registro de Leads")
    col_config = {
        "N_FORM": st.column_config.TextColumn("N. Form"),
        "FECHA_ENVIO_FORM": st.column_config.DateColumn("Fecha"),
        "NOMBRE_EMPRESA": st.column_config.TextColumn("Empresa"),
        "NOMBRE_ENVIO_MAIL": st.column_config.TextColumn("Contacto"),
        "MAIL": st.column_config.TextColumn("Email"),
        "TELÉFONO": st.column_config.TextColumn("Teléfono"),
        "MENSAJE": st.column_config.TextColumn("Mensaje", width="large"),
        "TIPO_FORM": st.column_config.TextColumn("Tipo Form"),
        "SON_CLIENTE": st.column_config.CheckboxColumn("Es Cliente"),
        "ANOTACIONES": st.column_config.TextColumn("Anotaciones"),
        "VALOR_LEAD": st.column_config.NumberColumn("Valor Lead (€)", format="%.2f"),
        "COSTE_DEL_LEAD": st.column_config.NumberColumn("Coste Lead (€)", format="%.2f"),
        "ORIGEN_FORM_HA_FINALIZADO": st.column_config.TextColumn("Finalizado"),
        "FACTURACION": st.column_config.TextColumn("Facturación"),
        "VERTICAL_EMPRESA": st.column_config.TextColumn("Vertical"),
        "LINKEDIN": st.column_config.LinkColumn("LinkedIn"),
        "CARGO": st.column_config.TextColumn("Cargo")
    }
    st.dataframe(df_f, use_container_width=True, column_config=col_config, hide_index=True)

# TAB 3: Detalle & Análisis
with tab3:
    st.markdown("### 🔍 Detalle & Análisis de Lead")
    options = df_f["N_FORM"].tolist() if len(df_f) > 0 else []
    sel_lead = st.selectbox("Selecciona un lead para análisis profundo", options=options)
    
    if sel_lead:
        row = df_f[df_f["N_FORM"] == sel_lead].iloc[0]
        c1, c2 = st.columns([2, 1])
        
        with c1:
            st.markdown(f"**Empresa:** {row['NOMBRE_EMPRESA']} | **Cargo:** {row['CARGO']}")
            st.markdown(f"**Email:** `{row['MAIL']}` | **Tel:** {row['TELÉFONO']} | [LinkedIn]({row['LINKEDIN']})")
            st.markdown(f"**Vertical:** `{row['VERTICAL_EMPRESA']}` | **Facturación:** `{row['FACTURACION']}`")
            st.markdown(f"**Mensaje:** *{row['MENSAJE']}*")
            st.markdown(f"**Anotaciones:** {row['ANOTACIONES']}")
        
        with c2:
            st.metric("Valor Lead", f"{row['VALOR_LEAD']:,.2f}€")
            st.metric("Coste Lead", f"{row['COSTE_DEL_LEAD']:,.2f}€")
            st.metric("ROI", f"{row['ROI_LEAD']:.2f}x")
            st.progress(row['PUNTUACION']/100)
            st.caption(f"Puntuación: **{row['PUNTUACION']}/100** | {row['ESTADO_VALOR']}")
        
        st.markdown("---")
        st.markdown("📝 **Actualizar Anotaciones**")
        new_notes = st.text_area("", value=row["ANOTACIONES"], label_visibility="collapsed")
        
        if st.button("Guardar Cambios"):
            idx = st.session_state.leads_df[st.session_state.leads_df["N_FORM"]==sel_lead].index[0]
            st.session_state.leads_df.at[idx, "ANOTACIONES"] = new_notes
            st.session_state.leads_df = calcular_valoracion(st.session_state.leads_df)
            st.success("✅ Anotación actualizada y scoring recalculado")
            st.rerun()

# Footer
st.markdown('<div class="kaibot-footer">© 2026 KaiBot. Todos los derechos reservados. | Optimizado para gestión comercial B2B.</div>', unsafe_allow_html=True)
