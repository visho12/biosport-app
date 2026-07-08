# =====================================================
# BIO SPORT PRO TRAINER v3.0
# Migracion segura — compatible con datos existentes
# =====================================================
import streamlit as st
import pandas as pd
import math, time, json, io, hashlib, gspread
from google.oauth2.service_account import Credentials
from datetime import date, datetime, timedelta

from domain.calculators import calc_1rm, calc_durnin, eval_grasa, calc_tmb, calc_get
from core.constants import (
    VIDEOS_BASE, OBJETIVOS, TIPOS_CARDIO, TIPOS_TEST, DIAS, GRUPOS,
    TIPOS_MICROCICLO, TABLA_BADILLO, GUIAS_BOMPA, GUIA_TEMPO,
    GUIA_DESCANSOS, ESCALA_RPE, ESCALA_BORG, GUIA_CARDIO, TABLA_ZONAS_FCM
)
from database.sheets_db import URL_SHEET, _gs_client, cargar_datos, guardar_datos, registrar_auditoria
from core.auth import (
    login, registrar_usuario_sistema, eliminar_usuario_sistema, 
    cambiar_password_usuario, cargar_usuarios_sistema
)
# --- IA ---
import google.generativeai as genai
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    _mv = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
    modelo_dante = genai.GenerativeModel(_mv[0]) if _mv else None
except Exception:
    modelo_dante = None

# --- PDF ---
try:
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.colors import HexColor
    from reportlab.lib import colors
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

# --- EXCEL ---
try:
    import openpyxl
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False

# =====================================================
# PAGINA
# =====================================================
st.set_page_config(page_title="Bio Sport Pro", layout="wide", page_icon="⚡")
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
</style>
""", unsafe_allow_html=True)

# =====================================================
# AUTENTICACION — Sistema dinamico con registro
# Superusuario: visho (hardcodeado)
# Resto de usuarios: guardados en hoja "usuarios_sistema" de Sheets
# =====================================================
def _hash(p): return hashlib.sha256(p.encode()).hexdigest()

ADMIN_USER = "visho"
ADMIN_PASS = st.secrets.get("PW_VISHO", "Bio2026")

def _get_hoja_usuarios(sheet):
    try:
        return sheet.worksheet("usuarios_sistema")
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title="usuarios_sistema", rows="200", cols="6")
        ws.append_row(["usuario","password_hash","nombre_completo",
                       "tipo_cobro","valor_cobro","fecha_registro"])
        return ws

@st.cache_data(ttl=600) # Memoria caché (10 min) para no colapsar el login
def cargar_usuarios_sistema():
    client = _gs_client()
    sheet  = client.open_by_url(URL_SHEET)
    ws     = _get_hoja_usuarios(sheet)
    rows   = ws.get_all_records()
    return {str(r["usuario"]).lower().strip(): r for r in rows if r.get("usuario")}

def registrar_usuario_sistema(usuario, password, nombre, tipo_cobro, valor_cobro):
    usuario = usuario.lower().strip()
    if not usuario or not password:
        return False, "Usuario y contraseña son obligatorios."
    if len(password) < 6:
        return False, "La contraseña debe tener al menos 6 caracteres."
    try:
        client  = _gs_client()
        sheet   = client.open_by_url(URL_SHEET)
        ws      = _get_hoja_usuarios(sheet)
        existentes = [r["usuario"] for r in ws.get_all_records() if r.get("usuario")]
        if usuario in existentes:
            return False, "El usuario ya existe."
        ws.append_row([
            usuario, _hash(password), nombre.strip(),
            tipo_cobro, valor_cobro,
            datetime.now().strftime("%d/%m/%Y %H:%M")
        ])
        cargar_usuarios_sistema.clear() # Limpiamos caché para que detecte al nuevo
        return True, ""
    except Exception as e:
        return False, str(e)

def eliminar_usuario_sistema(usuario):
    try:
        client = _gs_client()
        sheet  = client.open_by_url(URL_SHEET)
        ws     = _get_hoja_usuarios(sheet)
        celdas = ws.col_values(1)
        for i, val in enumerate(celdas):
            if val == usuario:
                ws.delete_rows(i + 1)
                cargar_usuarios_sistema.clear() # Limpiamos caché
                return True
    except Exception:
        pass
    return False

def cambiar_password_usuario(usuario, nueva_password):
    try:
        client = _gs_client()
        sheet  = client.open_by_url(URL_SHEET)
        ws     = _get_hoja_usuarios(sheet)
        celdas = ws.col_values(1)
        for i, val in enumerate(celdas):
            if val == usuario:
                ws.update_cell(i + 1, 2, _hash(nueva_password))
                cargar_usuarios_sistema.clear() # Limpiamos caché
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
        # Ahora si falla, te avisará en lugar de decir "contraseña incorrecta"
        st.error("⚠️ Google Sheets está saturado (Límite de lecturas). Espera 1 minuto.")
    return False

def get_info_usuario(u):
    if u == ADMIN_USER:
        return {"nombre_completo":"Administrador","tipo_cobro":"admin","valor_cobro":0}
    try:
        return cargar_usuarios_sistema().get(u, {})
    except Exception:
        return {}

def login():
    if not st.session_state.get("autenticado", False):
        st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@400;600&display=swap');
        [data-testid="stSidebar"]{display:none}
        [data-testid="collapsedControl"]{display:none}
        .stApp{background:radial-gradient(ellipse at top,#0a1a0a 0%,#0d0d0d 60%)}
        .login-logo{text-align:center;padding:48px 0 32px}
        .login-titulo{font-family:'Bebas Neue',sans-serif;font-size:3.6rem;color:#39FF14;
                      letter-spacing:6px;line-height:1;text-shadow:0 0 30px rgba(57,255,20,.4)}
        .login-sub{color:#555;font-size:.82rem;letter-spacing:3px;margin-top:6px;
                   text-transform:uppercase;font-family:'DM Sans',sans-serif}
        .login-card{background:linear-gradient(135deg,#111 0%,#1a1a1a 100%);
                    border:1px solid #1f1f1f;border-radius:16px;padding:32px 36px;
                    box-shadow:0 20px 60px rgba(0,0,0,.6),0 0 0 1px rgba(57,255,20,.08)}
        .stTextInput input{background:#0d0d0d!important;border:1px solid #2a2a2a!important;
                           border-radius:8px!important;color:#f0f0f0!important;
                           padding:12px 14px!important;font-size:1rem!important;
                           transition:border-color .2s!important}
        .stTextInput input:focus{border-color:#39FF14!important;
                                 box-shadow:0 0 0 2px rgba(57,255,20,.15)!important}
        .stTextInput label{color:#888!important;font-size:.82rem!important;
                           letter-spacing:1px!important;text-transform:uppercase!important}
        .stFormSubmitButton button{background:#39FF14!important;color:#000!important;
                                   font-family:'Bebas Neue',sans-serif!important;
                                   font-size:1.2rem!important;letter-spacing:3px!important;
                                   border-radius:8px!important;border:none!important;
                                   padding:14px!important;width:100%!important;
                                   box-shadow:0 4px 20px rgba(57,255,20,.3)!important;
                                   transition:all .2s!important}
        .stFormSubmitButton button:hover{background:#5fff3a!important;
                                         box-shadow:0 6px 30px rgba(57,255,20,.5)!important;
                                         transform:translateY(-1px)!important}
        .stTabs [data-baseweb="tab-list"]{gap:4px;background:transparent}
        .stTabs [data-baseweb="tab"]{color:#555;font-weight:600;font-size:.85rem;letter-spacing:1px}
        .stTabs [aria-selected="true"]{color:#39FF14!important;border-bottom-color:#39FF14!important}
        .login-footer{text-align:center;color:#333;font-size:.75rem;letter-spacing:1px;
                      margin-top:32px;font-family:'DM Sans',sans-serif}
        </style>""", unsafe_allow_html=True)

        st.markdown("""
        <div class='login-logo'>
            <div class='login-titulo'>BIO SPORT</div>
            <div class='login-sub'>Plataforma de Alto Rendimiento</div>
        </div>""", unsafe_allow_html=True)

        _, col, _ = st.columns([1, 1.4, 1])
        with col:
            st.markdown("<div class='login-card'>", unsafe_allow_html=True)
            tab_entrar, tab_ayuda = st.tabs(["Ingresar", "Sin acceso"])
            with tab_entrar:
                st.markdown("<br>", unsafe_allow_html=True)
                with st.form("login_form"):
                    u = st.text_input("Usuario", placeholder="tu usuario").lower().strip()
                    pw = st.text_input("Contrasena", type="password", placeholder="...")
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button("ENTRAR AL SISTEMA", type="primary", use_container_width=True):
                        if not u or not pw:
                            st.error("Completa usuario y contrasena.")
                        elif validar_usuario(u, pw):
                            info = get_info_usuario(u)
                            st.session_state.autenticado    = True
                            st.session_state.usuario_actual = u
                            st.session_state.nombre_usuario = info.get("nombre_completo", u.capitalize())
                            st.session_state.es_admin       = (u == ADMIN_USER)
                            st.rerun()
                        else:
                            st.error("Usuario o contrasena incorrectos.")
            with tab_ayuda:
                st.markdown("<br>", unsafe_allow_html=True)
                st.info("Contacta al administrador para obtener tu acceso. El te creara tu cuenta directamente desde la plataforma.")
                st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='login-footer'>BIO SPORT PRO - Plataforma de Entrenamiento Profesional</div>",
                    unsafe_allow_html=True)
        return False
    return True

if not login(): st.stop()

_nombre_sb = st.session_state.get("nombre_usuario", st.session_state["usuario_actual"].capitalize())
st.sidebar.markdown(f"**{_nombre_sb}**")
if st.sidebar.button("Cerrar sesion", key="btn_cerrar_sesion"):
    for k in list(st.session_state): del st.session_state[k]
    st.rerun()

# =====================================================
# CALCULOS
# =====================================================

def analizar_progreso(df_ej):
    if len(df_ej) < 3:
        return "sin_datos", "Necesitas al menos 3 registros para analizar.", "inf"
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
    if u[0] == u[1] == u[2]:
        return "estancado", f"⚠️ Estancamiento: {u[0]}kg en 3 sesiones seguidas. Considera descarga o cambio de estímulo.", "warn"
    if u[2] < u[0]:
        return "baja", f"📉 Bajada de {u[0]-u[2]:.1f}kg vs sesión de referencia. Revisa fatiga, sueño y nutrición.", "err"
    if tasa and tasa > 1.5:
        return "rapido", f"🔥 Progreso sólido: +{tasa:.1f}% por sesión en promedio. ¡Muy bien!", "ok"
    if u[2] > u[1]:
        return "ok_", f"✅ Progresando: {u[1]}kg → {u[2]}kg en la última sesión.", "ok"
    return "estable", "📊 Carga estable. Evalúa si es momento de sobrecarga progresiva.", "inf"

def calc_adherencia(cliente):
    hoy = date.today()
    dp = de = 0
    for i in range(30):
        dia = hoy - timedelta(days=29-i)
        nd  = DIAS[dia.weekday()]
        f   = st.session_state.planes_semanales.get(cliente, {}).get(nd, "Descanso")
        if f not in ("Descanso", ""):
            dp += 1
            fs = dia.strftime("%d/%m/%Y")
            if any(h["Cliente"]==cliente and h["Fecha"]==fs
                   for h in st.session_state.historial_global):
                de += 1
    pct = de/dp*100 if dp else 0
    return de, dp, pct

def parse_tiempo(t):
    try:
        t = str(t).strip()
        if ":" in t:
            a, b = t.split(":")
            return int(a)*60 + int(b)
        v = float(t)
        return int(v*60) if v < 10 else int(v)
    except Exception:
        return 90

def fstr(d): return d.strftime("%d/%m/%Y")
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
    hoy = date.today()
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
            except Exception:
                pass
    for dia, lista in rt.items():
        if lista:
            nd[dia] = f"||{chr(10).join(lista)}||"
            nf[dia] = ft[dia] if ft[dia]!="Descanso" else "Entrenamiento"
    st.session_state.planes_semanales[cliente] = nf
    st.session_state.detalles_planes[cliente]  = nd
    guardar_datos()

# =====================================================
# GENERADORES
# =====================================================
def pdf_plan(cliente, focos, detalles):
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
    cv.drawRightString(W-50,H-56,f"Fecha: {date.today():%d/%m/%Y}")

    y = H-110
    ts = focos.get("tipo_semana","")
    if ts:
        cv.setFont("Helvetica-Bold",11); cv.setFillColor(NEON)
        cv.drawString(50,y,f"Microciclo: {ts}"); y -= 22

    for dia in DIAS:
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

def excel_historial(cliente):
    if not OPENPYXL_OK: return None
    regs = [r for r in st.session_state.historial_global if r["Cliente"]==cliente]
    if not regs: return None
    df  = pd.DataFrame(regs); buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Historial")
        ws = w.sheets["Historial"]
        for col in ws.columns:
            ml = max(len(str(c.value or "")) for c in col)
            ws.column_dimensions[col[0].column_letter].width = min(ml+3,40)
    buf.seek(0); return buf

def dante_mesociclo(cliente, objetivo, semanas):
    if not modelo_dante: return None
    d = st.session_state.db_clientes.get(cliente,{})
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
# INICIALIZACION SEGURA DE ESTADO
# =====================================================
# Cargamos UNA SOLA VEZ por sesión
if "datos_cargados" not in st.session_state:
    _raw = cargar_datos()
    # Si hay datos guardados los usamos; si no, defaults vacíos
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
    # Claves nuevas — si no existen en datos guardados arrancan vacíos
    st.session_state.tests_fisicos      = _get("tests",           {})
    st.session_state.mesociclos         = _get("mesociclos",      {})
    st.session_state.datos_cargados     = True

# Estado de UI (no se guarda en Sheets)
for _k, _v in [("cliente_activo",None),("confirm_delete",False),
               ("live_idx",0)]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# =====================================================
# SIDEBAR
# =====================================================
st.sidebar.header("⚡ Bio Sport Pro")
lista = ["Crear Nuevo..."] + list(st.session_state.db_clientes.keys())
sel   = st.sidebar.selectbox("Atleta:", lista)

if sel == "Crear Nuevo...":
    nom = st.sidebar.text_input("Nombre del nuevo atleta:")
    if st.sidebar.button("Guardar Atleta", type="primary", key="btn_guardar_atleta"):
        n = nom.strip()
        if n and n not in st.session_state.db_clientes:
            st.session_state.db_clientes[n] = {
                "Peso":70,"Talla":170,"Edad":25,"Sexo":"Masculino"}
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
                st.session_state.historial_global = [
                    h for h in st.session_state.historial_global if h["Cliente"]!=sel]
                for _d in [st.session_state.planes_semanales,
                            st.session_state.detalles_planes,
                            st.session_state.tests_fisicos,
                            st.session_state.mesociclos]:
                    _d.pop(sel, None)
                guardar_datos()
                st.session_state.cliente_activo = None
                st.session_state.confirm_delete = False
                st.rerun()
            if cb.button("❌ Cancelar", key="btn_cancelar_eliminar"):
                st.session_state.confirm_delete = False; st.rerun()

        js = json.dumps({
            "clientes":  st.session_state.db_clientes,
            "historial": st.session_state.historial_global,
        }, indent=2, ensure_ascii=False)
        st.download_button("💾 Backup JSON", data=js,
                           file_name="backup_biosport.json", mime="application/json")

with st.sidebar.expander("🧮 Calculadora RM", expanded=False):
    _p = st.number_input("Peso (kg)", 0.0, step=0.5, key="rm_p")
    _r = st.number_input("Reps",      1, 20, 8,      key="rm_r")
    if _p > 0:
        _rm = calc_1rm(_p, _r)
        st.markdown(
            f"<div style='background:#1a1a1a;border:1px solid #39FF14;"
            f"border-radius:8px;padding:10px;text-align:center;margin:6px 0'>"
            f"<div style='color:#888;font-size:.75rem;letter-spacing:1px'>1RM ESTIMADO</div>"
            f"<div style='color:#39FF14;font-size:1.6rem;font-weight:700;"
            f"font-family:Bebas Neue,sans-serif'>{_rm:.1f} kg</div>"
            f"</div>",
            unsafe_allow_html=True
        )
        filas = ""
        for pct in [95, 90, 85, 80, 75, 70, 65, 60, 55, 50]:
            val   = _rm * pct / 100
            color = "#39FF14" if pct >= 85 else "#FFD700" if pct >= 70 else "#00BFFF"
            filas += (
                f"<div style='display:flex;justify-content:space-between;"
                f"padding:4px 8px;border-radius:4px;margin:2px 0;background:#1a1a1a'>"
                f"<span style='color:#888;font-size:.8rem'>{pct}%</span>"
                f"<span style='color:{color};font-weight:700;font-size:.9rem'>{val:.1f} kg</span>"
                f"</div>"
            )
        st.markdown(filas, unsafe_allow_html=True)
    else:
        st.caption("Ingresa peso y reps para calcular.")

MENU_ITEMS = [
    "🏠 Dashboard",
    "📋 Ficha & Antropo",
    "💪 Entrenamiento",
    "🏋️ Modo En Vivo",
    "🧠 Plan Semanal",
    "📆 Mesociclo IA",
    "🏃 Cardio",
    "🧪 Tests Físicos",
    "🥗 Nutrición",
    "📈 Progreso",
    "📚 Guías",
    "📝 Notas",
    "🎥 Videoteca",
]
if st.session_state.get("usuario_actual") == "visho":
    MENU_ITEMS.append("👑 Panel Admin")

menu = st.sidebar.radio("Menú:", MENU_ITEMS)
st.sidebar.divider()
if st.session_state.cliente_activo:
    st.sidebar.success(f"Atleta activo: {st.session_state.cliente_activo}")

# helper
def need_athlete():
    if not st.session_state.cliente_activo:
        st.warning("Selecciona un atleta en el menú lateral.")
        st.stop()
    return st.session_state.cliente_activo

# =====================================================
# 🏠 DASHBOARD
# =====================================================
if menu == "🏠 Dashboard":
    st.title("⚡ Dashboard Bio Sport")
    n_at  = len(st.session_state.db_clientes)
    hoy_s = date.today().strftime("%d/%m/%Y")
    n_hoy = sum(1 for h in st.session_state.historial_global if h["Fecha"]==hoy_s)
    n_tot = len(st.session_state.historial_global)

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("👥 Atletas",           n_at)
    c2.metric("🔥 Sesiones hoy",      n_hoy)
    c3.metric("📊 Registros totales", n_tot)
    c4.metric("📅 Hoy",              hoy_s)

    if st.session_state.db_clientes:
        st.divider(); st.subheader("Estado de Atletas")
        rows = []
        for nom, dat in st.session_state.db_clientes.items():
            regs = [h for h in st.session_state.historial_global if h["Cliente"]==nom]
            ult  = regs[-1]["Fecha"] if regs else "—"
            de, dp, pct = calc_adherencia(nom)
            rows.append({"Atleta":nom,
                         "Objetivo":dat.get("Objetivo_Prin","—"),
                         "Experiencia":dat.get("Experiencia","—"),
                         "Sesiones":len(regs),
                         "Último registro":ult,
                         "Adherencia 30d":f"{pct:.0f}%"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.divider(); st.subheader("📊 Adherencia (últimos 30 días)")
        for nom in st.session_state.db_clientes:
            de, dp, pct = calc_adherencia(nom)
            color = "#39FF14" if pct>=80 else "#FFD700" if pct>=50 else "#FF4B4B"
            w = min(int(pct),100)
            st.markdown(f"""
            <div style='margin-bottom:10px'>
              <span style='font-weight:600'>{nom}</span>
              <span style='float:right;color:{color};font-weight:700'>{pct:.0f}%
                &nbsp;({de}/{dp} días)</span>
              <div class='adh-bar'>
                <div style='height:12px;border-radius:6px;width:{w}%;background:{color}'></div>
              </div>
            </div>""", unsafe_allow_html=True)

# =====================================================
# 📋 FICHA & ANTROPO
# =====================================================
elif menu == "📋 Ficha & Antropo":
    c = need_athlete()
    d = st.session_state.db_clientes[c]
    tb1, tb2, tb3 = st.tabs(["📝 Datos Básicos","📏 Antropometría","🏥 Anamnesis"])

    with tb1:
        co1,co2,co3,co4 = st.columns(4)
        np_ = co1.number_input("Peso (kg)",  0.1, 250.0, float(d.get("Peso",70)),  step=0.5)
        nt_ = co2.number_input("Talla (cm)", 50.0,250.0, float(d.get("Talla",170)), step=0.5)
        ne_ = co3.number_input("Edad",       5,   100,   int(d.get("Edad",25)))
        ns_ = co4.selectbox("Sexo",["Masculino","Femenino"],
                            index=0 if d.get("Sexo","Masculino")=="Masculino" else 1)
        imc = np_/((nt_/100)**2)
        st.caption(f"IMC: **{imc:.1f}**")
        if st.button("💾 Actualizar Datos", type="primary", key="btn_actualizar_datos"):
            st.session_state.db_clientes[c].update(
                {"Peso":np_,"Talla":nt_,"Edad":ne_,"Sexo":ns_})
            guardar_datos(); st.toast("Datos actualizados ✅")
        st.divider()
        if st.checkbox("❤️ Calcular FCM (Tanaka)"):
            fcm = 208 - 0.7*ne_
            st.info(f"FCM estimada: **{fcm:.0f} lpm**")
            zc = st.columns(5)
            for i,(p,z) in enumerate([(60,"Z1"),(75,"Z2"),(85,"Z3"),(95,"Z4"),(100,"Z5")]):
                zc[i].metric(z, f"{fcm*p/100:.0f}")

    with tb2:
        st.subheader("Cálculo de Grasa — Durnin 4 Pliegues")
        ci, co = st.columns(2)
        with ci:
            p1 = st.number_input("Bíceps mm",        0.0,100.0,0.0,step=0.1)
            p2 = st.number_input("Tríceps mm",       0.0,100.0,0.0,step=0.1)
            p3 = st.number_input("Subescapular mm",  0.0,100.0,0.0,step=0.1)
            p4 = st.number_input("Suprailiaco mm",   0.0,100.0,0.0,step=0.1)
            suma = p1+p2+p3+p4
        with co:
            if suma > 0:
                try:
                    gr = calc_durnin(d.get("Edad",25), d.get("Sexo","Masculino"), suma)
                    if not (2 <= gr <= 60):
                        st.warning(f"Resultado fuera de rango: {gr:.1f}% — verifica pliegues.")
                    else:
                        peso = d.get("Peso",70)
                        mm = peso*(1-gr/100)
                        st.metric("% Grasa",    f"{gr:.1f}%")
                        st.metric("Masa Magra", f"{mm:.1f} kg")
                        st.metric("Masa Grasa", f"{peso-mm:.1f} kg")
                        cat, col_ = eval_grasa(d.get("Edad",25), d.get("Sexo","Masculino"), gr)
                        st.markdown(f"""<div style='background:#2D2D2D;padding:14px;
                          border-radius:8px;text-align:center;border:1px solid {col_};
                          margin-top:10px'>
                          <div style='color:#aaa;font-size:11px'>Clasificación</div>
                          <div style='color:{col_};font-size:1.3rem;font-weight:700'>{cat}
                          </div></div>""", unsafe_allow_html=True)
                except ValueError as e:
                    st.error(f"Error: {e}")
            else:
                st.info("Ingresa los 4 pliegues para calcular.")

    with tb3:
        co1,co2 = st.columns(2)
        fono = co1.text_input("📱 Teléfono",           value=d.get("Telefono",""))
        eme  = co2.text_input("🚨 Contacto Emergencia", value=d.get("Emergencia",""))
        les  = st.text_area("🩹 Lesiones",              value=d.get("Lesiones",""),    height=80)
        enf  = st.text_area("💊 Enfermedades/Medicamentos", value=d.get("Enfermedades",""), height=70)
        co3,co4 = st.columns(2)
        ops = ["Principiante","Intermedio","Avanzado"]
        ea  = d.get("Experiencia","Principiante"); ea = ea if ea in ops else "Principiante"
        exp = co3.selectbox("🏋️ Experiencia", ops, index=ops.index(ea))
        obj = co4.text_input("🎯 Objetivo Principal", value=d.get("Objetivo_Prin",""))
        est = st.text_area("💼 Estilo de Vida", value=d.get("Estilo_Vida",""), height=70)
        if st.button("💾 Guardar Anamnesis", type="primary", key="btn_guardar_anamnesis"):
            st.session_state.db_clientes[c].update({
                "Telefono":fono,"Emergencia":eme,"Lesiones":les,"Enfermedades":enf,
                "Experiencia":exp,"Objetivo_Prin":obj,"Estilo_Vida":est})
            guardar_datos(); st.toast("Historial guardado ✅")

# =====================================================
# 💪 ENTRENAMIENTO
# =====================================================
elif menu == "💪 Entrenamiento":
    c = need_athlete()
    fecha = st.date_input("📅 Fecha:", date.today())
    dia   = DIAS[fecha.weekday()]
    foco  = st.session_state.planes_semanales.get(c,{}).get(dia,"Sin planificar")
    det   = st.session_state.detalles_planes.get(c,{}).get(dia,"")

    if foco == "Descanso":
        st.success(f"🛌 {dia}: Descanso planificado")
    else:
        st.info(f"🔥 {dia}: {foco}")
        if det:
            with st.expander("👀 Ver plan del día", expanded=True):
                pts = det.split("||")
                if len(pts)==3:
                    if pts[0].strip(): st.markdown("**1️⃣ Calentamiento:**\n"+pts[0])
                    if pts[1].strip(): st.markdown("**2️⃣ Desarrollo:**\n"+pts[1])
                    if pts[2].strip(): st.markdown("**3️⃣ Vuelta a la Calma:**\n"+pts[2])
                else:
                    st.text(det)
    st.divider()

    col_e, col_t = st.columns([3,1])
    with col_e:
        obj_  = st.selectbox("🎯 Objetivo:", list(OBJETIVOS.keys()))
        sug   = OBJETIVOS[obj_]
        st.caption(f"Guía: {sug['Reps']} reps · {sug['RM']} · "
                   f"Pausa: {sug['Pausa']} · RPE: {sug['RPE']}")

        ej_ = st.selectbox("Ejercicio:",
                           list(st.session_state.biblioteca_videos.keys())+["✍️ Otro..."])
        if ej_ != "✍️ Otro...":
            ur = ult_reg(c, ej_)
            if ur:
                st.info(f"💡 Último: {ur['Series']}x{ur['Reps']} @ {ur['Carga']}kg")
                rm_ = calc_1rm(ur["Carga"], ur["Reps"])
                st.caption(f"1RM est: {rm_:.1f}kg · 80%:{rm_*.8:.1f} · 70%:{rm_*.7:.1f}")

        nom = st.text_input("Nombre:", value="" if ej_=="✍️ Otro..." else ej_)
        c1,c2,c3 = st.columns(3)
        se  = c1.number_input("Series", 1,10,4)
        re  = c2.number_input("Reps",   1,50,10)
        kg  = c3.number_input("Carga kg", 0.0, step=0.5)
        pt  = st.text_input("Pausa",  value=sug["Pausa"])
        rpe = st.slider("RPE", 1, 10, 7)

        if st.button("➕ Registrar Serie", type="primary", key="btn_registrar_serie"):
            if nom.strip():
                st.session_state.historial_global.append({
                    "Cliente":   c,
                    "Fecha":     fstr(fecha),
                    "Ejercicio": nom.strip(),
                    "Series":    se, "Reps": re, "Carga": kg,
                    "RPE":       rpe, "Tipo":"Fuerza", "Objetivo":obj_,
                })
                guardar_datos(); st.toast("Serie registrada 💪"); st.rerun()
            else:
                st.warning("Escribe el nombre del ejercicio.")

        hist_hoy = [h for h in st.session_state.historial_global
                    if h["Cliente"]==c and h["Fecha"]==fstr(fecha)]
        if hist_hoy:
            st.divider(); st.subheader(f"📝 Sesión {fstr(fecha)}")
            vol = sum(h["Series"]*h["Reps"]*h["Carga"]
                      for h in hist_hoy if h.get("Tipo")=="Fuerza")
            st.caption(f"Volumen total: **{vol:.0f} kg·rep**")
            for i, h in enumerate(st.session_state.historial_global):
                if h["Cliente"]==c and h["Fecha"]==fstr(fecha):
                    ci2, cd2 = st.columns([4,1])
                    ci2.write(f"✅ {h['Ejercicio']}: {h['Series']}x{h['Reps']}"
                              f" @ {h['Carga']}kg (RPE {h.get('RPE','-')})")
                    if cd2.button("🗑️", key=f"del_{i}"):
                        del st.session_state.historial_global[i]
                        guardar_datos(); st.rerun()

    with col_t:
        st.write("⏱️ Timer")
        seg = parse_tiempo(pt)
        st.caption(f"Pausa: {seg}s")
        if st.button("▶ Iniciar", key="btn_timer_ent"):
            ph = st.empty(); bar = st.progress(0.0)
            for i in range(seg, -1, -1):
                ph.metric("Restante", f"{i}s")
                bar.progress(1.0 - i/seg if seg else 1.0)
                time.sleep(1)
            ph.success("✅ ¡Tiempo!")
            bar.empty()

# =====================================================
# 🏋️ MODO EN VIVO
# =====================================================
elif menu == "🏋️ Modo En Vivo":
    c   = need_athlete()
    hoy = date.today()
    dia = DIAS[hoy.weekday()]
    det  = st.session_state.detalles_planes.get(c,{}).get(dia,"")
    foco = st.session_state.planes_semanales.get(c,{}).get(dia,"Sin planificar")

    st.title(f"🏋️ En Vivo — {c}")
    st.caption(f"{dia} · {foco}")

    ejs = []
    if det:
        pts = det.split("||")
        blq = pts[1] if len(pts)>1 else pts[0] if pts else ""
        ejs = [l.strip() for l in blq.split("\n") if l.strip()]

    if not ejs:
        st.info(f"No hay ejercicios planificados para {dia}. "
                f"Agrégalos en Plan Semanal."); st.stop()

    n   = len(ejs)
    idx = st.session_state.live_idx % n
    ej  = ejs[idx]

    st.markdown(f"""<div class='live-card'>
      <div style='color:#888;font-size:.8rem;letter-spacing:2px;text-transform:uppercase'>
        Ejercicio {idx+1} de {n}</div>
      <div class='live-title'>{ej}</div>
      <div style='color:#aaa;margin-top:8px'>Controla el movimiento · Respira</div>
    </div>""", unsafe_allow_html=True)

    ca, cb, cc = st.columns(3)
    with ca:
        if st.button("⬅️ Anterior", use_container_width=True, key="btn_live_prev"):
            st.session_state.live_idx = max(0, idx-1); st.rerun()
    with cb:
        pausa = st.selectbox("Descanso:",["45s","60s","90s","120s","180s","300s"],
                             index=2, label_visibility="collapsed")
        if st.button(f"⏱️ {pausa}", use_container_width=True, key="btn_live_timer"):
            sg = int(pausa.replace("s",""))
            ph = st.empty(); bar = st.progress(0.0)
            for i in range(sg, -1, -1):
                ph.metric("Descansando", f"{i}s")
                bar.progress(1.0 - i/sg if sg else 1.0)
                time.sleep(1)
            ph.success("¡A por la siguiente serie!")
    with cc:
        if st.button("➡️ Siguiente", use_container_width=True, type="primary", key="btn_live_next"):
            st.session_state.live_idx = min(n-1, idx+1); st.rerun()

    st.divider(); st.subheader("📝 Registrar serie rápida")
    q1,q2,q3 = st.columns(3)
    seq = q1.number_input("Series",1,10,4,key="lv_se")
    req = q2.number_input("Reps",  1,50,10,key="lv_re")
    kgq = q3.number_input("Carga", 0.0,step=0.5,key="lv_kg")
    if st.button("✅ Guardar serie", type="primary", key="btn_live_guardar"):
        nombre_ej = ej.split(":")[0].strip()
        st.session_state.historial_global.append({
            "Cliente":c,"Fecha":fstr(hoy),"Ejercicio":nombre_ej,
            "Series":seq,"Reps":req,"Carga":kgq,
            "RPE":7,"Tipo":"Fuerza","Objetivo":foco,
        })
        guardar_datos(); st.toast(f"✅ {nombre_ej} guardado")

    st.divider(); st.subheader("Lista de hoy")
    for i, e in enumerate(ejs):
        col = "#39FF14" if i==idx else "#444"
        st.markdown(f"<div style='padding:5px 12px;border-left:3px solid {col};"
                    f"margin:2px 0;font-size:.9rem'>{i+1}. {e}</div>",
                    unsafe_allow_html=True)

# =====================================================
# 🧠 PLAN SEMANAL — Fix selección tipo semana y grupos
# =====================================================
elif menu == "🧠 Plan Semanal":
    c = need_athlete()

    # CSS extra para tarjetas de días
    st.markdown("""
    <style>
    .dia-card {
        background: linear-gradient(135deg,#1a1a1a,#222);
        border: 1px solid #333;
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 10px;
        transition: border-color .2s;
    }
    .dia-card:hover { border-color: #555; }
    .dia-header {
        display: flex; justify-content: space-between;
        align-items: center; margin-bottom: 6px;
    }
    .dia-nombre {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 1.2rem; letter-spacing: 2px; color: #fff;
    }
    .dia-badge {
        font-size: .75rem; font-weight: 700;
        padding: 3px 10px; border-radius: 20px;
        text-transform: uppercase; letter-spacing: 1px;
    }
    .badge-descanso { background:#1a1a1a; color:#555; border:1px solid #333; }
    .badge-pierna   { background:#1a0d2e; color:#9b59b6; border:1px solid #9b59b6; }
    .badge-pecho    { background:#0d1f2e; color:#3498db; border:1px solid #3498db; }
    .badge-espalda  { background:#0d2e1a; color:#2ecc71; border:1px solid #2ecc71; }
    .badge-gluteo   { background:#2e1a0d; color:#e67e22; border:1px solid #e67e22; }
    .badge-full     { background:#2e0d0d; color:#e74c3c; border:1px solid #e74c3c; }
    .badge-torso    { background:#0d2e2e; color:#1abc9c; border:1px solid #1abc9c; }
    .badge-brazo    { background:#2e2e0d; color:#f1c40f; border:1px solid #f1c40f; }
    .badge-cardio   { background:#0d1a2e; color:#00BFFF; border:1px solid #00BFFF; }
    .ejercicio-chip {
        display:inline-block; background:#2d2d2d; border:1px solid #444;
        border-radius:6px; padding:4px 10px; margin:3px 4px 3px 0;
        font-size:.82rem; color:#ddd;
    }
    .ejercicio-chip:hover { border-color:#39FF14; color:#39FF14; cursor:default; }
    </style>
    """, unsafe_allow_html=True)

    # ── CABECERA ──────────────────────────────────────────────
    st.title(f"🧠 Plan Semanal — {c}")

    # ── INICIALIZAR ESTADO DE SELECCIONES ─────────────────────
    # Tipo de semana — inicializar desde datos guardados
    sk_mc = f"sel_microciclo_{c}"
    if sk_mc not in st.session_state:
        guardado = st.session_state.planes_semanales.get(c, {}).get("tipo_semana", TIPOS_MICROCICLO[1])
        st.session_state[sk_mc] = guardado

    # Grupos por día — inicializar desde datos guardados
    for dia in DIAS:
        sk_grp = f"sel_grupo_{c}_{dia}"
        if sk_grp not in st.session_state:
            st.session_state[sk_grp] = st.session_state.planes_semanales.get(c, {}).get(dia, "Descanso")

    # ── PASO 1: TIPO DE SEMANA ────────────────────────────────
    st.markdown("### 1️⃣ ¿Qué tipo de semana es?")
    mc_info = {
        "Ajuste (Descarga)":  ("📉", "Descarga",   "#00BFFF", "RPE 5-7 · Técnica y recuperación"),
        "Carga (Desarrollo)": ("📈", "Desarrollo",  "#39FF14", "RPE 7-8.5 · Cargas progresivas"),
        "Impacto (Choque)":   ("🔥", "Choque",      "#FF4B4B", "RPE 9-10 · Máximo esfuerzo"),
    }
    mc_cols = st.columns(3)
    for i, (tipo, (ico, label, color, desc)) in enumerate(mc_info.items()):
        with mc_cols[i]:
            selected = st.session_state[sk_mc] == tipo
            if st.button(
                f"{ico} {'✓ ' if selected else ''}{label}",
                key=f"mc_btn_{i}",
                use_container_width=True,
                type="primary" if selected else "secondary",
            ):
                st.session_state[sk_mc] = tipo
                st.rerun()
            st.markdown(
                f"<div style='text-align:center;font-size:.75rem;"
                f"color:{color if selected else '#666'};margin-top:-8px'>{desc}</div>",
                unsafe_allow_html=True
            )

    mc = st.session_state[sk_mc]  # valor activo del microciclo

    st.divider()

    # ── PASO 2: VISTA SEMANAL ─────────────────────────────────
    st.markdown("### 2️⃣ Diseña tu semana")
    st.caption("Haz clic en un día para editarlo 👇")

    BADGE_CLASS = {
        "Descanso":    "badge-descanso", "Pierna":       "badge-pierna",
        "Pecho/Hombro":"badge-pecho",    "Espalda":      "badge-espalda",
        "Glúteo":      "badge-gluteo",   "Full Body":    "badge-full",
        "Torso":       "badge-torso",    "Brazo":        "badge-brazo",
        "Cardio":      "badge-cardio",
    }
    ICONOS_GRUPO = {
        "Descanso":    "😴", "Pierna":       "🦵", "Pecho/Hombro": "💪",
        "Espalda":     "🏋️", "Glúteo":       "🍑", "Full Body":    "⚡",
        "Torso":       "🔝", "Brazo":        "💪", "Cardio":       "🏃",
    }

    # Resumen visual de la semana (7 chips en fila)
    cols_sem = st.columns(7)
    for i, dia in enumerate(DIAS):
        foco_actual = st.session_state[f"sel_grupo_{c}_{dia}"]
        cls  = BADGE_CLASS.get(foco_actual, "badge-descanso")
        ico_ = ICONOS_GRUPO.get(foco_actual, "📅")
        with cols_sem[i]:
            st.markdown(f"""
            <div style='text-align:center;padding:8px 4px;background:#1a1a1a;
                        border-radius:8px;border:1px solid #333'>
                <div style='font-size:1.3rem'>{ico_}</div>
                <div style='font-size:.7rem;font-weight:700;color:#aaa;
                            letter-spacing:1px'>{dia[:3].upper()}</div>
                <div style='font-size:.65rem;color:#666;margin-top:2px'>
                    {foco_actual if foco_actual != "Descanso" else "Descanso"}
                </div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── EDITOR DE DÍAS ─────────────────────────────────────────
    if "dia_editando" not in st.session_state:
        st.session_state.dia_editando = None

    grupos_lista = ["Descanso","Pierna","Pecho/Hombro","Espalda","Glúteo",
                    "Full Body","Torso","Brazo","Cardio"]

    for dia in DIAS:
        # Leer grupo activo desde session_state (fuente de verdad)
        sk_grp     = f"sel_grupo_{c}_{dia}"
        vd_actual  = st.session_state[sk_grp]
        det_actual = st.session_state.detalles_planes.get(c, {}).get(dia, "")

        cls   = BADGE_CLASS.get(vd_actual, "badge-descanso")
        ico_d = ICONOS_GRUPO.get(vd_actual, "📅")
        n_ejs = len([l for l in det_actual.replace("||", "\n").split("\n") if l.strip()]) if det_actual else 0
        ej_hint = f"{n_ejs} ejercicio{'s' if n_ejs != 1 else ''}" if n_ejs > 0 else "Sin detalles"

        # Tarjeta del día
        col_card, col_edit = st.columns([5, 1])
        with col_card:
            st.markdown(f"""
            <div class='dia-card'>
              <div class='dia-header'>
                <span class='dia-nombre'>{ico_d} {dia}</span>
                <span class='dia-badge {cls}'>{vd_actual}</span>
              </div>
              <div style='color:#666;font-size:.82rem'>{ej_hint}</div>
            </div>""", unsafe_allow_html=True)
        with col_edit:
            st.markdown("<div style='margin-top:12px'>", unsafe_allow_html=True)
            lbl = "✅ Listo" if st.session_state.dia_editando == dia else "✏️ Editar"
            if st.button(lbl, key=f"edit_btn_{dia}", use_container_width=True):
                st.session_state.dia_editando = None if st.session_state.dia_editando == dia else dia
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        # Panel de edición inline
        if st.session_state.dia_editando == dia:
            with st.container():
                st.markdown(f"""
                <div style='background:#111;border:1px solid #39FF14;border-radius:10px;
                            padding:18px;margin:-8px 0 12px 0'>
                    <div style='color:#39FF14;font-family:Bebas Neue,sans-serif;
                                font-size:1.1rem;letter-spacing:2px;margin-bottom:12px'>
                        ✏️ EDITANDO {dia.upper()}
                    </div>
                </div>""", unsafe_allow_html=True)

                # ── SELECTOR DE GRUPO — botones que guardan en session_state ──
                st.markdown("**¿Qué se trabaja este día?**")
                gcols = st.columns(5)
                for gi, grp in enumerate(grupos_lista):
                    with gcols[gi % 5]:
                        sel_g = vd_actual == grp
                        if st.button(
                            f"{ICONOS_GRUPO.get(grp, '📅')} {grp}",
                            key=f"grp_{dia}_{gi}",
                            use_container_width=True,
                            type="primary" if sel_g else "secondary"
                        ):
                            # Guardar selección en session_state inmediatamente
                            st.session_state[sk_grp] = grp
                            st.rerun()

                # Leer el grupo actualizado (puede haber cambiado con el botón de arriba)
                nuevo_grupo = st.session_state[sk_grp]

                if nuevo_grupo != "Descanso":
                    st.markdown("<br>**Ejercicios del día**", unsafe_allow_html=True)

                    prev = det_actual.split("||") if "||" in det_actual else ["", det_actual, ""]
                    d0 = prev[0] if len(prev) > 0 else ""
                    d1 = prev[1] if len(prev) > 1 else ""
                    d2 = prev[2] if len(prev) > 2 else ""

                    ec1, ec2, ec3 = st.columns(3)
                    with ec1:
                        st.markdown("🔥 **Calentamiento**")
                        st.caption("5-10 min antes de comenzar")
                        cal = st.text_area(
                            "cal", value=d0, height=160,
                            placeholder="Ej:\nTroteo 5 min\nMovilidad cadera\nActivación glúteo",
                            label_visibility="collapsed", key=f"cal_{dia}"
                        )
                    with ec2:
                        st.markdown("💪 **Bloque Principal**")
                        st.caption("Un ejercicio por línea")
                        des = st.text_area(
                            "des", value=d1, height=160,
                            placeholder="Ej:\nSentadilla: 4x8 @80kg\nPrensa: 3x12 @100kg",
                            label_visibility="collapsed", key=f"des_{dia}"
                        )
                    with ec3:
                        st.markdown("🧘 **Vuelta a la Calma**")
                        st.caption("Estiramientos y movilidad")
                        vue = st.text_area(
                            "vue", value=d2, height=160,
                            placeholder="Ej:\nEstiramiento cuádriceps\nFoam roller",
                            label_visibility="collapsed", key=f"vue_{dia}"
                        )

                    # Guardar los text_areas en session_state para no perderlos
                    st.session_state[f"det_cal_{c}_{dia}"] = cal
                    st.session_state[f"det_des_{c}_{dia}"] = des
                    st.session_state[f"det_vue_{c}_{dia}"] = vue

                    # Botón Dante
                    df_c = st.session_state.db_clientes.get(c, {})
                    pf_d = (f"Edad:{df_c.get('Edad','?')}, Exp:{df_c.get('Experiencia','?')}, "
                            f"Lesiones:{df_c.get('Lesiones','Ninguna')}")
                    if st.button(f"🤖 Dante: generar rutina de {nuevo_grupo}",
                                 key=f"dante_{dia}", use_container_width=True):
                        if modelo_dante:
                            with st.spinner("Dante diseñando..."):
                                try:
                                    r = modelo_dante.generate_content(
                                        f"Eres Dante, entrenador experto. Perfil:{pf_d}. "
                                        f"Microciclo:{mc}. Genera una rutina de {nuevo_grupo} para {dia}.\n"
                                        f"Formato EXACTO (3 secciones separadas por '---'):\n"
                                        f"CALENTAMIENTO:\n[lista de ejercicios]\n---\n"
                                        f"DESARROLLO:\n[ejercicios con series x reps @ peso]\n---\n"
                                        f"VUELTA A LA CALMA:\n[estiramientos]"
                                    )
                                    txt_dante = r.text
                                    partes_d  = txt_dante.split("---")
                                    if len(partes_d) >= 3:
                                        st.success("✅ Dante generó la rutina — aplícala abajo:")
                                        st.session_state[f"dante_cal_{dia}"] = partes_d[0].replace("CALENTAMIENTO:", "").strip()
                                        st.session_state[f"dante_des_{dia}"] = partes_d[1].replace("DESARROLLO:", "").strip()
                                        st.session_state[f"dante_vue_{dia}"] = partes_d[2].replace("VUELTA A LA CALMA:", "").strip()
                                    else:
                                        st.markdown(txt_dante)
                                except Exception as e:
                                    st.error(f"Error Dante: {e}")
                        else:
                            st.warning("Dante no disponible.")

                    if st.session_state.get(f"dante_cal_{dia}"):
                        with st.expander("👁️ Ver propuesta de Dante", expanded=True):
                            dc1, dc2, dc3 = st.columns(3)
                            dc1.markdown(f"**Calentamiento:**\n{st.session_state[f'dante_cal_{dia}']}")
                            dc2.markdown(f"**Desarrollo:**\n{st.session_state[f'dante_des_{dia}']}")
                            dc3.markdown(f"**Vuelta:**\n{st.session_state[f'dante_vue_{dia}']}")
                            if st.button("✅ Aplicar propuesta de Dante", key=f"apply_dante_{dia}",
                                         use_container_width=True, type="primary"):
                                # Guardar directamente en detalles_planes
                                st.session_state.detalles_planes.setdefault(c, {})[dia] = (
                                    f"{st.session_state[f'dante_cal_{dia}']}"
                                    f"||{st.session_state[f'dante_des_{dia}']}"
                                    f"||{st.session_state[f'dante_vue_{dia}']}"
                                )
                                st.session_state.planes_semanales.setdefault(c, {})[dia] = nuevo_grupo
                                for k_ in [f"dante_cal_{dia}", f"dante_des_{dia}", f"dante_vue_{dia}"]:
                                    st.session_state.pop(k_, None)
                                guardar_datos()
                                st.toast(f"Rutina de Dante aplicada a {dia} ✅")
                                st.rerun()
                else:
                    st.info("😴 Día de descanso — el atleta no entrena.")

    st.divider()

    # ── ACCIONES FINALES ───────────────────────────────────────
    st.markdown("### 3️⃣ Guardar y exportar")
    ca_f, cb_f, cc_f = st.columns(3)

    with ca_f:
        if st.button("💾 Guardar Plan Completo", type="primary",
                     key="btn_guardar_plan", use_container_width=True):
            # Construir nf y nd desde session_state (fuente de verdad)
            nf = {"tipo_semana": st.session_state[sk_mc]}
            nd = {}
            for dia in DIAS:
                sk_grp = f"sel_grupo_{c}_{dia}"
                grp    = st.session_state.get(sk_grp, "Descanso")
                nf[dia] = grp
                if grp != "Descanso":
                    cal_ = st.session_state.get(f"det_cal_{c}_{dia}",
                           st.session_state.get(f"cal_{dia}", ""))
                    des_ = st.session_state.get(f"det_des_{c}_{dia}",
                           st.session_state.get(f"des_{dia}", ""))
                    vue_ = st.session_state.get(f"det_vue_{c}_{dia}",
                           st.session_state.get(f"vue_{dia}", ""))
                    nd[dia] = f"{cal_}||{des_}||{vue_}"
                else:
                    nd[dia] = ""

            st.session_state.planes_semanales[c] = nf
            st.session_state.detalles_planes[c]  = nd
            st.session_state.dia_editando        = None
            ok = guardar_datos()
            if ok:
                st.toast("Plan guardado ✅")
                st.rerun()
            else:
                st.error("Error al guardar")

    with cb_f:
        if st.button("🔄 Importar del Historial",
                     key="btn_cargar_historial", use_container_width=True):
            importar_historial(c)
            # Sincronizar session_state con los datos importados
            for dia in DIAS:
                sk_grp = f"sel_grupo_{c}_{dia}"
                st.session_state[sk_grp] = st.session_state.planes_semanales.get(c, {}).get(dia, "Descanso")
            st.session_state[sk_mc] = st.session_state.planes_semanales.get(c, {}).get("tipo_semana", TIPOS_MICROCICLO[1])
            st.toast("Historial importado ✅")
            st.rerun()

    with cc_f:
        if REPORTLAB_OK:
            try:
                # Construir nf/nd desde session_state para el PDF
                nf_pdf = {"tipo_semana": st.session_state[sk_mc]}
                nd_pdf = {}
                for dia in DIAS:
                    grp = st.session_state.get(f"sel_grupo_{c}_{dia}", "Descanso")
                    nf_pdf[dia] = grp
                    nd_pdf[dia] = st.session_state.detalles_planes.get(c, {}).get(dia, "")
                pb = pdf_plan(c, nf_pdf, nd_pdf)
                if pb:
                    st.download_button("📄 Descargar PDF", data=pb,
                        file_name=f"Rutina_{c.replace(' ', '_')}.pdf",
                        mime="application/pdf", use_container_width=True)
            except Exception as e:
                st.error(f"Error PDF: {e}")
        else:
            st.caption("pip install reportlab para PDF")

# =====================================================
# 📆 MESOCICLO IA
# =====================================================
elif menu == "📆 Mesociclo IA":
    c = need_athlete()
    st.title(f"📆 Mesociclo IA — {c}")
    st.info("Dante generará un plan completo de semanas con progresión real.")

    m1,m2 = st.columns(2)
    obj_m = m1.selectbox("Objetivo:", ["Hipertrofia","Fuerza Máxima","Resistencia",
                                       "Potencia","Pérdida de Grasa","Rendimiento General"])
    sem   = m2.slider("Semanas:", 4, 12, 8)

    mesos = st.session_state.mesociclos.get(c, [])

    if st.button("🚀 Generar Mesociclo con Dante", type="primary", key="btn_generar_meso"):
        if modelo_dante:
            with st.spinner(f"Dante diseñando {sem} semanas..."):
                txt = dante_mesociclo(c, obj_m, sem)
                if txt:
                    nuevo = {"fecha":fstr(date.today()),
                             "objetivo":obj_m,"semanas":sem,"contenido":txt}
                    st.session_state.mesociclos.setdefault(c,[]).insert(0, nuevo)
                    guardar_datos(); st.success("✅ Mesociclo generado y guardado"); st.rerun()
        else:
            st.warning("Dante no disponible — verifica GEMINI_API_KEY en secrets.")

    if mesos:
        st.divider(); st.subheader("📚 Historial de Mesociclos")
        for i, m in enumerate(mesos):
            with st.expander(f"📅 {m['fecha']} · {m['objetivo']} · {m['semanas']} sem",
                             expanded=(i==0)):
                st.markdown(m["contenido"])
                co1, co2 = st.columns([3,1])
                co1.download_button("💾 Descargar TXT", data=m["contenido"],
                    file_name=f"Meso_{c.replace(' ','_')}_{m['fecha']}.txt",
                    mime="text/plain", key=f"dm_{i}")
                if co2.button("🗑️ Eliminar", key=f"del_m_{i}"):
                    st.session_state.mesociclos[c].pop(i)
                    guardar_datos(); st.rerun()
    else:
        st.info("No hay mesociclos generados aún. Usa el botón de arriba.")

# =====================================================
# 🏃 CARDIO
# =====================================================
elif menu == "🏃 Cardio":
    c = need_athlete()
    d = st.session_state.db_clientes[c]
    st.title(f"🏃 Cardio — {c}")
    tb1, tb2 = st.tabs(["🧮 Calculadora VAM","📝 Registrar Sesión"])

    with tb1:
        vam = float(d.get("VAM",0.0))
        cv1, cv2 = st.columns(2)
        nv  = cv1.number_input("VAM actual (m/s)", 0.0,10.0,vam,step=0.1)
        if cv2.button("Actualizar VAM", key="btn_actualizar_vam"):
            st.session_state.db_clientes[c]["VAM"]=nv
            guardar_datos(); st.toast("VAM actualizada ✅"); vam=nv
        if vam > 0:
            st.divider()
            cd_, cp_ = st.columns(2)
            dist_ = cd_.number_input("Distancia (m)",100,10000,400,step=100)
            pct_  = cp_.slider("% Intensidad VAM",50,120,90)
            vel_  = vam*(pct_/100); ts_ = dist_/vel_ if vel_ else 0
            mm_, ss_ = divmod(int(ts_),60)
            r1,r2,r3 = st.columns(3)
            r1.metric("Velocidad",f"{vel_:.2f} m/s")
            r2.metric("Tiempo",   f"{mm_}:{ss_:02d}")
            r3.metric("Ritmo /km",f"{int(1000/vel_//60)}:{int(1000/vel_%60):02d}" if vel_ else "—")
            st.divider(); st.subheader("Zonas Personalizadas")
            zdata=[]
            for z,lo,hi in [("Z1 Regenerativo",0.0,0.60),("Z2 Aeróbico",0.60,0.75),
                             ("Z3 Umbral",0.75,0.90),("Z4 VO2Max",0.95,1.05),
                             ("Z5 Anaeróbico",1.10,1.20)]:
                zdata.append({"Zona":z,"Vel Mín":f"{vam*lo:.2f} m/s",
                              "Vel Máx":f"{vam*hi:.2f} m/s",
                              "% VAM":f"{lo*100:.0f}-{hi*100:.0f}%"})
            st.dataframe(pd.DataFrame(zdata),use_container_width=True,hide_index=True)

    with tb2:
        fc_ = st.date_input("Fecha:", date.today(), key="fc_cardio")
        cc1,cc2 = st.columns(2)
        tc_ = cc1.selectbox("Actividad:", TIPOS_CARDIO)
        zc_ = cc2.selectbox("Zona:", ["Z1","Z2","Z3","Z4","Z5"])
        cc3,cc4,cc5 = st.columns(3)
        dur_  = cc3.number_input("Duración (min)",  1,300,30)
        dis_  = cc4.number_input("Distancia (km)",  0.0,200.0,0.0,step=0.1)
        fcp_  = cc5.number_input("FC Prom (lpm)",   0,250,0)
        not_  = st.text_area("Notas:", height=70)

        if st.button("➕ Registrar Cardio", type="primary", key="btn_registrar_cardio"):
            st.session_state.historial_global.append({
                "Cliente":c,"Fecha":fstr(fc_),"Ejercicio":tc_,
                "Series":1,"Reps":1,"Carga":dur_,
                "Tipo":"Cardio","Objetivo":f"Cardio {zc_}",
                "Zona":zc_,"Distancia":dis_,"FC_Prom":fcp_,"Notas":not_,
            })
            guardar_datos(); st.toast("Cardio registrado 🏃"); st.rerun()

        hc = [h for h in st.session_state.historial_global
              if h["Cliente"]==c and h.get("Tipo")=="Cardio"]
        if hc:
            st.divider(); st.subheader("📊 Historial Cardio")
            dfc = pd.DataFrame(hc)
            sc  = [x for x in ["Fecha","Ejercicio","Carga","Zona","Distancia","FC_Prom"] if x in dfc]
            st.dataframe(dfc[sc].tail(20).rename(columns={"Carga":"Duración (min)"}),
                         use_container_width=True,hide_index=True)
            if len(hc)>=3:
                st.line_chart(dfc.tail(20),x="Fecha",y="Carga")

# =====================================================
# 🧪 TESTS FÍSICOS
# =====================================================
elif menu == "🧪 Tests Físicos":
    c = need_athlete()
    st.title(f"🧪 Tests Físicos — {c}")
    tb1, tb2 = st.tabs(["📝 Nuevo Test","📈 Evolución"])

    with tb1:
        t1_,t2_ = st.columns(2)
        tipo_t  = t1_.selectbox("Tipo de Test:", TIPOS_TEST)
        fech_t  = t2_.date_input("Fecha:", date.today())
        res_t   = st.number_input("Resultado:", step=0.1,
                                  help="m=Cooper/1km · cm=CMJ/Flex · kg=Fuerza")
        if tipo_t == "Test Cooper (12 min)" and res_t > 0:
            vo2 = (res_t-504.9)/44.73
            st.metric("VO2Max estimado", f"{vo2:.1f} ml/kg/min")
        not_t = st.text_area("Observaciones:", height=80)
        con_t = st.selectbox("Condición:", ["Descansado","Normal","Cansado"])
        if st.button("💾 Guardar Test", type="primary", key="btn_guardar_test"):
            st.session_state.tests_fisicos.setdefault(c,[]).append({
                "Fecha":fstr(fech_t),"Test":tipo_t,
                "Resultado":res_t,"Condicion":con_t,"Notas":not_t,
            })
            guardar_datos(); st.toast("Test guardado ✅")

    with tb2:
        tc = st.session_state.tests_fisicos.get(c,[])
        if tc:
            dft = pd.DataFrame(tc)
            ts_ = dft["Test"].unique().tolist()
            sel_= st.selectbox("Ver evolución de:", ts_)
            dts = dft[dft["Test"]==sel_].copy()
            if len(dts)>1:
                st.line_chart(dts, x="Fecha", y="Resultado")
                r1,r2,r3 = st.columns(3)
                r1.metric("Mejor",    f"{dts['Resultado'].max():.1f}")
                r2.metric("Último",   f"{dts['Resultado'].iloc[-1]:.1f}")
                r3.metric("Δ último", f"{dts['Resultado'].iloc[-1]-dts['Resultado'].iloc[-2]:+.1f}"
                           if len(dts)>1 else "—")
            st.dataframe(dft.sort_values("Fecha",ascending=False),
                         use_container_width=True,hide_index=True)
            with st.expander("🗑️ Eliminar registro"):
                idx_d = st.number_input("Número (0=primero):",0,len(tc)-1,0)
                if st.button("Eliminar", key="btn_del_test"):
                    st.session_state.tests_fisicos[c].pop(idx_d)
                    guardar_datos(); st.rerun()
        else:
            st.info("No hay tests registrados. Agrega uno en 'Nuevo Test'.")

# =====================================================
# 🥗 NUTRICIÓN
# =====================================================
elif menu == "🥗 Nutrición":
    c = need_athlete()
    d = st.session_state.db_clientes[c]
    st.title(f"🥗 Nutrición — {c}")
    st.caption("Estimaciones orientativas. No reemplaza a un nutricionista certificado.")
    tb1, tb2 = st.tabs(["🔥 Gasto Energético","🍽️ Macros"])

    with tb1:
        peso  = float(d.get("Peso",70)); talla = float(d.get("Talla",170))
        edad  = int(d.get("Edad",25));   sexo  = d.get("Sexo","Masculino")
        tmb   = calc_tmb(peso,talla,edad,sexo)
        st.metric("TMB (Mifflin-St Jeor)", f"{tmb:.0f} kcal/día")
        act_  = st.selectbox("Nivel de Actividad:",["Sedentario","Ligero (1-3 días)",
                              "Moderado (3-5 días)","Activo (6-7 días)","Muy Activo (2x/día)"])
        get_  = calc_get(tmb, act_)
        st.metric("GET (Gasto Energético Total)", f"{get_:.0f} kcal/día")
        obj_n = st.selectbox("Objetivo Nutricional:",
                             ["Mantenimiento","Déficit (Perder Grasa)","Superávit (Ganar Masa)"])
        if obj_n == "Déficit (Perder Grasa)":
            df__ = st.slider("Déficit (kcal):",200,700,400,step=50)
            meta = get_-df__; st.success(f"Meta: **{meta:.0f} kcal/día** (déficit {df__})")
        elif obj_n == "Superávit (Ganar Masa)":
            sv__ = st.slider("Superávit (kcal):",100,500,250,step=50)
            meta = get_+sv__; st.success(f"Meta: **{meta:.0f} kcal/día** (superávit {sv__})")
        else:
            meta = get_; st.info(f"Meta: **{meta:.0f} kcal/día**")
        st.session_state.db_clientes[c]["meta_calorica"] = meta

    with tb2:
        meta_c = float(st.session_state.db_clientes[c].get("meta_calorica", 2000))
        peso_c = float(d.get("Peso", 70))

        st.caption("📌 Recomendaciones basadas en criterios nutricionales deportivos "
                   "(Fuente: Nutrición Deportiva — Estudiante 4° año, Santo Tomás)")
        st.divider()

        # ── PROTEÍNAS ──────────────────────────────────────────
        st.subheader("🥩 Proteínas  ·  1,8 – 2,2 g/kg")
        st.caption("Rango recomendado según objetivo. Mayor proteína en déficit calórico "
                   "o alta intensidad para preservar masa muscular.")
        col_p1, col_p2 = st.columns([2,1])
        with col_p1:
            prot_factor = st.slider(
                "g de proteína por kg de peso corporal:",
                min_value=1.8, max_value=2.2, value=2.0, step=0.1,
                help="1,8 g/kg → mantenimiento / 2,0 g/kg → hipertrofia / 2,2 g/kg → déficit o alta intensidad"
            )
        prot_g = peso_c * prot_factor
        with col_p2:
            st.metric("Proteínas totales", f"{prot_g:.0f} g/día", f"{prot_g*4:.0f} kcal")

        st.divider()

        # ── GRASAS ─────────────────────────────────────────────
        st.subheader("🥑 Grasas  ·  0,8 – 1,2 g/kg")
        st.caption("Las grasas sostienen la producción hormonal y la absorción de vitaminas "
                   "liposolubles (A, D, E, K). No bajar de 0,8 g/kg.")
        col_g1, col_g2 = st.columns([2,1])
        with col_g1:
            gras_factor = st.slider(
                "g de grasa por kg de peso corporal:",
                min_value=0.8, max_value=1.2, value=1.0, step=0.1,
                help="0,8 g/kg → déficit calórico / 1,0 g/kg → mantenimiento / 1,2 g/kg → dieta alta en grasas"
            )
        gras_g = peso_c * gras_factor
        with col_g2:
            st.metric("Grasas totales", f"{gras_g:.0f} g/día", f"{gras_g*9:.0f} kcal")

        st.divider()

        # ── CARBOHIDRATOS ──────────────────────────────────────
        st.subheader("🍚 Carbohidratos  ·  según carga de entrenamiento")
        st.caption("Los carbohidratos son el principal combustible durante el ejercicio de alta "
                   "intensidad. Se ajustan según el volumen e intensidad semanal.")

        CARB_RANGOS = {
            "Reposo / Descarga (1–2 g/kg)":          (1.0, 2.0, "Semana de descanso o descarga activa."),
            "Entrenamiento Ligero (2–3 g/kg)":        (2.0, 3.0, "1–2 sesiones suaves por semana."),
            "Entrenamiento Moderado (3–5 g/kg)":      (3.0, 5.0, "3–4 sesiones de intensidad media."),
            "Entrenamiento Intenso (5–7 g/kg)":       (5.0, 7.0, "5–6 sesiones de alta intensidad."),
            "Competencia / Muy Intenso (7–10 g/kg)":  (7.0, 10.0,"Fase de competencia o doble sesión diaria."),
        }

        carga_sel = st.selectbox(
            "Carga de entrenamiento semanal:",
            list(CARB_RANGOS.keys()),
            index=2,
        )
        lo_c, hi_c, desc_c = CARB_RANGOS[carga_sel]
        st.info(f"ℹ️ {desc_c}")

        col_c1, col_c2 = st.columns([2,1])
        with col_c1:
            carb_factor = st.slider(
                f"g de carbohidratos por kg  ({lo_c:.0f}–{hi_c:.0f} g/kg):",
                min_value=lo_c, max_value=hi_c,
                value=round((lo_c+hi_c)/2, 1),
                step=0.5,
                help="Ajusta dentro del rango según cómo se sienta el atleta durante los entrenamientos."
            )
        carb_g = peso_c * carb_factor
        with col_c2:
            st.metric("Carbohidratos totales", f"{carb_g:.0f} g/día", f"{carb_g*4:.0f} kcal")

        st.divider()

        # ── RESUMEN FINAL ──────────────────────────────────────
        st.subheader("📊 Resumen de la Distribución")

        kcal_prot = prot_g * 4
        kcal_carb = carb_g * 4
        kcal_gras = gras_g * 9
        kcal_tot  = kcal_prot + kcal_carb + kcal_gras
        diff      = kcal_tot - meta_c

        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        col_r1.metric("🥩 Proteínas",     f"{prot_g:.0f}g",  f"{kcal_prot:.0f} kcal")
        col_r2.metric("🍚 Carbohidratos", f"{carb_g:.0f}g",  f"{kcal_carb:.0f} kcal")
        col_r3.metric("🥑 Grasas",        f"{gras_g:.0f}g",  f"{kcal_gras:.0f} kcal")
        col_r4.metric("⚡ Total",          f"{kcal_tot:.0f} kcal",
                      f"{diff:+.0f} vs meta")

        # Barra visual de distribución porcentual
        pct_p = kcal_prot/kcal_tot*100 if kcal_tot else 0
        pct_c = kcal_carb/kcal_tot*100 if kcal_tot else 0
        pct_g = kcal_gras/kcal_tot*100 if kcal_tot else 0

        st.markdown(f"""
        <div style='margin:16px 0 6px;font-size:.85rem;color:#aaa'>
            Distribución calórica:
        </div>
        <div style='display:flex;height:22px;border-radius:6px;overflow:hidden;gap:2px'>
            <div style='width:{pct_p:.1f}%;background:#FF6B6B;display:flex;
                        align-items:center;justify-content:center;
                        font-size:.75rem;font-weight:700;color:#fff'>
                {pct_p:.0f}%
            </div>
            <div style='width:{pct_c:.1f}%;background:#4ECDC4;display:flex;
                        align-items:center;justify-content:center;
                        font-size:.75rem;font-weight:700;color:#fff'>
                {pct_c:.0f}%
            </div>
            <div style='width:{pct_g:.1f}%;background:#FFE66D;display:flex;
                        align-items:center;justify-content:center;
                        font-size:.75rem;font-weight:700;color:#333'>
                {pct_g:.0f}%
            </div>
        </div>
        <div style='display:flex;gap:16px;margin-top:6px;font-size:.8rem;color:#888'>
            <span>🟥 Proteínas</span>
            <span>🟦 Carbohidratos</span>
            <span>🟨 Grasas</span>
        </div>
        """, unsafe_allow_html=True)

        # Alerta si el total se aleja mucho de la meta
        st.markdown("<br>", unsafe_allow_html=True)
        if abs(diff) <= 100:
            st.markdown('<div class="abox ok">✅ La distribución está alineada con la meta calórica.</div>',
                        unsafe_allow_html=True)
        elif diff > 100:
            st.markdown(f'<div class="abox warn">⚠️ El total supera la meta en {diff:.0f} kcal. '
                        f'Considera reducir levemente los carbohidratos.</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="abox inf">ℹ️ El total está {abs(diff):.0f} kcal por debajo de la meta. '
                        f'Puedes aumentar los carbohidratos si el entrenamiento lo requiere.</div>',
                        unsafe_allow_html=True)

        st.caption("⚕️ Esta calculadora es una herramienta orientativa. "
                   "Para una planificación nutricional individualizada, consulta a un nutricionista.")

        if st.button("💾 Guardar Macros", type="primary", key="btn_guardar_macros"):
            st.session_state.db_clientes[c].update({
                "macros_prot":  prot_g,
                "macros_carb":  carb_g,
                "macros_grasa": gras_g,
                "macros_prot_factor":  prot_factor,
                "macros_gras_factor":  gras_factor,
                "macros_carb_factor":  carb_factor,
                "macros_carga_sel":    carga_sel,
            })
            guardar_datos()
            st.toast("Macros guardados ✅")

# =====================================================
# 📈 PROGRESO
# =====================================================
elif menu == "📈 Progreso":
    c = need_athlete()
    df_all = pd.DataFrame([r for r in st.session_state.historial_global if r["Cliente"]==c])
    if df_all.empty:
        st.info("Sin datos. Registra sesiones primero."); st.stop()

    tb1,tb2,tb3 = st.tabs(["💪 Fuerza","🏃 Cardio","📋 Historial Completo"])

    with tb1:
        if "Tipo" in df_all.columns:
            dff = df_all[df_all["Tipo"]=="Fuerza"]
        else:
            dff = df_all
        if not dff.empty:
            ej_ = st.selectbox("Ejercicio:", dff["Ejercicio"].unique().tolist())
            dej = dff[dff["Ejercicio"]==ej_].copy()
            if not dej.empty:
                st.line_chart(dej, x="Fecha", y="Carga")
                r1,r2,r3 = st.columns(3)
                r1.metric("Carga Máx",  f"{dej['Carga'].max():.1f} kg")
                r2.metric("Promedio",   f"{dej['Carga'].mean():.1f} kg")
                r3.metric("Sesiones",   len(dej))
                est,msg,cls = analizar_progreso(dej)
                st.markdown(f'<div class="abox {cls}">{msg}</div>', unsafe_allow_html=True)
                if "RPE" in dej.columns and dej["RPE"].notna().any():
                    st.subheader("😤 Evolución RPE")
                    st.line_chart(dej, x="Fecha", y="RPE")
        else:
            st.info("Sin datos de fuerza.")

    with tb2:
        if "Tipo" in df_all.columns:
            dfc = df_all[df_all["Tipo"]=="Cardio"]
        else:
            dfc = pd.DataFrame()
        if not dfc.empty:
            st.line_chart(dfc, x="Fecha", y="Carga")
            r1,r2,r3 = st.columns(3)
            r1.metric("Sesiones",         len(dfc))
            r2.metric("Duración Prom.",   f"{dfc['Carga'].mean():.0f} min")
            r3.metric("Duración Máx.",    f"{dfc['Carga'].max():.0f} min")
        else:
            st.info("Sin sesiones de cardio.")

    with tb3:
        f1,f2 = st.columns(2)
        fi_ = f1.date_input("Desde:", date.today()-timedelta(days=30))
        ff_ = f2.date_input("Hasta:", date.today())
        dfl = df_all.copy()
        try:
            dfl["_dt"] = pd.to_datetime(dfl["Fecha"], format="%d/%m/%Y")
            dfl = dfl[(dfl["_dt"]>=pd.Timestamp(fi_)) & (dfl["_dt"]<=pd.Timestamp(ff_))]
        except Exception:
            pass
        bus = st.text_input("🔍 Buscar ejercicio:", "")
        if bus and "Ejercicio" in dfl.columns:
            dfl = dfl[dfl["Ejercicio"].str.contains(bus, case=False, na=False)]
        mcols = [x for x in ["Fecha","Ejercicio","Series","Reps","Carga","RPE","Tipo","Objetivo"]
                 if x in dfl.columns]
        st.dataframe(dfl[mcols].sort_values("Fecha",ascending=False),
                     use_container_width=True, hide_index=True)
        st.caption(f"{len(dfl)} registros")

        if OPENPYXL_OK:
            xb = excel_historial(c)
            if xb:
                st.download_button("📊 Exportar Excel", data=xb,
                    file_name=f"Historial_{c.replace(' ','_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.caption("pip install openpyxl para exportar Excel")

        with st.expander("🗑️ Eliminar registros por fecha"):
            fb_ = st.date_input("Fecha a limpiar:", date.today())
            rf_ = [h for h in st.session_state.historial_global
                   if h["Cliente"]==c and h["Fecha"]==fstr(fb_)]
            if rf_:
                st.warning(f"Se eliminarán {len(rf_)} registros del {fstr(fb_)}.")
                if st.button("✅ Confirmar eliminación", key="btn_confirmar_hist"):
                    st.session_state.historial_global = [
                        h for h in st.session_state.historial_global
                        if not (h["Cliente"]==c and h["Fecha"]==fstr(fb_))]
                    guardar_datos(); st.success("Eliminados."); st.rerun()
            else:
                st.info("No hay registros en esa fecha.")

# =====================================================
# 📚 GUÍAS
# =====================================================
elif menu == "📚 Guías":
    t1,t2,t3,t4,t5,t6 = st.tabs(["Fuerza (Badillo)","Planif. (Bompa)",
                                "Tempo & Pausa","RPE & Borg","Zonas VAM", "Zonas FCM"])
    with t1: st.table(TABLA_BADILLO)
    with t2: st.table(GUIAS_BOMPA)
    with t3:
        c1,c2 = st.columns(2); c1.table(GUIA_TEMPO); c2.table(GUIA_DESCANSOS)
    with t4:
        c1,c2 = st.columns(2); c1.table(ESCALA_RPE); c2.table(ESCALA_BORG)
    with t5:
        st.table(GUIA_CARDIO)
    with t6:
        st.info("💡 **Nota:** Trabajar en la Zona 2 (60-70%) es ideal para maximizar la oxidación de grasas durante el ejercicio continuo.")
        st.table(TABLA_ZONAS_FCM)

# =====================================================
# 📝 NOTAS
# =====================================================
elif menu == "📝 Notas":
    st.title("📝 Notas Personales")
    st.caption("Espacio privado — visible solo para ti.")
    notas = st.text_area("Tus apuntes:", value=st.session_state.notas_personales, height=420)
    if st.button("💾 Guardar Notas", type="primary", key="btn_guardar_notas"):
        st.session_state.notas_personales = notas
        ok = guardar_datos()
        st.toast("Notas guardadas ☁️" if ok else "Error al guardar ❌")

# =====================================================
# 🎥 VIDEOTECA
# =====================================================
elif menu == "🎥 Videoteca":
    st.title("🎥 Videoteca")
    st.dataframe(
        pd.DataFrame(list(st.session_state.biblioteca_videos.items()),
                     columns=["Ejercicio","Enlace"]),
        use_container_width=True, hide_index=True)
    st.divider()
    ca, cd = st.columns(2)
    with ca:
        st.subheader("➕ Agregar")
        ne_ = st.text_input("Nombre:")
        nl_ = st.text_input("Enlace:")
        if st.button("Guardar", type="primary", key="btn_guardar_video"):
            if ne_.strip():
                st.session_state.biblioteca_videos[ne_.strip()] = nl_.strip()
                guardar_datos(); st.toast(f"'{ne_}' agregado ✅"); st.rerun()
            else:
                st.warning("Escribe un nombre.")
    with cd:
        st.subheader("🗑️ Eliminar")
        lista_ = list(st.session_state.biblioteca_videos.keys())
        if lista_:
            eb_ = st.selectbox("Selecciona:", lista_)
            if st.button("Eliminar", key="btn_del_video"):
                del st.session_state.biblioteca_videos[eb_]
                guardar_datos(); time.sleep(0.5); st.rerun()
        else:
            st.info("La videoteca está vacía.")


# =====================================================
# 👑 PANEL ADMIN — Optimizado contra Error 429 (Límites de Google)
# =====================================================
elif menu == "👑 Panel Admin":
    st.title("👑 Panel de Control Bio Sport")
    st.caption("Solo visible para el administrador del sistema.")

    # --- SISTEMA ANTI-COLAPSO DE GOOGLE SHEETS ---
    if st.button("🔄 Actualizar Datos de la Nube", use_container_width=True):
        st.session_state.pop("admin_cache", None)
        st.rerun()

    if "admin_cache" not in st.session_state:
        with st.spinner("Descargando base de datos global de forma segura..."):
            try:
                client = _gs_client()
                sheet  = client.open_by_url(URL_SHEET)
                usr_db = cargar_usuarios_sistema()
                
                # Descargamos la data de todos los entrenadores de UNA sola vez
                datos_entrenadores = {}
                for usr in usr_db.keys():
                    try:
                        ws = sheet.worksheet(usr)
                        vals = ws.col_values(1)
                        if vals:
                            datos_entrenadores[usr] = json.loads("".join(vals))
                    except Exception:
                        datos_entrenadores[usr] = {}
                        
                st.session_state.admin_cache = {
                    "usuarios": usr_db,
                    "datos": datos_entrenadores
                }
            except Exception as e:
                st.error(f"Error de conexión: {e}")
                st.stop()

    cache = st.session_state.admin_cache
    usuarios_db = cache["usuarios"]
    datos_completos = cache["datos"]

    tab_usuarios, tab_cobros, tab_ranking = st.tabs([
        "👥 Gestión de Preparadores",
        "💰 Cobros del Mes",
        "🏆 Ranking de Actividad"
    ])

    # ── TAB 1: GESTIÓN DE USUARIOS ──────────────────────
    with tab_usuarios:
        st.subheader("Preparadores registrados")
        if usuarios_db:
            filas_u = []
            for usr, info in usuarios_db.items():
                trato = (f"${int(info.get('valor_cobro',0)):,}/alumno"
                         if info.get("tipo_cobro") == "por_alumno"
                         else f"${int(info.get('valor_cobro',0)):,} fijo")
                filas_u.append({
                    "Usuario":         usr,
                    "Nombre":          info.get("nombre_completo","—"),
                    "Tipo de Cobro":   info.get("tipo_cobro","—"),
                    "Valor":           trato,
                    "Registrado":      info.get("fecha_registro","—"),
                })
            st.dataframe(pd.DataFrame(filas_u), use_container_width=True, hide_index=True)
        else:
            st.info("No hay preparadores registrados aún.")

        st.divider()

        # ── REGISTRAR NUEVO PREPARADOR ──
        with st.expander("➕ Registrar nuevo preparador", expanded=True):
            st.markdown("**Completa los datos del nuevo preparador:**")
            rn1, rn2 = st.columns(2)
            new_nombre  = rn1.text_input("Nombre completo:", key="reg_nombre")
            new_usuario = rn2.text_input("Usuario (sin espacios):", key="reg_usuario")
            rn3, rn4 = st.columns(2)
            new_pass    = rn3.text_input("Contraseña:", type="password", key="reg_pass")
            new_pass2   = rn4.text_input("Repetir contraseña:", type="password", key="reg_pass2")

            st.markdown("**Tipo de cobro:**")
            rc1, rc2, rc3 = st.columns(3)
            tipo_cobro = rc1.selectbox("Modalidad:",
                ["por_alumno","fijo_mensual"],
                format_func=lambda x: "Por alumno" if x=="por_alumno" else "Cuota fija mensual",
                key="reg_tipo")
            valor_cobro = rc2.number_input(
                "Valor ($):", min_value=0, value=2500, step=500, key="reg_valor",
                help="Si es por alumno: precio por cada atleta. Si es fijo: monto mensual total.")
            rc3.markdown("<br>", unsafe_allow_html=True)
            rc3.caption(f"Ejemplo: {valor_cobro:,} {'por cada atleta' if tipo_cobro=='por_alumno' else 'al mes'}")

            if st.button("✅ Crear cuenta de preparador", type="primary", key="btn_crear_usuario", use_container_width=True):
                if new_pass != new_pass2:
                    st.error("❌ Las contraseñas no coinciden.")
                elif not new_nombre.strip():
                    st.error("❌ El nombre completo es obligatorio.")
                else:
                    ok, msg = registrar_usuario_sistema(new_usuario, new_pass, new_nombre, tipo_cobro, valor_cobro)
                    if ok:
                        st.success("Preparador registrado correctamente.")
                        st.session_state.pop("admin_cache", None) # Limpiar cache para refrescar
                        st.rerun()
                    else:
                        st.error(f"❌ Error: {msg}")

        st.divider()

        # ── CAMBIAR CONTRASEÑA ──
        with st.expander("🔑 Cambiar contraseña de un preparador"):
            if usuarios_db:
                cp1, cp2, cp3 = st.columns(3)
                usr_cambiar = cp1.selectbox("Preparador:", list(usuarios_db.keys()), key="cp_usr")
                nueva_pw    = cp2.text_input("Nueva contraseña:", type="password", key="cp_new")
                nueva_pw2   = cp3.text_input("Repetir:", type="password", key="cp_rep")
                if st.button("Actualizar contraseña", key="btn_cambiar_pw"):
                    if nueva_pw != nueva_pw2:
                        st.error("Las contraseñas no coinciden.")
                    elif len(nueva_pw) < 6:
                        st.error("Mínimo 6 caracteres.")
                    else:
                        if cambiar_password_usuario(usr_cambiar, nueva_pw):
                            st.success(f"Contraseña de '{usr_cambiar}' actualizada ✅")
                            st.session_state.pop("admin_cache", None)
                        else:
                            st.error("Error al actualizar.")
            else:
                st.info("No hay preparadores registrados.")

        st.divider()

        # ── ELIMINAR PREPARADOR ──
        with st.expander("🗑️ Eliminar preparador"):
            if usuarios_db:
                st.warning("⚠️ Esta acción elimina el acceso del preparador. Sus datos en Sheets NO se borran.")
                usr_del = st.selectbox("Selecciona:", list(usuarios_db.keys()), key="del_usr")
                if st.button(f"Eliminar a {usr_del}", key="btn_del_usr", type="primary"):
                    if eliminar_usuario_sistema(usr_del):
                        st.success(f"'{usr_del}' eliminado del sistema ✅")
                        st.session_state.pop("admin_cache", None)
                        st.rerun()
                    else:
                        st.error("Error al eliminar.")
            else:
                st.info("No hay preparadores para eliminar.")

    # ── TAB 2: COBROS DEL MES ────────────────────────────
    with tab_cobros:
        st.subheader("Resumen de cobros — " + datetime.now().strftime("%B %Y").capitalize())
        cobros = []; total = 0
        for usr, info in usuarios_db.items():
            jd = datos_completos.get(usr, {})
            n  = len(jd.get("clientes", {}))
            tc = info.get("tipo_cobro", "por_alumno")
            vc = int(info.get("valor_cobro", 0))
            mo = n * vc if tc == "por_alumno" else vc
            
            cobros.append({
                "Preparador":  info.get("nombre_completo", usr),
                "Usuario":     usr,
                "Alumnos":     n,
                "Modalidad":   "Por alumno" if tc=="por_alumno" else "Fijo mensual",
                "Valor unit.": f"${vc:,}",
                "Total ($)":   mo,
            })
            total += mo

        if cobros:
            df_cobros = pd.DataFrame(cobros)
            c1, c2, c3 = st.columns(3)
            c1.metric("Preparadores activos", len(cobros))
            c2.metric("Alumnos totales",      sum(x["Alumnos"] for x in cobros))
            c3.metric("Total a recaudar",      f"${total:,}")
            st.divider()
            
            df_cobros["Total ($)"] = df_cobros["Total ($)"].apply(lambda x: f"${x:,}")
            st.dataframe(df_cobros, use_container_width=True, hide_index=True)

            csv_cobros = df_cobros.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📊 Exportar cobros CSV",
                data=csv_cobros,
                file_name=f"cobros_{datetime.now().strftime('%Y_%m')}.csv",
                mime="text/csv",
                key="btn_export_cobros"
            )
        else:
            st.info("No hay preparadores con datos registrados aún.")

    # ── TAB 3: RANKING ───────────────────────────────────
    with tab_ranking:
        st.subheader("Ranking de actividad — últimos 30 días")
        ranking = []
        for usr, info in usuarios_db.items():
            jd = datos_completos.get(usr, {})
            for nom in jd.get("clientes", {}):
                r30 = [r for r in jd.get("historial", [])
                       if r["Cliente"] == nom and
                       (date.today() - datetime.strptime(r["Fecha"], "%d/%m/%Y").date()).days <= 30]
                ranking.append({
                    "Atleta":       nom,
                    "Preparador":   info.get("nombre_completo", usr),
                    "Sesiones 30d": len(r30),
                })

        if ranking:
            df_rank = pd.DataFrame(ranking).sort_values("Sesiones 30d", ascending=False)
            st.dataframe(df_rank, use_container_width=True, hide_index=True)
            st.divider()
            top = df_rank.iloc[0]
            st.success(f"🏆 Atleta más activo: **{top['Atleta']}** "
                       f"({top['Preparador']}) — {top['Sesiones 30d']} sesiones")
        else:
            st.info("Sin actividad registrada en los últimos 30 días.")
