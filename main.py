import streamlit as st
import pandas as pd
import numpy as np
import re, hashlib
import plotly.graph_objects as go

st.set_page_config(page_title="Fuxion TI", layout="wide", initial_sidebar_state="collapsed")

# ---------------------------- Datos de ejemplo ----------------------------
@st.cache_data
def sample_data():
    np.random.seed(7)
    vendors = [f"Vendor {c}" for c in list("ABCDEFGHIJKLMN")]
    df = pd.DataFrame({
        "Label": vendors,
        "Ability_to_Execute": np.random.uniform(20, 100, len(vendors)),
        "Completeness_of_Vision": np.random.uniform(20, 100, len(vendors)),
    })
    return df

@st.cache_data(ttl=300)  # Cache por 5 minutos
def load_csv_from_url(url):
    """Carga un CSV desde URL con cache para evitar recargas múltiples."""
    src = normalize_drive_csv_url(url)
    return pd.read_csv(src)

# ---------------------------- Utilidades ----------------------------
def normalize_drive_csv_url(url: str) -> str:
    url = url.strip()
    if not url:
        return url
    if "docs.google.com/spreadsheets" in url and "output=csv" in url:
        return url
    m = re.search(r"/file/d/([A-Za-z0-9_-]+)", url)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    m = re.search(r"[?&]id=([A-Za-z0-9_-]+)", url)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    return url

PALETTE = [
    "#1f77b4","#ff7f0e","#2ca02c","#d62728","#9467bd","#8c564b",
    "#e377c2","#7f7f7f","#bcbd22","#17becf","#4e79a7","#f28e2b",
    "#59a14f","#e15759","#76b7b2","#edc948","#b07aa1","#ff9da6",
    "#9c755f","#bab0ab"
]

# Paleta de colores tipo mapa de calor (amarillo → naranja → rojo)
# Inspirada en mapas de calor geográficos
HEATMAP_PALETTE = [
    "#FFFF99",  # Amarillo muy claro
    "#FFFF66",  # Amarillo claro
    "#FFFF33",  # Amarillo
    "#FFFF00",  # Amarillo brillante
    "#FFEE00",  # Amarillo-naranja claro
    "#FFDD00",  # Amarillo-naranja
    "#FFCC00",  # Naranja amarillento
    "#FFAA00",  # Naranja claro
    "#FF8800",  # Naranja
    "#FF6600",  # Naranja oscuro
    "#FF4400",  # Naranja-rojo
    "#FF2200",  # Rojo-naranja
    "#FF0000",  # Rojo
    "#DD0000",  # Rojo oscuro
    "#BB0000",  # Rojo muy oscuro
]

def get_heatmap_color(value, min_val, max_val):
    """Retorna un color de la paleta heatmap basado en el valor normalizado."""
    if max_val == min_val:
        return HEATMAP_PALETTE[len(HEATMAP_PALETTE) // 2]  # Color medio
    
    # Normalizar el valor entre 0 y 1
    normalized = (value - min_val) / (max_val - min_val)
    
    # Mapear a un índice de la paleta
    index = int(normalized * (len(HEATMAP_PALETTE) - 1))
    index = max(0, min(len(HEATMAP_PALETTE) - 1, index))  # Asegurar que esté en rango
    
    return HEATMAP_PALETTE[index]

def get_heatmap_opacity(value, min_val, max_val):
    """Retorna la opacidad basada en el valor normalizado.
    Valores bajos (amarillo) = más transparente (0.3)
    Valores altos (rojo) = más opaco (0.7)
    """
    if max_val == min_val:
        return 0.5  # Opacidad media
    
    # Normalizar el valor entre 0 y 1
    normalized = (value - min_val) / (max_val - min_val)
    
    # Mapear a opacidad entre 0.3 (bajo) y 0.7 (alto)
    opacity = 0.3 + (normalized * 0.4)
    
    return opacity

def normalize_to_0_100(values):
    """Normaliza una serie de valores al rango 0-100.
    Retorna la serie normalizada y los valores min/max originales.
    """
    values = pd.Series(values)
    min_val = values.min()
    max_val = values.max()
    
    if max_val == min_val:
        # Todos los valores son iguales, retornar 50 (medio del rango)
        normalized = pd.Series([50.0] * len(values), index=values.index)
        return normalized, min_val, max_val
    
    # Normalizar a 0-100
    normalized = ((values - min_val) / (max_val - min_val)) * 100
    
    return normalized, min_val, max_val

def value_to_category(value):
    """Convierte un valor numérico a una categoría descriptiva basada en el rango -120 a 120.
    Las categorías son: Sin Valor, Muy Bajo, Bajo, Medio, Alto, Muy Alto
    """
    if pd.isna(value):
        return "--"
    
    try:
        val = float(value)
    except (ValueError, TypeError):
        return str(value)
    
    # Definir los límites de las categorías basados en el rango -120 a 120
    if val < -60:
        return "Sin Valor"
    elif val < -20:
        return "Muy Bajo"
    elif val < 20:
        return "Bajo"
    elif val < 60:
        return "Medio"
    elif val < 100:
        return "Alto"
    else:  # val >= 100
        return "Muy Alto"

# ---------------------------- Sidebar: carga de datos ----------------------------
st.sidebar.header("Datos")

# URL por defecto
DEFAULT_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT03vitsRz5kTfx8GCLjMc6j6fzclnppE7z_nZ969EiOL-9MaNcavcRRChPVl27UOHVi2n26THw1zjU/pub?gid=0&single=true&output=csv"

uploaded = st.sidebar.file_uploader("Sube un CSV", type=["csv"]) 
url_csv = st.sidebar.text_input("o pega una URL CSV (Google Drive publicado o HTTP)", DEFAULT_CSV_URL)

_df = None

# Prioridad 1: Archivo subido
if uploaded is not None:
    try:
        _df = pd.read_csv(uploaded)
        st.sidebar.success("CSV cargado desde archivo.")
    except Exception as e:
        st.sidebar.error(f"No se pudo leer el archivo: {e}")

# Prioridad 2: URL (incluyendo la URL por defecto)
if _df is None and url_csv.strip():
    try:
        _df = load_csv_from_url(url_csv)
        if url_csv == DEFAULT_CSV_URL:
            st.sidebar.success("CSV cargado desde fuente por defecto.")
        else:
            st.sidebar.success("CSV cargado desde URL.")
    except Exception as e:
        st.sidebar.error(f"No se pudo leer la URL: {e}")

# Prioridad 3: Datos de ejemplo (solo si todo falla)
if _df is None:
    _df = sample_data()
    st.sidebar.info("Usando datos de ejemplo.")

# Columnas detectadas
_text_cols_all = list(_df.select_dtypes(include=["object","string","category"]).columns)
_num_cols_all  = list(_df.select_dtypes(include=["number"]).columns)

# Detección de CSV de estado/exportado por la app
has_label = "Label" in _df.columns
has_xy = {"X","Y"}.issubset(_df.columns)
num_cols_all = [c for c in _num_cols_all if c not in {"Font_px","Width_px","Radius_px"}]

# Detectar si hay columnas numéricas para tamaño de burbuja
size_candidates = [c for c in num_cols_all if c not in {"X", "Y"}]

# Elegir base y nombres de ejes visibles
if has_label and has_xy:
    # CSV estado clásico
    df_raw = _df.copy()
    
    # Selector para columna de tamaño de burbuja (también para CSVs de estado)
    st.sidebar.subheader("Tamaño de Burbujas")
    size_col_options = ["Ninguno (tamaño fijo)"] + size_candidates
    default_size_idx = 0
    if "Costo" in size_candidates:
        default_size_idx = size_candidates.index("Costo") + 1
    
    size_col_selected = st.sidebar.selectbox("Columna para tamaño", size_col_options, index=default_size_idx, key="size_col_selector_state")
    
    # Construir base con columnas necesarias
    base_cols = ["Label", "X", "Y"]
    if size_col_selected != "Ninguno (tamaño fijo)" and size_col_selected in df_raw.columns:
        base_cols.append(size_col_selected)
        size_col = size_col_selected
    else:
        size_col = None
    
    # Guardar size_col en session_state para uso posterior
    st.session_state.size_col = size_col
    
    base = df_raw[base_cols].copy()
    
    # Calcular Radius_px basado en la columna de tamaño o usar valor fijo/existente
    if size_col and size_col in base.columns:
        # Normalizar valores a 0-100 primero
        size_values = base[size_col]
        normalized_values, min_val, max_val = normalize_to_0_100(size_values)
        
        # Escalar valores normalizados (0-100) a radios entre 10 y 50 pixels
        base["Radius_px"] = 10 + (normalized_values / 100) * 40
        
        st.sidebar.caption(f"📊 Rango original de {size_col}: {min_val:.1f} - {max_val:.1f}")
        st.sidebar.caption(f"📈 Normalizado: 0 - 100")
        st.sidebar.caption(f"🔵 Tamaño burbujas: 10px - 50px")
        
        # Leyenda del mapa de calor
        st.sidebar.markdown("---")
        st.sidebar.markdown("**🎨 Mapa de Calor:**")
        heatmap_html = """
        <div style="display: flex; align-items: center; margin: 5px 0;">
            <div style="flex: 1; height: 20px; background: linear-gradient(to right, #FFFF99, #FFFF00, #FFAA00, #FF6600, #FF0000, #BB0000); border-radius: 3px;"></div>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 10px; color: #666;">
            <span>🟡 0</span>
            <span>🟠 50</span>
            <span>🔴 100</span>
        </div>
        """
        st.sidebar.markdown(heatmap_html, unsafe_allow_html=True)
        st.sidebar.caption("Los colores representan el valor normalizado (0-100) de " + size_col)
        st.sidebar.caption("💧 Transparencia: Bajo (30%) → Alto (70%)")
    elif "Radius_px" not in base.columns:
        # Soporte para CSV antiguos con Font_px y Width_px
        if "Font_px" in df_raw.columns:
            base["Radius_px"] = df_raw["Font_px"]
        else:
            base["Radius_px"] = 20.0
    
    x_label, y_label = "X", "Y"
    is_state_csv = True
elif has_label:
    # CSV con Label pero sin X,Y: permitir selección de ejes
    axis_candidates = [c for c in num_cols_all]
    if len(axis_candidates) >= 2:
        # Auto-detectar ejes sugeridos
        default_x_idx = 0
        default_y_idx = min(1, len(axis_candidates)-1)
        
        # Selectboxes para elegir ejes
        st.sidebar.subheader("Ejes")
        label_col = st.sidebar.selectbox("Columna etiqueta", ["Label"], index=0, disabled=True, key="label_col_fixed")
        x_col = st.sidebar.selectbox("Eje X", axis_candidates, index=default_x_idx, key="x_col_selector")
        y_col = st.sidebar.selectbox("Eje Y", axis_candidates, index=default_y_idx, key="y_col_selector")
        
        # Selector para columna de tamaño de burbuja
        st.sidebar.subheader("Tamaño de Burbujas")
        size_col_options = ["Ninguno (tamaño fijo)"] + size_candidates
        # Buscar "Costo" como opción por defecto
        default_size_idx = 0
        if "Costo" in size_candidates:
            default_size_idx = size_candidates.index("Costo") + 1
        
        size_col_selected = st.sidebar.selectbox("Columna para tamaño", size_col_options, index=default_size_idx, key="size_col_selector")
        
        df_raw = _df.copy()
        
        # Construir base con columnas necesarias
        base_cols = ["Label", x_col, y_col]
        if size_col_selected != "Ninguno (tamaño fijo)" and size_col_selected in df_raw.columns:
            base_cols.append(size_col_selected)
            size_col = size_col_selected
        else:
            size_col = None
        
        # Guardar size_col en session_state para uso posterior
        st.session_state.size_col = size_col
        
        base = df_raw[base_cols].rename(columns={x_col:"X", y_col:"Y"}).copy()
        
        # Calcular Radius_px basado en la columna de tamaño o usar valor fijo
        if size_col and size_col in base.columns:
            # Normalizar valores a 0-100 primero
            size_values = base[size_col]
            normalized_values, min_val, max_val = normalize_to_0_100(size_values)
            
            # Escalar valores normalizados (0-100) a radios entre 10 y 50 pixels
            base["Radius_px"] = 10 + (normalized_values / 100) * 40
            
            st.sidebar.caption(f"📊 Rango original de {size_col}: {min_val:.1f} - {max_val:.1f}")
            st.sidebar.caption(f"📈 Normalizado: 0 - 100")
            st.sidebar.caption(f"🔵 Tamaño burbujas: 10px - 50px")
            
            # Leyenda del mapa de calor
            st.sidebar.markdown("---")
            st.sidebar.markdown("**🎨 Mapa de Calor:**")
            heatmap_html = """
            <div style="display: flex; align-items: center; margin: 5px 0;">
                <div style="flex: 1; height: 20px; background: linear-gradient(to right, #FFFF99, #FFFF00, #FFAA00, #FF6600, #FF0000, #BB0000); border-radius: 3px;"></div>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 10px; color: #666;">
                <span>🟡 0</span>
                <span>🟠 50</span>
                <span>🔴 100</span>
            </div>
            """
            st.sidebar.markdown(heatmap_html, unsafe_allow_html=True)
            st.sidebar.caption("Los colores representan el valor normalizado (0-100) de " + size_col)
            st.sidebar.caption("💧 Transparencia: Bajo (30%) → Alto (70%)")
        else:
            base["Radius_px"] = 20.0
        
        x_label, y_label = x_col, y_col
        is_state_csv = False  # No es CSV de estado, es CSV normal con selección de ejes
    else:
        # Menos de 2 columnas numéricas: mostrar error o usar selección manual
        if not has_label:
            _df["Label"] = _df.index.astype(str)
        if len(_text_cols_all) == 0:
            _df["Label"] = _df.index.astype(str)
            _text_cols_all = ["Label"]
        label_col = st.sidebar.selectbox("Columna etiqueta", _text_cols_all, index=0)
        x_col = st.sidebar.selectbox("Eje X", _num_cols_all, index=min(1, len(_num_cols_all)-1))
        y_col = st.sidebar.selectbox("Eje Y", _num_cols_all, index=min(0, len(_num_cols_all)-1))
        
        # Selector para columna de tamaño de burbuja
        st.sidebar.subheader("Tamaño de Burbujas")
        size_col_options = ["Ninguno (tamaño fijo)"] + size_candidates
        default_size_idx = 0
        if "Costo" in size_candidates:
            default_size_idx = size_candidates.index("Costo") + 1
        size_col_selected = st.sidebar.selectbox("Columna para tamaño", size_col_options, index=default_size_idx, key="size_col_selector2")
        
        base_cols = [label_col, x_col, y_col]
        if size_col_selected != "Ninguno (tamaño fijo)" and size_col_selected in _df.columns:
            base_cols.append(size_col_selected)
            size_col = size_col_selected
        else:
            size_col = None
        
        # Guardar size_col en session_state para uso posterior
        st.session_state.size_col = size_col
        
        base = _df[base_cols].dropna().copy().rename(columns={label_col:"Label", x_col:"X", y_col:"Y"})
        
        # Calcular Radius_px basado en la columna de tamaño
        if size_col and size_col in base.columns:
            # Normalizar valores a 0-100 primero
            size_values = base[size_col]
            normalized_values, min_val, max_val = normalize_to_0_100(size_values)
            
            # Escalar valores normalizados (0-100) a radios entre 10 y 50 pixels
            base["Radius_px"] = 10 + (normalized_values / 100) * 40
            
            st.sidebar.caption(f"📊 Rango original de {size_col}: {min_val:.1f} - {max_val:.1f}")
            st.sidebar.caption(f"📈 Normalizado: 0 - 100")
            st.sidebar.caption(f"🔵 Tamaño burbujas: 10px - 50px")
            
            # Leyenda del mapa de calor
            st.sidebar.markdown("---")
            st.sidebar.markdown("**🎨 Mapa de Calor:**")
            heatmap_html = """
            <div style="display: flex; align-items: center; margin: 5px 0;">
                <div style="flex: 1; height: 20px; background: linear-gradient(to right, #FFFF99, #FFFF00, #FFAA00, #FF6600, #FF0000, #BB0000); border-radius: 3px;"></div>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 10px; color: #666;">
                <span>🟡 0</span>
                <span>🟠 50</span>
                <span>🔴 100</span>
            </div>
            """
            st.sidebar.markdown(heatmap_html, unsafe_allow_html=True)
            st.sidebar.caption("Los colores representan el valor normalizado (0-100) de " + size_col)
            st.sidebar.caption("💧 Transparencia: Bajo (30%) → Alto (70%)")
        else:
            base["Radius_px"] = 20.0
        
        x_label, y_label = x_col, y_col
        is_state_csv = False
else:
    # CSV sin Label: fallback
    _df["Label"] = _df.index.astype(str)
    _text_cols_all = list(dict.fromkeys(["Label"] + _text_cols_all))
    x_col = st.sidebar.selectbox("Eje X", _num_cols_all, index=min(1, len(_num_cols_all)-1))
    y_col = st.sidebar.selectbox("Eje Y", _num_cols_all, index=min(0, len(_num_cols_all)-1))
    
    # Selector para columna de tamaño de burbuja
    st.sidebar.subheader("Tamaño de Burbujas")
    size_col_options = ["Ninguno (tamaño fijo)"] + size_candidates
    default_size_idx = 0
    if "Costo" in size_candidates:
        default_size_idx = size_candidates.index("Costo") + 1
    size_col_selected = st.sidebar.selectbox("Columna para tamaño", size_col_options, index=default_size_idx, key="size_col_selector3")
    
    base_cols = ["Label", x_col, y_col]
    if size_col_selected != "Ninguno (tamaño fijo)" and size_col_selected in _df.columns:
        base_cols.append(size_col_selected)
        size_col = size_col_selected
    else:
        size_col = None
    
    # Guardar size_col en session_state para uso posterior
    st.session_state.size_col = size_col
    
    base = _df[base_cols].dropna().copy().rename(columns={x_col:"X", y_col:"Y"})
    
    # Calcular Radius_px basado en la columna de tamaño
    if size_col and size_col in base.columns:
        size_values = base[size_col]
        min_val = size_values.min()
        max_val = size_values.max()
        if max_val > min_val:
            base["Radius_px"] = 10 + ((size_values - min_val) / (max_val - min_val)) * 40
            st.sidebar.caption(f"📊 Rango de {size_col}: {min_val:.1f} - {max_val:.1f}")
            st.sidebar.caption(f"🔵 Tamaño burbujas: 10px - 50px")
            
            # Leyenda del mapa de calor
            st.sidebar.markdown("---")
            st.sidebar.markdown("**🎨 Mapa de Calor:**")
            heatmap_html = """
            <div style="display: flex; align-items: center; margin: 5px 0;">
                <div style="flex: 1; height: 20px; background: linear-gradient(to right, #FFFF99, #FFFF00, #FFAA00, #FF6600, #FF0000, #BB0000); border-radius: 3px;"></div>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 10px; color: #666;">
                <span>🟡 Bajo</span>
                <span>🟠 Medio</span>
                <span>🔴 Alto</span>
            </div>
            """
            st.sidebar.markdown(heatmap_html, unsafe_allow_html=True)
            st.sidebar.caption("Los colores representan el valor de " + size_col)
            st.sidebar.caption("💧 Transparencia: Bajo (30%) → Alto (70%)")
        else:
            base["Radius_px"] = 25.0
            st.sidebar.info(f"Todos los valores de {size_col} son iguales")
    else:
        base["Radius_px"] = 20.0
    
    x_label, y_label = x_col, y_col
    is_state_csv = False

# Mostrar combos informativos solo para CSVs de estado (con columnas X,Y)
if is_state_csv:
    st.sidebar.subheader("Ejes")
    _label_opts = _text_cols_all if len(_text_cols_all) > 0 else ["Label"]
    try:
        _label_idx = _label_opts.index("Label")
    except ValueError:
        _label_opts = ["Label"] + _label_opts
        _label_idx = 0
    st.sidebar.selectbox("Columna etiqueta", _label_opts, index=_label_idx, disabled=True, key="ui_label_col")
    _x_opts = list(dict.fromkeys(list(_num_cols_all) + ([x_label] if x_label not in _num_cols_all else []))) or [x_label]
    _y_opts = list(dict.fromkeys(list(_num_cols_all) + ([y_label] if y_label not in _num_cols_all else []))) or [y_label]
    _x_idx = _x_opts.index(x_label) if x_label in _x_opts else 0
    _y_idx = _y_opts.index(y_label) if y_label in _y_opts else 0
    st.sidebar.selectbox("Eje X", _x_opts, index=_x_idx, disabled=True, key="ui_x_col")
    st.sidebar.selectbox("Eje Y", _y_opts, index=_y_idx, disabled=True, key="ui_y_col")

# ---------------------------- Estado robusto ----------------------------
# Guardar base original ANTES de aplicar filtros (para usar después)
base_original = base.copy()
_df_original = _df.copy()

# Calcular firma del estado basada en base original (sin filtros)
# Esto evita que el estado se resetee cuando cambia el filtro
sig = hashlib.md5(base_original.to_csv(index=False).encode("utf-8")).hexdigest()
if st.session_state.get("__last_source_sig__") != sig:
    st.session_state.pop("data", None)
    st.session_state["__last_source_sig__"] = sig

# ---------------------------- Filtro por Tamaño de Burbuja ----------------------------
def apply_filter_to_data(min_val, max_val):
    """Aplica el filtro a los datos y actualiza el estado"""
    global _df, base
    
    if size_col_for_filter and size_col_for_filter in _df_original.columns:
        # Aplicar filtro al DataFrame original
        _df_filtered = _df_original[_df_original[size_col_for_filter] >= min_val].copy()
        _df_filtered = _df_filtered[_df_filtered[size_col_for_filter] <= max_val].copy()
        
        # Si hay datos después de filtrar, aplicar el filtro
        if len(_df_filtered) > 0:
            # Actualizar _df con los datos filtrados
            _df = _df_filtered.copy()
            
            # Filtrar base usando los Labels que están en _df filtrado
            labels_in_filtered = set(_df['Label'].values)
            base = base_original[base_original['Label'].isin(labels_in_filtered)].copy()
            
            # Recalcular Radius_px si es necesario
            if size_col_for_filter in base.columns:
                size_values = base[size_col_for_filter]
                normalized_values, min_val_norm, max_val_norm = normalize_to_0_100(size_values)
                base["Radius_px"] = 10 + (normalized_values / 100) * 40
            
            # Actualizar el estado con los datos filtrados, preservando las posiciones X, Y existentes
            if "data" in st.session_state and len(base) > 0:
                # Obtener el estado actual para preservar X, Y
                state_data_current = st.session_state.data.copy()
                
                # Crear nuevo estado desde base filtrado
                state_data_new = base.copy()
                
                # Preservar las posiciones X, Y del estado actual si existen
                if 'Label' in state_data_current.columns and 'X' in state_data_current.columns and 'Y' in state_data_current.columns:
                    # Crear un diccionario con las posiciones actuales
                    positions_map = {}
                    for _, row in state_data_current.iterrows():
                        label = row['Label']
                        if label in labels_in_filtered:
                            x_val = row.get('X', 0)
                            y_val = row.get('Y', 0)
                            # Si no hay valores válidos, usar los de base
                            if pd.isna(x_val) or x_val == 0:
                                base_row = base[base['Label'] == label]
                                if len(base_row) > 0:
                                    x_val = base_row['X'].values[0]
                            if pd.isna(y_val) or y_val == 0:
                                base_row = base[base['Label'] == label]
                                if len(base_row) > 0:
                                    y_val = base_row['Y'].values[0]
                            positions_map[label] = {'X': x_val, 'Y': y_val}
                    
                    # Aplicar las posiciones preservadas
                    for label, pos in positions_map.items():
                        mask = state_data_new['Label'] == label
                        if mask.any():
                            state_data_new.loc[mask, 'X'] = pos['X']
                            state_data_new.loc[mask, 'Y'] = pos['Y']
                
                # Asegurar que Radius_px esté presente
                if "Radius_px" not in state_data_new.columns:
                    state_data_new["Radius_px"] = 20.0
                
                # Actualizar el estado solo si hay datos
                if len(state_data_new) > 0:
                    st.session_state.data = state_data_new
        else:
            # Si no hay datos después de filtrar, mantener datos originales
            _df = _df_original.copy()
            base = base_original.copy()

def apply_all_filters():
    """Aplica todos los filtros activos (tamaño y Status)"""
    global _df, base
    
    # Empezar con el DataFrame original
    _df_filtered = _df_original.copy()
    
    # Aplicar filtro por tamaño si existe
    if size_col_for_filter and size_col_for_filter in _df_original.columns and pd.api.types.is_numeric_dtype(_df_original[size_col_for_filter]):
        filter_key = "slider_filter_size"
        if filter_key in st.session_state:
            min_val, max_val = st.session_state[filter_key]
            _df_filtered = _df_filtered[_df_filtered[size_col_for_filter] >= min_val].copy()
            _df_filtered = _df_filtered[_df_filtered[size_col_for_filter] <= max_val].copy()
    
    # Aplicar filtro por Status si existe
    status_filter_key = "filter_status_values"
    if status_filter_key in st.session_state and "Status" in _df_filtered.columns:
        selected_statuses = st.session_state[status_filter_key]
        # Si está vacío, mostrar todos (no filtrar)
        if len(selected_statuses) > 0:
            all_statuses = sorted(_df_original["Status"].dropna().unique().tolist())
            # Solo filtrar si no están todos seleccionados
            if set(selected_statuses) != set(all_statuses):
                _df_filtered = _df_filtered[_df_filtered["Status"].isin(selected_statuses)].copy()
    
    # Si hay datos después de filtrar, aplicar el filtro
    if len(_df_filtered) > 0:
        # Actualizar _df con los datos filtrados
        _df = _df_filtered.copy()
        
        # Filtrar base usando los Labels que están en _df filtrado
        labels_in_filtered = set(_df['Label'].values)
        base = base_original[base_original['Label'].isin(labels_in_filtered)].copy()
        
        # Recalcular Radius_px si es necesario
        if size_col_for_filter and size_col_for_filter in base.columns:
            size_values = base[size_col_for_filter]
            normalized_values, min_val_norm, max_val_norm = normalize_to_0_100(size_values)
            base["Radius_px"] = 10 + (normalized_values / 100) * 40
        
        # Actualizar el estado con los datos filtrados, preservando las posiciones X, Y existentes
        if "data" in st.session_state and len(base) > 0:
            # Obtener el estado actual para preservar X, Y
            state_data_current = st.session_state.data.copy()
            
            # Crear nuevo estado desde base filtrado
            state_data_new = base.copy()
            
            # Preservar las posiciones X, Y del estado actual si existen
            if 'Label' in state_data_current.columns and 'X' in state_data_current.columns and 'Y' in state_data_current.columns:
                # Crear un diccionario con las posiciones actuales
                positions_map = {}
                for _, row in state_data_current.iterrows():
                    label = row['Label']
                    if label in labels_in_filtered:
                        x_val = row.get('X', 0)
                        y_val = row.get('Y', 0)
                        # Si no hay valores válidos, usar los de base
                        if pd.isna(x_val) or x_val == 0:
                            base_row = base[base['Label'] == label]
                            if len(base_row) > 0:
                                x_val = base_row['X'].values[0]
                        if pd.isna(y_val) or y_val == 0:
                            base_row = base[base['Label'] == label]
                            if len(base_row) > 0:
                                y_val = base_row['Y'].values[0]
                        positions_map[label] = {'X': x_val, 'Y': y_val}
                
                # Aplicar las posiciones preservadas
                for label, pos in positions_map.items():
                    mask = state_data_new['Label'] == label
                    if mask.any():
                        state_data_new.loc[mask, 'X'] = pos['X']
                        state_data_new.loc[mask, 'Y'] = pos['Y']
            
            # Asegurar que Radius_px esté presente
            if "Radius_px" not in state_data_new.columns:
                state_data_new["Radius_px"] = 20.0
            
            # Actualizar el estado solo si hay datos
            if len(state_data_new) > 0:
                st.session_state.data = state_data_new
    else:
        # Si no hay datos después de filtrar, mantener datos originales
        _df = _df_original.copy()
        base = base_original.copy()

# Obtener la columna de tamaño desde session_state
size_col_for_filter = st.session_state.get('size_col', None)

# Inicializar filtro si hay una columna de tamaño
if size_col_for_filter and size_col_for_filter in _df_original.columns and pd.api.types.is_numeric_dtype(_df_original[size_col_for_filter]):
    # Obtener valores min/max del DataFrame original
    col_min = float(_df_original[size_col_for_filter].min())
    col_max = float(_df_original[size_col_for_filter].max())
    
    # Usar session_state para mantener los valores del filtro
    filter_key = "slider_filter_size"
    
    # Inicializar valores por defecto si no existen
    if filter_key not in st.session_state:
        st.session_state[filter_key] = (col_min, col_max)
    
    # Obtener valores actuales del slider
    current_filter_value = st.session_state.get(filter_key, (col_min, col_max))
    
    # Asegurar que los valores estén en el rango válido
    current_min = max(col_min, min(col_max, current_filter_value[0]))
    current_max = min(col_max, max(col_min, current_filter_value[1]))
    
    # Si los valores están fuera de rango, resetearlos
    if current_min < col_min or current_max > col_max or current_min > current_max:
        current_min = col_min
        current_max = col_max
        st.session_state[filter_key] = (current_min, current_max)
    
# Inicializar filtro por Status si existe la columna
if "Status" in _df_original.columns:
    status_filter_key = "filter_status_values"
    if status_filter_key not in st.session_state:
        # Inicializar con todos los valores únicos
        all_statuses = sorted(_df_original["Status"].dropna().unique().tolist())
        st.session_state[status_filter_key] = all_statuses

# Aplicar todos los filtros inicialmente
apply_all_filters()

def _init_state_from_base(_base: pd.DataFrame) -> None:
    df_init = _base.copy()
    # Inicializar Radius_px para las burbujas
    if "Radius_px" not in df_init.columns:
        # Si existe Font_px del CSV anterior, usarlo como base para el radio
        if "Font_px" in df_init.columns:
            df_init["Radius_px"] = df_init["Font_px"]
        else:
            df_init["Radius_px"] = 20.0
    df_init["Radius_px"] = pd.to_numeric(df_init["Radius_px"], errors="coerce").fillna(20.0).clip(5, 200)
    st.session_state.data = df_init

def get_state_df() -> pd.DataFrame:
    if "data" not in st.session_state:
        # Inicializar con base_original (sin filtros)
        _init_state_from_base(base_original)
    return st.session_state.data

# Inicializa el estado con base original (antes de filtros)
_ = get_state_df()

# ---------------------------- Visualización con Plotly ----------------------------
# Reducir espacio superior con CSS personalizado
st.markdown("""
<style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
    }
    h1 {
        margin-top: 0rem;
        margin-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("Fuxion TI")

working = get_state_df().copy()

# Lista de todos los proyectos para el combobox
all_projects = working['Label'].tolist()

# Crear layout de dos columnas: gráfico a la izquierda, controles a la derecha
main_col, control_col = st.columns([2.5, 1])

# ---------------------------- Columna de Controles (derecha) ----------------------------
with control_col:
    # Label personalizado para Proyecto
    st.markdown("<p style='font-size: 18px; font-weight: bold; margin-bottom: 5px;'>Proyecto</p>", unsafe_allow_html=True)
    
    # Combobox para seleccionar proyecto
    selected_project = st.selectbox(
        "Proyecto",
        options=["Selecciona un proyecto..."] + all_projects,
        key="project_selector",
        label_visibility="collapsed"
    )
    
    # Obtener los datos del proyecto seleccionado
    if selected_project != "Selecciona un proyecto...":
        selected_row = _df[_df['Label'] == selected_project]
    else:
        selected_row = pd.DataFrame()
    
    st.markdown("---")
    
    # Obtener métricas dinámicamente desde las columnas disponibles
    # Excluir columnas técnicas y de ejes
    exclude_cols = {'Label', 'X', 'Y', 'Radius_px', 'Font_px', 'Width_px'}
    
    # Priorizar "Costo" si existe, luego las demás columnas numéricas y de texto
    available_metrics = [col for col in _df.columns if col not in exclude_cols]
    
    # Priorizar "Costo" al inicio si existe
    if 'Costo' in available_metrics:
        available_metrics.remove('Costo')
        metrics = ['Costo'] + available_metrics
    else:
        metrics = available_metrics
    
    # Si no hay métricas, no mostrar nada
    if len(metrics) > 0:
        # Calcular número de filas necesarias (2 columnas)
        num_cols_display = 2
        num_rows = (len(metrics) + num_cols_display - 1) // num_cols_display
        
        # Mostrar tarjetas de métricas en grid dinámico
        for row_idx in range(num_rows):
            metric_cols = st.columns(num_cols_display)
            for col_idx in range(num_cols_display):
                idx = row_idx * num_cols_display + col_idx
                if idx < len(metrics):
                    metric = metrics[idx]
                    with metric_cols[col_idx]:
                        # Obtener valor y convertirlo a categoría
                        if not selected_row.empty and metric in selected_row.columns:
                            val = selected_row[metric].values[0]
                            # Convertir a categoría si es numérico, sino mostrar como string
                            if pd.api.types.is_numeric_dtype(_df[metric]):
                                display_val = value_to_category(val)
                            else:
                                display_val = str(val)
                        else:
                            display_val = "--"
                        
                        st.markdown(f"""
                        <div style="
                            background: linear-gradient(135deg, rgba(255,255,255,0.95) 0%, rgba(248,250,252,0.95) 100%);
                            padding: 12px 10px;
                            border-radius: 10px;
                            text-align: center;
                            box-shadow: 0 2px 8px rgba(0,0,0,0.08), 0 1px 3px rgba(0,0,0,0.06);
                            border: 1px solid rgba(226,232,240,0.8);
                            transition: all 0.3s ease;
                            margin-bottom: 10px;
                        ">
                            <p style="
                                color: #64748b;
                                margin: 0;
                                font-size: 11px;
                                font-weight: 600;
                                text-transform: uppercase;
                                letter-spacing: 0.5px;
                            ">{metric}</p>
                            <p style="
                                color: #1e293b;
                                margin: 4px 0 0 0;
                                font-size: 18px;
                                font-weight: 700;
                            ">{display_val}</p>
                        </div>
                        """, unsafe_allow_html=True)
    
    # ---------------------------- Filtro por Tamaño ----------------------------
    if size_col_for_filter and size_col_for_filter in _df_original.columns and pd.api.types.is_numeric_dtype(_df_original[size_col_for_filter]):
        st.markdown("---")
        st.markdown("**🔍 Filtro por Tamaño:**")
        
        # Obtener valores min/max del DataFrame original
        col_min = float(_df_original[size_col_for_filter].min())
        col_max = float(_df_original[size_col_for_filter].max())
        
        # Usar session_state para mantener los valores del filtro
        filter_key = "slider_filter_size"
        
        # Obtener valores actuales del slider
        current_filter_value = st.session_state.get(filter_key, (col_min, col_max))
        
        # Asegurar que los valores estén en el rango válido
        current_min = max(col_min, min(col_max, current_filter_value[0]))
        current_max = min(col_max, max(col_min, current_filter_value[1]))
        
        # Si los valores están fuera de rango, resetearlos
        if current_min < col_min or current_max > col_max or current_min > current_max:
            current_min = col_min
            current_max = col_max
            st.session_state[filter_key] = (current_min, current_max)
        
        min_val, max_val = st.slider(
            f"Rango de {size_col_for_filter}",
            min_value=col_min,
            max_value=col_max,
            value=(current_min, current_max),
            key=filter_key
        )
        
        # Aplicar filtro cuando cambie
        if min_val != current_min or max_val != current_max:
            apply_all_filters()
    
    # ---------------------------- Filtro por Status ----------------------------
    if "Status" in _df_original.columns:
        st.markdown("---")
        st.markdown("**🔍 Filtro por Status:**")
        
        # Obtener todos los valores únicos de Status
        all_statuses = sorted(_df_original["Status"].dropna().unique().tolist())
        
        # Usar session_state para mantener los valores seleccionados
        status_filter_key = "filter_status_values"
        
        # Inicializar si no existe
        if status_filter_key not in st.session_state:
            st.session_state[status_filter_key] = all_statuses
        
        # Obtener valores actuales
        current_selected = st.session_state.get(status_filter_key, all_statuses)
        
        # Si current_selected está vacío, inicializar con todos
        if not current_selected or len(current_selected) == 0:
            current_selected = all_statuses
            # Solo modificar session_state si no existe el widget aún
            if status_filter_key not in st.session_state:
                st.session_state[status_filter_key] = all_statuses
        
        # Multiselect para seleccionar Status
        # El multiselect actualiza automáticamente st.session_state[status_filter_key]
        selected_statuses = st.multiselect(
            "Seleccionar Status",
            options=all_statuses,
            default=current_selected,
            key=status_filter_key
        )
        
        # Si no hay selección (lista vacía), tratar como "mostrar todos"
        # apply_all_filters manejará esto correctamente
        
        # Aplicar filtro cuando cambie (compara sets para ignorar orden)
        if set(selected_statuses) != set(current_selected):
            # Si se deseleccionaron todos, el multiselect guardará lista vacía en session_state
            # apply_all_filters tratará lista vacía como "mostrar todos"
            apply_all_filters()
        
        # Mostrar información solo si hay filtro activo
        if len(selected_statuses) > 0 and len(selected_statuses) < len(all_statuses):
            st.info(f"📊 Mostrando {len(_df)} de {len(_df_original)} registros")
            if st.button("🔄 Limpiar Filtro Status", key="clear_status_filter", use_container_width=True):
                # Resetear el filtro eliminando la key del session_state
                # En el próximo rerun, se inicializará con todos los valores
                if status_filter_key in st.session_state:
                    del st.session_state[status_filter_key]
                st.rerun()
    
    st.markdown("---")
    st.markdown("**Ajustar Valores:**")
    
    # Determinar si hay proyecto seleccionado
    is_project_selected = selected_project != "Selecciona un proyecto..."
    
    # Obtener la columna de tamaño desde session_state
    current_size_col = st.session_state.get('size_col', None)
    
    # Obtener valores actuales (o valores por defecto si no hay selección)
    if is_project_selected:
        current_x = working.loc[working['Label'] == selected_project, 'X'].values[0]
        current_y = working.loc[working['Label'] == selected_project, 'Y'].values[0]
        if current_size_col and current_size_col in _df.columns:
            current_size_value = _df.loc[_df['Label'] == selected_project, current_size_col].values[0]
        else:
            current_size_value = 0.0
    else:
        current_x = 0.0
        current_y = 0.0
        current_size_value = 0.0
    
    # Determinar rango del slider de tamaño basado en los datos
    if current_size_col and current_size_col in _df.columns:
        min_size_slider = _df[current_size_col].min()
        max_size_slider = _df[current_size_col].max()
        # Usar un step más pequeño si el rango es muy grande
        if max_size_slider - min_size_slider > 1000:
            step_size = (max_size_slider - min_size_slider) / 1000
        else:
            step_size = 0.01 if max_size_slider - min_size_slider < 100 else 1.0
    else:
        min_size_slider = 0
        max_size_slider = 100
        step_size = 1.0
    
    # Sliders verticales (uno debajo del otro)
    new_x = st.slider(
        f"📊 {x_label}",
        min_value=-120.0,
        max_value=120.0,
        value=float(current_x),
        step=1.0,
        key="slider_x",
        disabled=not is_project_selected
    )
    
    new_y = st.slider(
        f"📊 {y_label}",
        min_value=-120.0,
        max_value=120.0,
        value=float(current_y),
        step=1.0,
        key="slider_y",
        disabled=not is_project_selected
    )
    
    # Slider genérico para la columna de tamaño (solo si hay una columna seleccionada)
    if current_size_col and current_size_col in _df.columns:
        new_size_value = st.slider(
            f"💰 {current_size_col}",
            min_value=float(min_size_slider),
            max_value=float(max_size_slider),
            value=float(current_size_value),
            step=float(step_size),
            key="slider_size_col",
            disabled=not is_project_selected
        )
    else:
        new_size_value = current_size_value
    
    # Actualizar los valores si cambiaron (solo si hay proyecto seleccionado)
    if is_project_selected:
        if new_x != current_x or new_y != current_y:
            # Actualizar working DataFrame (para la visualización)
            working.loc[working['Label'] == selected_project, 'X'] = new_x
            working.loc[working['Label'] == selected_project, 'Y'] = new_y
            # Actualizar session state
            st.session_state.data.loc[st.session_state.data['Label'] == selected_project, 'X'] = new_x
            st.session_state.data.loc[st.session_state.data['Label'] == selected_project, 'Y'] = new_y
        
        if current_size_col and current_size_col in _df.columns and new_size_value != current_size_value:
            # Actualizar _df (que contiene la columna de tamaño)
            _df.loc[_df['Label'] == selected_project, current_size_col] = new_size_value
            # Recalcular Radius_px basado en el nuevo valor (normalizando a 0-100 primero)
            size_values = _df[current_size_col]
            normalized_values, min_val, max_val = normalize_to_0_100(size_values)
            working['Radius_px'] = 10 + (normalized_values / 100) * 40
            st.session_state.data['Radius_px'] = working['Radius_px']
    
    st.markdown("---")
    st.info("💡 **Tip:** Selecciona un proyecto y ajusta sus valores con los sliders")
    
    # Botón de descarga CSV
    st.markdown("---")
    _df_export = _df.copy()
    
    # Asegurar que Label esté primero, seguido de las columnas de ejes, luego el resto
    cols_order = ["Label"]
    if x_label in _df_export.columns and x_label != "Label":
        cols_order.append(x_label)
    if y_label in _df_export.columns and y_label != "Label" and y_label != x_label:
        cols_order.append(y_label)
    # Agregar todas las demás columnas que no están en cols_order
    for col in _df_export.columns:
        if col not in cols_order:
            cols_order.append(col)
    _df_export = _df_export[cols_order]
    
    csv = _df_export.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Descargar CSV", csv, file_name="cuadrante_mapa_calor.csv", mime="text/csv", use_container_width=True)

# ---------------------------- Columna del Gráfico (izquierda) ----------------------------
with main_col:
    # Calcular rango de radios para el mapa de calor
    radii = []
    for _, r in working.iterrows():
        radius = float(r.get("Radius_px", 20.0))
        if radius < 5:
            radius = 20.0
        radii.append(radius)

    min_radius = min(radii) if radii else 10
    max_radius = max(radii) if radii else 50

    # Obtener valores reales de la columna de tamaño para la leyenda
    size_col_for_legend = st.session_state.get('size_col', None)
    size_values_for_legend = []
    if size_col_for_legend and size_col_for_legend in _df.columns:
        for _, r in working.iterrows():
            val = _df.loc[_df['Label'] == r['Label'], size_col_for_legend].values
            if len(val) > 0:
                size_values_for_legend.append(val[0])
        min_size = min(size_values_for_legend) if size_values_for_legend else 0
        max_size = max(size_values_for_legend) if size_values_for_legend else 100
    else:
        min_size = 0
        max_size = 100

    # Preparar datos para Plotly
    colors = []
    opacities = []
    sizes = []
    hover_texts = []

    for _, r in working.iterrows():
        radius = float(r.get("Radius_px", 20.0))
        if radius < 5:
            radius = 20.0

        # Asignar color y opacidad basados en el tamaño (mapa de calor)
        color = get_heatmap_color(radius, min_radius, max_radius)
        opacity = get_heatmap_opacity(radius, min_radius, max_radius)

        colors.append(color)
        opacities.append(opacity)
        # Plotly usa el área de marker size, convertir radius a size apropiado
        sizes.append(radius * 2)  # Multiplicar por 2 para mejor visualización

        # Crear tooltip con formato personalizado
        hover_info = [f"<b>{r['Label']}</b>"]

        # Agregar todas las columnas (excepto Label y la columna de tamaño, que irá al final)
        # Excluir columnas técnicas internas
        exclude_cols = ['Label', 'Radius_px', 'Font_px', 'Width_px']
        if size_col_for_legend:
            exclude_cols.append(size_col_for_legend)

        for col in _df.columns:
            if col not in exclude_cols:
                val = _df.loc[_df['Label'] == r['Label'], col].values
                if len(val) > 0:
                    # Formatear según el tipo de dato
                    if col in _df.select_dtypes(include=['number']).columns:
                        hover_info.append(f"{col}: {val[0]:.2f}")
                    else:
                        hover_info.append(f"{col}: {val[0]}")

        # Agregar la columna de tamaño al final si existe
        if size_col_for_legend and size_col_for_legend in _df.columns:
            val = _df.loc[_df['Label'] == r['Label'], size_col_for_legend].values
            if len(val) > 0:
                # Formatear según si es numérico o no
                if pd.api.types.is_numeric_dtype(_df[size_col_for_legend]):
                    hover_info.append(f"{size_col_for_legend}: {val[0]:.2f}")
                else:
                    hover_info.append(f"{size_col_for_legend}: {val[0]}")

        hover_texts.append("<br>".join(hover_info))

    # Crear figura de Plotly
    fig = go.Figure()

    # Definir rangos fijos de -120 a 120
    x_abs_max = 120
    y_abs_max = 120
    
    # Dividir el espacio en categorías descriptivas (6 categorías)
    # Para negativos: Sin valor (-120 a -60), Muy bajo (-60 a 0)
    # Para positivos: Bajo (0 a 40), Medio (40 a 80), Alto (80 a 120)
    
    # Posiciones de las categorías (6 categorías) - ajustadas para rango -120 a 120
    category_positions = [-100, -60, -20, 20, 60, 100]
    # Etiquetas descriptivas: 3 negativas y 3 positivas
    category_labels = ["Sin Valor", "Muy Bajo", "Bajo", "Medio", "Alto", "Muy Alto"]
    
    # Agregar líneas divisorias entre categorías
    # Línea principal en x=0 y y=0 (división entre negativos y positivos)
    fig.add_shape(type="line",
        x0=0, y0=-120, x1=0, y1=120,
        line=dict(color="#9CA3AF", width=1.5, dash="dash"),
        layer="below"
    )
    
    fig.add_shape(type="line",
        x0=-120, y0=0, x1=120, y1=0,
        line=dict(color="#9CA3AF", width=1.5, dash="dash"),
        layer="below"
    )
    
    # Líneas divisorias secundarias en los puntos de división
    for divider in [-80, -40, 40, 80]:
        # Línea vertical
        fig.add_shape(type="line",
            x0=divider, y0=-120, x1=divider, y1=120,
            line=dict(color="#D1D5DB", width=0.8, dash="dot"),
            layer="below"
        )
        # Línea horizontal
        fig.add_shape(type="line",
            x0=-120, y0=divider, x1=120, y1=divider,
            line=dict(color="#D1D5DB", width=0.8, dash="dot"),
            layer="below"
        )

    # Crear una colorscale personalizada para la leyenda
    colorscale_values = [
        [0.0, "#FFFF99"],   # Amarillo muy claro
        [0.2, "#FFFF00"],   # Amarillo brillante
        [0.4, "#FFAA00"],   # Naranja claro
        [0.6, "#FF6600"],   # Naranja oscuro
        [0.8, "#FF0000"],   # Rojo
        [1.0, "#BB0000"],   # Rojo muy oscuro
    ]

    # Agregar las burbujas con colorscale
    # Usar enumerate para obtener índice posicional en lugar del índice del DataFrame
    for list_idx, (df_idx, row) in enumerate(working.iterrows()):
        # Calcular el valor normalizado para la colorbar basado en los valores originales de la columna de tamaño
        if size_col_for_legend and size_col_for_legend in _df.columns:
            # Obtener el valor original de la columna de tamaño
            size_val = _df.loc[_df['Label'] == row['Label'], size_col_for_legend].values
            if len(size_val) > 0:
                original_value = size_val[0]
                # Normalizar entre min_size y max_size para el colorbar (0-1)
                normalized_value = (original_value - min_size) / (max_size - min_size) if max_size > min_size else 0.5
                normalized_value = max(0, min(1, normalized_value))  # Asegurar que esté en rango 0-1
            else:
                normalized_value = 0.5
        else:
            # Si no hay columna de tamaño, usar el radius
            radius = float(row.get("Radius_px", 20.0))
            if radius < 5:
                radius = 20.0
            normalized_value = (radius - min_radius) / (max_radius - min_radius) if max_radius > min_radius else 0.5

        # Verificar si esta burbuja es la seleccionada
        is_selected = (selected_project != "Selecciona un proyecto..." and row['Label'] == selected_project)

        # Configurar el borde y opacidad según si está seleccionada
        if is_selected:
            border_width = 4
            border_color = '#1e3a5f'  # Azul oscuro para destacar
            bubble_opacity = 1.0  # Opacidad completa
        else:
            border_width = 0
            border_color = '#ffffff'
            # Si hay una selección, hacer las demás burbujas más transparentes
            if selected_project != "Selecciona un proyecto...":
                # Usar list_idx en lugar de idx para acceder a las listas
                bubble_opacity = opacities[list_idx] * 0.4 if list_idx < len(opacities) else 0.5  # Reducir opacidad al 40%
            else:
                bubble_opacity = opacities[list_idx] if list_idx < len(opacities) else 0.5

        fig.add_trace(go.Scatter(
            x=[row['X']],
            y=[row['Y']],
            mode='markers',
            marker=dict(
                size=sizes[list_idx] if list_idx < len(sizes) else 40,
                color=[normalized_value],  # Usar valor normalizado para la colorbar
                colorscale=colorscale_values,
                cmin=0,
                cmax=1,
                opacity=bubble_opacity,
                line=dict(width=border_width, color=border_color),
                showscale=True if list_idx == 0 else False,  # Mostrar colorbar solo en la primera burbuja
                colorbar=dict(
                    title=(size_col_for_legend if size_col_for_legend else "Tamaño") if list_idx == 0 else None,
                    titleside="right",
                    tickmode="linear",
                    tick0=0,
                    dtick=0.25,
                    tickvals=[0, 0.25, 0.5, 0.75, 1.0],
                    ticktext=[
                        f"{min_size:.2f}",
                        f"{min_size + (max_size - min_size) * 0.25:.2f}",
                        f"{min_size + (max_size - min_size) * 0.5:.2f}",
                        f"{min_size + (max_size - min_size) * 0.75:.2f}",
                        f"{max_size:.2f}"
                    ] if list_idx == 0 else None,
                    len=0.4,
                    thickness=15,
                    x=1.02
                ) if list_idx == 0 else None
            ),
            hovertemplate=hover_texts[list_idx] + '<extra></extra>' if list_idx < len(hover_texts) else '<extra></extra>',
            showlegend=False
        ))

    # Configurar layout con categorías descriptivas
    fig.update_layout(
        width=1100,
        height=1100,  # Hacer el gráfico cuadrado para mantener la proporción 1:1
        plot_bgcolor='white',
        xaxis=dict(
            title=x_label,
            zeroline=False,
            gridcolor='#E5E7EB',
            range=[-120, 120],
            showgrid=True,
            tickmode="array",
            tickvals=category_positions,  # Posiciones de las categorías
            ticktext=category_labels,  # Etiquetas descriptivas
            titlefont=dict(size=14),
            side="bottom",  # Título en la parte inferior
            tickfont=dict(size=11)
        ),
        yaxis=dict(
            title=y_label,
            zeroline=False,
            gridcolor='#E5E7EB',
            range=[-120, 120],
            showgrid=True,
            tickmode="array",
            tickvals=category_positions,  # Posiciones de las categorías
            ticktext=category_labels,  # Etiquetas descriptivas
            scaleanchor="x",
            scaleratio=1,
            tickfont=dict(size=11)
        ),
        hovermode='closest',
        margin=dict(l=60, r=60, t=40, b=60)
    )

    # Mostrar el gráfico (ocupa todo el ancho)
    st.plotly_chart(fig, use_container_width=True)

    # Información sobre controles
    st.info("💡 **Controles:** Pasa el cursor sobre las burbujas para ver detalles | Usa la rueda del mouse para zoom | Arrastra para mover la vista | Doble clic para resetear")
