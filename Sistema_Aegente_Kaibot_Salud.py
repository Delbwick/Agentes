# KaiBot - Generador de Contenidos LLM
# Versión Cliente - Optimizada y profesional
# © 2026 Kai Marketing LAB

import streamlit as st
from datetime import datetime
import json
import pandas as pd
from google.cloud import storage
from google.oauth2 import service_account
from openai import OpenAI
import re

# =====================================================
# CONFIGURACIÓN DE PÁGINA
# =====================================================

st.set_page_config(
    page_title="Generador de Contenidos IA | KaiBot",
    page_icon="https://kaibot.es/wp-content/uploads/2020/07/image1.png",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://kaibot.es/contacto-kaibot-b2b-marketing/',
        'Report a bug': "mailto:hello@kaibot.es",
        'About': "# KaiBot - Generador de Contenidos IA\n**Especialistas en Marketing Digital B2B**"
    }
)

# =====================================================
# CSS PERSONALIZADO - ESTILO KAIBOT
# =====================================================

st.markdown("""
    <style>
    /* Importar fuente profesional */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Variables de color KaiBot */
    :root {
        --kaibot-blue: #0066CC;
        --kaibot-blue-dark: #0052A3;
        --kaibot-blue-light: #3B82F6;
        --kaibot-dark: #1E293B;
        --kaibot-gray: #64748B;
        --kaibot-gray-light: #94A3B8;
        --kaibot-bg: #F8FAFC;
        --kaibot-white: #FFFFFF;
        --sidebar-bg: #1E293B;
        --accent-green: #10B981;
    }
    
    /* Fuente global */
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    
    /* Fondo principal */
    .main {
        background-color: var(--kaibot-bg);
    }
    
    /* Títulos profesionales */
    h1 {
        color: var(--kaibot-dark);
        font-weight: 700;
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
    }
    
    h2 {
        color: var(--kaibot-dark);
        font-weight: 600;
        font-size: 1.75rem;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    
    h3 {
        color: var(--kaibot-gray);
        font-weight: 600;
        font-size: 1.25rem;
    }
    
    /* Botones primarios KaiBot */
    .stButton>button[kind="primary"] {
        background: linear-gradient(135deg, var(--kaibot-blue) 0%, var(--kaibot-blue-dark) 100%);
        color: white;
        border: none;
        font-weight: 600;
        padding: 0.75rem 2rem;
        border-radius: 8px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(0, 102, 204, 0.2);
    }
    
    .stButton>button[kind="primary"]:hover {
        background: linear-gradient(135deg, var(--kaibot-blue-dark) 0%, #003d7a 100%);
        box-shadow: 0 6px 12px rgba(0, 102, 204, 0.3);
        transform: translateY(-2px);
    }
    
    /* Botones secundarios */
    .stButton>button {
        width: 100%;
        border-radius: 6px;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    
    /* TABS - Diseño profesional */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background-color: transparent;
        padding: 0;
        border-bottom: 2px solid #E2E8F0;
    }
    
    .stTabs [data-baseweb="tab-list"] button[role="tab"] {
        background-color: transparent;
        color: var(--kaibot-gray);
        border: none;
        border-bottom: 3px solid transparent;
        padding: 16px 32px;
        font-weight: 600;
        font-size: 15px;
        transition: all 0.3s ease;
    }
    
    .stTabs [data-baseweb="tab-list"] button[role="tab"]:hover {
        color: var(--kaibot-blue);
        border-bottom-color: var(--kaibot-blue-light);
    }
    
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        color: var(--kaibot-blue);
        border-bottom-color: var(--kaibot-blue);
        font-weight: 700;
    }
    
    .stTabs [data-baseweb="tab-panel"] {
        padding: 32px 0;
    }
    
    /* SIDEBAR - Diseño profesional oscuro */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--sidebar-bg) 0%, #0F172A 100%);
        padding-top: 2rem;
    }
    
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: white !important;
        font-weight: 600;
    }
    
    /* Inputs del sidebar */
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea {
        background-color: rgba(255, 255, 255, 0.1) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        color: var(--kaibot-blue-light) !important;
        border-radius: 6px;
        font-weight: 500;
    }
    
    [data-testid="stSidebar"] input::placeholder,
    [data-testid="stSidebar"] textarea::placeholder {
        color: rgba(255, 255, 255, 0.5) !important;
    }
    
    [data-testid="stSidebar"] input:focus,
    [data-testid="stSidebar"] textarea:focus {
        border-color: var(--kaibot-blue) !important;
        box-shadow: 0 0 0 2px rgba(0, 102, 204, 0.2);
    }
    
    /* Botones del sidebar */
    [data-testid="stSidebar"] .stButton>button {
        background-color: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        color: white !important;
        font-weight: 600;
    }
    
    [data-testid="stSidebar"] .stButton>button:hover {
        background-color: rgba(255, 255, 255, 0.15);
        border-color: rgba(255, 255, 255, 0.3);
    }
    
    [data-testid="stSidebar"] .stButton>button[kind="primary"] {
        background: linear-gradient(135deg, var(--kaibot-blue) 0%, var(--kaibot-blue-dark) 100%);
        border: none;
    }
    
    /* Expanders del sidebar */
    [data-testid="stSidebar"] .streamlit-expanderHeader {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 6px;
        font-weight: 600;
    }
    
    [data-testid="stSidebar"] .streamlit-expanderHeader:hover {
        background-color: rgba(255, 255, 255, 0.1);
    }
    
    /* Divisores */
    [data-testid="stSidebar"] hr {
        border-color: rgba(255, 255, 255, 0.2) !important;
        margin: 1.5rem 0;
    }
    
    /* Info boxes mejoradas */
    .stInfo {
        background-color: #EBF5FF;
        border-left: 4px solid var(--kaibot-blue);
        border-radius: 8px;
        padding: 1rem;
    }
    
    .stSuccess {
        background-color: #ECFDF5;
        border-left: 4px solid var(--accent-green);
        border-radius: 8px;
        padding: 1rem;
    }
    
    .stWarning {
        background-color: #FEF3C7;
        border-left: 4px solid #F59E0B;
        border-radius: 8px;
        padding: 1rem;
    }
    
    .stError {
        background-color: #FEE2E2;
        border-left: 4px solid #EF4444;
        border-radius: 8px;
        padding: 1rem;
    }
    
    /* Tablas profesionales */
    .dataframe {
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    /* Expanders mejorados */
    .streamlit-expanderHeader {
        background-color: white;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        font-weight: 600;
        color: var(--kaibot-dark);
    }
    
    /* Selectbox mejorado */
    .stSelectbox {
        border-radius: 6px;
    }
    
    /* Text areas */
    textarea {
        border-radius: 6px !important;
        border: 1px solid #E2E8F0 !important;
    }
    
    /* Spinner personalizado */
    .stSpinner > div {
        border-top-color: var(--kaibot-blue) !important;
    }
    
    /* Footer KaiBot */
    .footer-kaibot {
        background: linear-gradient(135deg, var(--kaibot-dark) 0%, #0F172A 100%);
        padding: 2rem;
        border-radius: 12px;
        margin-top: 3rem;
        color: white;
        text-align: center;
    }
    
    /* Padding optimizado */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    
    /* Progress bar */
    .stProgress > div > div {
        background-color: var(--kaibot-blue);
    }
    </style>
""", unsafe_allow_html=True)

# =====================================================
# CONFIGURACIÓN
# =====================================================

BUCKET_FOLDERS = {
    "documentos": "documentos/",
    "adicional": "adicional/",
    "validados": "documentos_validados/",
    "prompts": "prompts/"
}

# =====================================================
# FUNCIONES HELPER (todas las que ya tienes)
# =====================================================

# ... [Aquí van todas tus funciones helper existentes: get_gcs_client_from_json, list_folders_and_files, etc.]
# Para no hacer esto demasiado largo, mantén TODAS las funciones que ya tienes

# =====================================================
# HEADER PROFESIONAL
# =====================================================

# Logo y branding
col_logo, col_brand = st.columns([1, 5])

with col_logo:
    st.image("https://kaibot.es/wp-content/uploads/2020/07/image-4-300x184.png", width=120)

with col_brand:
    st.markdown("""
        <h1 style='margin-bottom: 0;'>Generador de Contenidos IA</h1>
        <p style='color: #64748B; font-size: 1.1rem; margin-top: 0.5rem;'>
            <strong>Powered by KaiBot</strong> | Análisis inteligente con OpenAI + Perplexity
        </p>
    """, unsafe_allow_html=True)

st.markdown("---")

# =====================================================
# SIDEBAR - GESTIÓN DE CONEXIONES
# =====================================================

with st.sidebar:
    # Branding en sidebar
    st.markdown("""
        <div style='text-align: center; padding: 1rem 0 2rem 0;'>
            <h2 style='color: white; margin-bottom: 0.5rem;'>⚙️ Configuración</h2>
            <p style='color: rgba(255,255,255,0.7); font-size: 0.9rem;'>Conecta tus servicios</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Estado de conexión visual
    connection_status = {
        "gcs": "gcs" in st.session_state and "bucket_name" in st.session_state,
        "openai": "openai" in st.session_state,
        "perplexity": "perplexity_key" in st.session_state
    }
    
    # Dashboard de estado
    st.markdown("### 📊 Estado de Servicios")
    
    for service, connected in connection_status.items():
        status_emoji = "✅" if connected else "❌"
        status_text = "Conectado" if connected else "Desconectado"
        status_color = "#10B981" if connected else "#EF4444"
        
        service_names = {
            "gcs": "Google Cloud",
            "openai": "OpenAI",
            "perplexity": "Perplexity"
        }
        
        st.markdown(f"""
            <div style='background: rgba(255,255,255,0.05); padding: 0.75rem; border-radius: 6px; margin-bottom: 0.5rem; border-left: 3px solid {status_color};'>
                <strong>{status_emoji} {service_names[service]}</strong><br>
                <small style='color: rgba(255,255,255,0.7);'>{status_text}</small>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Configuración Google Cloud
    with st.expander("☁️ Google Cloud Storage", expanded=not connection_status["gcs"]):
        bucket_name = st.text_input(
            "Nombre del Bucket",
            value=st.session_state.get("bucket_name", ""),
            placeholder="mi-bucket-kaibot"
        )
        
        sa_json = st.text_area(
            "Service Account (JSON)",
            height=150,
            placeholder='{"type": "service_account", ...}'
        )
        
        if st.button("💾 Conectar GCS", use_container_width=True):
            try:
                st.session_state.gcs = get_gcs_client_from_json(sa_json)
                st.session_state.bucket_name = bucket_name
                st.success("✅ Google Cloud conectado")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    # Configuración OpenAI
    with st.expander("🤖 OpenAI", expanded=not connection_status["openai"]):
        openai_key = st.text_input(
            "API Key",
            type="password",
            placeholder="sk-..."
        )
        
        if st.button("💾 Conectar OpenAI", use_container_width=True):
            try:
                st.session_state.openai = OpenAI(api_key=openai_key)
                st.success("✅ OpenAI conectado")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    # Configuración Perplexity
    with st.expander("🔍 Perplexity", expanded=not connection_status["perplexity"]):
        perplexity_key = st.text_input(
            "API Key",
            type="password",
            placeholder="pplx-..."
        )
        
        col_save, col_test = st.columns(2)
        
        with col_save:
            if st.button("💾 Guardar", use_container_width=True):
                st.session_state.perplexity_key = perplexity_key
                st.success("✅ Guardado")
                st.rerun()
        
        with col_test:
            if st.button("🧪 Probar", use_container_width=True) and perplexity_key:
                try:
                    from openai import OpenAI
                    test_client = OpenAI(api_key=perplexity_key, base_url="https://api.perplexity.ai")
                    test_client.chat.completions.create(
                        model="sonar",
                        messages=[{"role": "user", "content": "test"}]
                    )
                    st.success("✅ Funciona")
                except Exception as e:
                    st.error(f"❌ {str(e)}")
    
    st.markdown("---")
    
    # Ayuda y soporte
    st.markdown("### 💬 Soporte")
    st.markdown("""
        <div style='background: rgba(255,255,255,0.05); padding: 1rem; border-radius: 8px;'>
            <p style='margin-bottom: 0.5rem;'><strong>¿Necesitas ayuda?</strong></p>
            <p style='font-size: 0.9rem; margin-bottom: 0.5rem;'>
                📧 <a href='mailto:hello@kaibot.es' style='color: #3B82F6;'>hello@kaibot.es</a><br>
                📞 <a href='tel:+34633698832' style='color: #3B82F6;'>+34 633 69 88 32</a>
            </p>
            <a href='https://kaibot.es' target='_blank' style='color: #10B981; font-weight: 600; text-decoration: none;'>
                🌐 Visitar KaiBot.es →
            </a>
        </div>
    """, unsafe_allow_html=True)

# Verificar conexiones mínimas
if not all([connection_status["gcs"], connection_status["openai"], connection_status["perplexity"]]):
    st.warning("⚠️ **Configura todos los servicios** en el sidebar para comenzar")
    st.info("💡 Necesitas conectar Google Cloud Storage, OpenAI y Perplexity para usar el generador de contenidos")
    st.stop()

client = st.session_state.gcs
bucket_name = st.session_state.bucket_name

# =====================================================
# TABS PRINCIPALES
# =====================================================

tab1, tab2, tab3 = st.tabs(["🎯 Generar Contenido", "📁 Mis Archivos", "⚙️ Configuración Avanzada"])

# ... [Aquí irían los contenidos de cada tab, que te envío en el siguiente mensaje]

# =====================================================
# FOOTER KAIBOT
# =====================================================

st.markdown("""
    <div class='footer-kaibot'>
        <h3 style='color: white; margin-bottom: 1rem;'>Powered by KaiBot</h3>
        <p style='color: rgba(255,255,255,0.8); margin-bottom: 1rem;'>
            Especialistas en Marketing Digital B2B | Generación de leads industriales
        </p>
        <div style='display: flex; justify-content: center; gap: 2rem; flex-wrap: wrap;'>
            <span>📧 hello@kaibot.es</span>
            <span>📞 +34 633 69 88 32</span>
            <span>📍 Vitoria-Gasteiz</span>
        </div>
        <p style='margin-top: 1.5rem; color: rgba(255,255,255,0.6); font-size: 0.9rem;'>
            © 2026 Kai Marketing LAB. Todos los derechos reservados.
        </p>
    </div>
""", unsafe_allow_html=True)
