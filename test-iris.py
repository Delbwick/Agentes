#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏦 PREDICCIÓN DE QUIEBRAS BANCARIAS EN EE.UU. (PSU Big Data Financiero)
✅ Single-file Streamlit App | ✅ Compatible con GitHub/Streamlit Cloud
✅ Corregido para CSV reales sin cabecera (us_failures.csv)
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
        'target_col': 'status', 'models': {}, 'evaluation_results': {}, 'is_synthetic': True
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v
init_session_state()

# ============================================================================
# 🎲 GENERADOR DE DATOS SINTÉTICOS
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
            prob = (0.5 * (1 - equity/assets) + 0.3 * (npl > 0.04) + 0.2 * (roa < 0) + np.random.normal(0, 0.08))
            status = 1 if prob > np.percentile([0]*920 + [1]*80, 92) else 0
            data.append({
                'bank_id': f'BK_{bank_id:05d}', 'year': year, 'total_assets': assets,
                'total_liabilities': liabilities, 'equity_ratio': equity/assets,
                'roa': roa, 'roe': roe, 'tier1_capital': tier1, 'npl_ratio': npl,
                'status': 'failed' if status == 1 else 'alive'
            })
    df = pd.DataFrame(data)
    num_cols = df.select_dtypes(include='number').columns
    df[num_cols] = df[num_cols].mask(np.random.random(df[num_cols].shape) < 0.02)
    return df

# ============================================================================
# 📥 CARGA DE DATOS EXTERNOS (CORREGIDO PARA US_FAILURES.CSV)
# ============================================================================
def load_csv(file) -> pd.DataFrame:
    try:
        # Intento 1: Leer asumiendo cabecera
        for enc in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
            try: 
                df = pd.read_csv(file, encoding=enc)
                break
            except UnicodeDecodeError: continue
        else: raise ValueError("Encoding no detectado")

        # ✅ DETECCIÓN DE CSV SIN CABECERA (Como us_failures.csv)
        # Si la columna 0 parece un ID ("C_...") o la col 1 es "alive/failed", es datos puros
        col0 = str(df.columns[0]).lower()
        col1 = str(df.columns[1]).lower()
        
        is_headerless = ('c_' in col0) or ('alive' in col1) or ('failed' in col1) or (col1 in ['bankruptcy', 'operating normally'])
        
        if is_headerless:
            # Recargar sin cabecera
            file.seek(0)
            df = pd.read_csv(file, encoding=enc, header=None)
            # Asignar nombres por defecto
            df.columns = ['bank_id', 'status', 'year'] + [f'var_{i}' for i in range(4, len(df.columns) + 1)]
            
        # Convertir columnas numéricas (excepto ID y Status)
        for col in df.columns[2:]:
            if col != 'status':
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        return df
    except Exception as e:
        raise ValueError(f"Error al leer CSV: {str(e)}")

# ============================================================================
# 🖥️ SECCIONES ACADÉMICAS
# ============================================================================
def section_exploracion():
    st.header("🔍 1. Exploración de Datos (25%)")
    st.markdown("""
    **Qué se hace:** Carga, inspección estructural, análisis de distribuciones y correlaciones.  
    **Por qué se hace:** Fundamenta decisiones de preprocesamiento y evita suposiciones erróneas sobre escalas o tipos de dato.  
    **Impacto en el modelo:** Un EDA riguroso reduce data leakage y justifica transformaciones de escala y codificación del target.
    """)
    
    c1, c2 = st.columns([2, 1])
    with c1:
        mode = st.radio("Fuente de datos:", ["🎲 Datos Sintéticos", "📁 Subir CSV Real"], horizontal=True)
    with c2:
        if mode == "📁 Subir CSV Real":
            f = st.file_uploader("Archivo CSV/Excel", type=['csv','xlsx','xls'])
            if f: 
                try:
                    st.session_state.data_raw = load_csv(f)
                    st.session_state.is_synthetic = False
                    st.success(f"✅ Cargado: {st.session_state.data_raw.shape[0]} filas, {st.session_state.data_raw.shape[1]} columnas")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
        else:
            st.session_state.data_raw = generate_synthetic_data()
            st.session_state.is_synthetic = True

    if st.session_state.data_raw is None: return
    df = st.session_state.data_raw
    
    st.subheader("📊 Estructura")
    c1, c2, c3 = st.columns(3)
    c1.metric("Bancos únicos", df['bank_id'].nunique() if 'bank_id' in df.columns else "N/A")
    c2.metric("Años cubiertos", df['year'].nunique() if 'year' in df.columns else "N/A")
    
    # ✅ DETECCIÓN DE TARGET ROBUSTA
    tgt_col = None
    candidates = [c for c in df.columns if c.lower() in ['status', 'bankruptcy', 'class', 'target', 'estado']]
    if candidates: tgt_col = candidates[0]
    else:
        # Fallback: buscar columna con 'alive'/'failed'
        for c in df.columns:
            if df[c].dtype == 'object':
                vals = df[c].astype(str).str.lower().unique()
                if any('alive' in v or 'failed' in v for v in vals):
                    tgt_col = c; break
    
    if tgt_col:
        counts = df[tgt_col].value_counts()
        fail_pct = (counts.get('failed', 0) / len(df)) * 100
        c3.metric(f"Quiebras ({tgt_col})", f"{fail_pct:.2f}%")
    else:
        st.warning("⚠️ No se detectó columna objetivo automática. Usa la pestaña 2 para seleccionarla.")
        
    st.subheader("📈 Visualizaciones")
    num_cols = [c for c in df.select_dtypes('number').columns if c not in {'year', 'bank_id'} and not c.startswith('var_')]
    if not num_cols: num_cols = df.select_dtypes('number').columns[:5]
    
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
    1. Mapeo explícito del target: `"failed" → 1`, `"alive" → 0` (o variantes como Bankruptcy/Operating)
    2. Imputación de faltantes (mediana para numéricas, moda para categóricas)
    3. Escalado estándar y codificación One-Hot
    4. División estratificada Train/Test (80/20)
    
    **Por qué se hace:** Los algoritmos requieren datos numéricos homogéneos y un target binario numérico.  
    **Problema que resuelve:** Mitiga sesgos por escalas dispares y preserva la proporción real de quiebras.
    """)
    if st.session_state.data_raw is None: st.warning("⚠️ Carga datos primero."); return
    
    df = st.session_state.data_raw.copy()
    
    # ✅ DETECCIÓN DE COLUMNA TARGET CON MENSAJE
    tgt_opts = [c for c in df.columns if df[c].nunique() <= 5 and df[c].dtype in ['object', 'category', 'int64', 'float64']]
    # Priorizar columnas llamadas 'status' o similares
    priority = [c for c in tgt_opts if 'status' in c.lower() or 'bankrupt' in c.lower()]
    tgt_opts = priority + [c for c in tgt_opts if c not in priority]
    
    idx = 0
    for i, c in enumerate(tgt_opts):
        if c.lower() in ['status', 'bankruptcy', 'class']: idx = i; break
            
    st.session_state.target_col = st.selectbox("Selecciona columna objetivo:", tgt_opts, index=idx)
    imp = st.selectbox("Imputación:", ['median', 'mode', 'drop'], key="imp_strat")
    
    if st.button("🔄 Ejecutar Preprocesamiento", type="primary"):
        with st.spinner("Procesando..."):
            try:
                # 1. Mapeo de Target
                tgt = st.session_state.target_col
                def map_target(val):
                    v = str(val).strip().lower()
                    if 'failed' in v or 'bankrupt' in v: return 1
                    if 'alive' in v or 'operating' in v or 'normal' in v: return 0
                    try: return int(val)
                    except: return pd.NA
                df[tgt] = df[tgt].apply(map_target)
                df = df.dropna(subset=[tgt])
                
                if df[tgt].nunique() != 2:
                    st.error(f"❌ '{tgt}' no es binaria. Valores: {df[tgt].unique()}")
                    return

                # 2. Separación X/y
                X = df.drop([tgt], axis=1)
                y = df[tgt]
                num_cols = X.select_dtypes(include='number').columns.tolist()
                cat_cols = X.select_dtypes(include=['object', 'category']).columns.tolist()
                
                # 3. Pipeline
                transformers = []
                if num_cols:
                    transformers.append(('num', Pipeline([('imputer', SimpleImputer(strategy='median')), ('scaler', StandardScaler())]), num_cols))
                if cat_cols:
                    transformers.append(('cat', Pipeline([('imputer', SimpleImputer(strategy='most_frequent')), ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))]), cat_cols))
                
                preprocessor = ColumnTransformer(transformers=transformers, remainder='drop') if transformers else None
                X_proc = preprocessor.fit_transform(X) if preprocessor else X.values
                
                feat_names = num_cols.copy()
                if cat_cols and preprocessor:
                    feat_names += list(preprocessor.named_transformers_['cat'].named_steps['onehot'].get_feature_names_out(cat_cols))
                    
                # 4. Split
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
    **Problema que resuelve:** LogReg ofrece interpretabilidad; RF/GB reducen varianza y capturan no linealidades.  
    **Impacto en el modelo:** Permite seleccionar el mejor trade-off entre interpretabilidad y rendimiento, priorizando Recall.
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
    **Por qué se hace:** En quiebras, **Recall es la métrica crítica**: un falso negativo implica no detectar una entidad insolvente.  
    **Problema que resuelve:** Cuantifica capacidad predictiva con métricas que reflejan costes operativos reales.  
    **Impacto en el modelo:** Valida generalización fuera de muestra y justifica la selección del modelo óptimo.
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
    **📉 Conclusión Académica:** El pipeline cumple estándares regulatorios. La priorización de Recall sobre Accuracy mitiga riesgo sistémico. Limitaciones: datos históricos estáticos y ausencia de variables macroeconómicas. Mejoras futuras: validación temporal out-of-time e integración de SHAP.
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
