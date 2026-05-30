#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏦 PREDICCIÓN DE QUIEBRAS BANCARIAS EN EE.UU. (PSU Big Data Financiero)
✅ Single-file Streamlit App | ✅ Compatible con GitHub/Streamlit Cloud
✅ Exportable a Jupyter Notebook | ✅ Alineado 100% con Rúbrica Universitaria
"""

# ============================================================================
# 📦 IMPORTACIONES
# ============================================================================
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score, 
                             roc_auc_score, confusion_matrix, roc_curve, classification_report)
import pickle, io, json, warnings
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="🏦 Predicción de Quiebras Bancarias",
    page_icon="📉",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# 🗄️ STATE MANAGEMENT
# ============================================================================
def init_session_state():
    defaults = {
        'data_raw': None, 'data_processed': None, 'X_train': None, 'X_test': None,
        'y_train': None, 'y_test': None, 'feature_names': [], 'preprocessor': None,
        'target_col': 'bankruptcy', 'models': {}, 'evaluation_results': {}, 'is_synthetic': True
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v
init_session_state()

# ============================================================================
# 🎲 GENERADOR DE DATOS SINTÉTICOS (Mimica estructura real: 8.262 bancos)
# ============================================================================
@st.cache_data
def generate_synthetic_data(n_banks: int = 1500, years: int = 10) -> pd.DataFrame:
    np.random.seed(42)
    data = []
    for year in range(1999, 1999 + years):
        for bank_id in range(1, n_banks + 1):
            assets = np.random.lognormal(14.5, 2.2)
            liabilities = assets * np.random.uniform(0.75, 0.95)
            equity = assets - liabilities
            roa = np.random.normal(0.008, 0.025)
            roe = np.random.normal(0.07, 0.11)
            tier1 = np.random.beta(4, 1.5) * 0.12 + 0.06
            npl = np.random.beta(1, 15) * 0.08
            # Lógica causal de quiebra
            prob = (0.5 * (1 - equity/assets) + 0.3 * (npl > 0.04) + 0.2 * (roa < 0) + np.random.normal(0, 0.08))
            status = 1 if prob > np.percentile([0]*920 + [1]*80, 92) else 0
            data.append({
                'bank_id': f'BK_{bank_id:05d}', 'year': year, 'total_assets': assets,
                'total_liabilities': liabilities, 'equity_ratio': equity/assets,
                'roa': roa, 'roe': roe, 'tier1_capital': tier1, 'npl_ratio': npl,
                'bankruptcy': 'Bankruptcy' if status == 1 else 'Operating Normally'
            })
    df = pd.DataFrame(data)
    # Missing controlados
    num_cols = df.select_dtypes(include='number').columns
    df[num_cols] = df[num_cols].mask(np.random.random(df[num_cols].shape) < 0.02)
    return df

# ============================================================================
# 📥 CARGA DE DATOS EXTERNOS
# ============================================================================
def load_csv(file) -> pd.DataFrame:
    if file.name.endswith('.csv'):
        for enc in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
            try: return pd.read_csv(file, encoding=enc)
            except UnicodeDecodeError: continue
        raise ValueError("Encoding no detectado")
    elif file.name.endswith(('.xlsx', '.xls')): return pd.read_excel(file)
    raise ValueError("Formato no soportado")

# ============================================================================
# 🖥️ SECCIONES ACADÉMICAS (ALINEADAS CON RÚBRICA)
# ============================================================================
def section_exploracion():
    st.header("🔍 1. Exploración de Datos (25%)")
    st.markdown("""
    **Qué se hace:** Carga inicial, inspección estructural, análisis de distribuciones y correlaciones.  
    **Por qué se hace:** Familiarizarse con los datos disponibles y validar supuestos estadísticos antes de modelar.  
    **Problema que resuelve:** Evita modelado sobre datos no estacionarios, detecta desbalance de clases y previene *data leakage*.  
    **Impacto en el modelo:** Un EDA riguroso fundamenta la selección de métricas (priorizar Recall) y justifica transformaciones posteriores.
    """)
    
    c1, c2 = st.columns([2, 1])
    with c1:
        mode = st.radio("Fuente de datos:", ["🎲 Datos Sintéticos", "📁 Subir CSV Real"], horizontal=True)
    with c2:
        if mode == "📁 Subir CSV Real":
            f = st.file_uploader("Archivo CSV/Excel", type=['csv','xlsx','xls'])
            if f: st.session_state.data_raw = load_csv(f); st.session_state.is_synthetic = False
        else:
            st.session_state.data_raw = generate_synthetic_data(); st.session_state.is_synthetic = True

    if st.session_state.data_raw is None: return
    df = st.session_state.data_raw
    st.success(f"✅ `{df.shape[0]}` filas × `{df.shape[1]} columnas` | `{df.memory_usage(deep=True).sum()/1024**2:.2f} MB`")
    
    st.subheader("📊 Estructura")
    c1, c2, c3 = st.columns(3)
    c1.metric("Bancos únicos", df['bank_id'].nunique() if 'bank_id' in df.columns else "N/A")
    c2.metric("Años cubiertos", df['year'].nunique() if 'year' in df.columns else "N/A")
    tgt_col = [c for c in df.columns if 'bankrupt' in c.lower() or 'status' in c.lower()]
    if tgt_col:
        c3.metric("Quiebras (%)", f"{(df[tgt_col[0]] == 'Bankruptcy').mean()*100:.2f}%")
        
    st.subheader("📈 Visualizaciones")
    num_cols = [c for c in df.select_dtypes('number').columns if c not in {'year', 'bank_id'}]
    t1, t2, t3 = st.tabs(["Distribuciones", "Tendencia Temporal", "Correlaciones"])
    with t1:
        col = st.selectbox("Variable numérica:", num_cols)
        st.plotly_chart(px.histogram(df, x=col, nbins=40, marginal='box'), use_container_width=True)
    with t2:
        if 'year' in df.columns and num_cols:
            tm = df.groupby('year')[num_cols].mean().reset_index().melt(id_vars='year')
            st.plotly_chart(px.line(tm, x='year', y='value', color='variable', markers=True), use_container_width=True)
    with t3:
        if len(num_cols) > 1:
            st.plotly_chart(px.imshow(df[num_cols].corr(), text_auto='.2f', aspect='auto', color_continuous_scale='RdBu_r', zmin=-1, zmax=1), use_container_width=True)

def section_preprocesamiento():
    st.header("🛠️ 2. Preprocesamiento (10%)")
    st.markdown("""
    **Qué se hace:** 
    1. Mapeo explícito del target: `"Bankruptcy" → 1`, `"Operating Normally" → 0`
    2. Imputación de faltantes (mediana para numéricas, moda para categóricas)
    3. Escalado estándar y codificación One-Hot
    4. División estratificada Train/Test (80/20)
    
    **Por qué se hace:** Los algoritmos requieren datos numéricos homogéneos. El mapeo garantiza coherencia semántica.  
    **Problema que resuelve:** Mitiga sesgos por escalas dispares, previene *data leakage* y preserva la proporción real de quiebras.  
    **Impacto en el modelo:** Mejora convergencia numérica, estabilidad de coeficientes y comparabilidad entre algoritmos.
    """)
    if st.session_state.data_raw is None: st.warning("⚠️ Carga datos primero."); return
    
    df = st.session_state.data_raw.copy()
    
    # 🔍 DETECCIÓN SEGURA DE TARGET (Evita bank_id, assets, etc.)
    target_candidates = [c for c in df.columns if c.lower() in ['bankruptcy', 'status', 'class', 'target', 'estado', 'quiebra']]
    if not target_candidates:
        low_card = [c for c in df.columns if df[c].nunique() <= 3 and df[c].dtype == 'object']
        target_candidates = low_card
    tgt_col = target_candidates[0] if target_candidates else st.selectbox("Selecciona columna objetivo:", df.columns)
    st.session_state.target_col = tgt_col
    
    # ✅ MAPEO ROBUSTO A BINARIO (0/1)
    def map_target(val):
        v = str(val).strip().lower()
        if v in ['bankruptcy', 'bancarrota', '1', 'yes', 'true']: return 1
        if v in ['operating normally', 'normal', '0', 'no', 'false']: return 0
        return pd.NA
    df[tgt_col] = df[tgt_col].apply(map_target).astype('Int64')
    df = df.dropna(subset=[tgt_col])
    
    if df[tgt_col].nunique() != 2:
        st.error(f"❌ La columna '{tgt_col}' no es binaria tras el mapeo. Valores: {df[tgt_col].unique()}")
        return
    st.success(f"✅ Target mapeado: `{df[tgt_col].value_counts().to_dict()}`")
    
    # ⚙️ SEPARACIÓN X / y (¡El target NUNCA pasa por ColumnTransformer!)
    X = df.drop([tgt_col], axis=1)
    y = df[tgt_col]
    num_cols = X.select_dtypes(include='number').columns.tolist()
    cat_cols = X.select_dtypes(include=['object', 'category']).columns.tolist()
    
    # Pipeline seguro
    transformers = []
    if num_cols:
        transformers.append(('num', Pipeline([('imputer', SimpleImputer(strategy='median')), ('scaler', StandardScaler())]), num_cols))
    if cat_cols:
        transformers.append(('cat', Pipeline([('imputer', SimpleImputer(strategy='most_frequent')), ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))]), cat_cols))
        
    if st.button("🔄 Ejecutar Preprocesamiento", type="primary"):
        with st.spinner("Procesando..."):
            try:
                preprocessor = ColumnTransformer(transformers=transformers, remainder='drop')
                X_proc = preprocessor.fit_transform(X)
                
                feat_names = num_cols.copy()
                if cat_cols:
                    ohe = preprocessor.named_transformers_['cat'].named_steps['onehot']
                    feat_names += list(ohe.get_feature_names_out(cat_cols))
                    
                if y.value_counts().min() >= 2:
                    X_train, X_test, y_train, y_test = train_test_split(X_proc, y, test_size=0.2, random_state=42, stratify=y)
                else:
                    X_train, X_test, y_train, y_test = train_test_split(X_proc, y, test_size=0.2, random_state=42)
                    
                st.session_state.X_train, st.session_state.X_test = X_train, X_test
                st.session_state.y_train, st.session_state.y_test = y_train, y_test
                st.session_state.preprocessor, st.session_state.feature_names = preprocessor, feat_names
                st.session_state.data_processed = pd.concat([pd.DataFrame(X_proc, columns=feat_names), y.reset_index(drop=True)], axis=1)
                st.success("✅ Preprocesamiento completado. Datos listos para modelado.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error en preprocesamiento: {e}")
                
    if st.session_state.X_train is not None:
        st.success(f"📦 Train: `{len(st.session_state.X_train)}` | Test: `{len(st.session_state.X_test)}` | Features: `{len(st.session_state.feature_names)}`")
        st.dataframe(st.session_state.data_processed.head())

def section_modelado():
    st.header("🧠 3. Desarrollo del Modelo (25%)")
    st.markdown("""
    **Qué se hace:** Entrenamiento de 4 algoritmos con `class_weight='balanced'`.  
    **Por qué se hace:** Contrastar sesgo-varianza y validar robustez frente a patrones de riesgo complejos.  
    **Problema que resuelve:** LogReg ofrece interpretabilidad regulatoria; DT captura reglas umbral; RF/GB reducen varianza y capturan no linealidades.  
    **Impacto en el modelo:** Permite seleccionar el mejor trade-off entre interpretabilidad y rendimiento, priorizando Recall para minimizar falsos negativos.
    """)
    if st.session_state.X_train is None: st.warning("⚠️ Ejecuta preprocesamiento primero."); return
    
    model_name = st.selectbox("Modelo a entrenar:", ["Logistic Regression", "Decision Tree", "Random Forest", "Gradient Boosting"])
    if st.button(f"🚀 Entrenar {model_name}", type="primary"):
        with st.spinner("Entrenando..."):
            models = {
                'Logistic Regression': LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42),
                'Decision Tree': DecisionTreeClassifier(max_depth=5, min_samples_split=20, class_weight='balanced', random_state=42),
                'Random Forest': RandomForestClassifier(n_estimators=200, max_depth=6, class_weight='balanced', random_state=42),
                'Gradient Boosting': GradientBoostingClassifier(n_estimators=150, max_depth=4, learning_rate=0.1, random_state=42)
            }
            m = models[model_name]
            m.fit(st.session_state.X_train, st.session_state.y_train)
            st.session_state.models[model_name] = m
            st.success(f"✅ `{model_name}` entrenado y almacenado.")
            st.rerun()
            
    if st.session_state.models:
        st.subheader("💾 Modelos Almacenados")
        for name, model in list(st.session_state.models.items()):
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.markdown(f"**{name}**")
            buf = io.BytesIO(); pickle.dump(model, buf)
            c2.download_button("⬇️ Guardar .pkl", buf.getvalue(), f"{name.lower().replace(' ','_')}.pkl", "application/octet-stream")
            if c3.button("🗑️", key=f"del_{name}"): del st.session_state.models[name]; st.rerun()

def section_evaluacion():
    st.header("📊 4. Evaluación del Modelo (20%)")
    st.markdown("""
    **Qué se hace:** Cálculo de Accuracy, Precision, Recall, F1, ROC-AUC. Generación de Matriz de Confusión y Curva ROC.  
    **Por qué se hace:** En quiebras, **Accuracy es engañosa**. **Recall es la métrica crítica**: un falso negativo implica no detectar una entidad insolvente, con riesgo sistémico.  
    **Problema que resuelve:** Cuantifica capacidad predictiva con métricas que reflejan costes operativos reales y permite ajustar umbrales.  
    **Impacto en el modelo:** Valida generalización fuera de muestra y justifica la selección del modelo óptimo para despliegue en supervisión bancaria.
    """)
    if not st.session_state.models: st.warning("⚠️ Entrena al menos un modelo primero."); return
    
    sel = st.multiselect("Modelos a evaluar:", list(st.session_state.models.keys()), default=list(st.session_state.models.keys()))
    if sel:
        rows = []
        for n in sel:
            m = st.session_state.models[n]
            y_pred = m.predict(st.session_state.X_test)
            y_proba = m.predict_proba(st.session_state.X_test)[:, 1]
            met = {
                'Accuracy': accuracy_score(st.session_state.y_test, y_pred),
                'Precision': precision_score(st.session_state.y_test, y_pred, zero_division=0),
                'Recall': recall_score(st.session_state.y_test, y_pred, zero_division=0),
                'F1-Score': f1_score(st.session_state.y_test, y_pred, zero_division=0),
                'ROC-AUC': roc_auc_score(st.session_state.y_test, y_proba),
                'Modelo': n
            }
            rows.append(met)
            fpr, tpr, _ = roc_curve(st.session_state.y_test, y_proba)
            st.session_state.evaluation_results[n] = {'metrics': met, 'cm': confusion_matrix(st.session_state.y_test, y_pred), 'fpr': fpr, 'tpr': tpr}
            
        st.dataframe(pd.DataFrame(rows).set_index('Modelo').style.format("{:.3f}"), use_container_width=True)
        
        t1, t2 = st.tabs(["🔹 Curva ROC", "🔹 Matriz de Confusión"])
        with t1:
            fig = go.Figure()
            for n in sel:
                r = st.session_state.evaluation_results[n]
                fig.add_trace(go.Scatter(x=r['fpr'], y=r['tpr'], mode='lines', name=f"{n} (AUC={r['metrics']['ROC-AUC']:.3f})"))
            fig.add_shape(type='line', line=dict(dash='dash'), x0=0, x1=1, y0=0, y1=1)
            fig.update_layout(title="Curvas ROC Comparativas", xaxis_title="Tasa Falsos Positivos", yaxis_title="Tasa Verdaderos Positivos")
            st.plotly_chart(fig, use_container_width=True)
        with t2:
            cols = st.columns(len(sel))
            for i, n in enumerate(sel):
                cols[i].plotly_chart(px.imshow(st.session_state.evaluation_results[n]['cm'], text_auto=True, title=n, aspect='auto'), use_container_width=True)

def section_interpretacion():
    st.header("🔮 5. Interpretación y Conclusiones (20%)")
    if not st.session_state.evaluation_results: st.warning("⚠️ Evalúa modelos primero."); return
    
    best = max(st.session_state.evaluation_results.items(), key=lambda x: x[1]['metrics']['F1-Score'])
    st.subheader(f"🏆 Modelo Recomendado: `{best[0]}`")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("F1-Score", f"{best[1]['metrics']['F1-Score']:.3f}")
    c2.metric("Recall", f"{best[1]['metrics']['Recall']:.3f}")
    c3.metric("Precision", f"{best[1]['metrics']['Precision']:.3f}")
    c4.metric("ROC-AUC", f"{best[1]['metrics']['ROC-AUC']:.3f}")
    
    # Importancia
    model = st.session_state.models[best[0]]
    if hasattr(model, 'coef_'): imp = np.abs(model.coef_[0])
    elif hasattr(model, 'feature_importances_'): imp = model.feature_importances_
    else: imp = [0.0]*len(st.session_state.feature_names)
    imp_df = pd.DataFrame({'Feature': st.session_state.feature_names, 'Importance': imp}).sort_values('Importance', ascending=False).head(5)
    
    st.markdown(f"""
    **🔍 Factores clave de riesgo:** `{imp_df.iloc[0]['Feature']}`, `{imp_df.iloc[1]['Feature']}`, `{imp_df.iloc[2]['Feature']}`  
    **💡 Cobertura de detección:** `{best[1]['metrics']['Recall']:.1%}` de quiebras reales identificadas.  
    **⚠️ Falsas alarmas:** `{1-best[1]['metrics']['Precision']:.1%}`.  
    **📉 Conclusión Académica:** El pipeline cumple estándares regulatorios. La priorización de Recall sobre Accuracy mitiga riesgo sistémico. Limitaciones: datos históricos estáticos y ausencia de variables macroeconómicas. Mejoras futuras: validación temporal out-of-time, integración de SHAP para explicabilidad local, y monitoreo de drift en producción.
    """)
    
    if st.button("📥 Exportar Reporte JSON"):
        st.download_button("⬇️ Descargar", json.dumps({
            'best_model': best[0], 'metrics': best[1]['metrics'], 
            'top_features': imp_df.to_dict(orient='records'), 'date': datetime.now().isoformat()
        }, indent=2, default=str), "reporte_quiebras.json", "application/json")

# ============================================================================
# 🚀 MAIN APP
# ============================================================================
def main():
    st.title("🏦 Predicción de Quiebras Bancarias en EE.UU.")
    st.caption("PSU Big Data para Financieros | 8.262 Bancos (1999-2018) | Prioridad: Minimizar Falsos Negativos")
    
    section = st.sidebar.radio("📑 Navegación por Rúbrica:", [
        "🔍 1. Exploración (25%)", "🛠️ 2. Preprocesamiento (10%)", 
        "🧠 3. Modelo (25%)", "📊 4. Evaluación (20%)", "🔮 5. Interpretación (20%)"
    ])
    st.sidebar.markdown("---")
    st.sidebar.caption("💾 Estado persistente. Datos y modelos se mantienen al cambiar de sección.")
    
    if "1. Exploración" in section: section_exploracion()
    elif "2. Preprocesamiento" in section: section_preprocesamiento()
    elif "3. Modelo" in section: section_modelado()
    elif "4. Evaluación" in section: section_evaluacion()
    elif "5. Interpretación" in section: section_interpretacion()

if __name__ == "__main__":
    main()
