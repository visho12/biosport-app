import streamlit as st
import hashlib
from datetime import datetime
from database.sheets_db import _gs_client, URL_SHEET

def _hash(p): return hashlib.sha256(p.encode()).hexdigest()

ADMIN_USER = "visho"
ADMIN_PASS = st.secrets.get("PW_VISHO", "Bio2026")

def _get_hoja_usuarios(sheet):
    import gspread
    try:
        return sheet.worksheet("usuarios_sistema")
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title="usuarios_sistema", rows="200", cols="6")
        ws.append_row(["usuario","password_hash","nombre_completo",
                       "tipo_cobro","valor_cobro","fecha_registro"])
        return ws

@st.cache_data(ttl=600)
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
        cargar_usuarios_sistema.clear()
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
                cargar_usuarios_sistema.clear()
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
