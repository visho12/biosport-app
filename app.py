# =====================================================
# BIO SPORT PRO TRAINER v3.0 - MASTER DEFINITIVO
# Todo integrado en 1 archivo (Links seguros + Anti-Error 429)
# =====================================================
import streamlit as st

# set_page_config DEBE ser siempre la primera llamada de Streamlit
st.set_page_config(page_title="Bio Sport Pro", layout="wide", page_icon="⚡")

import os
import json
import time
import math
import io
import hmac
import base64
import urllib.parse
import hashlib
from datetime import date, datetime, timedelta
import pytz
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- IA GEMINI ---
import google.generativeai as genai
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    _mv = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
    modelo_dante = genai.GenerativeModel(_mv[0]) if _mv else None
except Exception:
    modelo_dante = None

# --- PDF (ReportLab) ---
try:
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.colors import HexColor
    from reportlab.lib import colors
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

# --- EXCEL (OpenPyXL) ---
try:
    import openpyxl
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False

# =====================================================
# HORA DE CHILE Y HELPERS
# =====================================================
ZONA_CHILE = pytz.timezone("America/Santiago")

def hoy_chile() -> date:
    try:
        return datetime.now(ZONA_CHILE).date()
    except Exception:
        return date.today()

def fstr(d): 
    return d.strftime("%d/%m/%Y")

# =====================================================
# SEGURIDAD: ENLACES FIRMADOS CON HMAC (WhatsApp)
# =====================================================
def _secreto_link() -> bytes:
    try:
        return str(st.secrets["LINK_SECRET"]).encode()
    except Exception:
        # Fallback de seguridad por si no lo agregas en Secrets inmediatamente
        return b"bio-sport-secret-key-firmas-2026"

def firmar_link(entrenador: str, atleta: str) -> str:
    msg = f"{entrenador}|{atleta}".encode()
    sig = hmac.new(_secreto_link(), msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode()[:32]

def verificar_link(entrenador: str, atleta: str, sig: str) -> bool:
    if not sig: 
        return False
    return hmac.compare_digest(firmar_link(entrenador, atleta), sig)

def construir_link(base: str, entrenador: str, atleta: str) -> str:
    q = urllib.parse.urlencode({
        "entrenador": entrenador,
        "atleta": atleta,
        "sig": firmar_link(entrenador, atleta),
    })
    return f"{base.rstrip('/')}/?{q}"

# =====================================================
# ESTILOS CSS
# =====================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@400;600&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',sans-serif}
h1,h2,h3{font-family:'Bebas Neue',sans-serif;letter-spacing:2px}
.stButton>button{border-radius:4px;font-weight:600;transition:all .2s}
.stButton>button:hover{transform:translateY(-1px);box-shadow:0 4px 15px rgba(57,255,20,.3)}
.abox{padding:12px 16px;border-radius:6px;margin:8px 0;font-size:.9rem}
.ok  {background:#0d2b0d;border-left:3px solid #39FF14;color:#39FF14}
.warn{background:#2b2200;border-left:3px solid #FFD700;color:#FFD700}
.err {background:#2b0000;border-left:3px solid #FF4B4B;color:#FF4B4B}
.inf {background:#001a2b;border-left:3px solid #00BFFF;color:#00BFFF}
.live-card{background:linear-gradient(135deg,#1a1a1a,#2d2d2d);border:2px solid #39FF14;
           border-radius:12px;padding:24px;text-align:center;margin-bottom:16px}
.live-title{font-family:'Bebas Neue',sans-serif;font-size:2.6rem;color:#39FF14;letter-spacing:3px}
.adh-bar{height:12px;border-radius:6px;background:#2d2d2d;overflow:hidden;margin:4px 0}
.dia-card {
    background: linear-gradient(135deg,#1a1a1a,#222);
    border: 1px solid #333; border-radius: 10px;
    padding: 14px 16px; margin-bottom: 10px; transition: border-color .2s;
}
.dia-card:hover { border-color: #555; }
.dia-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.dia-nombre { font-family: 'Bebas Neue', sans-serif; font-size: 1.2rem; letter-spacing: 2px; color: #fff; }
.dia-badge { font-size: .75rem; font-weight: 700; padding: 3px 10px; border-radius: 20px; text-transform: uppercase; letter-spacing: 1px; }
.badge-descanso { background:#1a1a1a; color:#555; border:1px solid #333; }
.badge-pierna   { background:#1a0d2e; color:#9b59b6; border:1px solid #9b59b6; }
.badge-pecho    { background:#0d1f2e; color:#3498db; border:1px solid #3498db; }
.badge-espalda  { background:#0d2e1a; color:#2ecc71; border:1px solid #2ecc71; }
.badge-gluteo   { background:#2e1a0d; color:#e67e22; border:1px solid #e67e22; }
.badge-full     { background:#2e0d0d; color:#e74c3c; border:1px solid #e74c3c; }
.badge-torso    { background:#0d2e2e; color:#1abc9c; border:1px solid #1abc9c; }
.badge-brazo    { background:#2e2e0d; color:#f1c40f; border:1px solid #f1c40f; }
.badge-cardio   { background:#0d1a2e; color:#00BFFF; border:1px solid #00BFFF; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# CONSTANTES TÉCNICAS
# =====================================================
VIDEOS_BASE = {
    "Sentadilla Goblet":  "https://www.youtube.com/watch?v=MeIiIdhvXT4",
    "Sentadilla Libre":   "https://www.youtube.com/watch?v=1OoMs3MaXI4",
    "Flexiones":          "https://www.youtube.com/watch?v=e_K0yT3t3IM",
    "Jalón al Pecho":     "https://www.youtube.com/watch?v=HSoHeSrp-j4",
    "Peso Muerto Rumano": "https://www.youtube.com/watch?v=JCXUYuzwNrM",
    "Plancha Abdominal":  "https://www.youtube.com/watch?v=ASdvN_XEl_c",
    "Press Banca":        "https://www.youtube.com/watch?v=VmB1G1K7v94",
    "Zancadas":           "https://www.youtube.com/watch?v=0_ZmM-J7y_M",
    "Remo Mancuerna":     "https://www.youtube.com/watch?v=D7KaRcCIQms",
    "Press Militar":      "https://www.youtube.com/watch?v=M2rwvNhTOu0",
}
OBJETIVOS = {
    "Hipertrofia":   {"Reps":"6-12",  "Pausa":"1:30","RPE":"7-9",      "RM":"65-80%"},
    "Fuerza Máxima": {"Reps":"1-5",   "Pausa":"3:00","RPE":"8-10",     "RM":"85-100%"},
    "Resistencia":   {"Reps":"15-20+","Pausa":"0:45","RPE":"6-8",      "RM":"<60%"},
    "Potencia":      {"Reps":"1-5",   "Pausa":"2:00","RPE":"Explosivo","RM":"30-70%"},
}
TIPOS_CARDIO  = ["Carrera","Bicicleta","Elíptica","Remo","Natación","HIIT","Caminata","Otro"]
TIPOS_TEST    = ["Test Cooper (12 min)","Yo-Yo","Salto CMJ","Flexibilidad Sit&Reach",
                 "Fuerza Relativa","1RM Estimado","Test 1km","Otro"]
DIAS          = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
GRUPOS        = ["Descanso","Pierna","Pecho/Hombro","Espalda","Glúteo",
                 "Full Body","Torso","Brazo","Cardio"]
TIPOS_MICROCICLO = ["Ajuste (Descarga)","Carga (Desarrollo)","Impacto (Choque)"]

TABLA_BADILLO = pd.DataFrame({
    "Zona":["Fuerza Máx","Fuerza-Hipert","Hipert Alta","Hipert Media","Resistencia"],
    "% 1RM":["85-100%","80-85%","70-80%","60-75%","<60%"],
    "Reps":["1-5","5-7","6-12","12-20","20+"],
    "Descanso":["3-5 min","3 min","2 min","1-2 min","<1 min"],
})
GUIAS_BOMPA = pd.DataFrame({
    "Fase":["Adaptación","Hipertrofia","Fuerza Máx","Potencia","Transición"],
    "Intensidad":["30-60%","60-80%","85-100%","30-80%","Baja"],
    "Reps":["12-20","6-12","1-5","1-10","Libre"],
    "Descanso":["1-2 min","1-3 min","3-5+ min","3-5+ min","Libre"],
})
GUIA_TEMPO = pd.DataFrame({
    "Objetivo":["Hipertrofia","Fuerza Máx","Potencia","Resistencia"],
    "Tempo":["3-0-1-0","X-0-X-0","X-X-X","2-0-2-0"],
    "Explicación":["Bajada lenta","Máx velocidad","Explosivo","Continuo"],
})
GUIA_DESCANSOS = pd.DataFrame({
    "Objetivo":["Fuerza/Potencia","Hipertrofia","Resistencia"],
    "Tiempo":["3-5+ min","60-90 seg","30-60 seg"],
    "Por qué":["Recuperar ATP","Estrés Metabólico","Limpiar lactato"],
})
ESCALA_RPE = pd.DataFrame({
    "RPE":[10,9,8,7,6],
    "RIR":["0 (Fallo)","1","2","3","4"],
    "Sensación":["Imposible","Podría 1 más","Podría 2 más","Podría 3 más","Calentamiento"],
})
ESCALA_BORG = pd.DataFrame({
    "Nivel":["Muy Suave","Suave","Moderado","Duro","Muy Duro","Máximo"],
    "Escala 0-10":["0-2","3","4-5","6-7","8-9","10"],
    "Test Habla":["Cantar","Fluida","Frases","Palabras","Apenas","Sin aliento"],
})
GUIA_CARDIO = pd.DataFrame({
    "Zona":["Z1 Regenerativo","Z2 Aeróbico","Z3 Umbral","Z4 VO2Max","Z5 Anaeróbico"],
    "% VAM":["<60%","60-75%","75-90%","95-105%",">110%"],
    "Sensación":["Muy fácil","Fácil","Duro","Muy duro","Agonía"],
})
TABLA_ZONAS_FCM = pd.DataFrame({
    "Zona": ["Zona 1 (Recuperación)", "Zona 2 (Quema Grasa)", "Zona 3 (Aeróbica)", "Zona 4 (Umbral Anaeróbico)", "Zona 5 (Máxima)"],
    "% FCM": ["50% - 60%", "60% - 70%", "70% - 80%", "80% - 90%", "90% - 100%"],
    "Beneficio": ["Salud cardiovascular y recuperación activa", "Metabolismo de grasas y base aeróbica", "Capacidad aeróbica y resistencia", "Resistencia a la fatiga de alta intensidad", "Potencia máxima y velocidad anaeróbica"]
})

# =====================================================
# GOOGLE SHEETS BASE
# =====================================================
URL_SHEET = "https://docs.google.com/spreadsheets/d/1NxZNe_1GjunjcpJs91tHJIAnZievTsNuVTTFe6uMqik/edit#gid=0"

def _gs_client():
    sc = ["https://www.googleapis.com/auth/spreadsheets"]
    cr = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=sc)
    return gspread.authorize(cr)

# =====================================================
# AUTENTICACIÓN DINÁMICA CON CACHÉ (Anti-Error 429)
# =====================================================
def _hash(p): 
    return hashlib.sha256(p.encode()).hexdigest()

ADMIN_USER = "visho"
ADMIN_PASS = st.secrets.get("PW_VISHO", "Bio2026")

def _get_hoja_usuarios(sheet):
    try:
        return sheet.worksheet("usuarios_sistema")
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title="usuarios_sistema", rows="200", cols="6")
        ws.append_row(["usuario","password_hash","nombre_completo","tipo_cobro","valor_cobro","fecha_registro"])
        return ws

@st.cache_data(ttl=600)
def cargar_usuarios_sistema():
    try:
        client = _gs_client()
        sheet  = client.open_by_url(URL_SHEET)
        ws     = _get_hoja_usuarios(sheet)
        rows   = ws.get_all_records()
        return {str(r["usuario"]).lower().strip(): r for r in rows if r.get("usuario")}
    except Exception:
        return {}

def registrar_usuario_sistema(usuario, password, nombre, tipo_cobro, valor_cobro):
    usuario = usuario.lower().strip()
    if not usuario or not password: 
        return False, "Usuario y contraseña son obligatorios."
    if len(password) < 6: 
        return False, "La contraseña debe tener al menos 6 caracteres."
    try:
        client = _gs_client(); sheet = client.open_by_url(URL_SHEET); ws = _get_hoja_usuarios(sheet)
        existentes = [r["usuario"] for r in ws.get_all_records() if r.get("usuario")]
        if usuario in existentes: 
            return False, "El usuario ya existe."
        ws.append_row([
            usuario, _hash(password), nombre.strip(),
            tipo_cobro, valor_cobro,
            datetime.now().strftime("%d/%m/%Y %H:%M")
        ])
        cargar_usuarios_sistema.clear()
        return True, ""
    except Exception as e:
        return False, str(e)

def eliminar_usuario_sistema(usuario):
    try:
        client = _gs_client(); sheet = client.open_by_url(URL_SHEET); ws = _get_hoja_usuarios(sheet)
        celdas = ws.col_values(1)
        for i, val in enumerate(celdas):
            if val == usuario:
                ws.delete_rows(i + 1)
                cargar_usuarios_sistema.clear()
                return True
    except Exception:
        pass
    return False

def cambiar_password_usuario(usuario, nueva_password):
    try:
        client = _gs_client(); sheet = client.open_by_url(URL_SHEET); ws = _get_hoja_usuarios(sheet)
        celdas = ws.col_values(1)
        for i, val in enumerate(celdas):
            if val == usuario:
                ws.update_cell(i + 1, 2, _hash(nueva_password))
                cargar_usuarios_sistema.clear()
                return True
    except Exception:
        pass
    return False

def validar_usuario(u, c):
    if u == ADMIN_USER: 
        return c == ADMIN_PASS
    try:
        usuarios = cargar_usuarios_sistema()
        if u in usuarios: 
            return str(usuarios[u].get("password_hash")) == _hash(c)
    except Exception:
        st.error("⚠️ Google Sheets está saturado (Límite de lecturas 429). Espera 1 minuto.")
    
    # Fallback legacy
    LEGACY = {
        "eduardo":  st.secrets.get("PW_EDUARDO",  "Bio2026"),
        "davidp":   st.secrets.get("PW_DAVIDP",   "Davidp2026"),
        "clemente": st.secrets.get("PW_CLEMENTE", "Clemente2026"),
    }
    return LEGACY.get(u) == c

def get_info_usuario(u):
    if u == ADMIN_USER: 
        return {"nombre_completo":"Administrador","tipo_cobro":"admin","valor_cobro":0}
    try:
        info = cargar_usuarios_sistema().get(u, {})
        if info: return info
    except Exception:
        pass
    nombres_legacy = {"eduardo": "Eduardo", "davidp": "David P.", "clemente": "Clemente"}
    return {"nombre_completo": nombres_legacy.get(u, u.capitalize())}

# =====================================================
# DETECCIÓN DE LINK DIRECTO (WhatsApp firmado)
# =====================================================
es_link_directo = False
atleta_url = st.query_params.get("atleta", None)
entrenador_url = st.query_params.get("entrenador", None)

if atleta_url and entrenador_url:
    sig_url = st.query_params.get("sig", "")
    if not verificar_link(entrenador_url, atleta_url, sig_url):
        st.error("⛔ Enlace inválido o alterado. Solicita un nuevo enlace a tu entrenador.")
        st.stop()
    es_link_directo = True
    st.markdown("""<style>[data-testid="stSidebar"] {display: none !important;}
                   [data-testid="collapsedControl"] {display: none !important;}</style>""", unsafe_allow_html=True)
    st.session_state.usuario_actual = entrenador_url
    st.session_state.cliente_activo = atleta_url
    modo_app = "Portal del Atleta 📱"

# =====================================================
# LOGIN NORMAL
# =====================================================
if not es_link_directo:
    def login():
        if not st.session_state.get("autenticado", False):
            st.markdown("""<style>[data-testid="stSidebar"]{display:none}[data-testid="collapsedControl"]{display:none}
            .stApp{background:radial-gradient(ellipse at top,#0a1a0a 0%,#0d0d0d 60%)}
            .login-card{background:linear-gradient(135deg,#111 0%,#1a1a1a 100%);border:1px solid #1f1f1f;border-radius:16px;padding:32px 36px;box-shadow:0 20px 60px rgba(0,0,0,.6),0 0 0 1px rgba(57,255,20,.08)}
            .stFormSubmitButton button{background:#39FF14!important;color:#000!important;font-family:'Bebas Neue',sans-serif!important;font-size:1.2rem!important;border-radius:8px!important;padding:14px!important;width:100%!important}</style>""", unsafe_allow_html=True)
            _, col, _ = st.columns([1, 1.4, 1])
            with col:
                st.markdown("<div style='text-align:center;padding:24px 0 16px'><span style='font-family:Bebas Neue;font-size:3.6rem;color:#39FF14;letter-spacing:6px'>BIO SPORT</span><br><span style='color:#666;font-size:.85rem;letter-spacing:2px'>PLATAFORMA DE ALTO RENDIMIENTO</span></div>", unsafe_allow_html=True)
                st.markdown("<div class='login-card'>", unsafe_allow_html=True)
                with st.form("login_form"):
                    u = st.text_input("Usuario", placeholder="tu usuario").lower().strip()
                    pw = st.text_input("Contraseña", type="password", placeholder="••••••••")
                    if st.form_submit_button("ENTRAR AL SISTEMA", type="primary", use_container_width=True):
                        if not u or not pw: 
                            st.error("Completa usuario y contraseña.")
                        elif validar_usuario(u, pw):
                            info = get_info_usuario(u)
                            st.session_state.autenticado    = True
                            st.session_state.usuario_actual = u
                            st.session_state.nombre_usuario = info.get("nombre_completo", u.capitalize())
                            st.session_state.es_admin       = (u == ADMIN_USER)
                            st.rerun()
                        else: 
                            st.error("Usuario o contraseña incorrectos.")
                st.markdown("</div>", unsafe_allow_html=True)
            return False
        return True

    if not login(): 
        st.stop()

    _nombre_sb = st.session_state.get("nombre_usuario", st.session_state["usuario_actual"].capitalize())
    st.sidebar.markdown(f"**👤 {_nombre_sb}**")
    if st.sidebar.button("Cerrar sesión", key="btn_cerrar_sesion"):
        for k in list(st.session_state): del st.session_state[k]
        st.rerun()
    st.sidebar.markdown("---")
    modo_app = st.sidebar.radio("Vista:", ["Entrenador 🛠️", "Portal del Atleta 📱"], key="interruptor_vista")
    st.sidebar.markdown("---")

# =====================================================
# CARGA Y GUARDADO DE DATOS (Google Sheets)
# =====================================================
def cargar_datos():
    usuario = st.session_state.get("usuario_actual", "default")
    raw = None
    try:
        client = _gs_client()
        sheet  = client.open_by_url(URL_SHEET)
        try:
            ws = sheet.worksheet(usuario)
        except gspread.exceptions.WorksheetNotFound:
            ws = sheet.add_worksheet(title=usuario, rows="200", cols="20")
            return None
        vals = ws.col_values(1)
        if vals:
            raw = json.loads("".join(vals))
    except Exception:
        pass

    if raw is None:
        return None

    defaults = {
        "clientes":        {},
        "historial":       [],
        "videos":          VIDEOS_BASE,
        "planes":          {},
        "detalles_planes": {},
        "notas":           "",
        "tests":           {},      
        "mesociclos":      {},      
    }
    for k, v in defaults.items():
        if k not in raw:
            raw[k] = v   

    return raw

def guardar_datos():
    usuario = st.session_state.get("usuario_actual", "default")
    try:
        payload = {
            "clientes":        st.session_state.db_clientes,
            "historial":       st.session_state.historial_global,
            "videos":          st.session_state.biblioteca_videos,
            "planes":          st.session_state.planes_semanales,
            "detalles_planes": st.session_state.detalles_planes,
            "notas":           st.session_state.notas_personales,
            "tests":           st.session_state.tests_fisicos,
            "mesociclos":      st.session_state.mesociclos,
        }
        js     = json.dumps(payload, ensure_ascii=False)
        client = _gs_client()
        sheet  = client.open_by_url(URL_SHEET)
        try:
            ws = sheet.worksheet(usuario)
        except gspread.exceptions.WorksheetNotFound:
            ws = sheet.add_worksheet(title=usuario, rows="200", cols="20")

        chunks = [js[i:i+40000] for i in range(0, len(js), 40000)]
        ws.clear()
        cells  = ws.range(1, 1, len(chunks), 1)
        for i, cell in enumerate(cells):
            cell.value = chunks[i]
        ws.update_cells(cells)
        return True
    except Exception:
        return False

def registrar_auditoria(nombre_alumno):
    usuario = st.session_state.get("usuario_actual", "")
    if usuario == "visho":
        return
    try:
        client = _gs_client()
        sheet  = client.open_by_url(URL_SHEET)
        meses  = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                  "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        nh = f"Auditoria_{meses[datetime.now().month-1]}_{datetime.now().year}"
        try:
            ws = sheet.worksheet(nh)
        except gspread.exceptions.WorksheetNotFound:
            ws = sheet.add_worksheet(title=nh, rows="1000", cols="4")
            ws.append_row(["Fecha","Preparador","Alumno","Estado"])
        for f in ws.get_all_values():
            if len(f) >= 3 and f[1].lower() == usuario and f[2].lower() == nombre_alumno.lower():
                return
        ws.append_row([datetime.now().strftime("%d/%m/%Y %H:%M"),
                       usuario.capitalize(), nombre_alumno, "Pendiente"])
    except Exception:
        pass

# =====================================================
# INICIALIZACIÓN DE ESTADO
# =====================================================
if "datos_cargados" not in st.session_state:
    _raw = cargar_datos()
    def _get(key, default):
        if _raw and _raw.get(key) is not None:
            return _raw[key]
        return default

    st.session_state.db_clientes        = _get("clientes",        {})
    st.session_state.historial_global   = _get("historial",       [])
    st.session_state.biblioteca_videos  = _get("videos",          VIDEOS_BASE)
    st.session_state.planes_semanales   = _get("planes",          {})
    st.session_state.detalles_planes    = _get("detalles_planes", {})
    st.session_state.notas_personales   = _get("notas",           "")
    st.session_state.tests_fisicos      = _get("tests",           {})
    st.session_state.mesociclos         = _get("mesociclos",      {})
    st.session_state.datos_cargados     = True

for _k, _v in [("cliente_activo",None),("confirm_delete",False),("live_idx",0)]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# =====================================================
# FUNCIONES DE CÁLCULO
# =====================================================
def calc_1rm(p, r): return p * (1 + r / 30)

def calc_durnin(edad, sexo, s4):
    if s4 <= 0: raise ValueError("La suma de pliegues debe ser > 0")
    c, m = (1.1631, 0.0632) if sexo == "Masculino" else (1.1599, 0.0717)
    d = c - m * math.log10(s4)
    if d <= 0: raise ValueError("Densidad inválida")
    return (495 / d) - 450

def eval_grasa(edad, sexo, g):
    if sexo == "Masculino":
        t = {24:[3,9,19,23],29:[3,10,20,24],34:[3,11,21,25],39:[3,12,22,26],
             44:[3,13,23,27],49:[3,15,25,28],54:[3,17,26,29],59:[3,19,28,30]}
        row = next((v for k,v in t.items() if edad<=k), [3,20,29,31])
    else:
        t = {24:[8,15,25,30],29:[8,16,26,31],34:[8,17,27,32],39:[8,19,28,33],
             44:[8,21,29,34],49:[8,23,31,36],54:[8,25,33,37],59:[8,26,34,38]}
        row = next((v for k,v in t.items() if edad<=k), [8,27,35,39])
    if g <= row[0]: return "Grasa Esencial",  "#FF4B4B"
    if g <= row[1]: return "Graso Disminuido", "#00C853"
    if g <= row[2]: return "Graso Adecuado",   "#00BFFF"
    if g <= row[3]: return "Graso Aumentado",  "#FFD700"
    return "Grasa Muy Alta", "#DC143C"

def calc_tmb(peso, talla, edad, sexo):
    base = 10*peso + 6.25*talla - 5*edad
    return base + 5 if sexo == "Masculino" else base - 161

def calc_get(tmb, act):
    f = {"Sedentario":1.2,"Ligero (1-3 días)":1.375,"Moderado (3-5 días)":1.55,"Activo (6-7 días)":1.725,"Muy Activo (2x/día)":1.9}
    return tmb * f.get(act, 1.55)

def analizar_progreso(df_ej):
    if len(df_ej) < 3: return "sin_datos", "Necesitas al menos 3 registros para analizar.", "inf"
    cs = df_ej["Carga"].tolist()
    u  = cs[-3:]
    n  = len(cs)
    tasa = None
    if n >= 5:
        xs = list(range(n)); mx = sum(xs)/n; my = sum(cs)/n
        nd = sum((x-mx)*(y-my) for x,y in zip(xs,cs))
        dd = sum((x-mx)**2 for x in xs)
        p  = nd/dd if dd else 0
        tasa = (p/my)*100 if my else 0
    if u[0] == u[1] == u[2]: return "estancado", f"⚠️ Estancamiento: {u[0]}kg en 3 sesiones seguidas.", "warn"
    if u[2] < u[0]: return "baja", f"📉 Bajada de {u[0]-u[2]:.1f}kg vs referencia.", "err"
    if tasa and tasa > 1.5: return "rapido", f"🔥 Progreso sólido: +{tasa:.1f}% por sesión.", "ok"
    if u[2] > u[1]: return "ok_", f"✅ Progresando: {u[1]}kg → {u[2]}kg.", "ok"
    return "estable", "📊 Carga estable.", "inf"

def calc_adherencia(cliente):
    hoy = hoy_chile()
    dp = de = 0
    for i in range(30):
        dia = hoy - timedelta(days=29-i)
        nd  = DIAS[dia.weekday()]
        f   = st.session_state.planes_semanales.get(cliente, {}).get(nd, "Descanso")
        if f not in ("Descanso", ""):
            dp += 1
            fs = dia.strftime("%d/%m/%Y")
            if any(h["Cliente"]==cliente and h["Fecha"]==fs for h in st.session_state.historial_global):
                de += 1
    pct = de/dp*100 if dp else 0
    return de, dp, pct

def parse_tiempo(t):
    try:
        t = str(t).strip()
        if ":" in t: return int(t.split(":")[0])*60 + int(t.split(":")[1])
        v = float(t)
        return int(v*60) if v < 10 else int(v)
    except Exception: return 90

def ult_reg(cliente, ej):
    for r in reversed(st.session_state.historial_global):
        if r["Cliente"]==cliente and r["Ejercicio"]==ej and r.get("Tipo")=="Fuerza":
            return r
    return None

def importar_historial(cliente):
    dm = {i: d for i,d in enumerate(DIAS)}
    nd = st.session_state.detalles_planes.get(cliente,{}).copy()
    nf = st.session_state.planes_semanales.get(cliente,{}).copy()
    rt = {d:[] for d in DIAS}; ft = {d:"Descanso" for d in DIAS}
    hoy = hoy_chile()
    for reg in reversed(st.session_state.historial_global):
        if reg["Cliente"] == cliente:
            try:
                fd = datetime.strptime(reg["Fecha"],"%d/%m/%Y").date()
                if (hoy-fd).days < 14:
                    dia = dm[fd.weekday()]
                    txt = (f"{reg['Ejercicio']}: {reg['Series']}x{reg['Reps']} ({reg['Carga']}kg)"
                           if reg.get("Tipo")=="Fuerza"
                           else f"Cardio: {reg['Ejercicio']} ({reg['Carga']}min)")
                    if txt not in rt[dia]: rt[dia].insert(0, txt)
                    if "Objetivo" in reg and ft[dia]=="Descanso": ft[dia]=reg["Objetivo"]
            except Exception: pass
    for dia, lista in rt.items():
        if lista:
            nd[dia] = f"||{chr(10).join(lista)}||"
            nf[dia] = ft[dia] if ft[dia]!="Descanso" else "Entrenamiento"
    st.session_state.planes_semanales[cliente] = nf
    st.session_state.detalles_planes[cliente]  = nd
    guardar_datos()

# =====================================================
# GENERADORES PDF / EXCEL / IA
# =====================================================
def pdf_plan(cliente, focos, detalles, dias_orden=DIAS):
    if not REPORTLAB_OK: return None
    buf = io.BytesIO()
    cv  = rl_canvas.Canvas(buf, pagesize=letter)
    W, H = letter
    NEON = HexColor("#39FF14"); DARK = HexColor("#1E1E1E")
    GREY = HexColor("#2D2D2D"); BLK  = HexColor("#222222"); SUB = HexColor("#666666")

    cv.setFillColor(DARK); cv.rect(0,H-85,W,85,fill=1,stroke=0)
    cv.setFillColor(NEON);  cv.setFont("Helvetica-Bold",22)
    cv.drawString(50,H-42,"PLAN DE ENTRENAMIENTO")
    cv.setFont("Helvetica",13); cv.drawString(50,H-65,f"Atleta: {cliente}")
    cv.setFont("Helvetica",8);  cv.setFillColor(HexColor("#AAAAAA"))
    cv.drawRightString(W-50,H-42,"BIO SPORT PRO")
    cv.drawRightString(W-50,H-56,f"Fecha: {hoy_chile():%d/%m/%Y}")

    y = H-110
    ts = focos.get("tipo_semana","")
    if ts:
        cv.setFont("Helvetica-Bold",11); cv.setFillColor(NEON)
        cv.drawString(50,y,f"Microciclo: {ts}"); y -= 22

    for dia in dias_orden:
        foco = focos.get(dia,"Descanso")
        det  = detalles.get(dia,"")
        lns  = len(det.split("\n")) if det else 0
        need = 50 + lns*13
        if y - need < 45: cv.showPage(); y = H-50
        if foco != "Descanso":
            cv.setFillColor(GREY); cv.rect(50,y-18,W-100,22,fill=1,stroke=0)
            cv.setFillColor(NEON); cv.setFont("Helvetica-Bold",11)
            cv.drawString(58,y-11,f"{dia.upper()}  ·  {foco}")
            cv.setStrokeColor(NEON); cv.setLineWidth(0.4)
            cv.line(50,y-18,W-50,y-18); y -= 28
            if det:
                parts = det.split("||")
                labels = ["Calentamiento","Desarrollo","Vuelta a la Calma"]
                if len(parts)==3:
                    for i,blk in enumerate(parts):
                        if not blk.strip(): continue
                        if y<55: cv.showPage(); y=H-50
                        cv.setFont("Helvetica-Bold",8); cv.setFillColor(NEON)
                        cv.drawString(62,y,f"[ {labels[i]} ]"); y-=12
                        cv.setFont("Helvetica",9); cv.setFillColor(BLK)
                        for ln in blk.split("\n"):
                            if ln.strip():
                                if y<45: cv.showPage(); y=H-50
                                cv.drawString(70,y,f"· {ln.strip()}"); y-=12
                        y -= 4
                else:
                    cv.setFont("Helvetica",9); cv.setFillColor(BLK)
                    for ln in det.split("\n"):
                        if ln.strip():
                            if y<45: cv.showPage(); y=H-50
                            cv.drawString(62,y,f"· {ln.strip()}"); y-=12
            else:
                cv.setFont("Helvetica-Oblique",8); cv.setFillColor(SUB)
                cv.drawString(62,y,"(Sin detalles)"); y-=12
            y -= 10
        else:
            cv.setFont("Helvetica-Oblique",8); cv.setFillColor(SUB)
            cv.drawString(58,y-8,f"{dia}: Descanso / Recuperación"); y-=22

    cv.setFont("Helvetica",7); cv.setFillColor(SUB)
    cv.drawCentredString(W/2,22,"La constancia es la clave del éxito · Bio Sport Pro")
    cv.save(); buf.seek(0); return buf

def excel_historial(cliente, historial):
    if not OPENPYXL_OK: return None
    regs = [r for r in historial if r["Cliente"]==cliente]
    if not regs: return None
    df  = pd.DataFrame(regs); buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Historial")
        ws = w.sheets["Historial"]
        for col in ws.columns:
            ml = max(len(str(c.value or "")) for c in col)
            ws.column_dimensions[col[0].column_letter].width = min(ml+3,40)
    buf.seek(0); return buf

def dante_mesociclo(cliente, objetivo, semanas, db_clientes):
    if not modelo_dante: return None
    d = db_clientes.get(cliente,{})
    perfil = (f"Edad:{d.get('Edad','?')}, Experiencia:{d.get('Experiencia','?')}, "
              f"Lesiones:{d.get('Lesiones','Ninguna')}, Objetivo:{objetivo}")
    prompt = (f"Eres Dante, experto en periodización deportiva. "
              f"Genera un mesociclo de {semanas} semanas para:\n{perfil}\n"
              f"Por cada semana indica: tipo (adaptación/carga/impacto/descarga), "
              f"intensidad (%RM), volumen (series por grupo), "
              f"ejercicios principales (3-5), RPE objetivo y nota del entrenador. "
              f"Sé específico, práctico y estructurado.")
    try:
        return modelo_dante.generate_content(prompt).text
    except Exception as e:
        return f"Error: {e}"

# =====================================================
# VISTA: PORTAL DEL ATLETA (Link WhatsApp)
# =====================================================
if modo_app == "Portal del Atleta 📱":
    st.title("📱 Portal de Entrenamiento")
    c = st.session_state.cliente_activo
    
    if not c or c not in st.session_state.db_clientes:
        st.error("Atleta no encontrado en este entrenador.")
        st.stop()

    st.success(f"¡Vamos con todo hoy, {c}! 🔥")
    hoy_str = DIAS[hoy_chile().weekday()]
    foco_hoy = st.session_state.planes_semanales.get(c, {}).get(hoy_str, "Descanso")
    detalles_hoy = st.session_state.detalles_planes.get(c, {}).get(hoy_str, "")

    if foco_hoy == "Descanso" or not detalles_hoy.strip():
        st.info(f"🛌 Hoy ({hoy_str}) es día de descanso o no tienes rutina asignada. ¡Recupérate bien!")
    else:
        st.markdown(f"### 🎯 Objetivo de hoy: {foco_hoy}")
        partes = detalles_hoy.split("||")
        desarrollo = partes[1] if len(partes) > 1 else (partes[0] if partes else "")
        ejercicios = [linea.strip() for linea in desarrollo.split("\n") if linea.strip()]

        if not ejercicios:
            st.warning("El bloque principal de la rutina está vacío.")
        else:
            for idx, linea_ejercicio in enumerate(ejercicios):
                nombre_base = linea_ejercicio.split(":")[0].strip()
                st.markdown("---")
                col_info, col_gif = st.columns([1, 1])

                with col_info:
                    st.markdown(f"#### {idx + 1}. {nombre_base}")
                    if ":" in linea_ejercicio:
                        st.markdown(f"**Indicaciones:** {linea_ejercicio.split(':', 1)[1].strip()}")

                with col_gif:
                    if nombre_base in st.session_state.biblioteca_videos:
                        st.image(st.session_state.biblioteca_videos[nombre_base], use_container_width=True)
                    else:
                        st.info("Sin vista previa")

                with st.expander(f"✍️ Registrar series de {nombre_base}", expanded=False):
                    c1, c2, c3, c4 = st.columns(4)
                    s_atl = c1.number_input("Series", 1, 10, 4, key=f"s_atl_{idx}")
                    r_atl = c2.number_input("Reps", 1, 50, 10, key=f"r_atl_{idx}")
                    k_atl = c3.number_input("Kg", 0.0, step=0.5, key=f"k_atl_{idx}")
                    rpe_atl = c4.slider("RPE", 1, 10, 7, key=f"rpe_atl_{idx}")

                    if st.button("✅ Guardar en mi historial", key=f"btn_atl_{idx}", use_container_width=True):
                        st.session_state.historial_global.append({
                            "Cliente": c,
                            "Fecha": fstr(hoy_chile()),
                            "Ejercicio": nombre_base,
                            "Series": s_atl, "Reps": r_atl,
                            "Carga": k_atl, "RPE": rpe_atl,
                            "Tipo": "Fuerza", "Objetivo": foco_hoy,
                        })
                        guardar_datos()
                        st.success("¡Excelente! Serie registrada en tu historial. 💪")
    st.stop()

# =====================================================
# VISTA: ENTRENADOR (Menú y Gestión)
# =====================================================
lista = ["Crear Nuevo..."] + list(st.session_state.db_clientes.keys())
sel   = st.sidebar.selectbox("Atleta:", lista)

if sel == "Crear Nuevo...":
    nom = st.sidebar.text_input("Nombre del nuevo atleta:")
    if st.sidebar.button("Guardar Atleta", type="primary", key="btn_guardar_atleta"):
        n = nom.strip()
        if n and n not in st.session_state.db_clientes:
            st.session_state.db_clientes[n] = {"Peso":70,"Talla":170,"Edad":25,"Sexo":"Masculino"}
            guardar_datos()
            registrar_auditoria(n)
            st.toast(f"✅ {n} registrado", icon="🔥")
            time.sleep(0.6); st.rerun()
        elif n in st.session_state.db_clientes:
            st.sidebar.warning("Ese atleta ya existe.")
else:
    st.session_state.cliente_activo = sel
    with st.sidebar.expander("⚙️ Gestión", expanded=False):
        if not st.session_state.confirm_delete:
            if st.button("🗑️ Eliminar Atleta", key="btn_eliminar_atleta"):
                st.session_state.confirm_delete = True; st.rerun()
        else:
            st.warning(f"¿Eliminar **{sel}** definitivamente?")
            ca, cb = st.columns(2)
            if ca.button("✅ Sí, eliminar", key="btn_confirmar_eliminar"):
                del st.session_state.db_clientes[sel]
                st.session_state.historial_global = [h for h in st.session_state.historial_global if h["Cliente"]!=sel]
                for _d in [st.session_state.planes_semanales, st.session_state.detalles_planes, st.session_state.tests_fisicos, st.session_state.mesociclos]:
                    _d.pop(sel, None)
                guardar_datos()
                st.session_state.cliente_activo = None
                st.session_state.confirm_delete = False
                st.rerun()
            if cb.button("❌ Cancelar", key="btn_cancelar_eliminar"):
                st.session_state.confirm_delete = False; st.rerun()

        js = json.dumps({"clientes": st.session_state.db_clientes, "historial": st.session_state.historial_global}, indent=2, ensure_ascii=False)
        st.download_button("💾 Backup JSON", data=js, file_name="backup_biosport.json", mime="application/json")

with st.sidebar.expander("🧮 Calculadora RM", expanded=False):
    _p = st.number_input("Peso (kg)", 0.0, step=0.5, key="rm_p")
    _r = st.number_input("Reps", 1, 20, 8, key="rm_r")
    if _p > 0:
        _rm = calc_1rm(_p, _r)
        st.markdown(f"<div style='background:#1a1a1a;border:1px solid #39FF14;border-radius:8px;padding:10px;text-align:center;margin:6px 0'><div style='color:#888;font-size:.75rem'>1RM ESTIMADO</div><div style='color:#39FF14;font-size:1.6rem;font-weight:700'>{_rm:.1f} kg</div></div>", unsafe_allow_html=True)

MENU_ITEMS = ["🏠 Dashboard","📋 Ficha & Antropo","💪 Entrenamiento","🏋️ Modo En Vivo","🧠 Plan Semanal","📆 Mesociclo IA","🏃 Cardio","🧪 Tests Físicos","🥗 Nutrición","📈 Progreso","📚 Guías","📝 Notas","🎥 Videoteca"]
if st.session_state.get("es_admin", False): 
    MENU_ITEMS.append("👑 Panel Admin")

menu = st.sidebar.radio("Menú:", MENU_ITEMS)
st.sidebar.divider()
if st.session_state.cliente_activo: 
    st.sidebar.success(f"Atleta activo: {st.session_state.cliente_activo}")

def need_athlete():
    if not st.session_state.cliente_activo:
        st.warning("Selecciona un atleta en el menú lateral.")
        st.stop()
    return st.session_state.cliente_activo

# -----------------------------------------------------
# MÓDULOS DE LA APLICACIÓN
# -----------------------------------------------------
if menu == "🏠 Dashboard":
    st.title("⚡ Dashboard Bio Sport")
    n_at = len(st.session_state.db_clientes)
    hoy_s = fstr(hoy_chile())
    n_hoy = sum(1 for h in st.session_state.historial_global if h["Fecha"] == hoy_s)
    n_tot = len(st.session_state.historial_global)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 Atletas", n_at)
    c2.metric("🔥 Sesiones hoy", n_hoy)
    c3.metric("📊 Registros totales", n_tot)
    c4.metric("📅 Hoy", hoy_s)

    if st.session_state.db_clientes:
        st.divider(); st.subheader("Estado de Atletas")
        rows = []
        for nom, dat in st.session_state.db_clientes.items():
            regs = [h for h in st.session_state.historial_global if h["Cliente"] == nom]
            ult = regs[-1]["Fecha"] if regs else "—"
            de, dp, pct = calc_adherencia(nom)
            rows.append({"Atleta": nom, "Objetivo": dat.get("Objetivo_Prin", "—"), "Experiencia": dat.get("Experiencia", "—"), "Sesiones": len(regs), "Último registro": ult, "Adherencia 30d": f"{pct:.0f}%"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

elif menu == "📋 Ficha & Antropo":
    c = need_athlete()
    d = st.session_state.db_clientes[c]
    tb1, tb2, tb3 = st.tabs(["📝 Datos Básicos", "📏 Antropometría", "🏥 Anamnesis"])

    with tb1:
        co1, co2, co3, co4 = st.columns(4)
        np_ = co1.number_input("Peso (kg)", 0.1, 250.0, float(d.get("Peso", 70)), step=0.5)
        nt_ = co2.number_input("Talla (cm)", 50.0, 250.0, float(d.get("Talla", 170)), step=0.5)
        ne_ = co3.number_input("Edad", 5, 100, int(d.get("Edad", 25)))
        ns_ = co4.selectbox("Sexo", ["Masculino", "Femenino"], index=0 if d.get("Sexo", "Masculino") == "Masculino" else 1)
        imc = np_ / ((nt_ / 100) ** 2)
        st.caption(f"IMC: **{imc:.1f}**")
        if st.button("💾 Actualizar Datos", type="primary"):
            st.session_state.db_clientes[c].update({"Peso": np_, "Talla": nt_, "Edad": ne_, "Sexo": ns_})
            guardar_datos(); st.toast("Datos actualizados ✅")

    with tb2:
        st.subheader("Cálculo de Grasa — Durnin 4 Pliegues")
        ci, co = st.columns(2)
        with ci:
            p1 = st.number_input("Bíceps mm", 0.0, 100.0, 0.0, step=0.1)
            p2 = st.number_input("Tríceps mm", 0.0, 100.0, 0.0, step=0.1)
            p3 = st.number_input("Subescapular mm", 0.0, 100.0, 0.0, step=0.1)
            p4 = st.number_input("Suprailiaco mm", 0.0, 100.0, 0.0, step=0.1)
            suma = p1 + p2 + p3 + p4
        with co:
            if suma > 0:
                try:
                    gr = calc_durnin(d.get("Edad", 25), d.get("Sexo", "Masculino"), suma)
                    if not (2 <= gr <= 60): st.warning(f"Fuera de rango: {gr:.1f}%")
                    else:
                        peso = d.get("Peso", 70); mm = peso * (1 - gr / 100)
                        st.metric("% Grasa", f"{gr:.1f}%"); st.metric("Masa Magra", f"{mm:.1f} kg")
                        cat, col_ = eval_grasa(d.get("Edad", 25), d.get("Sexo", "Masculino"), gr)
                        st.markdown(f"<div style='background:#2D2D2D;padding:12px;border-radius:8px;border:1px solid {col_};text-align:center'><div style='color:{col_};font-size:1.2rem;font-weight:700'>{cat}</div></div>", unsafe_allow_html=True)
                except ValueError as e: st.error(f"Error: {e}")
            else: st.info("Ingresa los 4 pliegues.")

    with tb3:
        fono = st.text_input("📱 Teléfono", value=d.get("Telefono", ""))
        les  = st.text_area("🩹 Lesiones", value=d.get("Lesiones", ""), height=80)
        obj  = st.text_input("🎯 Objetivo Principal", value=d.get("Objetivo_Prin", ""))
        if st.button("💾 Guardar Anamnesis", type="primary"):
            st.session_state.db_clientes[c].update({"Telefono": fono, "Lesiones": les, "Objetivo_Prin": obj})
            guardar_datos(); st.toast("Guardado ✅")

elif menu == "💪 Entrenamiento":
    c = need_athlete()
    fecha = st.date_input("📅 Fecha:", hoy_chile())
    dia   = DIAS[fecha.weekday()]
    foco  = st.session_state.planes_semanales.get(c, {}).get(dia, "Sin planificar")
    det   = st.session_state.detalles_planes.get(c, {}).get(dia, "")

    if foco == "Descanso": st.success(f"🛌 {dia}: Descanso planificado")
    else:
        st.info(f"🔥 {dia}: {foco}")
        if det:
            with st.expander("👀 Ver plan del día", expanded=True):
                pts = det.split("||")
                if len(pts) == 3:
                    if pts[0].strip(): st.markdown("**1️⃣ Calentamiento:**\n" + pts[0])
                    if pts[1].strip(): st.markdown("**2️⃣ Desarrollo:**\n" + pts[1])
                    if pts[2].strip(): st.markdown("**3️⃣ Vuelta a la Calma:**\n" + pts[2])
                else: st.text(det)
    st.divider()

    col_e, col_t = st.columns([3, 1])
    with col_e:
        obj_ = st.selectbox("🎯 Objetivo:", list(OBJETIVOS.keys()))
        sug  = OBJETIVOS[obj_]
        st.caption(f"Guía: {sug['Reps']} reps · {sug['RM']} · Pausa: {sug['Pausa']} · RPE: {sug['RPE']}")

        st.markdown("#### 🔎 Buscar Ejercicio")
        filtro = st.radio("Categoría:", ["Todos", "Barra", "Mancuerna", "Cable", "Polea", "Banda", "Sentadilla", "Salto", "Peso Corporal"], horizontal=True)
        if filtro == "Todos": lista_filtrada = list(st.session_state.biblioteca_videos.keys())
        else: lista_filtrada = [ej for ej in st.session_state.biblioteca_videos.keys() if filtro.lower() in ej.lower()]
        
        lista_ordenada = sorted(lista_filtrada) + ["✍️ Otro..."]
        col_sel, col_gif = st.columns([6, 4])
        with col_sel:
            ej_ = st.selectbox("Elige el ejercicio:", lista_ordenada)
            if ej_ != "✍️ Otro...":
                ur = ult_reg(c, ej_)
                if ur: st.info(f"💡 Último: {ur['Series']}x{ur['Reps']} @ {ur['Carga']}kg")

        with col_gif:
            if ej_ != "✍️️ Otro..." and ej_ in st.session_state.biblioteca_videos:
                enlace = st.session_state.biblioteca_videos[ej_]
                if "githubusercontent.com" in enlace or ".gif" in enlace:
                    st.image(enlace, use_container_width=True)

        nom = st.text_input("Nombre en rutina:", value="" if ej_ == "✍️ Otro..." else ej_)
        c1, c2, c3 = st.columns(3)
        se = c1.number_input("Series", 1, 10, 4)
        re = c2.number_input("Reps", 1, 50, 10)
        kg = c3.number_input("Carga kg", 0.0, step=0.5)
        pt = st.text_input("Pausa", value=sug["Pausa"])
        rpe = st.slider("RPE", 1, 10, 7)

        if st.button("➕ Registrar Serie", type="primary"):
            if nom.strip():
                st.session_state.historial_global.append({
                    "Cliente": c, "Fecha": fstr(fecha), "Ejercicio": nom.strip(),
                    "Series": se, "Reps": re, "Carga": kg, "RPE": rpe, "Tipo": "Fuerza", "Objetivo": obj_
                })
                guardar_datos(); st.toast("Serie registrada 💪"); st.rerun()

        hist_hoy = [h for h in st.session_state.historial_global if h["Cliente"] == c and h["Fecha"] == fstr(fecha)]
        if hist_hoy:
            st.divider(); st.subheader(f"📝 Sesión {fstr(fecha)}")
            for i, h in enumerate(hist_hoy):
                ci2, cd2 = st.columns([4, 1])
                ci2.write(f"✅ {h['Ejercicio']}: {h['Series']}x{h['Reps']} @ {h['Carga']}kg")
                if cd2.button("🗑️", key=f"del_{i}"):
                    st.session_state.historial_global = [x for x in st.session_state.historial_global if x is not h]
                    guardar_datos(); st.rerun()

    with col_t:
        st.write("⏱️ Timer")
        seg = parse_tiempo(pt)
        if st.button("▶ Iniciar"):
            ph = st.empty(); bar = st.progress(0.0)
            for i in range(seg, -1, -1):
                ph.metric("Restante", f"{i}s"); bar.progress(1.0 - i/seg if seg else 1.0); time.sleep(1)
            ph.success("✅ ¡Tiempo!"); bar.empty()

elif menu == "🏋️ Modo En Vivo":
    c = need_athlete()
    hoy = hoy_chile(); dia = DIAS[hoy.weekday()]
    det = st.session_state.detalles_planes.get(c, {}).get(dia, "")
    foco = st.session_state.planes_semanales.get(c, {}).get(dia, "Sin planificar")

    st.title(f"🏋️ En Vivo — {c}"); st.caption(f"{dia} · {foco}")
    ejs = []
    if det:
        pts = det.split("||"); blq = pts[1] if len(pts) > 1 else (pts[0] if pts else "")
        ejs = [l.strip() for l in blq.split("\n") if l.strip()]

    if not ejs: st.info(f"No hay ejercicios hoy."); st.stop()

    n = len(ejs); idx = st.session_state.live_idx % n; ej = ejs[idx]
    st.markdown(f"<div class='live-card'><div class='live-title'>{ej}</div></div>", unsafe_allow_html=True)

    ca, cb, cc = st.columns(3)
    with ca:
        if st.button("⬅️ Anterior", use_container_width=True): st.session_state.live_idx = max(0, idx-1); st.rerun()
    with cb:
        pausa = st.selectbox("Descanso:", ["45s", "60s", "90s", "120s"], index=1)
        if st.button(f"⏱️ {pausa}", use_container_width=True):
            sg = int(pausa.replace("s","")); ph = st.empty()
            for i in range(sg, -1, -1): ph.metric("Descanso", f"{i}s"); time.sleep(1)
            ph.success("¡Listo!")
    with cc:
        if st.button("➡️️ Siguiente", use_container_width=True, type="primary"): st.session_state.live_idx = min(n-1, idx+1); st.rerun()

elif menu == "🧠 Plan Semanal":
    c = need_athlete()
    st.title(f"🧠 Plan Semanal — {c}")

    sk_mc = f"sel_microciclo_{c}"
    if sk_mc not in st.session_state:
        st.session_state[sk_mc] = st.session_state.planes_semanales.get(c, {}).get("tipo_semana", TIPOS_MICROCICLO[1])

    for dia in DIAS:
        sk_grp = f"sel_grupo_{c}_{dia}"
        if sk_grp not in st.session_state:
            st.session_state[sk_grp] = st.session_state.planes_semanales.get(c, {}).get(dia, "Descanso")

    st.markdown("### 1️⃣ Tipo de Semana")
    mc_cols = st.columns(3)
    for i, tipo in enumerate(TIPOS_MICROCICLO):
        with mc_cols[i]:
            if st.button(tipo, key=f"mc_b_{i}", type="primary" if st.session_state[sk_mc] == tipo else "secondary", use_container_width=True):
                st.session_state[sk_mc] = tipo; st.rerun()

    st.divider(); st.markdown("### 2️⃣ Días de Entrenamiento")
    for dia in DIAS:
        sk_grp = f"sel_grupo_{c}_{dia}"
        vd_act = st.session_state[sk_grp]
        with st.expander(f"📅 {dia} — {vd_act}", expanded=(vd_act != "Descanso")):
            st.session_state[sk_grp] = st.selectbox(f"Enfoque {dia}:", GRUPOS, index=GRUPOS.index(vd_act) if vd_act in GRUPOS else 0, key=f"sb_{dia}")
            if st.session_state[sk_grp] != "Descanso":
                prev = st.session_state.detalles_planes.get(c, {}).get(dia, "||").split("||")
                d0 = prev[0] if len(prev) > 0 else ""; d1 = prev[1] if len(prev) > 1 else ""; d2 = prev[2] if len(prev) > 2 else ""
                c1, c2, c3 = st.columns(3)
                cal = c1.text_area("🔥 Calentamiento", value=d0, key=f"cal_{dia}", height=120)
                des = c2.text_area("💪 Desarrollo", value=d1, key=f"des_{dia}", height=120)
                vue = c3.text_area("🧘 Vuelta a la calma", value=d2, key=f"vue_{dia}", height=120)
                st.session_state[f"det_res_{dia}"] = f"{cal}||{des}||{vue}"

    st.divider()
    ca_f, cb_f = st.columns(2)
    with ca_f:
        if st.button("💾 Guardar Plan Completo", type="primary", use_container_width=True):
            nf = {"tipo_semana": st.session_state[sk_mc]}; nd = {}
            for dia in DIAS:
                grp = st.session_state[f"sel_grupo_{c}_{dia}"]
                nf[dia] = grp
                nd[dia] = st.session_state.get(f"det_res_{dia}", "") if grp != "Descanso" else ""
            st.session_state.planes_semanales[c] = nf
            st.session_state.detalles_planes[c]  = nd
            guardar_datos(); st.toast("Plan guardado ✅"); st.rerun()

    with cb_f:
        if REPORTLAB_OK:
            pb = pdf_plan(c, st.session_state.planes_semanales.get(c, {}), st.session_state.detalles_planes.get(c, {}))
            if pb: st.download_button("📄 Descargar PDF", data=pb, file_name=f"Rutina_{c}.pdf", mime="application/pdf", use_container_width=True)

    # ENLACE SEGURO FIRMADO CON HMAC PARA WHATSAPP
    st.divider()
    st.markdown(f"### 🔗 Enlace Permanente para {c}")
    st.info("📲 **¡Copia y envía este link por WhatsApp!** Es 100% reutilizable y está firmado. El atleta no necesita clave y solo verá su propia rutina.")
    url_base = st.secrets.get("APP_URL", "https://biosport-app-skvkkvdkaojtifgiaavzob.streamlit.app")
    entrenador_actual = st.session_state.get("usuario_actual", "visho")
    link_firmado = construir_link(url_base, entrenador_actual, c)
    st.code(link_firmado, language="http")

elif menu == "📆 Mesociclo IA":
    c = need_athlete()
    st.title(f"📆 Mesociclo IA — {c}")
    obj_m = st.selectbox("Objetivo:", ["Hipertrofia", "Fuerza Máxima", "Resistencia", "Potencia"])
    sem = st.slider("Semanas:", 4, 12, 8)
    if st.button("🚀 Generar Mesociclo", type="primary"):
        if modelo_dante:
            with st.spinner("Diseñando..."):
                txt = dante_mesociclo(c, obj_m, sem, st.session_state.db_clientes)
                if txt:
                    st.session_state.mesociclos.setdefault(c, []).insert(0, {"fecha": fstr(hoy_chile()), "objetivo": obj_m, "semanas": sem, "contenido": txt})
                    guardar_datos(); st.rerun()

    for m in st.session_state.mesociclos.get(c, []):
        with st.expander(f"📅 {m['fecha']} — {m['objetivo']} ({m['semanas']} sem)"):
            st.markdown(m["contenido"])

elif menu == "🏃 Cardio":
    c = need_athlete()
    d = st.session_state.db_clientes[c]
    st.title(f"🏃 Cardio — {c}")
    vam = float(d.get("VAM", 0.0))
    nv = st.number_input("VAM actual (m/s):", 0.0, 10.0, vam, step=0.1)
    if st.button("Actualizar VAM"):
        st.session_state.db_clientes[c]["VAM"] = nv; guardar_datos(); st.toast("VAM Actualizada ✅")

elif menu == "🧪 Tests Físicos":
    c = need_athlete(); st.title(f"🧪 Tests Físicos — {c}")
    tt = st.selectbox("Test:", TIPOS_TEST); res = st.number_input("Resultado:", step=0.1)
    if st.button("💾 Guardar Test", type="primary"):
        st.session_state.tests_fisicos.setdefault(c, []).append({"Fecha": fstr(hoy_chile()), "Test": tt, "Resultado": res})
        guardar_datos(); st.toast("Test guardado ✅")

elif menu == "🥗 Nutrición":
    c = need_athlete(); d = st.session_state.db_clientes[c]; st.title(f"🥗 Nutrición — {c}")
    peso = float(d.get("Peso", 70)); tmb = calc_tmb(peso, float(d.get("Talla", 170)), int(d.get("Edad", 25)), d.get("Sexo", "Masculino"))
    act = st.selectbox("Nivel Actividad:", ["Sedentario", "Ligero (1-3 días)", "Moderado (3-5 días)", "Activo (6-7 días)"])
    get_ = calc_get(tmb, act)
    st.metric("Gasto Energético Estimado", f"{get_:.0f} kcal/día")

elif menu == "📈 Progreso":
    c = need_athlete(); st.title(f"📈 Progreso — {c}")
    df_all = pd.DataFrame([r for r in st.session_state.historial_global if r["Cliente"] == c])
    if df_all.empty: st.info("Sin registros aún."); st.stop()
    st.line_chart(df_all[df_all["Tipo"] == "Fuerza"], x="Fecha", y="Carga")

elif menu == "📚 Guías": 
    st.table(TABLA_BADILLO)
elif menu == "📝 Notas": 
    nt = st.text_area("Apuntes:", value=st.session_state.notas_personales, height=300)
    if st.button("Guardar"): st.session_state.notas_personales = nt; guardar_datos(); st.toast("Guardado")
elif menu == "🎥 Videoteca":
    st.dataframe(pd.DataFrame(list(st.session_state.biblioteca_videos.items()), columns=["Ejercicio", "Enlace"]))

elif menu == "👑 Panel Admin":
    st.title("👑 Panel de Control Bio Sport")
    if st.button("🔄 Actualizar Datos de la Nube", use_container_width=True):
        st.session_state.pop("admin_cache", None); st.rerun()

    if "admin_cache" not in st.session_state:
        with st.spinner("Descargando base de datos segura..."):
            client = _gs_client(); sheet = client.open_by_url(URL_SHEET); usr_db = cargar_usuarios_sistema()
            datos_entrenadores = {}
            for usr in usr_db.keys():
                try:
                    ws = sheet.worksheet(usr); vals = ws.col_values(1)
                    if vals: datos_entrenadores[usr] = json.loads("".join(vals))
                except Exception: datos_entrenadores[usr] = {}
            st.session_state.admin_cache = {"usuarios": usr_db, "datos": datos_entrenadores}

    cache = st.session_state.admin_cache
    usuarios_db = cache["usuarios"]; datos_completos = cache["datos"]

    tab_usuarios, tab_cobros, tab_ranking = st.tabs(["👥 Preparadores", "💰 Cobros", "🏆 Ranking"])
    with tab_usuarios:
        st.subheader("Preparadores")
        if usuarios_db:
            st.dataframe(pd.DataFrame([{"Usuario": u, "Nombre": i.get("nombre_completo", "—"), "Cobro": i.get("tipo_cobro")} for u, i in usuarios_db.items()]))
        with st.expander("➕ Registrar nuevo preparador"):
            un = st.text_input("Usuario (sin espacios):")
            pn = st.text_input("Contraseña:", type="password")
            nn = st.text_input("Nombre completo:")
            tc = st.selectbox("Modalidad:", ["por_alumno", "fijo_mensual"])
            vc = st.number_input("Valor ($):", value=2500)
            if st.button("Crear cuenta", type="primary"):
                ok, msg = registrar_usuario_sistema(un, pn, nn, tc, vc)
                if ok: 
                    st.success("Registrado correctamente"); st.session_state.pop("admin_cache", None); st.rerun()
                else: 
                    st.error(msg)

    with tab_cobros:
        st.subheader("Cobros del Mes")
        cobros = []; total = 0
        for usr, info in usuarios_db.items():
            n = len(datos_completos.get(usr, {}).get("clientes", {}))
            tc = info.get("tipo_cobro", "por_alumno")
            vc = int(info.get("valor_cobro", 0))
            mo = n * vc if tc == "por_alumno" else vc
            cobros.append({"Preparador": usr, "Alumnos": n, "Total": f"${mo:,}"})
            total += mo
        st.dataframe(pd.DataFrame(cobros))
        st.metric("Total a Recaudar", f"${total:,}")

    with tab_ranking:
        st.subheader("Ranking Actividad (30 días)")
        rank = []
        for usr, info in usuarios_db.items():
            for nom in datos_completos.get(usr, {}).get("clientes", {}):
                r30 = [r for r in datos_completos.get(usr, {}).get("historial", []) if r.get("Cliente")==nom]
                rank.append({"Atleta": nom, "Preparador": usr, "Sesiones": len(r30)})
        if rank:
            st.dataframe(pd.DataFrame(rank).sort_values("Sesiones", ascending=False))
