#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📊 ANALIZADOR FINANCIERO CON STREAMLIT - VERSIÓN SINGLE FILE - IRIS 
Importa CSV + Esquema desde Jupyter Notebook → Matching → Análisis → Visualización

✅ Todo en un solo archivo para fácil despliegue en Streamlit Cloud
✅ Compatible con GitHub: solo necesitas este archivo + requirements.txt
"""

# ============================================================================
# 📦 IMPORTACIONES
# ============================================================================
import streamlit as st
import pandas as pd
import numpy as np
import json
import re
import plotly.express as px
import plotly.graph_objects as go
from io import StringIO, BytesIO
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import nbformat

# ============================================================================
# ⚙️ CONFIGURACIÓN DE PÁGINA
# ============================================================================
st.set_page_config(
    page_title="📊 Analizador Financiero",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# 🗄️ MÓDULO: DATA LOADER
# ============================================================================
def load_csv(file) -> pd.DataFrame:
    """Carga archivo CSV o Excel con detección automática de encoding"""
    if file.name.endswith('.csv'):
        for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
            try:
                return pd.read_csv(file, encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("No se pudo determinar el encoding del archivo CSV")
    elif file.name.endswith(('.xlsx', '.xls')):
        return pd.read_excel(file)
    raise ValueError(f"Formato no soportado: {file.name}")


def load_schema_from_notebook(file) -> dict:
    """Extrae esquema de variables desde notebook Jupyter o archivo JSON"""
    content = file.getvalue()
    if isinstance(content, bytes):
        content = content.decode('utf-8')
    
    if file.name.endswith('.json'):
        return json.loads(content)
    
    if file.name.endswith('.ipynb'):
        nb = nbformat.reads(content, as_version=4)
        for cell in nb.cells:
            if cell.cell_type == 'code':
                source = cell.get('source', '')
                if 'SCHEMA_DEFINITION' in source or '"type":' in source:
                    schema_match = re.search(r'schema\s*=\s*({.*?})(?=\n\w|\n#|$)', source, re.DOTALL)
                    if schema_match:
                        try:
                            return json.loads(schema_match.group(1))
                        except json.JSONDecodeError:
                            import ast
                            return ast.literal_eval(schema_match.group(1))
    
    try:
        return json.loads(content)
    except:
        raise ValueError(
            "No se pudo extraer el esquema. Formato esperado:\n"
            "• JSON: {'col': {'type': 'float', ...}}\n"
            "• Notebook: Celda con variable 'schema' y marcador 'SCHEMA_DEFINITION'"
        )


def validate_data_with_schema(df: pd.DataFrame, mapping: dict, schema: dict) -> pd.DataFrame:
    """Valida y transforma datos según esquema mapeado"""
    df_validated = df.copy()
    
    for csv_col, schema_key in mapping.items():
        if csv_col not in df_validated.columns:
            continue
        var_def = schema.get(schema_key, {})
        var_type = var_def.get('type', 'string')
        
        if var_type in ['float', 'decimal', 'currency', 'amount']:
            df_validated[csv_col] = pd.to_numeric(
                df_validated[csv_col].astype(str).str.replace(r'[,$€£%]', '', regex=True).str.strip(),
                errors='coerce'
            )
        elif var_type in ['integer', 'int', 'count']:
            df_validated[csv_col] = pd.to_numeric(df_validated[csv_col], errors='coerce').astype('Int64')
        elif var_type in ['date', 'datetime', 'timestamp']:
            date_format = var_def.get('format', None)
            df_validated[csv_col] = pd.to_datetime(df_validated[csv_col], format=date_format, errors='coerce')
        elif var_type == 'boolean':
            df_validated[csv_col] = df_validated[csv_col].astype(str).str.lower().map(
                {'true': True, 'false': False, '1': True, '0': False, 'si': True, 'no': False}
            )
        
        if 'min' in var_def:
            df_validated.loc[df_validated[csv_col] < var_def['min'], csv_col] = None
        if 'max' in var_def:
            df_validated.loc[df_validated[csv_col] > var_def['max'], csv_col] = None
        if 'allowed_values' in var_def:
            df_validated.loc[~df_validated[csv_col].isin(var_def['allowed_values']), csv_col] = None
    
    return df_validated

# ============================================================================
# 🔗 MÓDULO: COLUMN MATCHER
# ============================================================================
class ColumnMatcher:
    """Gestiona el matching entre columnas CSV y esquema"""
    
    def __init__(self, csv_columns: List[str], schema: Dict):
        self.csv_columns = csv_columns
        self.schema = schema
        self.suggestions = self._generate_suggestions()
    
    def _generate_suggestions(self) -> Dict[str, List[str]]:
        """Genera sugerencias de matching basadas en similitud de nombres"""
        suggestions = {}
        schema_keys = list(self.schema.keys())
        
        for csv_col in self.csv_columns:
            csv_lower = csv_col.lower().replace('_', '').replace(' ', '').replace('-', '')
            matches = []
            for schema_key in schema_keys:
                schema_lower = schema_key.lower().replace('_', '').replace(' ', '').replace('-', '')
                if csv_lower == schema_lower or csv_lower in schema_lower or schema_lower in csv_lower:
                    matches.append((schema_key, 1.0))
                elif any(kw in csv_lower for kw in schema_lower.split()) or any(kw in schema_lower for kw in csv_lower.split()):
                    matches.append((schema_key, 0.7))
            suggestions[csv_col] = [m[0] for m in sorted(matches, key=lambda x: -x[1])]
        return suggestions
    
    def get_schema_info(self, schema_key: str) -> Dict:
        return self.schema.get(schema_key, {})


def render_matcher_interface(matcher: ColumnMatcher) -> Dict[str, str]:
    """Renderiza interfaz Streamlit para matching de columnas"""
    mapping = {}
    st.markdown("### 🔗 Asigna columnas del CSV a variables del esquema")
    st.info("💡 Las sugerencias se generan automáticamente por similitud de nombres")
    
    cols = st.columns(2)
    for idx, csv_col in enumerate(matcher.csv_columns):
        col_idx = idx % 2
        with cols[col_idx]:
            st.markdown(f"**📄 `{csv_col}`**")
            options = ["-- Sin mapear --"] + matcher.suggestions.get(csv_col, []) + \
                     [k for k in matcher.schema.keys() if k not in matcher.suggestions.get(csv_col, [])]
            seen = set()
            unique_options = [opt for opt in options if not (opt in seen or seen.add(opt))]
            
            default_idx = 0
            if matcher.suggestions.get(csv_col) and matcher.suggestions[csv_col][0] in unique_options:
                default_idx = unique_options.index(matcher.suggestions[csv_col][0])
            
            selected = st.selectbox("Variable del esquema:", unique_options, key=f"match_{csv_col}", 
                                  label_visibility="collapsed", index=default_idx)
            
            if selected and selected != "-- Sin mapear --":
                mapping[csv_col] = selected
                info = matcher.get_schema_info(selected)
                if info:
                    with st.expander(f"📋 Info: {selected}", expanded=False):
                        st.markdown(f"- **Tipo:** `{info.get('type', 'string')}`")
                        if 'description' in info: st.markdown(f"- **Descripción:** {info['description']}")
                        if 'format' in info: st.markdown(f"- **Formato:** `{info['format']}`")
                        if 'required' in info: st.markdown(f"- **Requerida:** {'✅ Sí' if info['required'] else '❌ No'}")
            st.divider()
    
    if mapping and 'data' in st.session_state and st.session_state.data is not None:
        st.markdown("### ✅ Resumen de Mapping")
        st.dataframe(st.session_state.data[list(mapping.keys())].head(3))
    return mapping

# ============================================================================
# 📊 MÓDULO: FINANCIAL ANALYZER
# ============================================================================
class FinancialAnalyzer:
    """Analizador especializado en datos financieros"""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.n_rows, self.n_cols = df.shape
        self.numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
        self.categorical_columns = df.select_dtypes(include=['object', 'category']).columns.tolist()
    
    @property
    def memory_usage(self) -> float:
        return self.df.memory_usage(deep=True).sum() / 1024 ** 2
    
    @property
    def dtypes_summary(self) -> pd.Series:
        return self.df.dtypes.value_counts()
    
    @property
    def dtypes_detail(self) -> pd.DataFrame:
        return pd.DataFrame({
            'columna': self.df.columns,
            'tipo': self.df.dtypes.values,
            'nulos': self.df.isnull().sum().values,
            'únicos': [self.df[col].nunique() for col in self.df.columns]
        })
    
    def get_descriptive_stats(self, columns: Optional[List[str]] = None) -> pd.DataFrame:
        cols = columns or self.numeric_columns
        if not cols: return pd.DataFrame()
        stats = self.df[cols].describe(include='all').T
        stats['cv'] = stats['std'] / stats['mean']
        stats['iqr'] = stats['75%'] - stats['25%']
        return stats
    
    def get_missing_values(self) -> pd.DataFrame:
        missing = self.df.isnull().sum()
        missing = missing[missing > 0].sort_values(ascending=False)
        if missing.empty: return pd.DataFrame()
        return pd.DataFrame({
            'missing_count': missing,
            'missing_pct': (missing / len(self.df) * 100).round(2)
        })
    
    def get_duplicates_info(self) -> Dict:
        dup_count = self.df.duplicated().sum()
        return {
            'count': int(dup_count),
            'percentage': float(dup_count / len(self.df) * 100) if len(self.df) > 0 else 0
        }
    
    def detect_outliers(self, column: str, method: str = 'iqr') -> int:
        if column not in self.numeric_columns: return 0
        data = self.df[column].dropna()
        if method == 'iqr':
            q1, q3 = data.quantile([0.25, 0.75])
            iqr = q3 - q1
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            return int(((data < lower) | (data > upper)).sum())
        return 0
    
    def detect_date_columns(self) -> List[str]:
        date_cols = []
        for col in self.df.columns:
            if any(kw in col.lower() for kw in ['date', 'fecha', 'time', 'timestamp', 'año', 'mes']):
                date_cols.append(col)
            elif pd.api.types.is_datetime64_any_dtype(self.df[col]):
                date_cols.append(col)
            elif self.df[col].dtype == 'object':
                sample = self.df[col].dropna().head(100)
                if len(sample) > 0:
                    try:
                        pd.to_datetime(sample, errors='raise')
                        date_cols.append(col)
                    except: pass
        return date_cols

# ============================================================================
# 📈 MÓDULO: VISUALIZATIONS
# ============================================================================
class PlotManager:
    """Gestor de visualizaciones financieras"""
    
    @staticmethod
    def histogram(series: pd.Series, title: str = "Distribución") -> go.Figure:
        fig = px.histogram(x=series.dropna(), nbins=30, title=title, labels={'x': 'Valor', 'y': 'Frecuencia'})
        mean_val = series.mean()
        fig.add_vline(x=mean_val, line_dash="dash", line_color="red", annotation_text=f"Media: {mean_val:.2f}")
        return fig
    
    @staticmethod
    def boxplot_by_category(df: pd.DataFrame, cat_col: str, num_col: str) -> go.Figure:
        return px.box(df, x=cat_col, y=num_col, title=f"{num_col} por {cat_col}", color=cat_col, points="outliers")
    
    @staticmethod
    def correlation_heatmap(df: pd.DataFrame) -> go.Figure:
        corr = df.corr(numeric_only=True)
        return px.imshow(corr, text_auto='.2f', aspect='auto', color_continuous_scale='RdBu_r', title='Matriz de Correlación')
    
    @staticmethod
    def time_series_line(df: pd.DataFrame, date_col: str, value_col: str) -> go.Figure:
        fig = px.area(df, x=date_col, y=value_col, title=f"Evolución de {value_col}", labels={date_col: 'Fecha', value_col: 'Valor'})
        if len(df) > 10:
            fig.add_trace(go.Scatter(
                x=df[date_col],
                y=df[value_col].rolling(window=min(30, len(df)//5)).mean(),
                mode='lines', name='Tendencia (media móvil)', line=dict(dash='dash', color='orange')
            ))
        return fig
    
    @staticmethod
    def bar_chart(df: pd.DataFrame, x: str, y: str, title: str = "") -> go.Figure:
        return px.bar(df, x=x, y=y, title=title, text_auto='.2s')
    
    @staticmethod
    def scatter_plot(df: pd.DataFrame, x: str, y: str, color: str = None, title: str = "") -> go.Figure:
        return px.scatter(df, x=x, y=y, color=color, title=title, trendline='ols' if not color else None)

# ============================================================================
# 🎨 MÓDULO: UI COMPONENTS
# ============================================================================
def render_header():
    st.title("📊 Analizador de Datos Financieros")
    st.markdown("""
    > **Importa tu CSV + Esquema desde Jupyter → Matching de columnas → Análisis financiero completo**
    """)
    st.markdown("---")

def render_sidebar():
    st.sidebar.header("🔧 Panel de Control")
    step = st.sidebar.radio(
        "Selecciona una etapa:",
        ["📁 1. Importar Datos", "🔗 2. Matching de Columnas", "📈 3. Análisis Financiero", "💾 4. Exportar Resultados"]
    )
    st.sidebar.markdown("---")
    st.sidebar.markdown("**🔗 Enlaces útiles:**\n- [📚 Documentación](https://github.com)\n- [🐛 Reportar issue](https://github.com/issues)")
    return step

def render_footer():
    st.markdown("---")
    st.caption(f"📊 Analizador Financiero v1.0 | Desarrollado con Streamlit + Pandas + Plotly | {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# ============================================================================
# 📁 ETAPA 1: IMPORTAR DATOS
# ============================================================================
def stage_import_data():
    st.header("📁 Importar Archivos")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📄 Archivo CSV con Datos")
        csv_file = st.file_uploader("Sube tu archivo CSV", type=['csv', 'xlsx', 'xls'], key="csv_uploader")
        if csv_file:
            try:
                st.session_state.data = load_csv(csv_file)
                st.success(f"✅ Datos cargados: {st.session_state.data.shape[0]} filas × {st.session_state.data.shape[1]} columnas")
                with st.expander("👁️ Vista previa de datos"):
                    st.dataframe(st.session_state.data.head())
            except Exception as e:
                st.error(f"❌ Error al cargar CSV: {str(e)}")
    
    with col2:
        st.subheader("📓 Esquema desde Jupyter Notebook")
        schema_file = st.file_uploader("Sube notebook (.ipynb) o archivo JSON con esquema", type=['ipynb', 'json'], key="schema_uploader")
        if schema_file:
            try:
                st.session_state.schema = load_schema_from_notebook(schema_file)
                st.success(f"✅ Esquema cargado: {len(st.session_state.schema)} variables definidas")
                with st.expander("👁️ Ver esquema"):
                    st.json(st.session_state.schema, expanded=False)
            except Exception as e:
                st.error(f"❌ Error al cargar esquema: {str(e)}")
    
    if st.session_state.data is not None and st.session_state.schema is not None:
        st.info("💡 Ambos archivos cargados. Continúa con el **Matching de Columnas** en el menú lateral.")

# ============================================================================
# 🔗 ETAPA 2: MATCHING DE COLUMNAS
# ============================================================================
def stage_column_matching():
    st.header("🔗 Matching de Columnas")
    
    if st.session_state.data is None or st.session_state.schema is None:
        st.warning("⚠️ Primero importa ambos archivos en la etapa 1.")
        return
    
    matcher = ColumnMatcher(st.session_state.data.columns.tolist(), st.session_state.schema)
    mapping = render_matcher_interface(matcher)
    st.session_state.mapping = mapping
    
    if mapping and st.button("✅ Validar y Aplicar Mapping", type="primary"):
        try:
            validated_data = validate_data_with_schema(st.session_state.data, mapping, st.session_state.schema)
            st.session_state.analyzed_data = validated_data
            st.success("✅ Mapping aplicado correctamente. ¡Listo para analizar!")
            with st.expander("📊 Resumen de validación"):
                col1, col2, col3 = st.columns(3)
                col1.metric("Filas totales", len(validated_data))
                col2.metric("Columnas mapeadas", len(mapping))
                col3.metric("Variables numéricas", validated_data.select_dtypes(include=[np.number]).shape[1])
        except Exception as e:
            st.error(f"❌ Error en validación: {str(e)}")

# ============================================================================
# 📈 ETAPA 3: ANÁLISIS FINANCIERO
# ============================================================================
def stage_financial_analysis():
    st.header("📈 Análisis Financiero")
    
    if st.session_state.analyzed_data is None:
        st.warning("⚠️ Primero completa el matching de columnas.")
        return
    
    analyzer = FinancialAnalyzer(st.session_state.analyzed_data)
    plots = PlotManager()
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Resumen General", "🔢 Estadísticas", "🔍 Calidad de Datos", "📊 Visualizaciones", "🔄 Series Temporales"
    ])
    
    with tab1:
        st.subheader("📋 Resumen del Dataset")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Filas", analyzer.n_rows)
        col2.metric("Columnas", analyzer.n_cols)
        col3.metric("Memoria (MB)", f"{analyzer.memory_usage:.2f}")
        col4.metric("Tipos de dato", f"{len(analyzer.dtypes_summary)}")
        st.markdown("### 📊 Distribución de Tipos de Variable")
        st.bar_chart(analyzer.dtypes_summary)
        with st.expander("👁️ Ver tipos de dato por columna"):
            st.dataframe(analyzer.dtypes_detail)
    
    with tab2:
        st.subheader("🔢 Estadísticas Descriptivas")
        numeric_cols = st.multiselect("Selecciona columnas para analizar:", analyzer.numeric_columns, 
                                     default=analyzer.numeric_columns[:min(5, len(analyzer.numeric_columns))])
        if numeric_cols:
            stats_df = analyzer.get_descriptive_stats(numeric_cols)
            st.dataframe(stats_df.style.format("{:.2f}"))
            st.markdown("### 🎯 Métricas Clave")
            for col in numeric_cols[:3]:
                with st.container():
                    st.markdown(f"**{col}**")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Media", f"{stats_df.loc[col, 'mean']:.2f}" if 'mean' in stats_df.columns else "N/A")
                    c2.metric("Mediana", f"{stats_df.loc[col, '50%']:.2f}" if '50%' in stats_df.columns else "N/A")
                    c3.metric("Desv. Est.", f"{stats_df.loc[col, 'std']:.2f}" if 'std' in stats_df.columns else "N/A")
                    c4.metric("Rango", f"{stats_df.loc[col, 'max'] - stats_df.loc[col, 'min']:.2f}" if 'max' in stats_df.columns else "N/A")
                    st.divider()
    
    with tab3:
        st.subheader("🔍 Calidad de Datos")
        missing_info = analyzer.get_missing_values()
        if not missing_info.empty:
            st.markdown("### ❌ Valores Nulos")
            st.bar_chart(missing_info['missing_pct'].sort_values(ascending=False))
            st.dataframe(missing_info.style.format({'missing_count': '{:.0f}', 'missing_pct': '{:.2f}%'}))
        else:
            st.success("✅ No se encontraron valores nulos")
        col1, col2 = st.columns(2)
        with col1:
            duplicates = analyzer.get_duplicates_info()
            st.metric("Filas duplicadas", duplicates['count'])
            if duplicates['percentage'] > 0:
                st.warning(f"⚠️ {duplicates['percentage']:.2f}% de duplicados")
        with col2:
            if analyzer.numeric_columns:
                outliers = analyzer.detect_outliers(analyzer.numeric_columns[0])
                st.metric("Outliers detectados", outliers)
    
    with tab4:
        st.subheader("📊 Visualizaciones Interactivas")
        if analyzer.numeric_columns:
            col = st.selectbox("Selecciona columna para histograma:", analyzer.numeric_columns)
            fig = plots.histogram(st.session_state.analyzed_data[col], title=f"Distribución: {col}")
            st.plotly_chart(fig, use_container_width=True)
            if len(analyzer.numeric_columns) >= 2:
                st.markdown("### 🔗 Matriz de Correlación")
                corr_cols = st.multiselect("Columnas para correlación:", analyzer.numeric_columns, 
                                          default=analyzer.numeric_columns[:min(10, len(analyzer.numeric_columns))])
                if corr_cols and len(corr_cols) >= 2:
                    fig = plots.correlation_heatmap(st.session_state.analyzed_data[corr_cols])
                    st.plotly_chart(fig, use_container_width=True)
        if analyzer.categorical_columns and analyzer.numeric_columns:
            st.markdown("### 📦 Boxplots por Categoría")
            cat_col = st.selectbox("Columna categórica:", analyzer.categorical_columns, key="box_cat")
            num_col = st.selectbox("Variable numérica:", analyzer.numeric_columns, key="box_num")
            fig = plots.boxplot_by_category(st.session_state.analyzed_data, cat_col, num_col)
            st.plotly_chart(fig, use_container_width=True)
    
    with tab5:
        st.subheader("🔄 Análisis de Series Temporales")
        date_cols = analyzer.detect_date_columns()
        if date_cols:
            date_col = st.selectbox("Columna de fecha:", date_cols)
            value_col = st.selectbox("Variable a graficar:", analyzer.numeric_columns)
            df_temp = st.session_state.analyzed_data.copy()
            df_temp[date_col] = pd.to_datetime(df_temp[date_col])
            df_temp = df_temp.sort_values(date_col)
            fig = plots.time_series_line(df_temp, date_col, value_col)
            st.plotly_chart(fig, use_container_width=True)
            period = st.selectbox("Agrupar por:", ['Día', 'Semana', 'Mes', 'Trimestre', 'Año'])
            freq_map = {'Día': 'D', 'Semana': 'W', 'Mes': 'M', 'Trimestre': 'Q', 'Año': 'Y'}
            df_grouped = df_temp.set_index(date_col)[value_col].resample(freq_map[period]).mean()
            st.line_chart(df_grouped)
        else:
            st.info("ℹ️ No se detectaron columnas de fecha. Para análisis temporal, mapea una columna como 'date' en el esquema.")

# ============================================================================
# 💾 ETAPA 4: EXPORTAR RESULTADOS
# ============================================================================
def stage_export_results():
    st.header("💾 Exportar Resultados")
    
    if st.session_state.analyzed_data is None:
        st.warning("⚠️ Primero realiza un análisis en la etapa 3.")
        return
    
    st.markdown("### 📥 Formatos de Exportación")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📊 Descargar CSV Procesado"):
            csv = st.session_state.analyzed_data.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(label="📥 Click para descargar", data=csv, file_name="datos_financieros_procesados.csv", mime="text/csv")
        if st.button("📈 Descargar Resumen Estadístico"):
            analyzer = FinancialAnalyzer(st.session_state.analyzed_data)
            stats = analyzer.get_descriptive_stats(analyzer.numeric_columns)
            csv_stats = stats.to_csv(encoding='utf-8-sig')
            st.download_button(label="📥 Descargar estadísticas", data=csv_stats, file_name="resumen_estadistico.csv", mime="text/csv")
    
    with col2:
        if st.button("📋 Descargar Reporte JSON"):
            analyzer = FinancialAnalyzer(st.session_state.analyzed_data)
            report = {
                'metadata': {'filas': analyzer.n_rows, 'columnas': analyzer.n_cols, 'fecha_generacion': pd.Timestamp.now().isoformat()},
                'estadisticas': analyzer.get_descriptive_stats(analyzer.numeric_columns).to_dict() if analyzer.numeric_columns else {},
                'calidad_datos': analyzer.get_missing_values().to_dict() if not analyzer.get_missing_values().empty else {}
            }
            json_report = json.dumps(report, indent=2, default=str)
            st.download_button(label="📥 Descargar JSON", data=json_report, file_name="reporte_analisis.json", mime="application/json")
        if st.button("🔗 Descargar Mapping de Columnas"):
            mapping_json = json.dumps(st.session_state.mapping, indent=2, ensure_ascii=False)
            st.download_button(label="📥 Descargar mapping", data=mapping_json, file_name="column_mapping.json", mime="application/json")

# ============================================================================
# 🚀 FUNCIÓN PRINCIPAL
# ============================================================================
def main():
    # Inicializar estado de sesión
    if 'data' not in st.session_state: st.session_state.data = None
    if 'schema' not in st.session_state: st.session_state.schema = None
    if 'mapping' not in st.session_state: st.session_state.mapping = {}
    if 'analyzed_data' not in st.session_state: st.session_state.analyzed_data = None
    
    render_header()
    step = render_sidebar()
    
    if step == "📁 1. Importar Datos":
        stage_import_data()
    elif step == "🔗 2. Matching de Columnas":
        stage_column_matching()
    elif step == "📈 3. Análisis Financiero":
        stage_financial_analysis()
    elif step == "💾 4. Exportar Resultados":
        stage_export_results()
    
    render_footer()

if __name__ == "__main__":
    main()
