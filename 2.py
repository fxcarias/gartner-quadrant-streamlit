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
    Valores bajos (amarillo) = más transparente (0.5)
    Valores altos (rojo) = más opaco (0.95)
    """
    if max_val == min_val:
        return 0.75  # Opacidad media
    
    # Normalizar el valor entre 0 y 1
    normalized = (value - min_val) / (max_val - min_val)
    
    # Mapear a opacidad entre 0.5 (bajo) y 0.95 (alto)
    opacity = 0.5 + (normalized * 0.45)
    
    return opacity

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
    
    base = df_raw[base_cols].copy()
    
    # Calcular Radius_px basado en la columna de tamaño o usar valor fijo/existente
    if size_col and size_col in base.columns:
        # Escalar valores de la columna de tamaño a radios entre 10 y 50 pixels
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
            st.sidebar.caption("💧 Transparencia: Bajo (50%) → Alto (95%)")
        else:
            base["Radius_px"] = 25.0
            st.sidebar.info(f"Todos los valores de {size_col} son iguales")
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
        
        base = df_raw[base_cols].rename(columns={x_col:"X", y_col:"Y"}).copy()
        
        # Calcular Radius_px basado en la columna de tamaño o usar valor fijo
        if size_col and size_col in base.columns:
            # Escalar valores de la columna de tamaño a radios entre 10 y 50 pixels
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
                    <div style="flex: 1; height: 20px; background: linear-gradient(to right, #00b300, #80ff00, #ffff00, #ff9900, #ff0000, #cc0000); border-radius: 3px;"></div>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 10px; color: #666;">
                    <span>🟢 Bajo</span>
                    <span>🟡 Medio</span>
                    <span>🔴 Alto</span>
                </div>
                """
                st.sidebar.markdown(heatmap_html, unsafe_allow_html=True)
                st.sidebar.caption("Los colores representan el valor de " + size_col)
            else:
                base["Radius_px"] = 25.0
                st.sidebar.info(f"Todos los valores de {size_col} son iguales")
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
        
        base = _df[base_cols].dropna().copy().rename(columns={label_col:"Label", x_col:"X", y_col:"Y"})
        
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
                    <div style="flex: 1; height: 20px; background: linear-gradient(to right, #00b300, #80ff00, #ffff00, #ff9900, #ff0000, #cc0000); border-radius: 3px;"></div>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 10px; color: #666;">
                    <span>🟢 Bajo</span>
                    <span>🟡 Medio</span>
                    <span>🔴 Alto</span>
                </div>
                """
                st.sidebar.markdown(heatmap_html, unsafe_allow_html=True)
                st.sidebar.caption("Los colores representan el valor de " + size_col)
            else:
                base["Radius_px"] = 25.0
                st.sidebar.info(f"Todos los valores de {size_col} son iguales")
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
            st.sidebar.caption("💧 Transparencia: Bajo (50%) → Alto (95%)")
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
sig = hashlib.md5(base.to_csv(index=False).encode("utf-8")).hexdigest()
if st.session_state.get("__last_source_sig__") != sig:
    st.session_state.pop("data", None)
    st.session_state["__last_source_sig__"] = sig

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
        _init_state_from_base(base)
    return st.session_state.data

# Inicializa ya
_ = get_state_df()

# ---------------------------- Visualización con Plotly ----------------------------
st.title("Fuxion TI")

working = get_state_df().copy()

# Lista de todos los proyectos para el combobox
all_projects = working['Label'].tolist()

# Crear layout de dos columnas: gráfico a la izquierda, controles a la derecha
main_col, control_col = st.columns([2.5, 1])

# ---------------------------- Columna de Controles (derecha) ----------------------------
with control_col:
    # Combobox para seleccionar proyecto
    selected_project = st.selectbox(
        "📋 Proyecto",
        options=["Selecciona un proyecto..."] + all_projects,
        key="project_selector"
    )
    
    # Obtener los datos del proyecto seleccionado
    if selected_project != "Selecciona un proyecto...":
        selected_row = _df[_df['Label'] == selected_project]
    else:
        selected_row = pd.DataFrame()
    
    st.markdown("---")
    
    # Definir las métricas que siempre deben mostrarse
    metrics = ["Costo", "Impacto", "Esfuerzo", "Variable"]
    
    # Mostrar tarjetas de métricas en 2 columnas (2x2)
    for row_idx in range(2):  # 2 filas
        metric_cols = st.columns(2)  # 2 columnas
        for col_idx in range(2):  # 2 métricas por fila
            idx = row_idx * 2 + col_idx
            if idx < len(metrics):
                metric = metrics[idx]
                with metric_cols[col_idx]:
                    # Obtener valor o mostrar "--"
                    if not selected_row.empty and metric in selected_row.columns:
                        val = selected_row[metric].values[0]
                        if metric == "Costo":
                            display_val = f"{val:.0f}"
                        else:
                            display_val = f"{val:.2f}"
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
    
    st.markdown("---")
    st.markdown("**Ajustar Valores:**")
    
    # Determinar si hay proyecto seleccionado
    is_project_selected = selected_project != "Selecciona un proyecto..."
    
    # Obtener valores actuales (o valores por defecto si no hay selección)
    if is_project_selected:
        current_x = working.loc[working['Label'] == selected_project, 'X'].values[0]
        current_y = working.loc[working['Label'] == selected_project, 'Y'].values[0]
        current_cost = _df.loc[_df['Label'] == selected_project, 'Costo'].values[0] if 'Costo' in _df.columns else 0
    else:
        current_x = 0.0
        current_y = 0.0
        current_cost = 0.0
    
    # Determinar rango del slider de costo basado en los datos
    if 'Costo' in _df.columns:
        min_cost_slider = _df['Costo'].min()
        max_cost_slider = _df['Costo'].max()
    else:
        min_cost_slider = 0
        max_cost_slider = 100
    
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
    
    new_cost = st.slider(
        "💰 Costo",
        min_value=float(min_cost_slider),
        max_value=float(max_cost_slider),
        value=float(current_cost),
        step=1.0,
        key="slider_cost",
        disabled=not is_project_selected
    )
    
    # Actualizar los valores si cambiaron (solo si hay proyecto seleccionado)
    if is_project_selected:
        if new_x != current_x or new_y != current_y:
            # Actualizar working DataFrame (para la visualización)
            working.loc[working['Label'] == selected_project, 'X'] = new_x
            working.loc[working['Label'] == selected_project, 'Y'] = new_y
            # Actualizar session state
            st.session_state.data.loc[st.session_state.data['Label'] == selected_project, 'X'] = new_x
            st.session_state.data.loc[st.session_state.data['Label'] == selected_project, 'Y'] = new_y
        
        if 'Costo' in _df.columns and new_cost != current_cost:
            # Actualizar _df (que contiene Costo)
            _df.loc[_df['Label'] == selected_project, 'Costo'] = new_cost
            # Recalcular Radius_px basado en el nuevo costo
            size_values = _df['Costo']
            min_val = size_values.min()
            max_val = size_values.max()
            if max_val > min_val:
                working['Radius_px'] = 10 + ((size_values - min_val) / (max_val - min_val)) * 40
                st.session_state.data['Radius_px'] = working['Radius_px']
    
    st.markdown("---")
    st.info("💡 **Tip:** Selecciona un proyecto y ajusta sus valores con los sliders")

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

    # Obtener valores reales de Costo para la leyenda
    cost_values = []
    if 'Costo' in _df.columns:
        for _, r in working.iterrows():
            val = _df.loc[_df['Label'] == r['Label'], 'Costo'].values
            if len(val) > 0:
                cost_values.append(val[0])
        min_cost = min(cost_values) if cost_values else 0
        max_cost = max(cost_values) if cost_values else 100
    else:
        min_cost = min_radius
        max_cost = max_radius

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

        # Agregar todas las columnas (excepto Label y Costo, que irá al final)
        # Excluir columnas técnicas internas
        exclude_cols = ['Label', 'Radius_px', 'Font_px', 'Width_px', 'Costo']

        for col in _df.columns:
            if col not in exclude_cols:
                val = _df.loc[_df['Label'] == r['Label'], col].values
                if len(val) > 0:
                    # Formatear según el tipo de dato
                    if col in _df.select_dtypes(include=['number']).columns:
                        hover_info.append(f"{col}: {val[0]:.2f}")
                    else:
                        hover_info.append(f"{col}: {val[0]}")

        # Agregar Costo al final si existe
        if 'Costo' in _df.columns:
            val = _df.loc[_df['Label'] == r['Label'], 'Costo'].values
            if len(val) > 0:
                hover_info.append(f"Costo: {val[0]:.2f}")

        hover_texts.append("<br>".join(hover_info))

    # Crear figura de Plotly
    fig = go.Figure()

    # Definir rangos fijos de -120 a 120
    x_abs_max = 120
    y_abs_max = 120

    # Agregar líneas de ejes en x=0 y y=0
    fig.add_shape(type="line",
        x0=-120, y0=0, x1=120, y1=0,
        line=dict(color="#9CA3AF", width=1, dash="dash"))

    fig.add_shape(type="line",
        x0=0, y0=-120, x1=0, y1=120,
        line=dict(color="#9CA3AF", width=1, dash="dash"))

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
    for idx, row in working.iterrows():
        # Calcular el valor normalizado para la colorbar
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
                bubble_opacity = opacities[idx] * 0.4  # Reducir opacidad al 40%
            else:
                bubble_opacity = opacities[idx]

        fig.add_trace(go.Scatter(
            x=[row['X']],
            y=[row['Y']],
            mode='markers',
            marker=dict(
                size=sizes[idx],
                color=[normalized_value],  # Usar valor normalizado para la colorbar
                colorscale=colorscale_values,
                cmin=0,
                cmax=1,
                opacity=bubble_opacity,
                line=dict(width=border_width, color=border_color),
                showscale=True if idx == 0 else False,  # Mostrar colorbar solo en la primera burbuja
                colorbar=dict(
                    title="Costo" if idx == 0 else None,
                    titleside="right",
                    tickmode="linear",
                    tick0=0,
                    dtick=0.25,
                    tickvals=[0, 0.25, 0.5, 0.75, 1.0],
                    ticktext=[
                        f"{min_cost:.0f}",
                        f"{min_cost + (max_cost - min_cost) * 0.25:.0f}",
                        f"{min_cost + (max_cost - min_cost) * 0.5:.0f}",
                        f"{min_cost + (max_cost - min_cost) * 0.75:.0f}",
                        f"{max_cost:.0f}"
                    ] if idx == 0 else None,
                    len=0.4,
                    thickness=15,
                    x=1.02
                ) if idx == 0 else None
            ),
            hovertemplate=hover_texts[idx] + '<extra></extra>',
            showlegend=False
        ))

    # Configurar layout
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
            dtick=20  # Marcas cada 20 unidades
        ),
        yaxis=dict(
            title=y_label,
            zeroline=False,
            gridcolor='#E5E7EB',
            range=[-120, 120],
            showgrid=True,
            dtick=20,  # Marcas cada 20 unidades
            scaleanchor="x",
            scaleratio=1
        ),
        hovermode='closest',
        margin=dict(l=60, r=60, t=40, b=60)
    )

    # Mostrar el gráfico (ocupa todo el ancho)
    st.plotly_chart(fig, use_container_width=True)

    # Información sobre controles
    st.info("💡 **Controles:** Pasa el cursor sobre las burbujas para ver detalles | Usa la rueda del mouse para zoom | Arrastra para mover la vista | Doble clic para resetear")


# ---------------------------- Exportación ----------------------------

# Exportar CSV con los datos actuales
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
st.download_button("📥 Descargar CSV", csv, file_name="cuadrante_mapa_calor.csv", mime="text/csv")
