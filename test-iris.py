#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📊 ANALIZADOR DE QUIEBRAS BANCARIAS - STREAMLIT
Estructura de 5 tabs: Exploración → Preprocesamiento → Modelado → Evaluación → Interpretación
✅ Datos sintéticos por defecto | ✅ Modelos múltiples | ✅ Persistencia | ✅ UI Profesional
"""

# ============================================================================
# 📦 IMPORTACIONES & CONFIG
# ============================================================================
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
    confusion_matrix, roc_curve, classification_report
)
import pickle
import io
import json
import re
import nbformat
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="🏦 Analizador de Quiebras Financieras",
    page_icon="📉",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# 🗄️ STATE MANAGEMENT
# ============================================================================
def init_session_state():
    defaults = {
        'data_raw': None, 'schema': None, 'mapping': {}, 'data_processed': None,
        'X_train': None, 'X_test': None, 'y_train': None, 'y_test': None,
        'feature_names': [], 'preprocessor': None, 'target_col': 'bankrupt',
        'models': {}, 'metrics': {}, 'evaluation_results': {},
        'is_synthetic': True, 'upload_available': True
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session_state()

# ============================================================================
# 🎲 SYNTHETIC DATA GENERATOR
# ============================================================================
@st.cache_data
def generate_synthetic_data(n_companies: int = 80, n_years: int = 6) -> pd.DataFrame:
    """Genera datos financieros realistas con relación causal hacia quiebra"""
    np.random.seed(42)
    sectors = ['Retail', 'Manufactura', 'Tecnología', 'Construcción', 'Servicios']
    data = []
    
    for year in range(2019, 2019 + n_years):
        for comp_id in range(1, n_companies + 1):
            sector = np.random.choice(sectors)
            base_assets = np.random.uniform(1e6, 5e7)
            growth = np.random.normal(0.05, 0.15)
            
            assets = base_assets * (1 + growth * (year - 2019)) * np.random.uniform(0.8, 1.2)
            liabilities = assets * np.random.uniform(0.4, 0.85) * (1 + np.random.normal(0, 0.1))
            equity = assets - liabilities
            revenue = assets * np.random.uniform(0.5, 1.5) * (1 + growth * (year - 2019))
            expenses = revenue * np.random.uniform(0.6, 0.95)
            net_income = revenue - expenses
            cash_flow = net_income * np.random.uniform(0.7, 1.3) + np.random.normal(0, 1e4)
            
            debt_ratio = liabilities / assets if assets > 0 else 0
            current_ratio = cash_flow / (liabilities * 0.1) if liabilities > 0 else np.inf
            
            # Lógica de quiebra con ruido
            bankrupt_prob = (
                0.6 * min(debt_ratio / 0.7, 1.0) +
                0.3 * max(0, 1 - current_ratio / 1.5) +
                0.1 * (1 if net_income < 0 else 0) +
                np.random.normal(0, 0.1)
            )
            bankrupt = 1 if bankrupt_prob > 0.55 else 0
            
            data.append({
                'company_id': f'EMP_{comp_id:04d}',
                'sector': sector,
                'year': year,
                'asset_total': max(0, assets),
                'liability_total': max(0, liabilities),
                'equity': max(0, equity),
                'revenue': max(0, revenue),
                'net_income': net_income,
                'cash_flow': cash_flow,
                'debt_ratio': debt_ratio,
                'current_ratio': current_ratio,
                'bankrupt': bankrupt
            })
    
    df = pd.DataFrame(data)
    
    # Introducir valores faltantes y outliers controlados
    mask_missing = np.random.random(df.shape) < 0.03
    df[df.columns[4:]] = df[df.columns[4:]].mask(mask_missing)
    outlier_mask = np.random.random(len(df)) < 0.02
    df.loc[outlier_mask, 'debt_ratio'] = np.random.uniform(1.5, 3.0, outlier_mask.sum())
    df.loc[outlier_mask, 'current_ratio'] = np.random.uniform(-0.5, 0.2, outlier_mask.sum())
    
    return df

# ============================================================================
# 📥 DATA LOADER & SCHEMA (EXISTING FUNCTIONALITY PRESERVED)
# ============================================================================
def load_csv(file) -> pd.DataFrame:
    if file.name.endswith('.csv'):
        for enc in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
            try: return pd.read_csv(file, encoding=enc)
            except UnicodeDecodeError: continue
        raise ValueError("Encoding no detectado")
    elif file.name.endswith(('.xlsx', '.xls')): return pd.read_excel(file)
    raise ValueError("Formato no soportado")

def load_schema_from_notebook(file) -> dict:
    content = file.getvalue()
    if isinstance(content, bytes): content = content.decode('utf-8')
    if file.name.endswith('.json'): return json.loads(content)
    if file.name.endswith('.ipynb'):
        nb = nbformat.reads(content, as_version=4)
        for cell in nb.cells:
            if cell.cell_type == 'code' and ('SCHEMA_DEFINITION' in cell.source or '"type":' in cell.source):
                m = re.search(r'schema\s*=\s*({.*?})(?=\n\w|\n#|$)', cell.source, re.DOTALL)
                if m:
                    try: return json.loads(m.group(1))
                    except: import ast; return ast.literal_eval(m.group(1))
    try: return json.loads(content)
    except: raise ValueError("Formato de esquema no válido. Use JSON o notebook con # SCHEMA_DEFINITION")

def validate_data_with_schema(df: pd.DataFrame, mapping: dict, schema: dict) -> pd.DataFrame:
    df_v = df.copy()
    for csv_c, sch_k in mapping.items():
        if csv_c not in df_v.columns: continue
        td = schema.get(sch_k, {}).get('type', 'string')
        if td in ['float', 'decimal', 'currency', 'amount']:
            df_v[csv_c] = pd.to_numeric(df_v[csv_c].astype(str).str.replace(r'[,$€£%]', '', regex=True).str.strip(), errors='coerce')
        elif td in ['integer', 'int', 'count']: df_v[csv_c] = pd.to_numeric(df_v[csv_c], errors='coerce').astype('Int64')
        elif td in ['date', 'datetime', 'timestamp']:
            df_v[csv_c] = pd.to_datetime(df_v[csv_c], format=schema.get(sch_k, {}).get('format'), errors='coerce')
        elif td == 'boolean':
            df_v[csv_c] = df_v[csv_c].astype(str).str.lower().map({'true':1,'false':0,'1':1,'0':0,'si':1,'no':0})
        if 'min' in schema.get(sch_k, {}): df_v.loc[df_v[csv_c] < schema[sch_k]['min'], csv_c] = None
        if 'max' in schema.get(sch_k, {}): df_v.loc[df_v[csv_c] > schema[sch_k]['max'], csv_c] = None
    return df_v

# ============================================================================
# ⚙️ PREPROCESSING & MODELING ENGINE
# ============================================================================
class BankruptcyPreprocessor:
    def __init__(self, df: pd.DataFrame, target_col: str = 'bankrupt'):
        self.df = df.copy()
        self.target_col = target_col
        self.numeric_cols = df.select_dtypes(include='number').columns.drop([target_col], errors='ignore').tolist()
        self.categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        
    def fit_transform(self, impute_strategy: str = 'median', encode: str = 'onehot') -> Tuple[pd.DataFrame, Any, Any]:
        df = self.df.copy()
        # Imputación
        if impute_strategy == 'median':
            df[self.numeric_cols] = df[self.numeric_cols].transform(lambda x: x.fillna(x.median()))
            for c in self.categorical_cols: df[c] = df[c].fillna(df[c].mode()[0] if not df[c].mode().empty else 'Unknown')
        elif impute_strategy == 'drop': df = df.dropna()
        
        # Target encoding
        if df[self.target_col].dtype == 'object':
            le = LabelEncoder()
            df[self.target_col] = le.fit_transform(df[self.target_col])
        
        # Separar X, y
        X = df.drop([self.target_col], axis=1)
        y = df[self.target_col]
        
        # Pipeline
        num_trans = Pipeline([
            ('imputer', 'passthrough'),
            ('scaler', StandardScaler())
        ])
        cat_trans = Pipeline([
            ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
        ]) if self.categorical_cols else 'passthrough'
        
        preprocessor = ColumnTransformer(
            transformers=[('num', num_trans, self.numeric_cols), ('cat', cat_trans, self.categorical_cols)]
        )
        
        X_processed = preprocessor.fit_transform(X)
        feature_names = self.numeric_cols.copy()
        if self.categorical_cols:
            ohe = preprocessor.named_transformers_['cat'].named_steps['onehot']
            feature_names += list(ohe.get_feature_names_out(self.categorical_cols))
            
        return pd.DataFrame(X_processed, columns=feature_names), y, preprocessor, feature_names

def train_model(model_name: str, X_train: pd.DataFrame, y_train: pd.DataFrame) -> Any:
    models = {
        'Logistic Regression': LogisticRegression(max_iter=1000, class_weight='balanced'),
        'Decision Tree': DecisionTreeClassifier(max_depth=5, min_samples_split=10, class_weight='balanced'),
        'Random Forest': RandomForestClassifier(n_estimators=100, max_depth=6, class_weight='balanced', random_state=42),
        'Gradient Boosting': GradientBoostingClassifier(n_estimators=150, max_depth=4, learning_rate=0.1, random_state=42),
        'SVM': SVC(kernel='rbf', class_weight='balanced', probability=True, random_state=42)
    }
    model = models[model_name]
    model.fit(X_train, y_train)
    return model

def evaluate_model(model, X_test: pd.DataFrame, y_test: pd.DataFrame) -> Dict[str, Any]:
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1] if hasattr(model, "predict_proba") else [0.5]*len(y_test)
    
    metrics = {
        'Accuracy': accuracy_score(y_test, y_pred),
        'Precision': precision_score(y_test, y_pred, zero_division=0),
        'Recall': recall_score(y_test, y_pred, zero_division=0),
        'F1-Score': f1_score(y_test, y_pred, zero_division=0),
        'ROC-AUC': roc_auc_score(y_test, y_proba)
    }
    cm = confusion_matrix(y_test, y_pred)
    fpr, tpr, _ = roc_curve(y_test, y_proba)
    return metrics, cm, fpr, tpr

def get_feature_importance(model, feature_names: List[str]) -> pd.DataFrame:
    if hasattr(model, 'coef_'):
        importances = np.abs(model.coef_[0])
    elif hasattr(model, 'feature_importances_'):
        importances = model.feature_importances_
    else:
        return pd.DataFrame({'Feature': feature_names, 'Importance': 0.0})
    
    df_imp = pd.DataFrame({'Feature': feature_names, 'Importance': importances}).sort_values('Importance', ascending=False)
    return df_imp

# ============================================================================
# 🧠 QWEN SUGGESTIONS ENGINE
# ============================================================================
def generate_qwen_suggestions(df: pd.DataFrame, metrics: Optional[Dict] = None) -> List[str]:
    suggestions = []
    n_rows, n_cols = df.shape
    missing_pct = df.isnull().mean().mean() * 100
    target_col = [c for c in df.columns if 'bankrupt' in c.lower() or 'quiebra' in c.lower()]
    
    if target_col:
        balance = df[target_col[0]].value_counts(normalize=True)
        if balance.iloc[1] < 0.3: suggestions.append("⚠️ Clase desbalanceada. Considere SMOTE o ajuste de class_weight en el modelo.")
    
    if missing_pct > 5: suggestions.append("🔧 >5% de valores faltantes. Valide imputación por mediana/moda o KNN.")
    if n_rows < 500: suggestions.append("📈 Dataset pequeño. Use validación cruzada estratificada para evitar overfitting.")
    
    corr = df.select_dtypes('number').corr()
    high_corr = [(c1, c2) for c1 in corr.columns for c2 in corr.columns if c1 < c2 and abs(corr.loc[c1, c2]) > 0.85]
    if high_corr: suggestions.append(f"🔗 Multicolinealidad detectada: {high_corr[0]}. Considere eliminar una o usar PCA.")
    
    if metrics and metrics.get('Recall', 0) < 0.6:
        suggestions.append("🎯 Recall bajo. En quiebras, priorizamos evitar falsos negativos. Ajuste umbral o use modelos ensemble.")
    
    suggestions.append("💡 Recorte outliers en `debt_ratio` y `current_ratio` mediante IQR o winsorización.")
    suggestions.append("📊 Valide estabilidad temporal: entrene por años históricos y test en último año.")
    return suggestions

# ============================================================================
# 🖥️ UI COMPONENTS
# ============================================================================
def render_tab1_exploracion():
    st.header("🔍 1. Exploración de Datos")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        mode = st.radio("Fuente de datos:", ["🎲 Datos Sintéticos", "📁 Cargar CSV/Excel"], horizontal=True)
    with col2:
        if mode == "📁 Cargar CSV/Excel":
            csv_file = st.file_uploader("Archivo de datos", type=['csv','xlsx','xls'], key="csv_up")
            if csv_file:
                st.session_state.data_raw = load_csv(csv_file)
                st.session_state.is_synthetic = False
            schema_file = st.file_uploader("Esquema Jupyter/JSON", type=['ipynb','json'], key="schema_up")
            if schema_file and st.session_state.data_raw is not None:
                st.session_state.schema = load_schema_from_notebook(schema_file)
    else:
        st.session_state.data_raw = generate_synthetic_data()
        st.session_state.is_synthetic = True

    if st.session_state.data_raw is None:
        st.info("Cargue datos o use el generador sintético.")
        return

    df = st.session_state.data_raw
    st.success(f"✅ Datos cargados: `{df.shape[0]}` filas × `{df.shape[1]}` columnas | Memoria: `{df.memory_usage(deep=True).sum()/1024**2:.2f} MB`")
    
    if not st.session_state.is_synthetic and st.session_state.schema:
        with st.expander("🔗 Aplicar Mapping de Esquema"):
            mapping = {}
            for col in df.columns:
                opts = ['-- Ignorar --'] + list(st.session_state.schema.keys())
                sel = st.selectbox(f"{col} →", opts, key=f"map_{col}")
                if sel != '-- Ignorar --': mapping[col] = sel
            if mapping and st.button("✅ Aplicar Mapping"):
                st.session_state.data_raw = validate_data_with_schema(df, mapping, st.session_state.schema)
                st.rerun()

    # Análisis estructural
    st.subheader("📊 Estructura y Tipos")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Empresas únicas", df['company_id'].nunique() if 'company_id' in df.columns else "N/A")
    c2.metric("Años cubiertos", df['year'].nunique() if 'year' in df.columns else "N/A")
    c3.metric("Variables numéricas", df.select_dtypes('number').shape[1])
    c4.metric("Variables categóricas", df.select_dtypes('object').shape[1])
    
    st.dataframe(df.dtypes.to_frame(name='Tipo'), use_container_width=True)
    
    # Distribuciones y temporales
    st.subheader("📈 Distribuciones y Tendencia Temporal")
    num_cols = df.select_dtypes('number').columns.tolist()
    if 'bankrupt' in num_cols: num_cols = [c for c in num_cols if c != 'bankrupt']
    
    tab_plots = st.tabs(["🔹 Histogramas", "🔹 Tendencia Temporal", "🔹 Correlaciones"])
    with tab_plots[0]:
        col = st.selectbox("Columna para distribuir:", num_cols)
        fig = px.histogram(df, x=col, nbins=40, marginal='box', title=f"Distribución: {col}")
        st.plotly_chart(fig, use_container_width=True)
    with tab_plots[1]:
        if 'year' in df.columns:
            time_mean = df.groupby('year')[num_cols].mean().reset_index().melt(id_vars='year')
            fig = px.line(time_mean, x='year', y='value', color='variable', title="Evolución de Medias Anuales", markers=True)
            st.plotly_chart(fig, use_container_width=True)
        else: st.warning("No hay columna `year` para análisis temporal.")
    with tab_plots[2]:
        corr = df[num_cols].corr()
        st.dataframe(corr.style.background_gradient(cmap='RdBu_r', vmin=-1, vmax=1), use_container_width=True)
        
    # Qwen Suggestions
    st.subheader("🤖 Sugerencias de Qwen")
    sugg = generate_qwen_suggestions(df)
    for s in sugg: st.info(s)

def render_tab2_preprocesamiento():
    st.header("🛠️ 2. Preprocesamiento")
    if st.session_state.data_raw is None:
        st.warning("⚠️ Cargue datos primero en la pestaña 1.")
        return
    
    df = st.session_state.data_raw.copy()
    
    st.subheader("⚙️ Configuración de Limpieza")
    c1, c2, c3 = st.columns(3)
    with c1: impute = st.selectbox("Imputación de faltantes:", ['median', 'mode', 'drop'], key="imp_strategy")
    with c2: target_col = st.selectbox("Variable objetivo:", df.columns, index=df.columns.get_loc('bankrupt') if 'bankrupt' in df.columns else 0, key="tgt")
    st.session_state.target_col = target_col
    with c3: balance_action = st.checkbox("Balancear clases (class_weight)", value=True)
    
    if st.button("🔄 Ejecutar Preprocesamiento", type="primary"):
        with st.spinner("Procesando..."):
            prep = BankruptcyPreprocessor(df, target_col)
            X, y, preprocessor, feat_names = prep.fit_transform(impute_strategy=impute)
            st.session_state.X_train, st.session_state.X_test, st.session_state.y_train, st.session_state.y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            st.session_state.preprocessor = preprocessor
            st.session_state.feature_names = feat_names
            st.session_state.data_processed = pd.concat([X, y], axis=1)
            st.success("✅ Preprocesamiento completado. Datos listos para modelado.")
    
    if st.session_state.X_train is not None:
        st.success(f"📦 Train: `{st.session_state.X_train.shape[0]}` | Test: `{st.session_state.X_test.shape[0]}` | Features: `{len(st.session_state.feature_names)}`")
        with st.expander("👁️ Vista de datos procesados"):
            st.dataframe(st.session_state.data_processed.head())

def render_tab3_modelado():
    st.header("🧠 3. Desarrollo del Modelo")
    if st.session_state.X_train is None:
        st.warning("⚠️ Ejecute el preprocesamiento primero.")
        return
    
    st.subheader("📦 Selección y Entrenamiento")
    models_avail = list(st.session_state.models.keys())
    new_model = st.selectbox("Modelo a entrenar:", [
        "Logistic Regression", "Decision Tree", "Random Forest", "Gradient Boosting", "SVM"
    ])
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button(f"🚀 Entrenar {new_model}", type="primary"):
            with st.spinner("Entrenando..."):
                model = train_model(new_model, st.session_state.X_train, st.session_state.y_train)
                st.session_state.models[new_model] = model
                st.success(f"✅ `{new_model}` almacenado correctamente.")
                st.rerun()
    with c2:
        if models_avail:
            load_btn = st.file_uploader("Cargar modelo (.pkl)", type=['pkl'], key="model_up")
            if load_btn:
                st.session_state.models['Custom'] = pickle.loads(load_btn.read())
                st.success("✅ Modelo cargado desde archivo.")
                st.rerun()
    
    if st.session_state.models:
        st.subheader("💾 Modelos Almacenados")
        for name, model in st.session_state.models.items():
            col1, col2, col3 = st.columns([3, 1, 1])
            col1.markdown(f"**{name}** | Parámetros: `{model.get_params()}`")
            buf = io.BytesIO()
            pickle.dump(model, buf)
            col2.download_button("⬇️ Guardar", buf.getvalue(), f"{name.lower().replace(' ','_')}.pkl", "application/octet-stream")
            if col3.button("🗑️ Eliminar", key=f"del_{name}"):
                del st.session_state.models[name]
                st.rerun()

def render_tab4_evaluacion():
    st.header("📊 4. Evaluación de Modelos")
    if not st.session_state.models:
        st.warning("⚠️ Entrene al menos un modelo primero.")
        return
    
    st.subheader("🎯 Métricas de Clasificación")
    selected = st.multiselect("Modelos a evaluar:", list(st.session_state.models.keys()), default=list(st.session_state.models.keys()))
    
    if selected:
        metrics_df = []
        for name in selected:
            model = st.session_state.models[name]
            m, cm, fpr, tpr = evaluate_model(model, st.session_state.X_test, st.session_state.y_test)
            m['Modelo'] = name
            metrics_df.append(m)
            
            st.session_state.evaluation_results[name] = {'metrics': m, 'cm': cm, 'fpr': fpr, 'tpr': tpr}
        
        st.dataframe(pd.DataFrame(metrics_df).set_index('Modelo').style.format("{:.3f}"), use_container_width=True)
        
        # Visualizaciones
        tab_v = st.tabs(["🔹 Matriz de Confusión", "🔹 Curva ROC", "🔹 Importancia de Features"])
        with tab_v[0]:
            cols = st.columns(len(selected))
            for i, name in enumerate(selected):
                cm = st.session_state.evaluation_results[name]['cm']
                fig = px.imshow(cm, text_auto=True, title=f"{name}", labels={'x':'Predicho','y':'Real'}, 
                              color_continuous_scale='Blues', aspect='auto')
                cols[i].plotly_chart(fig, use_container_width=True)
        with tab_v[1]:
            fig = go.Figure()
            for name in selected:
                res = st.session_state.evaluation_results[name]
                fig.add_trace(go.Scatter(x=res['fpr'], y=res['tpr'], mode='lines', name=f"{name} (AUC={res['metrics']['ROC-AUC']:.3f})"))
            fig.add_shape(type='line', line=dict(dash='dash'), x0=0, x1=1, y0=0, y1=1)
            fig.update_layout(title="Curvas ROC", xaxis_title="Tasa de Falsos Positivos", yaxis_title="Tasa de Verdaderos Positivos")
            st.plotly_chart(fig, use_container_width=True)
        with tab_v[2]:
            if st.session_state.feature_names:
                model = st.session_state.models.get(selected[0])
                imp = get_feature_importance(model, st.session_state.feature_names).head(10)
                fig = px.bar(imp, x='Importance', y='Feature', orientation='h', title=f"Top Features: {selected[0]}")
                st.plotly_chart(fig, use_container_width=True)

def render_tab5_interpretacion():
    st.header("🔮 5. Interpretación y Conclusiones")
    if not st.session_state.evaluation_results:
        st.warning("⚠️ Evalúe modelos primero.")
        return
    
    best_model = max(st.session_state.evaluation_results.items(), key=lambda x: x[1]['metrics']['F1-Score'])
    st.subheader(f"🏆 Modelo Recomendado: `{best_model[0]}`")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("F1-Score", f"{best_model[1]['metrics']['F1-Score']:.3f}")
    c2.metric("Recall", f"{best_model[1]['metrics']['Recall']:.3f}")
    c3.metric("Precision", f"{best_model[1]['metrics']['Precision']:.3f}")
    c4.metric("ROC-AUC", f"{best_model[1]['metrics']['ROC-AUC']:.3f}")
    
    st.subheader("📝 Interpretación Empresarial")
    model = st.session_state.models[best_model[0]]
    imp_df = get_feature_importance(model, st.session_state.feature_names)
    
    st.markdown(f"""
    🔍 **Factores clave de riesgo:** `{imp_df.iloc[0]['Feature']}`, `{imp_df.iloc[1]['Feature']}`, `{imp_df.iloc[2]['Feature']}`  
    💡 **Umbral óptimo:** El modelo prioriza `{best_model[1]['metrics']['Recall']:.1%}` de quiebras reales detectadas.  
    ⚠️ **Riesgo operativo:** Falsos positivos en `{1-best_model[1]['metrics']['Precision']:.1%}` podrían generar revisión innecesaria de créditos.  
    📉 **Recomendación:** Implementar alertas tempranas cuando `{imp_df.iloc[0]['Feature']}` supere `{imp_df.iloc[0]['Importance']:.2f}` en peso relativo.
    """)
    
    st.subheader("💾 Exportar Reporte")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📄 Exportar JSON Completo"):
            report = {
                'metadata': {'date': datetime.now().isoformat(), 'n_models': len(st.session_state.models)},
                'best_model': best_model[0],
                'metrics': best_model[1]['metrics'],
                'feature_importance': imp_df.head(10).to_dict(orient='records'),
                'qwen_suggestions': generate_qwen_suggestions(st.session_state.data_raw, best_model[1]['metrics'])
            }
            st.download_button("⬇️ Descargar", json.dumps(report, indent=2, default=str), "reporte_quiebras.json", "application/json")
    with c2:
        if st.button("📊 Exportar CSV Evaluaciones"):
            ev_df = pd.DataFrame({k: v['metrics'] for k,v in st.session_state.evaluation_results.items()}).T
            st.download_button("⬇️ Descargar", ev_df.to_csv(index_label="modelo"), "metricas_modelos.csv", "text/csv")
    
    st.info("💡 **Próximos pasos:** Desplegar modelo como API FastAPI, integrar monitoreo de drift con Evidently AI, y validar en out-of-time sample.")

# ============================================================================
# 🚀 MAIN APP
# ============================================================================
def main():
    st.title("🏦 Analizador de Quiebras Financieras")
    st.caption("Pipeline completo: Exploración → Preprocesamiento → Modelado → Evaluación → Interpretación | Datos sintéticos por defecto")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔍 1. Exploración", "🛠️ 2. Preprocesamiento", "🧠 3. Modelado", "📊 4. Evaluación", "🔮 5. Interpretación"
    ])
    
    with tab1: render_tab1_exploracion()
    with tab2: render_tab2_preprocesamiento()
    with tab3: render_tab3_modelado()
    with tab4: render_tab4_evaluacion()
    with tab5: render_tab5_interpretacion()

if __name__ == "__main__":
    main()
