import streamlit as st
import pandas as pd
import math
import time
import json
import io
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, datetime
import hashlib

# =====================================================
# LIBRERÍA IA
# =====================================================
import google.generativeai as genai

try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    modelos_validos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    modelo_dante = genai.GenerativeModel(modelos_validos[0]) if modelos_validos else None
except Exception as e:
    modelo_dante = None

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.colors import HexColor
except ImportError:
    st.error("⚠️ Falta 'reportlab'. Instala con: pip install reportlab")

# =====================================================
# 1. CONFIGURACIÓN DE PÁGINA
# =====================================================
st.set_page_config(page_title="Bio Sport Pro Trainer", layout="wide", page_icon="⚡")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

h1, h2, h3 {
    font-family: 'Bebas Neue', sans-serif;
    letter-spacing: 2px;
}

.stButton > button {
    border-radius: 4px;
    font-family: 'DM Sans', sans-serif;
    font-weight: 600;
    letter-spacing: 0.5px;
    transition: all 0.2s ease;
}

.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 15px rgba(57, 255, 20, 0.3);
}

.metric-card {
    background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
    border: 1px solid #39FF14;
    border-radius: 8px;
    padding: 16px;
    text-align: center;
}

.metric-value {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 2.5rem;
    color: #39FF14;
    line-height: 1;
}

.metric-label {
    color: #aaa;
    font-size: 0.8rem;
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.alert-box {
    padding: 12px 16px;
    border-radius: 6px;
    margin: 8px 0;
    font-size: 0.9rem;
}

.alert-success { background: #0d2b0d; border-left: 3px solid #39FF14; color: #39FF14; }
.alert-warning { background: #2b2200; border-left: 3px solid #FFD700; color: #FFD700; }
.alert-danger  { background: #2b0000; border-left: 3px solid #FF4B4B; color: #FF4B4B; }
.alert-info    { background: #001a2b; border-left: 3px solid #00BFFF; color: #00BFFF; }

.sidebar-athlete {
    background: linear-gradient(135deg, #1a1a1a, #222);
    border: 1px solid #333;
    border-radius: 8px;
    padding: 10px 14px;
    margin: 8px 0;
}
</style>
""", unsafe_allow_html=True)


# =====================================================
# 2. AUTENTICACIÓN SEGURA (sin contraseñas en código)
# =====================================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def validar_usuario(usuario: str, clave: str) -> bool:
    """
    Lee credenciales desde st.secrets["usuarios"].
    En secrets.toml agrega:
        [usuarios]
        visho   = "hash_sha256_de_tu_clave"
        eduardo = "hash_sha256_de_tu_clave"
    Genera el hash con: hashlib.sha256("TuClave".encode()).hexdigest()
    
    FALLBACK TEMPORAL: si no existe la sección, usa el diccionario hardcodeado
    solo para no romper la app en producción mientras migras.
    """
    try:
        usuarios_secrets = st.secrets.get("usuarios", {})
        if usuarios_secrets:
            stored_hash = usuarios_secrets.get(usuario)
            if stored_hash:
                return stored_hash == hash_password(clave)
            return False
    except Exception:
        pass

    # ⚠️ FALLBACK — MIGRA ESTO A st.secrets LO ANTES POSIBLE
    usuarios_fallback = {
        "visho":    st.secrets.get("PW_VISHO",    "Bio2026"),
        "eduardo":  st.secrets.get("PW_EDUARDO",  "Bio2026"),
        "davidp":   st.secrets.get("PW_DAVIDP",   "Davidp2026"),
        "clemente": st.secrets.get("PW_CLEMENTE",  "Clemente2026"),
    }
    return usuarios_fallback.get(usuario) == clave


def login():
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("""
            <div style='text-align:center; padding: 40px 0 20px;'>
                <span style='font-family: Bebas Neue, sans-serif; font-size: 3rem; 
                             color: #39FF14; letter-spacing: 4px;'>⚡ BIO SPORT</span><br>
                <span style='color: #888; font-size: 0.9rem; letter-spacing: 2px;'>
                    PLATAFORMA DE ALTO RENDIMIENTO
                </span>
            </div>
            """, unsafe_allow_html=True)

            with st.form("formulario_login"):
                usuario = st.text_input("Usuario", placeholder="tu usuario").lower().strip()
                clave   = st.text_input("Contraseña", type="password", placeholder="••••••••")
                boton   = st.form_submit_button("ENTRAR AL SISTEMA", type="primary", use_container_width=True)
                if boton:
                    if validar_usuario(usuario, clave):
                        st.session_state["autenticado"]    = True
                        st.session_state["usuario_actual"] = usuario
                        st.rerun()
                    else:
                        st.error("Credenciales incorrectas")
        return False
    return True


if not login():
    st.stop()

st.sidebar.markdown(
    f"<div class='sidebar-athlete'>👤 <b>{st.session_state['usuario_actual'].capitalize()}</b></div>",
    unsafe_allow_html=True
)
if st.sidebar.button("Cerrar Sesión"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()


# =====================================================
# 3. TABLAS TÉCNICAS
# =====================================================
VIDEOS_BASE = {
    "Sentadilla Goblet":   "https://www.youtube.com/watch?v=MeIiIdhvXT4",
    "Sentadilla Libre":    "https://www.youtube.com/watch?v=1OoMs3MaXI4",
    "Flexiones":           "https://www.youtube.com/watch?v=e_K0yT3t3IM",
    "Jalón al Pecho":      "https://www.youtube.com/watch?v=HSoHeSrp-j4",
    "Peso Muerto Rumano":  "https://www.youtube.com/watch?v=JCXUYuzwNrM",
    "Plancha Abdominal":   "https://www.youtube.com/watch?v=ASdvN_XEl_c",
    "Press Banca":         "https://www.youtube.com/watch?v=VmB1G1K7v94",
    "Zancadas":            "https://www.youtube.com/watch?v=0_ZmM-J7y_M",
    "Remo Mancuerna":      "https://www.youtube.com/watch?v=D7KaRcCIQms",
    "Press Militar":       "https://www.youtube.com/watch?v=M2rwvNhTOu0",
}

SUGERENCIAS_OBJETIVO = {
    "Hipertrofia":    {"Reps": "6-12",  "Pausa": "1:30-2:00", "RPE": "7-9",     "RM": "65-80%"},
    "Fuerza Máxima":  {"Reps": "1-5",   "Pausa": "3:00-5:00", "RPE": "8-10",    "RM": "85-100%"},
    "Resistencia":    {"Reps": "15-20+", "Pausa": "0:30-1:00", "RPE": "6-8",    "RM": "< 60%"},
    "Potencia":       {"Reps": "1-5",   "Pausa": "2:00-3:00", "RPE": "Explosivo","RM": "30-70%"},
}

TABLA_BADILLO = pd.DataFrame({
    "Zona":      ["Fuerza Máx","Fuerza-Hipertrofia","Hipertrofia Alta","Hipertrofia Media","Resistencia"],
    "% 1RM":     ["85-100%","80-85%","70-80%","60-75%","<60%"],
    "Reps":      ["1-5","5-7","6-12","12-20","20+"],
    "Descanso":  ["3-5 min","3 min","2 min","1-2 min","<1 min"],
})

GUIAS_BOMPA = pd.DataFrame({
    "Fase":        ["Adaptación","Hipertrofia","Fuerza Máx","Potencia","Transición"],
    "Intensidad":  ["30-60%","60-80%","85-100%","30-80%","Baja"],
    "Reps":        ["12-20","6-12","1-5","1-10","Libre"],
    "Descanso":    ["1-2 min","1-3 min","3-5+ min","3-5+ min","Libre"],
})

GUIA_TEMPO = pd.DataFrame({
    "Objetivo":    ["Hipertrofia","Fuerza Máx","Potencia","Resistencia"],
    "Tempo":       ["3-0-1-0","X-0-X-0","X-X-X","2-0-2-0"],
    "Explicación": ["Bajada lenta","Máxima velocidad","Explosivo","Continuo"],
})

GUIA_DESCANSOS = pd.DataFrame({
    "Objetivo": ["Fuerza/Potencia","Hipertrofia","Resistencia"],
    "Tiempo":   ["3 a 5+ min","60 a 90 seg","30 a 60 seg"],
    "¿Por qué?":["Recuperar ATP","Estrés Metabólico","Limpiar lactato"],
})

ESCALA_RPE = pd.DataFrame({
    "RPE":      [10, 9, 8, 7, 6],
    "RIR":      ["0 (Fallo)","1","2","3","4"],
    "Sensación":["Imposible más","Podría 1 más","Podría 2 más","Podría 3 más","Calentamiento"],
})

ESCALA_BORG = pd.DataFrame({
    "Nivel":                   ["Muy Suave","Suave","Moderado","Duro","Muy Duro","Máximo"],
    "Escala Modificada (0-10)":["0-2","3","4-5","6-7","8-9","10"],
    "Test del Habla":          ["Cantar","Conversación fluida","Frases cortas","Palabras sueltas","Apenas hablar","Sin aliento / Agonía"],
})

GUIA_ZONAS_CARDIO = pd.DataFrame({
    "Zona":      ["Z1 (Regenerativo)","Z2 (Aeróbico)","Z3 (Umbral)","Z4 (VO2Max)","Z5 (Anaeróbico)"],
    "% VAM":     ["< 60%","60-75%","75-90%","95-105%","> 110%"],
    "Sensación": ["Muy fácil","Fácil","Duro","Muy duro","Agonía"],
})

TIPOS_CARDIO = ["Carrera", "Bicicleta", "Elíptica", "Remo", "Natación", "HIIT", "Caminata", "Otro"]


# =====================================================
# 4. BASE DE DATOS — Google Sheets con manejo de errores
# =====================================================
URL_SHEET = "https://docs.google.com/spreadsheets/d/1NxZNe_1GjunjcpJs91tHJIAnZievTsNuVTTFe6uMqik/edit?gid=0#gid=0"


def get_gsheets_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_info = dict(st.secrets["gcp_service_account"])
    credentials = Credentials.from_service_account_info(creds_info, scopes=scopes)
    return gspread.authorize(credentials)


def cargar_datos_disco():
    usuario = st.session_state.get("usuario_actual", "default")
    try:
        client = get_gsheets_client()
        sheet = client.open_by_url(URL_SHEET)
        try:
            worksheet = sheet.worksheet(usuario)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=usuario, rows="100", cols="20")
            return None

        col_values = worksheet.col_values(1)
        if col_values:
            return json.loads("".join(col_values))
    except gspread.exceptions.APIError as e:
        st.sidebar.error(f"⚠️ Error de Google Sheets: {e}")
    except json.JSONDecodeError:
        st.sidebar.error("⚠️ Los datos guardados están corruptos. Contacta al administrador.")
    except Exception as e:
        st.sidebar.error(f"⚠️ Error inesperado al cargar: {e}")
    return None


def guardar_datos_disco():
    usuario = st.session_state.get("usuario_actual", "default")
    try:
        datos = {
            "clientes":       st.session_state.db_clientes,
            "historial":      st.session_state.historial_global,
            "videos":         st.session_state.biblioteca_videos,
            "planes":         st.session_state.planes_semanales,
            "detalles_planes":st.session_state.detalles_planes,
            "notas":          st.session_state.notas_personales,
        }
        json_str = json.dumps(datos, ensure_ascii=False)
        client   = get_gsheets_client()
        sheet    = client.open_by_url(URL_SHEET)
        try:
            worksheet = sheet.worksheet(usuario)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=usuario, rows="100", cols="20")

        chunks    = [json_str[i:i+40000] for i in range(0, len(json_str), 40000)]
        worksheet.clear()
        cell_list = worksheet.range(1, 1, len(chunks), 1)
        for i, cell in enumerate(cell_list):
            cell.value = chunks[i]
        worksheet.update_cells(cell_list)
        return True
    except gspread.exceptions.APIError as e:
        st.sidebar.error(f"⚠️ Error guardando en Sheets: {e}")
    except Exception as e:
        st.sidebar.error(f"⚠️ Error inesperado al guardar: {e}")
    return False


def registrar_auditoria_cobro(nombre_alumno):
    usuario = st.session_state.get("usuario_actual", "desconocido")
    if usuario == "visho":
        return
    try:
        client = get_gsheets_client()
        sheet  = client.open_by_url(URL_SHEET)
        meses  = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                  "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        mes_actual  = meses[datetime.now().month - 1]
        ano_actual  = datetime.now().year
        nombre_hoja = f"Auditoria_{mes_actual}_{ano_actual}"
        try:
            worksheet = sheet.worksheet(nombre_hoja)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=nombre_hoja, rows="1000", cols="4")
            worksheet.append_row(["Fecha Registro","Preparador","Nombre Alumno","Estado Pago"])

        registros = worksheet.get_all_values()
        for fila in registros:
            if len(fila) >= 3 and fila[1].lower() == usuario.lower() and fila[2].lower() == nombre_alumno.lower():
                return
        worksheet.append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), usuario.capitalize(), nombre_alumno, "Pendiente"])
    except Exception:
        pass


# =====================================================
# 5. CÁLCULOS Y UTILIDADES
# =====================================================
def calcular_1rm(p, r):
    return p * (1 + (r / 30))


def calcular_durnin(edad, sexo, s4):
    if s4 <= 0:
        raise ValueError("La suma de pliegues debe ser mayor a 0.")
    c, m = (1.1631, 0.0632) if sexo == "Masculino" else (1.1599, 0.0717)
    densidad = c - (m * math.log10(s4))
    if densidad <= 0:
        raise ValueError("Densidad calculada inválida. Revisa los pliegues.")
    return (495 / densidad) - 450


def evaluar_grasa(edad, sexo, grasa):
    if sexo == "Masculino":
        if edad <= 24:   thresholds = [3, 9, 19, 23]
        elif edad <= 29: thresholds = [3, 10, 20, 24]
        elif edad <= 34: thresholds = [3, 11, 21, 25]
        elif edad <= 39: thresholds = [3, 12, 22, 26]
        elif edad <= 44: thresholds = [3, 13, 23, 27]
        elif edad <= 49: thresholds = [3, 15, 25, 28]
        elif edad <= 54: thresholds = [3, 17, 26, 29]
        elif edad <= 59: thresholds = [3, 19, 28, 30]
        else:            thresholds = [3, 20, 29, 31]
    else:
        if edad <= 24:   thresholds = [8, 15, 25, 30]
        elif edad <= 29: thresholds = [8, 16, 26, 31]
        elif edad <= 34: thresholds = [8, 17, 27, 32]
        elif edad <= 39: thresholds = [8, 19, 28, 33]
        elif edad <= 44: thresholds = [8, 21, 29, 34]
        elif edad <= 49: thresholds = [8, 23, 31, 36]
        elif edad <= 54: thresholds = [8, 25, 33, 37]
        elif edad <= 59: thresholds = [8, 26, 34, 38]
        else:            thresholds = [8, 27, 35, 39]

    if grasa <= thresholds[0]:   return "Grasa Esencial",                "#FF4B4B"
    elif grasa <= thresholds[1]: return "Compartimento Graso Disminuido", "#00C853"
    elif grasa <= thresholds[2]: return "Compartimento Graso Adecuado",   "#00BFFF"
    elif grasa <= thresholds[3]: return "Compartimento Graso Aumentado",  "#FFD700"
    else:                        return "Grasa Muy Aumentada",             "#DC143C"


def analizar_progreso_avanzado(datos_ejercicio: pd.DataFrame):
    """
    Análisis de progreso con ventana deslizante de 2 semanas.
    Retorna (estado, mensaje, color_clase).
    """
    if len(datos_ejercicio) < 3:
        return "sin_datos", "Necesitas al menos 3 registros para analizar el progreso.", "alert-info"

    cargas = datos_ejercicio["Carga"].tolist()
    ultimas_3 = cargas[-3:]

    # Tasa de progreso: pendiente normalizada
    n = len(cargas)
    if n >= 5:
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(cargas) / n
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, cargas))
        den = sum((x - mean_x) ** 2 for x in xs)
        pendiente = num / den if den != 0 else 0
        tasa_progreso = (pendiente / mean_y) * 100 if mean_y > 0 else 0
    else:
        tasa_progreso = None

    # Detección de patrones
    if ultimas_3[0] == ultimas_3[1] == ultimas_3[2]:
        return "estancamiento", (
            f"⚠️ **Estancamiento detectado:** {ultimas_3[0]}kg en las últimas 3 sesiones. "
            f"Recomendación: semana de descarga o variación del estímulo (cambio de rango de reps, pausa, tempo)."
        ), "alert-warning"

    if ultimas_3[2] < ultimas_3[0]:
        caida = ultimas_3[0] - ultimas_3[2]
        return "baja", (
            f"📉 **Bajada de rendimiento:** -{caida:.1f}kg respecto a la sesión de referencia. "
            f"Posibles causas: fatiga acumulada, sueño insuficiente o nutrición deficiente."
        ), "alert-danger"

    if tasa_progreso is not None and tasa_progreso > 1.5:
        return "progreso_rapido", (
            f"🔥 **Progreso sólido:** tasa de mejora de +{tasa_progreso:.1f}% por sesión en promedio. ¡Excelente trabajo!"
        ), "alert-success"

    if ultimas_3[2] > ultimas_3[1]:
        return "progreso", (
            f"✅ **Progresando correctamente:** {ultimas_3[1]}kg → {ultimas_3[2]}kg en la última sesión."
        ), "alert-success"

    return "estable", "📊 Tendencia estable. Revisa si es momento de aplicar sobrecarga progresiva.", "alert-info"


def interpretar_tiempo(t):
    try:
        t = str(t).strip()
        if ":" in t:
            return int(t.split(":")[0]) * 60 + int(t.split(":")[1])
        return int(float(t) * 60) if float(t) < 10 else int(float(t))
    except Exception:
        return 90


def fecha_es(f):
    return f.strftime("%d/%m/%Y")


def obtener_ultimo_registro(cliente, ejercicio):
    for reg in reversed(st.session_state.historial_global):
        if reg["Cliente"] == cliente and reg["Ejercicio"] == ejercicio and reg.get("Tipo") == "Fuerza":
            return reg
    return None


def importar_historial_al_plan(cliente):
    dias_semana = {0:"Lunes",1:"Martes",2:"Miércoles",3:"Jueves",4:"Viernes",5:"Sábado",6:"Domingo"}
    nuevo_detalles = st.session_state.detalles_planes.get(cliente, {}).copy()
    nuevo_focos    = st.session_state.planes_semanales.get(cliente, {}).copy()
    rutinas_temp   = {d: [] for d in dias_semana.values()}
    focos_temp     = {d: "Descanso" for d in dias_semana.values()}
    hoy = date.today()
    for reg in reversed(st.session_state.historial_global):
        if reg["Cliente"] == cliente:
            try:
                fecha_reg = datetime.strptime(reg["Fecha"], "%d/%m/%Y").date()
                if (hoy - fecha_reg).days < 14:
                    dia = dias_semana[fecha_reg.weekday()]
                    if reg.get("Tipo") == "Fuerza":
                        txt = f"{reg['Ejercicio']}: {reg['Series']}x{reg['Reps']} ({reg['Carga']}kg)"
                    else:
                        txt = f"Cardio: {reg['Ejercicio']} ({reg['Carga']}min)"
                    if txt not in rutinas_temp[dia]:
                        rutinas_temp[dia].insert(0, txt)
                    if "Objetivo" in reg and focos_temp[dia] == "Descanso":
                        focos_temp[dia] = reg["Objetivo"]
            except Exception:
                pass
    for dia, lista in rutinas_temp.items():
        if lista:
            nuevo_detalles[dia] = f"||{chr(10).join(lista)}||"
            if focos_temp[dia] != "Descanso":
                nuevo_focos[dia] = focos_temp[dia]
            elif nuevo_focos.get(dia) == "Descanso":
                nuevo_focos[dia] = "Entrenamiento Realizado"
    st.session_state.planes_semanales[cliente] = nuevo_focos
    st.session_state.detalles_planes[cliente]  = nuevo_detalles
    guardar_datos_disco()


# =====================================================
# 6. GENERADOR PDF
# =====================================================
def generar_pdf_plan(cliente, plan_focos, plan_detalles):
    buffer = io.BytesIO()
    c      = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    COLOR_NEON    = HexColor("#39FF14")
    COLOR_OSCURO  = HexColor("#1E1E1E")
    COLOR_GRIS    = HexColor("#2D2D2D")
    COLOR_TEXTO   = HexColor("#222222")   # Negro para legibilidad en PDF blanco
    COLOR_SUBTEXTO = HexColor("#555555")

    # Encabezado
    c.setFillColor(COLOR_OSCURO)
    c.rect(0, height - 90, width, 90, fill=1, stroke=0)
    c.setFillColor(COLOR_NEON)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(50, height - 45, "PLAN DE ENTRENAMIENTO")
    c.setFont("Helvetica", 13)
    c.drawString(50, height - 68, f"Atleta: {cliente}")
    c.setFont("Helvetica", 9)
    c.drawRightString(width - 50, height - 45, "BIO SPORT PRO TRAINER")
    c.setFillColor(HexColor("#AAAAAA"))
    c.drawRightString(width - 50, height - 60, f"Generado: {date.today().strftime('%d/%m/%Y')}")

    y = height - 115
    dias_orden = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

    tipo_sem = plan_focos.get("tipo_semana", "")
    if tipo_sem:
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(COLOR_NEON)
        c.drawString(50, y, f"Microciclo: {tipo_sem}")
        y -= 25

    for dia in dias_orden:
        foco   = plan_focos.get(dia, "Descanso")
        detalle = plan_detalles.get(dia, "")
        lineas  = len(detalle.split("\n")) if detalle else 0
        altura  = 55 + lineas * 13

        if y - altura < 50:
            c.showPage()
            y = height - 50

        if foco != "Descanso":
            # Fondo del encabezado del día
            c.setFillColor(COLOR_GRIS)
            c.rect(50, y - 18, width - 100, 22, fill=1, stroke=0)
            c.setFillColor(COLOR_NEON)
            c.setFont("Helvetica-Bold", 11)
            c.drawString(58, y - 11, f"{dia.upper()}  ·  {foco}")
            c.setStrokeColor(COLOR_NEON)
            c.setLineWidth(0.5)
            c.line(50, y - 18, width - 50, y - 18)
            y -= 30

            if detalle:
                partes = detalle.split("||")
                if len(partes) == 3:
                    titulos = ["Calentamiento", "Desarrollo", "Vuelta a la Calma"]
                    for i, bloque in enumerate(partes):
                        if bloque.strip():
                            if y < 60:
                                c.showPage(); y = height - 50
                            c.setFont("Helvetica-Bold", 9)
                            c.setFillColor(COLOR_NEON)
                            c.drawString(65, y, f"[ {titulos[i]} ]")
                            y -= 13
                            c.setFont("Helvetica", 10)
                            c.setFillColor(COLOR_TEXTO)
                            for linea in bloque.split("\n"):
                                if linea.strip():
                                    if y < 50:
                                        c.showPage(); y = height - 50
                                    c.drawString(75, y, f"• {linea.strip()}")
                                    y -= 13
                            y -= 5
                else:
                    c.setFont("Helvetica", 10)
                    c.setFillColor(COLOR_TEXTO)
                    for linea in detalle.split("\n"):
                        if linea.strip():
                            if y < 50:
                                c.showPage(); y = height - 50
                            c.drawString(65, y, f"• {linea.strip()}")
                            y -= 13
            else:
                c.setFont("Helvetica-Oblique", 9)
                c.setFillColor(COLOR_SUBTEXTO)
                c.drawString(65, y, "(Sin detalles registrados)")
                y -= 13
            y -= 12
        else:
            c.setFont("Helvetica-Oblique", 9)
            c.setFillColor(COLOR_SUBTEXTO)
            c.drawString(58, y - 8, f"{dia}: Descanso / Recuperación Activa")
            y -= 25

    # Pie de página
    c.setFont("Helvetica", 8)
    c.setFillColor(COLOR_SUBTEXTO)
    c.drawCentredString(width / 2, 25, "La constancia es la clave del éxito · Bio Sport Pro Trainer")
    c.save()
    buffer.seek(0)
    return buffer


# =====================================================
# 7. PANEL ADMIN
# =====================================================
def mostrar_panel_admin():
    st.title("👑 Panel de Control Bio Sport")
    st.markdown("Resumen de alumnos activos y cálculo de mensualidades.")
    with st.spinner("Calculando cobros..."):
        try:
            client = get_gsheets_client()
            sheet  = client.open_by_url(URL_SHEET)
            reglas_cobro = {
                "eduardo":  {"tipo": "por_alumno", "valor": 2500},
                "davidp":   {"tipo": "fijo",       "valor": 10000},
                "clemente": {"tipo": "por_alumno", "valor": 2500},
            }
            datos_cobro, total_global = [], 0
            for preparador, regla in reglas_cobro.items():
                try:
                    ws = sheet.worksheet(preparador)
                    col_values = ws.col_values(1)
                    if col_values:
                        json_data   = json.loads("".join(col_values))
                        num_alumnos = len(json_data.get("clientes", {}))
                        if regla["tipo"] == "por_alumno":
                            monto      = num_alumnos * regla["valor"]
                            tipo_trato = f"${regla['valor']:,} x alumno".replace(",",".")
                        else:
                            monto      = regla["valor"]
                            tipo_trato = "Cuota Fija Mensual"
                        datos_cobro.append({
                            "Preparador":        preparador.capitalize(),
                            "Alumnos Activos":   num_alumnos,
                            "Tipo de Trato":     tipo_trato,
                            "Monto a Cobrar ($)":f"${monto:,}".replace(",","."),
                        })
                        total_global += monto
                except Exception:
                    continue

            if datos_cobro:
                c1, c2 = st.columns(2)
                c1.metric("Alumnos Totales", sum(d["Alumnos Activos"] for d in datos_cobro))
                c2.metric("Total a Recaudar", f"${total_global:,}".replace(",","."))
                st.table(pd.DataFrame(datos_cobro))
            else:
                st.warning("No hay datos registrados aún.")
        except Exception as e:
            st.error(f"Error cargando el panel: {e}")


# =====================================================
# 8. INICIALIZACIÓN DE ESTADO
# =====================================================
datos = cargar_datos_disco()

if "db_clientes"       not in st.session_state: st.session_state.db_clientes        = datos["clientes"]        if datos else {}
if "historial_global"  not in st.session_state: st.session_state.historial_global   = datos["historial"]       if datos else []
if "biblioteca_videos" not in st.session_state: st.session_state.biblioteca_videos  = datos.get("videos", VIDEOS_BASE) if datos else VIDEOS_BASE
if "planes_semanales"  not in st.session_state: st.session_state.planes_semanales   = datos.get("planes", {})  if datos else {}
if "detalles_planes"   not in st.session_state: st.session_state.detalles_planes    = datos.get("detalles_planes", {}) if datos else {}
if "notas_personales"  not in st.session_state: st.session_state.notas_personales   = datos.get("notas", "")   if datos else ""
if "cliente_activo"    not in st.session_state: st.session_state.cliente_activo     = None
if "pendiente_guardar" not in st.session_state: st.session_state.pendiente_guardar  = False


# =====================================================
# 9. SIDEBAR
# =====================================================
st.sidebar.header("⚡ Bio Sport Pro")

lista = ["Crear Nuevo..."] + list(st.session_state.db_clientes.keys())
sel   = st.sidebar.selectbox("Atleta:", lista)

if sel == "Crear Nuevo...":
    nom = st.sidebar.text_input("Nombre del nuevo atleta:")
    if st.sidebar.button("Guardar Atleta", type="primary"):
        if nom:
            nom_limpio = nom.strip()
            if nom_limpio not in st.session_state.db_clientes:
                st.session_state.db_clientes[nom_limpio] = {
                    "Peso":70, "Talla":170, "Edad":25, "Sexo":"Masculino"
                }
                guardar_datos_disco()
                registrar_auditoria_cobro(nom_limpio)
                st.toast("Atleta registrado", icon="🔥")
                time.sleep(0.8)
                st.rerun()
            else:
                st.sidebar.warning("Ese atleta ya existe.")
else:
    st.session_state.cliente_activo = sel

    with st.sidebar.expander("⚙️ Gestión", expanded=False):
        # CONFIRMACIÓN antes de eliminar
        if "confirm_delete" not in st.session_state:
            st.session_state.confirm_delete = False

        if not st.session_state.confirm_delete:
            if st.button("🗑️ Eliminar Atleta"):
                st.session_state.confirm_delete = True
                st.rerun()
        else:
            st.warning(f"¿Eliminar a **{sel}** permanentemente? Esta acción no se puede deshacer.")
            col_si, col_no = st.columns(2)
            if col_si.button("✅ Sí, eliminar"):
                del st.session_state.db_clientes[sel]
                st.session_state.historial_global = [
                    h for h in st.session_state.historial_global if h["Cliente"] != sel
                ]
                if sel in st.session_state.planes_semanales:   del st.session_state.planes_semanales[sel]
                if sel in st.session_state.detalles_planes:    del st.session_state.detalles_planes[sel]
                guardar_datos_disco()
                st.session_state.cliente_activo  = None
                st.session_state.confirm_delete  = False
                st.rerun()
            if col_no.button("❌ Cancelar"):
                st.session_state.confirm_delete = False
                st.rerun()

        json_str = json.dumps({
            "clientes": st.session_state.db_clientes,
            "historial": st.session_state.historial_global,
            "planes": st.session_state.planes_semanales,
            "detalles": st.session_state.detalles_planes,
        }, indent=4, ensure_ascii=False)
        st.download_button("💾 Backup JSON", data=json_str,
                           file_name="backup_biosport.json", mime="application/json")

with st.sidebar.expander("🧮 Calculadora RM", expanded=False):
    p_rm = st.number_input("Peso (kg)", 0.0, step=0.5, key="rm_peso")
    r_rm = st.number_input("Reps",      1, 20, 8,        key="rm_reps")
    if p_rm > 0:
        rm = calcular_1rm(p_rm, r_rm)
        st.write(f"**1RM estimado: {rm:.1f} kg**")
        cols_rm = st.columns(2)
        cols_rm[0].caption(f"90%: {rm*0.9:.1f}kg\n80%: {rm*0.8:.1f}kg")
        cols_rm[1].caption(f"70%: {rm*0.7:.1f}kg\n60%: {rm*0.6:.1f}kg")

opciones_menu = [
    "0. 🏠 Inicio",
    "1. 📋 Ficha & Antropo",
    "2. 💪 Entrenamiento",
    "3. 🧠 Plan Semanal",
    "4. 🏃‍♂️ Cardio",
    "5. 📈 Progreso",
    "6. 📚 Guías Completas",
    "7. 📝 Notas",
    "8. 🎥 Videoteca",
]
if st.session_state.get("usuario_actual") == "visho":
    opciones_menu.append("👑 Panel Admin")

menu = st.sidebar.radio("Menú:", opciones_menu)
st.sidebar.divider()
if st.session_state.cliente_activo:
    st.sidebar.success(f"Atleta: {st.session_state.cliente_activo}")


# =====================================================
# PESTAÑA 0: INICIO — DASHBOARD
# =====================================================
if menu == "0. 🏠 Inicio":
    st.title("⚡ Dashboard Bio Sport")
    st.markdown("Visión general de tus atletas y rendimiento diario.")

    total_atletas = len(st.session_state.db_clientes)
    hoy_str       = date.today().strftime("%d/%m/%Y")
    entrenos_hoy  = len([h for h in st.session_state.historial_global if h["Fecha"] == hoy_str])
    total_registros = len(st.session_state.historial_global)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👥 Atletas Activos",       total_atletas)
    col2.metric("🔥 Sesiones Hoy",          entrenos_hoy)
    col3.metric("📊 Registros Totales",     total_registros)
    col4.metric("📅 Fecha",                 hoy_str)

    st.divider()

    if st.session_state.db_clientes:
        st.subheader("📋 Resumen por Atleta")
        filas = []
        for nombre, datos_c in st.session_state.db_clientes.items():
            regs  = [h for h in st.session_state.historial_global if h["Cliente"] == nombre]
            ultimo = regs[-1]["Fecha"] if regs else "Sin registros"
            filas.append({
                "Atleta":           nombre,
                "Edad":             datos_c.get("Edad", "-"),
                "Objetivo":         datos_c.get("Objetivo_Prin", "-"),
                "Experiencia":      datos_c.get("Experiencia", "-"),
                "Sesiones Totales": len(regs),
                "Último Registro":  ultimo,
            })
        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("💡 Tips del Sistema")
    st.info(
        "- La **pestaña Progreso** ahora detecta automáticamente estancamientos, bajadas y progreso rápido.\n"
        "- La **pestaña Cardio** ya registra sesiones en el historial.\n"
        "- El botón **Eliminar Atleta** ahora pide confirmación antes de borrar.\n"
        "- Los datos se guardan con el botón 💾 para reducir llamadas a la API de Google Sheets."
    )


# =====================================================
# PESTAÑA 1: FICHA Y ANTROPOMETRÍA
# =====================================================
elif menu == "1. 📋 Ficha & Antropo":
    if not st.session_state.cliente_activo:
        st.warning("Selecciona un atleta en el menú lateral.")
        st.stop()

    c = st.session_state.cliente_activo
    d = st.session_state.db_clientes[c]

    t1, t2, t3 = st.tabs(["📝 Datos Básicos", "📏 Antropometría", "🏥 Anamnesis"])

    with t1:
        col1, col2, col3, col4 = st.columns(4)
        np_ = col1.number_input("Peso (kg)",  0.1, 250.0, float(d.get("Peso",  70)),  step=0.5)
        nt_ = col2.number_input("Talla (cm)", 50.0, 250.0, float(d.get("Talla", 170)), step=0.5)
        ne_ = col3.number_input("Edad",        5,   100,   int(d.get("Edad",    25)))
        ns_ = col4.selectbox("Sexo", ["Masculino","Femenino"],
                             index=0 if d.get("Sexo","Masculino")=="Masculino" else 1)

        imc = np_ / ((nt_ / 100) ** 2)
        st.caption(f"IMC calculado: **{imc:.1f}**")

        if st.button("Actualizar Datos Básicos", type="primary"):
            st.session_state.db_clientes[c].update({"Peso":np_,"Talla":nt_,"Edad":ne_,"Sexo":ns_})
            guardar_datos_disco()
            st.toast("Datos actualizados", icon="💾")

        st.divider()
        if st.checkbox("❤️ Calcular FCM (Tanaka)"):
            fcm = 208 - (0.7 * ne_)
            st.info(f"FCM estimada: **{fcm:.0f} lpm** · Fórmula Tanaka (208 − 0.7 × Edad)")
            col_z1, col_z2, col_z3, col_z4, col_z5 = st.columns(5)
            col_z1.metric("Z1 (<60%)",  f"{fcm*0.60:.0f}")
            col_z2.metric("Z2 (75%)",   f"{fcm*0.75:.0f}")
            col_z3.metric("Z3 (85%)",   f"{fcm*0.85:.0f}")
            col_z4.metric("Z4 (95%)",   f"{fcm*0.95:.0f}")
            col_z5.metric("Z5 (100%)",  f"{fcm:.0f}")

    with t2:
        st.subheader("Cálculo de Grasa — Durnin 4 Pliegues + Siri")
        col_in, col_out = st.columns(2)
        with col_in:
            st.caption("Ingresa los pliegues en mm:")
            p1 = st.number_input("Bíceps (mm)",        0.0, 100.0, 0.0, step=0.1)
            p2 = st.number_input("Tríceps (mm)",       0.0, 100.0, 0.0, step=0.1)
            p3 = st.number_input("Subescapular (mm)",  0.0, 100.0, 0.0, step=0.1)
            p4 = st.number_input("Suprailiaco (mm)",   0.0, 100.0, 0.0, step=0.1)
            suma = p1 + p2 + p3 + p4

        with col_out:
            if suma > 0:
                try:
                    grasa = calcular_durnin(d.get("Edad",25), d.get("Sexo","Masculino"), suma)
                    if not (2 <= grasa <= 60):
                        st.warning(f"Resultado fuera de rango ({grasa:.1f}%). Verifica los pliegues.")
                    else:
                        masa_magra = d.get("Peso",70) * (1 - grasa/100)
                        st.metric("% Grasa",    f"{grasa:.1f}%")
                        st.metric("Masa Magra", f"{masa_magra:.1f} kg")
                        st.metric("Masa Grasa", f"{d.get('Peso',70) - masa_magra:.1f} kg")

                        categoria, color = evaluar_grasa(d.get("Edad",25), d.get("Sexo","Masculino"), grasa)
                        st.markdown(f"""
                        <div style="background:#2D2D2D;padding:15px;border-radius:8px;
                                    text-align:center;border:1px solid {color};margin-top:12px;">
                            <div style="color:#aaa;font-size:12px;">Clasificación:</div>
                            <div style="color:{color};font-size:1.4rem;font-weight:700;
                                        text-transform:uppercase;">{categoria}</div>
                        </div>""", unsafe_allow_html=True)
                except ValueError as e:
                    st.error(f"Error en el cálculo: {e}")
            else:
                st.info("Ingresa los 4 pliegues para calcular.")

    with t3:
        st.subheader("Historial Clínico y Deportivo")
        col1, col2 = st.columns(2)
        fono      = col1.text_input("📱 Teléfono / WhatsApp",    value=d.get("Telefono",  ""))
        emergencia= col2.text_input("🚨 Contacto de Emergencia", value=d.get("Emergencia",""))
        st.divider()
        lesiones     = st.text_area("🩹 Lesiones o Molestias",        value=d.get("Lesiones",   ""), height=90)
        enfermedades = st.text_area("💊 Enfermedades / Medicamentos",  value=d.get("Enfermedades",""), height=70)
        st.divider()
        col3, col4 = st.columns(2)
        opciones_exp = ["Principiante","Intermedio","Avanzado"]
        exp_actual   = d.get("Experiencia","Principiante")
        if exp_actual not in opciones_exp: exp_actual = "Principiante"
        experiencia   = col3.selectbox("🏋️ Nivel de Experiencia", opciones_exp, index=opciones_exp.index(exp_actual))
        objetivo_prin = col4.text_input("🎯 Objetivo Principal", value=d.get("Objetivo_Prin",""))
        estilo_vida   = st.text_area("💼 Estilo de Vida y Estrés", value=d.get("Estilo_Vida",""), height=70)

        if st.button("💾 Guardar Anamnesis", type="primary"):
            st.session_state.db_clientes[c].update({
                "Telefono": fono, "Emergencia": emergencia,
                "Lesiones": lesiones, "Enfermedades": enfermedades,
                "Experiencia": experiencia, "Objetivo_Prin": objetivo_prin,
                "Estilo_Vida": estilo_vida,
            })
            guardar_datos_disco()
            st.toast("Historial clínico guardado", icon="🏥")


# =====================================================
# PESTAÑA 2: ENTRENAMIENTO
# =====================================================
elif menu == "2. 💪 Entrenamiento":
    if not st.session_state.cliente_activo:
        st.stop()

    c = st.session_state.cliente_activo
    fecha_sel = st.date_input("📅 Fecha de la Sesión:", date.today())
    dia_nombre = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"][fecha_sel.weekday()]

    plan_foco = st.session_state.planes_semanales.get(c, {}).get(dia_nombre, "Sin planificar")
    plan_det  = st.session_state.detalles_planes.get(c, {}).get(dia_nombre, "")

    if plan_foco == "Descanso":
        st.success(f"🛌 **{dia_nombre}:** Día de descanso planificado.")
    else:
        st.info(f"🔥 **{dia_nombre}:** {plan_foco}")
        if plan_det:
            with st.expander("👀 Ver Detalles del Plan", expanded=True):
                partes = plan_det.split("||")
                if len(partes) == 3:
                    if partes[0].strip(): st.markdown("**1️⃣ Calentamiento:**\n" + partes[0])
                    if partes[1].strip(): st.markdown("**2️⃣ Desarrollo:**\n"    + partes[1])
                    if partes[2].strip(): st.markdown("**3️⃣ Vuelta a la Calma:**\n" + partes[2])
                else:
                    st.text(plan_det)

    st.divider()
    col_ent, col_timer = st.columns([3, 1])

    with col_ent:
        obj_sel = st.selectbox("🎯 Objetivo Sesión:", list(SUGERENCIAS_OBJETIVO.keys()))
        sug     = SUGERENCIAS_OBJETIVO[obj_sel]
        st.caption(f"Guía: {sug['Reps']} reps · RM: {sug['RM']} · Pausa: {sug['Pausa']} · RPE: {sug['RPE']}")

        ej_sel = st.selectbox("Ejercicio:", list(st.session_state.biblioteca_videos.keys()) + ["✍️ Otro..."])
        if ej_sel != "✍️ Otro...":
            ultimo = obtener_ultimo_registro(c, ej_sel)
            if ultimo:
                st.info(f"💡 Último registro: {ultimo['Series']}x{ultimo['Reps']} @ {ultimo['Carga']}kg")
                rm_calc = calcular_1rm(ultimo["Carga"], ultimo["Reps"])
                st.caption(f"1RM estimado: {rm_calc:.1f}kg · 80%: {rm_calc*0.8:.1f}kg · 70%: {rm_calc*0.7:.1f}kg")

        nom = st.text_input("Nombre:", value=ej_sel if ej_sel != "✍️ Otro..." else "")
        c1, c2, c3 = st.columns(3)
        se  = c1.number_input("Series", 1, 10, 4)
        re  = c2.number_input("Reps",   1, 50, 10)
        kg  = c3.number_input("Carga (kg)", 0.0, step=0.5)
        pt  = st.text_input("Pausa (ej: 2:00 o 120)", value=sug["Pausa"].split("-")[0])
        rpe = st.slider("RPE sesión", 1, 10, 7)

        if st.button("➕ Registrar Serie", type="primary"):
            if nom.strip():
                st.session_state.historial_global.append({
                    "Cliente":  c,
                    "Fecha":    fecha_es(fecha_sel),
                    "Ejercicio":nom.strip(),
                    "Series":   se,
                    "Reps":     re,
                    "Carga":    kg,
                    "RPE":      rpe,
                    "Tipo":     "Fuerza",
                    "Objetivo": obj_sel,
                })
                guardar_datos_disco()
                st.toast("Serie registrada", icon="💪")
                st.rerun()
            else:
                st.warning("Escribe el nombre del ejercicio.")

        # Historial del día
        hist_dia = [h for h in st.session_state.historial_global
                    if h["Cliente"] == c and h["Fecha"] == fecha_es(fecha_sel)]
        if hist_dia:
            st.divider()
            st.subheader(f"📝 Sesión del {fecha_es(fecha_sel)}")
            volumen_total = sum(h["Series"] * h["Reps"] * h["Carga"] for h in hist_dia if h.get("Tipo") == "Fuerza")
            st.caption(f"Volumen total de la sesión: **{volumen_total:.0f} kg·rep**")
            for i, h in enumerate(st.session_state.historial_global):
                if h["Cliente"] == c and h["Fecha"] == fecha_es(fecha_sel):
                    col_inf, col_del = st.columns([4, 1])
                    col_inf.write(f"✅ {h['Ejercicio']}: {h['Series']}x{h['Reps']} @ {h['Carga']}kg (RPE {h.get('RPE','-')})")
                    if col_del.button("🗑️", key=f"del_{i}"):
                        del st.session_state.historial_global[i]
                        guardar_datos_disco()
                        st.rerun()

    with col_timer:
        st.write("⏱️ Descanso")
        seg = interpretar_tiempo(pt)
        st.write(f"Pausa: **{seg}s**")
        if st.button(f"▶ Iniciar Timer"):
            ph  = st.empty()
            bar = st.progress(0.0)
            for i in range(seg, -1, -1):
                ph.metric("Restante", f"{i}s")
                bar.progress(1.0 - (i / seg) if seg > 0 else 1.0)
                time.sleep(1)
            ph.success("✅ ¡Tiempo!")
            bar.empty()


# =====================================================
# PESTAÑA 3: PLAN SEMANAL
# =====================================================
elif menu == "3. 🧠 Plan Semanal":
    if not st.session_state.cliente_activo:
        st.stop()

    c = st.session_state.cliente_activo
    col_head1, col_head2 = st.columns([3, 1])
    col_head1.subheader(f"Planificación Semanal — {c}")
    with col_head2:
        if st.button("🔄 Cargar Historial"):
            importar_historial_al_plan(c)
            st.toast("Historial importado al plan", icon="✅")
            st.rerun()

    tipos_semana = ["Ajuste (Descarga)", "Carga (Desarrollo)", "Impacto (Choque)"]
    tipo_guardado = st.session_state.planes_semanales.get(c, {}).get("tipo_semana", "Carga (Desarrollo)")
    microciclo_sel = st.select_slider(
        "📊 Intensidad del Microciclo:",
        options=tipos_semana,
        value=tipo_guardado if tipo_guardado in tipos_semana else "Carga (Desarrollo)"
    )
    if microciclo_sel == "Ajuste (Descarga)":
        st.info("📉 Recuperación y técnica. RPE 5-7. Volumen reducido.")
    elif microciclo_sel == "Carga (Desarrollo)":
        st.success("📈 Desarrollo progresivo. RPE 7-8.5. Cargas crecientes.")
    else:
        st.error("🔥 Sobrecarga máxima. RPE 9-10. Esfuerzo máximo.")

    # Consulta a Dante (IA)
    with st.expander("🤖 Consultar a Dante (IA)"):
        datos_ficha = st.session_state.db_clientes.get(c, {})
        perfil = (f"Edad: {datos_ficha.get('Edad','N/A')}, "
                  f"Experiencia: {datos_ficha.get('Experiencia','N/A')}, "
                  f"Lesiones: {datos_ficha.get('Lesiones','Ninguna')}, "
                  f"Objetivo: {datos_ficha.get('Objetivo_Prin','General')}.")
        col_dia, col_btn = st.columns([2, 1])
        dia_dante = col_dia.selectbox("Enfoque:", ["Pierna","Torso","Full Body","Cardio","Glúteo","Brazo"])
        if col_btn.button("✨ Generar Rutina") and modelo_dante:
            with st.spinner("Dante está diseñando tu rutina..."):
                prompt = (
                    f"Eres Dante, entrenador experto en periodización. "
                    f"Perfil del atleta: {perfil}. "
                    f"Microciclo actual: {microciclo_sel}. "
                    f"Crea una rutina completa para: {dia_dante}. "
                    f"Estructura exacta:\n"
                    f"1. Calentamiento (5-10 min)\n"
                    f"2. Bloque principal (ejercicios con series, reps, descanso)\n"
                    f"3. Vuelta a la calma (5 min)\n"
                    f"Sé específico, conciso y evita agravar las lesiones mencionadas."
                )
                try:
                    respuesta = modelo_dante.generate_content(prompt)
                    st.markdown(respuesta.text)
                except Exception as e:
                    st.error(f"Error con Dante: {e}")
        elif not modelo_dante:
            st.warning("Dante no está disponible. Verifica la API key de Gemini.")

    # Editor de días
    opciones = ["Descanso","Pierna","Pecho/Hombro","Espalda","Glúteo","Full Body","Torso","Brazo","Cardio"]
    dias     = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
    nuevo_focos   = {"tipo_semana": microciclo_sel}
    nuevo_detalles = {}

    for dia in dias:
        with st.expander(f"📅 {dia}", expanded=False):
            val_def = st.session_state.planes_semanales.get(c, {}).get(dia, "Descanso")
            if val_def not in opciones:
                opciones.append(val_def)
            nuevo_focos[dia] = st.selectbox(
                f"Enfoque {dia}", opciones,
                index=opciones.index(val_def), key=f"foco_{dia}"
            )
            if nuevo_focos[dia] != "Descanso":
                partes = st.session_state.detalles_planes.get(c, {}).get(dia, "||").split("||")
                cal_def = partes[0] if len(partes) > 0 else ""
                des_def = partes[1] if len(partes) > 1 else ""
                vue_def = partes[2] if len(partes) > 2 else ""

                col1, col2, col3 = st.columns(3)
                calentamiento = col1.text_area("1️⃣ Calentamiento", value=cal_def, key=f"cal_{dia}", height=150)
                desarrollo    = col2.text_area("2️⃣ Desarrollo",    value=des_def, key=f"des_{dia}", height=150)
                vuelta        = col3.text_area("3️⃣ Vuelta a la Calma", value=vue_def, key=f"vue_{dia}", height=150)
                nuevo_detalles[dia] = f"{calentamiento}||{desarrollo}||{vuelta}"
            else:
                nuevo_detalles[dia] = ""

    col_guardar, col_pdf = st.columns(2)
    with col_guardar:
        if st.button("💾 Guardar Plan", type="primary"):
            st.session_state.planes_semanales[c] = nuevo_focos
            st.session_state.detalles_planes[c]  = nuevo_detalles
            ok = guardar_datos_disco()
            st.toast("Plan guardado" if ok else "Error al guardar", icon="📅" if ok else "❌")

    with col_pdf:
        try:
            pdf_bytes = generar_pdf_plan(c, nuevo_focos, nuevo_detalles)
            st.download_button(
                "📄 Descargar PDF",
                data=pdf_bytes,
                file_name=f"Rutina_{c.replace(' ','_')}.pdf",
                mime="application/pdf"
            )
        except Exception as e:
            st.error(f"Error generando PDF: {e}")


# =====================================================
# PESTAÑA 4: CARDIO — AHORA REGISTRA EN EL HISTORIAL
# =====================================================
elif menu == "4. 🏃‍♂️ Cardio":
    if not st.session_state.cliente_activo:
        st.stop()

    c = st.session_state.cliente_activo
    d = st.session_state.db_clientes[c]
    st.title(f"🏃‍♂️ Cardio — {c}")

    t_calc, t_registro = st.tabs(["🧮 Calculadora VAM", "📝 Registrar Sesión"])

    with t_calc:
        st.subheader("Calculadora de Velocidad Aeróbica Máxima (VAM)")
        vam_actual = d.get("VAM", 0.0)
        col_v1, col_v2 = st.columns(2)
        nueva_vam = col_v1.number_input("VAM del atleta (m/s)", 0.0, 10.0, float(vam_actual), step=0.1)
        if col_v2.button("Actualizar VAM"):
            st.session_state.db_clientes[c]["VAM"] = nueva_vam
            guardar_datos_disco()
            st.toast("VAM actualizada", icon="💾")
            vam_actual = nueva_vam

        if vam_actual > 0:
            st.divider()
            st.subheader("Calculadora de Tiempos por Distancia")
            col_d, col_p = st.columns(2)
            dist = col_d.number_input("Distancia (m)", 100, 10000, 400, step=100)
            pct  = col_p.slider("% Intensidad (VAM)", 50, 120, 90)
            vel_objetivo = vam_actual * (pct / 100)
            tiempo_seg   = dist / vel_objetivo if vel_objetivo > 0 else 0
            mins, segs   = divmod(int(tiempo_seg), 60)

            col_r1, col_r2, col_r3 = st.columns(3)
            col_r1.metric("Velocidad Objetivo", f"{vel_objetivo:.2f} m/s")
            col_r2.metric("Tiempo Objetivo",    f"{mins}:{segs:02d}")
            col_r3.metric("Ritmo /km",          f"{int(1000/vel_objetivo//60)}:{int(1000/vel_objetivo%60):02d} min/km" if vel_objetivo > 0 else "-")

            st.divider()
            st.subheader("Tabla de Zonas de Cardio Personalizadas")
            zonas_data = []
            for zona, pct_rango, label in [
                ("Z1 Regenerativo","< 60%", "Muy fácil"),
                ("Z2 Aeróbico",    "60-75%","Fácil"),
                ("Z3 Umbral",      "75-90%","Duro"),
                ("Z4 VO2Max",      "95-105%","Muy duro"),
                ("Z5 Anaeróbico",  "> 110%","Agonía"),
            ]:
                lo_str, hi_str = (pct_rango.replace(">","").replace("<","").strip(), None) if "-" not in pct_rango else pct_rango.split("-")
                try:
                    lo = float(lo_str.replace("%","")) / 100
                    hi = float(hi_str.replace("%","")) / 100 if hi_str else lo * 1.1
                    zonas_data.append({
                        "Zona": zona,
                        "% VAM": pct_rango,
                        "Vel Mín (m/s)": f"{vam_actual*lo:.2f}",
                        "Vel Máx (m/s)": f"{vam_actual*hi:.2f}",
                        "Sensación": label,
                    })
                except Exception:
                    pass
            st.dataframe(pd.DataFrame(zonas_data), use_container_width=True, hide_index=True)

    with t_registro:
        st.subheader("Registrar Sesión de Cardio")
        fecha_cardio = st.date_input("Fecha:", date.today(), key="fecha_cardio")
        col_c1, col_c2 = st.columns(2)
        tipo_cardio = col_c1.selectbox("Tipo de actividad:", TIPOS_CARDIO)
        zona_cardio = col_c2.selectbox("Zona de Intensidad:", ["Z1","Z2","Z3","Z4","Z5"])
        col_c3, col_c4, col_c5 = st.columns(3)
        duracion  = col_c3.number_input("Duración (min)", 1, 300, 30)
        distancia_c = col_c4.number_input("Distancia (km, opcional)", 0.0, 200.0, 0.0, step=0.1)
        fc_prom   = col_c5.number_input("FC Promedio (lpm, opcional)", 0, 250, 0)
        notas_c   = st.text_area("Notas de la sesión:", height=70)

        if st.button("➕ Registrar Cardio", type="primary"):
            registro_cardio = {
                "Cliente":    c,
                "Fecha":      fecha_es(fecha_cardio),
                "Ejercicio":  tipo_cardio,
                "Series":     1,
                "Reps":       1,
                "Carga":      duracion,
                "Tipo":       "Cardio",
                "Objetivo":   f"Cardio Z{zona_cardio[-1]}",
                "Zona":       zona_cardio,
                "Distancia":  distancia_c,
                "FC_Prom":    fc_prom,
                "Notas":      notas_c,
            }
            st.session_state.historial_global.append(registro_cardio)
            guardar_datos_disco()
            st.toast("Sesión de cardio registrada", icon="🏃")
            st.rerun()

        # Historial cardio
        hist_cardio = [h for h in st.session_state.historial_global
                       if h["Cliente"] == c and h.get("Tipo") == "Cardio"]
        if hist_cardio:
            st.divider()
            st.subheader("📊 Historial de Cardio")
            df_cardio = pd.DataFrame(hist_cardio)[["Fecha","Ejercicio","Carga","Zona","Distancia","FC_Prom","Notas"]]
            df_cardio.columns = ["Fecha","Actividad","Duración (min)","Zona","Dist (km)","FC Prom","Notas"]
            st.dataframe(df_cardio.tail(20), use_container_width=True, hide_index=True)

            if len(hist_cardio) >= 3:
                st.subheader("📈 Evolución de Duración")
                df_plot = pd.DataFrame(hist_cardio).tail(20)
                st.line_chart(df_plot, x="Fecha", y="Carga")


# =====================================================
# PESTAÑA 5: PROGRESO — ANÁLISIS INTELIGENTE MEJORADO
# =====================================================
elif menu == "5. 📈 Progreso":
    if not st.session_state.cliente_activo:
        st.stop()

    c  = st.session_state.cliente_activo
    df_all = pd.DataFrame([r for r in st.session_state.historial_global if r["Cliente"] == c])

    if df_all.empty:
        st.info("Sin datos para analizar. Comienza a registrar sesiones.")
        st.stop()

    t_fuerza, t_cardio, t_historial = st.tabs(["💪 Fuerza", "🏃 Cardio", "📋 Historial Completo"])

    with t_fuerza:
        df_f = df_all[df_all.get("Tipo", pd.Series(["Fuerza"]*len(df_all))) == "Fuerza"] if "Tipo" in df_all.columns else df_all
        if not df_f.empty:
            ejercicios = df_f["Ejercicio"].unique().tolist()
            ej_sel = st.selectbox("Selecciona Ejercicio:", ejercicios)
            datos_ej = df_f[df_f["Ejercicio"] == ej_sel].copy()

            if not datos_ej.empty:
                st.subheader(f"📈 Evolución de Carga — {ej_sel}")
                st.line_chart(datos_ej, x="Fecha", y="Carga")

                col_s1, col_s2, col_s3 = st.columns(3)
                col_s1.metric("Carga Máxima",  f"{datos_ej['Carga'].max():.1f} kg")
                col_s2.metric("Carga Promedio", f"{datos_ej['Carga'].mean():.1f} kg")
                col_s3.metric("Sesiones",       len(datos_ej))

                st.subheader("🧠 Análisis Automático")
                estado, mensaje, clase = analizar_progreso_avanzado(datos_ej)
                st.markdown(f'<div class="alert-box {clase}">{mensaje}</div>', unsafe_allow_html=True)

                if "RPE" in datos_ej.columns and datos_ej["RPE"].notna().any():
                    st.subheader("😤 Evolución del RPE")
                    st.line_chart(datos_ej, x="Fecha", y="RPE")
        else:
            st.info("Sin datos de fuerza registrados.")

    with t_cardio:
        df_c = df_all[df_all.get("Tipo", pd.Series()) == "Cardio"] if "Tipo" in df_all.columns else pd.DataFrame()
        if not df_c.empty:
            st.subheader("🏃 Sesiones de Cardio")
            st.line_chart(df_c, x="Fecha", y="Carga")
            col_c1, col_c2, col_c3 = st.columns(3)
            col_c1.metric("Sesiones Totales",  len(df_c))
            col_c2.metric("Duración Promedio", f"{df_c['Carga'].mean():.0f} min")
            col_c3.metric("Duración Máxima",   f"{df_c['Carga'].max():.0f} min")
        else:
            st.info("Sin sesiones de cardio registradas.")

    with t_historial:
        st.subheader("📋 Historial Completo")

        col_f1, col_f2 = st.columns(2)
        fecha_ini = col_f1.date_input("Desde:", value=date.today() - pd.Timedelta(days=30))
        fecha_fin = col_f2.date_input("Hasta:", value=date.today())

        df_filtrado = df_all.copy()
        try:
            df_filtrado["Fecha_dt"] = pd.to_datetime(df_filtrado["Fecha"], format="%d/%m/%Y")
            df_filtrado = df_filtrado[
                (df_filtrado["Fecha_dt"] >= pd.Timestamp(fecha_ini)) &
                (df_filtrado["Fecha_dt"] <= pd.Timestamp(fecha_fin))
            ]
        except Exception:
            pass

        if "Ejercicio" in df_filtrado.columns:
            busqueda = st.text_input("🔍 Buscar ejercicio:", "")
            if busqueda:
                df_filtrado = df_filtrado[df_filtrado["Ejercicio"].str.contains(busqueda, case=False, na=False)]

        cols_mostrar = [col for col in ["Fecha","Ejercicio","Series","Reps","Carga","RPE","Tipo","Objetivo"] if col in df_filtrado.columns]
        st.dataframe(df_filtrado[cols_mostrar].sort_values("Fecha", ascending=False),
                     use_container_width=True, hide_index=True)

        st.caption(f"Mostrando {len(df_filtrado)} registros")

        # Eliminar registros por fecha
        with st.expander("🗑️ Eliminar registros del historial"):
            fecha_borrar = st.date_input("Eliminar registros de esta fecha:", date.today())
            regs_fecha   = [h for h in st.session_state.historial_global
                           if h["Cliente"] == c and h["Fecha"] == fecha_es(fecha_borrar)]
            if regs_fecha:
                st.warning(f"Se eliminarán {len(regs_fecha)} registros del {fecha_es(fecha_borrar)}.")
                if st.button("Confirmar eliminación"):
                    st.session_state.historial_global = [
                        h for h in st.session_state.historial_global
                        if not (h["Cliente"] == c and h["Fecha"] == fecha_es(fecha_borrar))
                    ]
                    guardar_datos_disco()
                    st.success("Registros eliminados.")
                    st.rerun()
            else:
                st.info("No hay registros en esa fecha.")


# =====================================================
# PESTAÑA 6: GUÍAS COMPLETAS
# =====================================================
elif menu == "6. 📚 Guías Completas":
    t1, t2, t3, t4, t5 = st.tabs(["Fuerza (Badillo)","Planif. (Bompa)","Tempo & Pausa","RPE & Borg","Zonas Cardio"])
    with t1: st.table(TABLA_BADILLO)
    with t2: st.table(GUIAS_BOMPA)
    with t3:
        col1, col2 = st.columns(2)
        col1.table(GUIA_TEMPO)
        col2.table(GUIA_DESCANSOS)
    with t4:
        col1, col2 = st.columns(2)
        col1.table(ESCALA_RPE)
        col2.table(ESCALA_BORG)
    with t5:
        st.table(GUIA_ZONAS_CARDIO)


# =====================================================
# PESTAÑA 7: NOTAS
# =====================================================
elif menu == "7. 📝 Notas":
    st.title("📝 Notas Personales")
    st.caption("Espacio privado — solo visible para ti.")
    notas = st.text_area("Tus apuntes:", value=st.session_state.notas_personales, height=350)
    if st.button("💾 Guardar Notas", type="primary"):
        st.session_state.notas_personales = notas
        ok = guardar_datos_disco()
        st.toast("Notas guardadas en la nube" if ok else "Error al guardar", icon="☁️" if ok else "❌")


# =====================================================
# PESTAÑA 8: VIDEOTECA
# =====================================================
elif menu == "8. 🎥 Videoteca":
    st.title("🎥 Videoteca y Biblioteca de Ejercicios")
    df_v = pd.DataFrame(
        list(st.session_state.biblioteca_videos.items()),
        columns=["Ejercicio","Enlace"]
    )
    st.dataframe(df_v, use_container_width=True, hide_index=True)
    st.divider()

    col_add, col_del = st.columns(2)
    with col_add:
        st.subheader("➕ Agregar Ejercicio")
        n_ej = st.text_input("Nombre:")
        n_li = st.text_input("Enlace (YouTube, Drive, etc.):")
        if st.button("Guardar Ejercicio", type="primary"):
            if n_ej.strip():
                st.session_state.biblioteca_videos[n_ej.strip()] = n_li.strip()
                guardar_datos_disco()
                st.toast(f"'{n_ej}' agregado", icon="✅")
                st.rerun()
            else:
                st.warning("Escribe un nombre para el ejercicio.")

    with col_del:
        st.subheader("🗑️ Eliminar Ejercicio")
        lista_ejercicios = list(st.session_state.biblioteca_videos.keys())
        if lista_ejercicios:
            ej_borrar = st.selectbox("Selecciona:", lista_ejercicios)
            if st.button("Eliminar"):
                del st.session_state.biblioteca_videos[ej_borrar]
                guardar_datos_disco()
                st.success(f"'{ej_borrar}' eliminado.")
                time.sleep(0.8)
                st.rerun()
        else:
            st.info("La videoteca está vacía.")


# =====================================================
# PANEL ADMIN
# =====================================================
elif menu == "👑 Panel Admin":
    mostrar_panel_admin()
