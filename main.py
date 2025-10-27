import streamlit as st
import pandas as pd
import numpy as np
import re, hashlib
from streamlit_drawable_canvas import st_canvas

st.set_page_config(page_title="Fuxion TI", layout="wide")

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

# ---------------------------- Sidebar: carga de datos ----------------------------
st.sidebar.header("Datos")
uploaded = st.sidebar.file_uploader("Sube un CSV", type=["csv"]) 
url_csv = st.sidebar.text_input("o pega una URL CSV (Google Drive publicado o HTTP)", "")

_df = None
if url_csv.strip():
    try:
        src = normalize_drive_csv_url(url_csv)
        _df = pd.read_csv(src)
        st.sidebar.success("CSV cargado desde URL.")
    except Exception as e:
        st.sidebar.error(f"No se pudo leer la URL: {e}")

if _df is None and uploaded is not None:
    try:
        _df = pd.read_csv(uploaded)
        st.sidebar.success("CSV cargado desde archivo.")
    except Exception as e:
        st.sidebar.error(f"No se pudo leer el archivo: {e}")

if _df is None:
    _df = sample_data()

# Columnas detectadas
_text_cols_all = list(_df.select_dtypes(include=["object","string","category"]).columns)
_num_cols_all  = list(_df.select_dtypes(include=["number"]).columns)

# Detección de CSV de estado/exportado por la app
has_label = "Label" in _df.columns
has_xy = {"X","Y"}.issubset(_df.columns)
num_cols_all = [c for c in _num_cols_all if c not in {"Font_px","Width_px"}]

# Elegir base y nombres de ejes visibles
if has_label and has_xy:
    # CSV estado clásico
    df_raw = _df.copy()
    if "Font_px" not in df_raw.columns: df_raw["Font_px"] = 14.0
    if "Width_px" not in df_raw.columns:
        df_raw["Width_px"] = [max(80.0, min(400.0, 0.6*14.0*max(6, len(str(lbl)))+16)) for lbl in df_raw["Label"]]
    base = df_raw[["Label","X","Y","Font_px","Width_px"]].copy()
    x_label, y_label = "X", "Y"
    is_state_csv = True
elif has_label:
    # Intentar detectar 2 numéricas como ejes personalizados
    axis_candidates = [c for c in num_cols_all]
    if len(axis_candidates) >= 2:
        x_label, y_label = axis_candidates[0], axis_candidates[1]
        df_raw = _df.copy()
        if "Font_px" not in df_raw.columns: df_raw["Font_px"] = 14.0
        if "Width_px" not in df_raw.columns:
            df_raw["Width_px"] = [max(80.0, min(400.0, 0.6*14.0*max(6, len(str(lbl)))+16)) for lbl in df_raw["Label"]]
        base = df_raw[["Label", x_label, y_label, "Font_px", "Width_px"]].rename(columns={x_label:"X", y_label:"Y"}).copy()
        is_state_csv = True
    else:
        # Modo normal con selección manual
        if not has_label:
            _df["Label"] = _df.index.astype(str)
        if len(_text_cols_all) == 0:
            _df["Label"] = _df.index.astype(str)
            _text_cols_all = ["Label"]
        label_col = st.sidebar.selectbox("Columna etiqueta", _text_cols_all, index=0)
        x_col = st.sidebar.selectbox("Eje X", _num_cols_all, index=min(1, len(_num_cols_all)-1))
        y_col = st.sidebar.selectbox("Eje Y", _num_cols_all, index=min(0, len(_num_cols_all)-1))
        base = _df[[label_col, x_col, y_col]].dropna().copy().rename(columns={label_col:"Label", x_col:"X", y_col:"Y"})
        base["Font_px"] = 14.0
        base["Width_px"] = [max(80.0, min(400.0, 0.6*14.0*max(6, len(str(lbl)))+16)) for lbl in base["Label"]]
        x_label, y_label = x_col, y_col
        is_state_csv = False
else:
    # CSV sin Label: fallback
    _df["Label"] = _df.index.astype(str)
    _text_cols_all = list(dict.fromkeys(["Label"] + _text_cols_all))
    x_col = st.sidebar.selectbox("Eje X", _num_cols_all, index=min(1, len(_num_cols_all)-1))
    y_col = st.sidebar.selectbox("Eje Y", _num_cols_all, index=min(0, len(_num_cols_all)-1))
    base = _df[["Label", x_col, y_col]].dropna().copy().rename(columns={x_col:"X", y_col:"Y"})
    base["Font_px"] = 14.0
    base["Width_px"] = [max(80.0, min(400.0, 0.6*14.0*max(6, len(str(lbl)))+16)) for lbl in base["Label"]]
    x_label, y_label = x_col, y_col
    is_state_csv = False

# Mostrar combos informativos (si estado CSV, deshabilitados pero con valores)
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
st.sidebar.selectbox("Eje X", _x_opts, index=_x_idx, disabled=is_state_csv, key="ui_x_col")
st.sidebar.selectbox("Eje Y", _y_opts, index=_y_idx, disabled=is_state_csv, key="ui_y_col")

# ---------------------------- Estado robusto ----------------------------
sig = hashlib.md5(base.to_csv(index=False).encode("utf-8")).hexdigest()
if st.session_state.get("__last_source_sig__") != sig:
    st.session_state.pop("data", None)
    st.session_state["__last_source_sig__"] = sig
    st.session_state["__hydrated__"] = False

def _init_state_from_base(_base: pd.DataFrame) -> None:
    df_init = _base.copy()
    if "Font_px" not in df_init.columns:
        df_init["Font_px"] = 14.0
    df_init["Font_px"] = pd.to_numeric(df_init["Font_px"], errors="coerce").fillna(14.0).clip(6, 400)
    if "Width_px" not in df_init.columns:
        df_init["Width_px"] = [max(80.0, min(400.0, 0.6*14.0*max(6, len(str(lbl)))+16)) for lbl in df_init["Label"]]
    df_init["Width_px"] = pd.to_numeric(df_init["Width_px"], errors="coerce").fillna(180.0).clip(40, 2000)
    st.session_state.data = df_init

def get_state_df() -> pd.DataFrame:
    if "data" not in st.session_state:
        _init_state_from_base(base)
    return st.session_state.data

# Inicializa ya
_ = get_state_df()

# ---------------------------- Canvas ----------------------------
st.title("Fuxion TI")

CANVAS_W, CANVAS_H, PAD = 1100, 700, 60

working = get_state_df().copy()

# Ejes simétricos basados en datos
x_abs_max = float(max(abs(working["X"].min()), abs(working["X"].max()))) or 1.0
y_abs_max = float(max(abs(working["Y"].min()), abs(working["Y"].max()))) or 1.0
x_disp_min, x_disp_max = -x_abs_max, x_abs_max
y_disp_min, y_disp_max = -y_abs_max, y_abs_max

def x_to_px(x):
    return PAD + (x - x_disp_min) / (x_disp_max - x_disp_min) * (CANVAS_W - 2*PAD)

def y_to_px(y):
    # invertido (arriba mayor)
    return PAD + (y_disp_max - y) / (y_disp_max - y_disp_min) * (CANVAS_H - 2*PAD)

def px_to_x(px):
    return x_disp_min + (px - PAD) / (CANVAS_W - 2*PAD) * (x_disp_max - x_disp_min)

def px_to_y(py):
    return y_disp_max - (py - PAD) / (CANVAS_H - 2*PAD) * (y_disp_max - y_disp_min)

x0_px = x_to_px(0.0)
y0_px = y_to_px(0.0)

objects = [
    # Ejes bloqueados
    {"type": "line", "x1": PAD, "y1": y0_px, "x2": CANVAS_W - PAD, "y2": y0_px,
     "stroke": "#9CA3AF", "strokeWidth": 1, "strokeDashArray": [6,4],
     "selectable": False, "evented": False, "hoverCursor": "default"},
    {"type": "line", "x1": x0_px, "y1": PAD, "x2": x0_px, "y2": CANVAS_H - PAD,
     "stroke": "#9CA3AF", "strokeWidth": 1, "strokeDashArray": [6,4],
     "selectable": False, "evented": False, "hoverCursor": "default"},
    # Labels de ejes en ambos extremos (plomo, pequeños, fijos)
    {"type": "textbox", "left": PAD, "top": y0_px + 10, "originX": "left",  "originY": "top",    "text": str(x_label), "fontSize": 10, "fill": "#6B7280", "fontFamily": "Arial", "editable": False, "selectable": False, "evented": False},
    {"type": "textbox", "left": CANVAS_W - PAD, "top": y0_px + 10, "originX": "right", "originY": "top",    "text": str(x_label), "fontSize": 10, "fill": "#6B7280", "fontFamily": "Arial", "editable": False, "selectable": False, "evented": False},
    {"type": "textbox", "left": x0_px + 10, "top": PAD,           "originX": "left",  "originY": "top",    "text": str(y_label), "fontSize": 10, "fill": "#6B7280", "fontFamily": "Arial", "editable": False, "selectable": False, "evented": False},
    {"type": "textbox", "left": x0_px + 10, "top": CANVAS_H - PAD, "originX": "left",  "originY": "bottom", "text": str(y_label), "fontSize": 10, "fill": "#6B7280", "fontFamily": "Arial", "editable": False, "selectable": False, "evented": False},
]

# Ticks -10..10
for t in range(-10, 11):
    x_val = (t / 10.0) * x_abs_max
    x_px = x_to_px(x_val)
    objects.append({"type": "line", "x1": x_px, "y1": y0_px - 4, "x2": x_px, "y2": y0_px + 4, "stroke": "#CBD5E1", "strokeWidth": 1, "selectable": False, "evented": False})
    if t % 2 == 0:
        objects.append({"type": "textbox", "left": x_px, "top": y0_px + 14, "originX": "center", "originY": "top", "text": str(t), "fontSize": 9, "fill": "#9CA3AF", "fontFamily": "Arial", "editable": False, "selectable": False, "evented": False})
    y_val = (t / 10.0) * y_abs_max
    y_px = y_to_px(y_val)
    objects.append({"type": "line", "x1": x0_px - 4, "y1": y_px, "x2": x0_px + 4, "y2": y_px, "stroke": "#CBD5E1", "strokeWidth": 1, "selectable": False, "evented": False})
    if t % 2 == 0:
        objects.append({"type": "textbox", "left": x0_px - 8, "top": y_px, "originX": "right", "originY": "center", "text": str(t), "fontSize": 9, "fill": "#9CA3AF", "fontFamily": "Arial", "editable": False, "selectable": False, "evented": False})

# Labels de datos (solo texto) normalizados sin escalas
for i, (_, r) in enumerate(working.iterrows()):
    cx = float(x_to_px(r["X"]))
    cy = float(y_to_px(r["Y"]))
    color = PALETTE[i % len(PALETTE)]
    label = str(r["Label"]) if "Label" in r else str(i)
    font_px = float(r.get("Font_px", 14.0))
    width_px = float(r.get("Width_px", 180.0))
    objects.append({
        "type": "textbox",
        "left": cx, "top": cy,
        "originX": "center", "originY": "center",
        "text": label,
        "fontSize": font_px, "fontFamily": "Arial",
        "width": width_px,
        "fill": color,
        "editable": False, "selectable": True,
        "hasControls": True, "lockUniScaling": False, "lockScalingFlip": True,
        "splitByGrapheme": True, "textAlign": "center",
        "name": f"lbl::{label}",
        "scaleX": 1.0, "scaleY": 1.0
    })

initial_json = {"version": "5.2.4", "objects": objects}

canvas_res = st_canvas(
    fill_color="rgba(0,0,0,0)", background_color="#ffffff",
    height=CANVAS_H, width=CANVAS_W,
    drawing_mode="transform",
    initial_drawing=initial_json,
    display_toolbar=False,
    key="magic_quadrant_canvas_text"
)

# ---------------------------- Lectura del canvas y exportación ----------------------------

def _apply_canvas_to_df(canvas_json, df_state: pd.DataFrame) -> pd.DataFrame:
    """Devuelve un DF con X,Y,Font_px,Width_px tal como se ven en el lienzo."""
    df_upd = df_state.copy()
    if not canvas_json or "objects" not in canvas_json:
        return df_upd
    df_upd = df_upd.set_index("Label")
    objs = canvas_json.get("objects", [])
    obj_map = {}
    for o in objs:
        if o.get("type") != "textbox":
            continue
        name = o.get("name", "")
        txt = o.get("text", "")
        if isinstance(name, str) and name.startswith("lbl::"):
            lab = name.split("lbl::", 1)[1]
            obj_map[lab] = o
        elif isinstance(txt, str) and txt in df_upd.index and txt not in obj_map:
            obj_map[txt] = o
    for lab in df_upd.index.tolist():
        o = obj_map.get(lab)
        if not o:
            continue
        left = float(o.get("left", np.nan)); top = float(o.get("top", np.nan))
        if not np.isnan(left) and not np.isnan(top):
            df_upd.loc[lab, "X"] = px_to_x(left)
            df_upd.loc[lab, "Y"] = px_to_y(top)
        font_sz = float(o.get("fontSize", df_upd.loc[lab, "Font_px"])) if "Font_px" in df_upd.columns else float(o.get("fontSize", 14.0))
        sx = float(o.get("scaleX", 1.0) or 1.0); sy = float(o.get("scaleY", 1.0) or 1.0)
        width_obj = float(o.get("width", df_upd.loc[lab, "Width_px"])) if "Width_px" in df_upd.columns else float(o.get("width", 180.0))
        eff_font = float(np.clip(font_sz * max(sx, sy), 6.0, 400.0)); eff_font = float(np.round(eff_font, 2))
        if (sx == 1.0 and sy == 1.0) and isinstance(o.get("height"), (int, float)):
            h = float(o.get("height")); est = max(6.0, min(400.0, h / 1.2)); eff_font = max(eff_font, est)
        eff_width = float(np.clip(width_obj * sx, 40.0, 2000.0)); eff_width = float(np.round(eff_width, 2))
        df_upd.loc[lab, "Font_px"] = eff_font
        df_upd.loc[lab, "Width_px"] = eff_width
    return df_upd.reset_index()

# Normalización anti-parpadeo

def _needs_rerun(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    need_cols = ["Font_px","Width_px","X","Y"]
    if any(c not in a.columns or c not in b.columns for c in need_cols):
        return True
    a2 = a.set_index("Label")[need_cols].sort_index().round(2)
    b2 = b.set_index("Label")[need_cols].sortIndex().round(2) if hasattr(b.set_index("Label"), 'sortIndex') else b.set_index("Label")[need_cols].sort_index().round(2)
    return not a2.equals(b2)

# Construimos DF "en vivo" y control de hidratación
df_live = _apply_canvas_to_df(canvas_res.json_data if canvas_res else None, get_state_df())
if st.session_state.get("__hydrated__", False):
    if _needs_rerun(get_state_df(), df_live):
        st.session_state.data = df_live.copy()
        # Compatibility: st.rerun() in newer versions, st.experimental_rerun() in older
        if hasattr(st, 'rerun'):
            st.rerun()
        else:
            st.experimental_rerun()
else:
    st.session_state["__hydrated__"] = True

# Exportar con nombres de ejes visibles
_df_export = df_live.rename(columns={"X": x_label, "Y": y_label})
cols_export = [c for c in ["Label", x_label, y_label, "Font_px", "Width_px"] if c in _df_export.columns]
_df_export = _df_export[cols_export]

csv = _df_export.to_csv(index=False).encode("utf-8")
st.download_button("📥 Descargar CSV actualizado (estado actual)", csv, file_name="cuadrante_actualizado.csv", mime="text/csv")
