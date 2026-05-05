import streamlit as st
import pandas as pd
import math
import time
import json
import os
import io
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, datetime, timedelta

# --- AGREGADO PARA DANTE (IA) ---
import google.generativeai as genai

try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    modelos_validos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    if modelos_validos:
        cerebro_elegido = modelos_validos[0]
        modelo_dante = genai.GenerativeModel(cerebro_elegido)
    else:
        modelo_dante = None
        st.error("No se encontraron modelos de IA compatibles en tu cuenta.")
except Exception as e:
    st.error(f"⚠️ Error despertando a Dante: {e}")
    modelo_dante = None
# --------------------------------

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.colors import HexColor
except ImportError:
    st.error("⚠️ Falta la librería 'reportlab'. Instálala escribiendo: pip install reportlab")

# =====================================================
# 1. CONFIGURACIÓN DE PÁGINA
# =====================================================
st.set_page_config(page_title="Bio Sport Pro Trainer", layout="wide", page_icon="⚡")

def validar_usuario(usuario, clave):
    usuarios_validos = {
        "visho": "Bio2026",
        "eduardo": "Bio2026",
        "davidp": "Davidp2026",
        "clemente": "Clemente2026",
    }
    return usuarios_validos.get(usuario) == clave

def login():
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        # Título de login centralizado
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.title("⚡ ACCESO BIO SPORT")
            st.markdown("Plataforma de Alto Rendimiento")
            with st.form("formulario_login"):
                usuario = st.text_input("Usuario").lower().strip()
                clave = st.text_input("Contraseña", type="password")
                boton_entrar = st.form_submit_button("Entrar al Sistema", type="primary")
                
                if boton_entrar:
                    if validar_usuario(usuario, clave):
                        st.session_state["autenticado"] = True
                        st.session_state["usuario_actual"] = usuario
                        st.rerun()
                    else:
                        st.error("Credenciales incorrectas")
        return False
    return True

if not login():
    st.stop()

st.sidebar.markdown(f"### 👤 Entrenador: **{st.session_state['usuario_actual'].capitalize()}**")

if st.sidebar.button("Cerrar Sesión"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# =====================================================
# 2. TABLAS TÉCNICAS Y VIDEOTECA
# =====================================================
VIDEOS_BASE = {
    "Sentadilla Goblet": "https://www.youtube.com/watch?v=MeIiIdhvXT4",
    "Sentadilla Libre": "https://www.youtube.com/watch?v=1OoMs3MaXI4",
    "Flexiones": "https://www.youtube.com/watch?v=e_K0yT3t3IM",
    "Jalón al Pecho": "https://www.youtube.com/watch?v=HSoHeSrp-j4",
    "Peso Muerto Rumano": "https://www.youtube.com/watch?v=JCXUYuzwNrM",
    "Plancha Abdominal": "https://www.youtube.com/watch?v=ASdvN_XEl_c",
    "Press Banca": "https://www.youtube.com/watch?v=VmB1G1K7v94"
}
SUGERENCIAS_OBJETIVO = {
    "Hipertrofia": {"Reps": "6-12", "Pausa": "1:30-2:00", "RPE": "7-9", "RM": "65-80%"},
    "Fuerza Máxima": {"Reps": "1-5", "Pausa": "3:00-5:00", "RPE": "8-10", "RM": "85-100%"},
    "Resistencia": {"Reps": "15-20+", "Pausa": "0:30-1:00", "RPE": "6-8", "RM": "< 60%"},
    "Potencia": {"Reps": "1-5", "Pausa": "2:00-3:00", "RPE": "Explosivo", "RM": "30-70%"}
}

# =====================================================
# 3. ZONA DE FUNCIONES PRINCIPALES
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
        except:
            worksheet = sheet.add_worksheet(title=usuario, rows="100", cols="20")
            return None
        col_values = worksheet.col_values(1) 
        if col_values:
            return json.loads("".join(col_values))
    except: pass
    return None

def guardar_datos_disco():
    usuario = st.session_state.get("usuario_actual", "default")
    try:
        datos = {
            "clientes": st.session_state.db_clientes,
            "historial": st.session_state.historial_global,
            "videos": st.session_state.biblioteca_videos,
            "planes": st.session_state.planes_semanales,
            "detalles_planes": st.session_state.detalles_planes, 
            "notas": st.session_state.notas_personales
        }
        json_str = json.dumps(datos)
        client = get_gsheets_client()
        sheet = client.open_by_url(URL_SHEET)
        try: worksheet = sheet.worksheet(usuario)
        except: worksheet = sheet.add_worksheet(title=usuario, rows="100", cols="20")
        chunks = [json_str[i:i+40000] for i in range(0, len(json_str), 40000)]
        worksheet.clear()
        cell_list = worksheet.range(1, 1, len(chunks), 1)
        for i, cell in enumerate(cell_list): cell.value = chunks[i]
        worksheet.update_cells(cell_list)
    except Exception as e:
        st.sidebar.error(f"⚠️ Error guardando: {e}")

def registrar_auditoria_cobro(nombre_alumno):
    usuario = st.session_state.get("usuario_actual", "desconocido")
    if usuario == "visho": return
    try:
        client = get_gsheets_client()
        sheet = client.open_by_url(URL_SHEET)
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_actual = meses[datetime.now().month - 1]
        ano_actual = datetime.now().year
        nombre_hoja = f"Auditoria_{mes_actual}_{ano_actual}"
        try: worksheet = sheet.worksheet(nombre_hoja)
        except:
            worksheet = sheet.add_worksheet(title=nombre_hoja, rows="1000", cols="4")
            worksheet.append_row(["Fecha Registro", "Preparador", "Nombre Alumno", "Estado Pago"])
        registros = worksheet.get_all_values()
        for fila in registros:
            if len(fila) >= 3 and fila[1].lower() == usuario.lower() and fila[2].lower() == nombre_alumno.lower(): return
        worksheet.append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), usuario.capitalize(), nombre_alumno, "Pendiente"])
    except: pass

def mostrar_panel_admin():
    st.title("👑 Panel de Control Bio Sport")
    st.write("Resumen de alumnos activos y cálculo automático de mensualidades.")
    with st.spinner("Calculando cobros en tiempo real..."):
        try:
            client = get_gsheets_client()
            sheet = client.open_by_url(URL_SHEET)
            reglas_cobro = {
                "eduardo": {"tipo": "por_alumno", "valor": 2500},
                "davidp":  {"tipo": "fijo",       "valor": 10000},
                "clemente":{"tipo": "por_alumno", "valor": 2500}
            }
            datos_cobro, total_global = [], 0
            for preparador, regla in reglas_cobro.items():
                try:
                    ws = sheet.worksheet(preparador)
                    col_values = ws.col_values(1)
                    if col_values:
                        json_data = json.loads("".join(col_values))
                        num_alumnos = len(json_data.get("clientes", {}))
                        if regla["tipo"] == "por_alumno":
                            monto = num_alumnos * regla["valor"]
                            tipo_trato = f"${regla['valor']:,} x alumno".replace(",", ".")
                        elif regla["tipo"] == "fijo":
                            monto = regla["valor"]
                            tipo_trato = "Cuota Fija Mensual"
                        datos_cobro.append({"Preparador": preparador.capitalize(), "Alumnos Activos": num_alumnos, "Tipo de Trato": tipo_trato, "Monto a Cobrar ($)": f"${monto:,}".replace(",", ".")})
                        total_global += monto
                except: continue
            if datos_cobro:
                c1, c2 = st.columns(2)
                c1.metric("Alumnos Totales en App", sum(d['Alumnos Activos'] for d in datos_cobro))
                c2.metric("Total a Recaudar", f"${total_global:,}".replace(",", "."))
                st.table(pd.DataFrame(datos_cobro))
            else: st.warning("No hay datos registrados aún.")
        except Exception as e: st.error(f"Error cargando el panel: {e}")

def obtener_ultimo_registro(cliente, ejercicio):
    for registro in reversed(st.session_state.historial_global):
        if registro['Cliente'] == cliente and registro['Ejercicio'] == ejercicio and registro.get('Tipo') == 'Fuerza': return registro
    return None

def importar_historial_al_plan(cliente):
    dias_semana = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
    nuevo_detalles = st.session_state.detalles_planes.get(cliente, {}).copy()
    nuevo_focos = st.session_state.planes_semanales.get(cliente, {}).copy()
    rutinas_temp = {dia: [] for dia in dias_semana.values()}
    focos_temp = {dia: "Descanso" for dia in dias_semana.values()}
    hoy = date.today()
    for reg in reversed(st.session_state.historial_global):
        if reg['Cliente'] == cliente:
            try:
                fecha_reg = datetime.strptime(reg['Fecha'], "%d/%m/%Y").date()
                if (hoy - fecha_reg).days < 14:
                    dia_nombre = dias_semana[fecha_reg.weekday()]
                    txt = f"{reg['Ejercicio']}: {reg['Series']}x{reg['Reps']} ({reg['Carga']}kg)" if reg.get('Tipo') == 'Fuerza' else f"Cardio: {reg['Ejercicio']} ({reg['Carga']}min)"
                    if txt not in rutinas_temp[dia_nombre]: rutinas_temp[dia_nombre].insert(0, txt)
                    if 'Objetivo' in reg and focos_temp[dia_nombre] == "Descanso": focos_temp[dia_nombre] = reg['Objetivo']
            except: pass
    for dia, lista in rutinas_temp.items():
        if lista:
            nuevo_detalles[dia] = f"||{chr(10).join(lista)}||" 
            if focos_temp[dia] != "Descanso": nuevo_focos[dia] = focos_temp[dia]
            elif nuevo_focos.get(dia) == "Descanso": nuevo_focos[dia] = "Entrenamiento Realizado"
    st.session_state.planes_semanales[cliente], st.session_state.detalles_planes[cliente] = nuevo_focos, nuevo_detalles
    guardar_datos_disco()
    return True

def calcular_1rm(p, r): return p * (1 + (r / 30))
def calcular_jackson_3(edad, sexo, s3): return (495 / (1.10938 - (0.0008267 * s3) + (0.0000016 * (s3**2)) - (0.0002574 * edad)) - 450) if sexo == "Masculino" else (495 / (1.0994921 - (0.0009929 * s3) + (0.0000023 * (s3**2)) - (0.0001392 * edad)) - 450)
def calcular_durnin(edad, sexo, s4): c, m = (1.1631, 0.0632) if sexo == "Masculino" else (1.1599, 0.0717); return (495 / (c - (m * math.log10(s4)))) - 450
def interpretar_tiempo(t):
    try:
        t = str(t).strip()
        if ":" in t: return int(t.split(":")[0]) * 60 + int(t.split(":")[1])
        return int(float(t) * 60) if float(t) < 10 else int(float(t))
    except: return 90
def fecha_es(f): return f.strftime("%d/%m/%Y")

# =====================================================
# 4. INICIALIZACIÓN
# =====================================================
datos = cargar_datos_disco()
if 'db_clientes' not in st.session_state: st.session_state.db_clientes = datos["clientes"] if datos else {}
if 'historial_global' not in st.session_state: st.session_state.historial_global = datos["historial"] if datos else []
if 'biblioteca_videos' not in st.session_state: st.session_state.biblioteca_videos = datos["videos"] if (datos and "videos" in datos) else VIDEOS_BASE
if 'planes_semanales' not in st.session_state: st.session_state.planes_semanales = datos["planes"] if (datos and "planes" in datos) else {}
if 'detalles_planes' not in st.session_state: st.session_state.detalles_planes = datos["detalles_planes"] if (datos and "detalles_planes" in datos) else {}
if 'notas_personales' not in st.session_state: st.session_state.notas_personales = datos["notas"] if (datos and "notas" in datos) else ""
if 'cliente_activo' not in st.session_state: st.session_state.cliente_activo = None

# =====================================================
# 5. SIDEBAR Y MENÚ DINÁMICO
# =====================================================
st.sidebar.header("⚡ Bio Sport Pro")
lista = ["Crear Nuevo..."] + list(st.session_state.db_clientes.keys())
sel = st.sidebar.selectbox("Atleta:", lista)

if sel == "Crear Nuevo...":
    nom = st.sidebar.text_input("Nombre del nuevo atleta:")
    if st.sidebar.button("Guardar Atleta", type="primary"):
        if nom:
            nom_limpio = nom.strip()
            if nom_limpio not in st.session_state.db_clientes:
                st.session_state.db_clientes[nom_limpio] = {"Peso":70, "Talla":170, "Edad":25, "Sexo":"Masculino"}
                guardar_datos_disco()
                registrar_auditoria_cobro(nom_limpio)
                st.toast("Atleta registrado correctamente", icon="🔥")
                time.sleep(1)
                st.rerun()
            else:
                st.sidebar.warning("Ese atleta ya existe.")
else:
    st.session_state.cliente_activo = sel
    
    with st.sidebar.expander("⚙️ Gestión y Seguridad", expanded=False):
        if st.button("🗑️ Eliminar Atleta"):
            del st.session_state.db_clientes[sel]
            st.session_state.historial_global = [h for h in st.session_state.historial_global if h['Cliente'] != sel]
            if sel in st.session_state.planes_semanales: del st.session_state.planes_semanales[sel]
            if sel in st.session_state.detalles_planes: del st.session_state.detalles_planes[sel]
            guardar_datos_disco()
            st.session_state.cliente_activo = None
            st.rerun()
        
        json_str = json.dumps({"clientes": st.session_state.db_clientes, "historial": st.session_state.historial_global, "planes": st.session_state.planes_semanales, "detalles": st.session_state.detalles_planes}, indent=4)
        st.download_button(label="💾 Backup Data", data=json_str, file_name=f"backup_biosport.json", mime="application/json")

with st.sidebar.expander("🧮 Calculadora RM Rápida", expanded=False):
    p_rm = st.number_input("Peso (kg)", 0.0, step=0.5); r_rm = st.number_input("Reps", 1, 20, 8)
    if p_rm > 0:
        rm = calcular_1rm(p_rm, r_rm)
        st.write(f"1RM: **{rm:.1f} kg**")
        c1, c2 = st.columns(2)
        with c1: st.caption(f"90%: {rm*0.9:.1f}"); st.caption(f"80%: {rm*0.8:.1f}")
        with c2: st.caption(f"70%: {rm*0.7:.1f}"); st.caption(f"60%: {rm*0.6:.1f}")

opciones_menu = ["0. 🏠 Inicio", "1. 📋 Ficha & Antropo", "2. 💪 Entrenamiento", "3. 🧠 Plan Semanal", "4. 🏃‍♂️ Cardio", "5. 📈 Progreso", "6. 📚 Guías Completas", "7. 📝 Notas"]
if st.session_state.get('usuario_actual') == "visho": opciones_menu.append("👑 Panel Admin")
menu = st.sidebar.radio("Menú Principal:", opciones_menu)

st.sidebar.divider()
if st.session_state.cliente_activo:
    st.sidebar.success(f"Atleta Activo: {st.session_state.cliente_activo}")

# =====================================================
# PESTAÑA 0: INICIO (NUEVO DASHBOARD)
# =====================================================
if menu == "0. 🏠 Inicio":
    st.title("⚡ Dashboard Bio Sport")
    st.markdown("Visión general de tus atletas y rendimiento diario.")
    
    # Cálculo de métricas
    total_atletas = len(st.session_state.db_clientes)
    hoy_str = date.today().strftime("%d/%m/%Y")
    entrenos_hoy = len([h for h in st.session_state.historial_global if h['Fecha'] == hoy_str])
    
    col1, col2, col3 = st.columns(3)
    col1.metric("👥 Mis Atletas Activos", total_atletas)
    col2.metric("🔥 Entrenamientos Hoy (Global)", entrenos_hoy)
    col3.metric("📅 Fecha Actual", hoy_str)
    
    st.divider()
    st.subheader("💡 Tips del Sistema")
    st.info("- Usa la nueva pestaña **Progreso** para que la IA detecte si tu atleta está estancado.\n- El **Panel Admin** registra a los atletas nuevos automáticamente.\n- Al calcular el cardio, usa la nueva fórmula de Tanaka en **Ficha & Antropo**.")

# =====================================================
# PESTAÑA 1: FICHA Y ANTROPOMETRÍA
# =====================================================
elif menu == "1. 📋 Ficha & Antropo":
    if not st.session_state.cliente_activo: st.warning("Selecciona un atleta en el menú lateral."); st.stop()
    c = st.session_state.cliente_activo
    d = st.session_state.db_clientes[c]
    
    t1, t2, t3 = st.tabs(["📝 Datos Básicos", "📏 Antropometría", "🏥 Anamnesis"])
    with t1:
        c1, c2, c3, c4 = st.columns(4)
        np = c1.number_input("Peso (kg)", value=float(d.get('Peso', 70)))
        nt = c2.number_input("Talla (cm)", value=float(d.get('Talla', 170)))
        ne = c3.number_input("Edad", value=int(d.get('Edad', 25)))
        ns = c4.selectbox("Sexo", ["Masculino", "Femenino"], index=0 if d.get('Sexo', 'Masculino')=="Masculino" else 1)
        
        if st.button("Actualizar Datos Básicos", type="primary"):
            st.session_state.db_clientes[c].update({"Peso":np,"Talla":nt,"Edad":ne,"Sexo":ns})
            guardar_datos_disco(); st.toast("Datos básicos actualizados", icon="💾")

        st.divider()
        if st.checkbox("❤️ Calcular Frecuencia Cardíaca Máxima (Fórmula Tanaka)"):
            fcm = 208 - (0.7 * ne)
            st.info(f"Frecuencia Cardíaca Máxima sugerida: **{fcm:.0f} lpm** (Latidos por minuto)")
            st.caption("Basado en la fórmula de Tanaka: 208 - (0.7 × Edad). Ideal para programar zonas de cardio de manera segura.")

    with t2:
        st.subheader("Cálculo de Grasa (Siri)")
        metodo = st.radio("Protocolo:", ["Jackson (3 Pliegues)", "Durnin (4 Pliegues)"], horizontal=True)
        col_in, col_out = st.columns(2)
        suma = 0
        with col_in:
            if metodo == "Jackson (3 Pliegues)":
                if d.get('Sexo', 'Masculino') == "Masculino":
                    p1 = st.number_input("Pectoral (mm)", 0.0); p2 = st.number_input("Abdominal (mm)", 0.0); p3 = st.number_input("Muslo (mm)", 0.0)
                else:
                    p1 = st.number_input("Tríceps (mm)", 0.0); p2 = st.number_input("Suprailiaco (mm)", 0.0); p3 = st.number_input("Muslo (mm)", 0.0)
                suma = p1+p2+p3
                if suma > 0: grasa = calcular_jackson_3(d.get('Edad', 25), d.get('Sexo', 'Masculino'), suma)
            else:
                p1 = st.number_input("Bíceps (mm)", 0.0); p2 = st.number_input("Tríceps (mm)", 0.0); p3 = st.number_input("Subescapular (mm)", 0.0); p4 = st.number_input("Suprailiaco (mm)", 0.0)
                suma = p1+p2+p3+p4
                if suma > 0: grasa = calcular_durnin(d.get('Edad', 25), d.get('Sexo', 'Masculino'), suma)
        with col_out:
            if suma > 0:
                st.metric("% Grasa", f"{grasa:.1f}%")
                st.metric("Masa Magra", f"{(d.get('Peso', 70)*(1-grasa/100)):.1f} kg")

    with t3:
        col1, col2 = st.columns(2)
        fono = col1.text_input("📱 Teléfono", value=d.get("Telefono", ""))
        emergencia = col2.text_input("🚨 Contacto Emergencia", value=d.get("Emergencia", ""))
        lesiones = st.text_area("🩹 Lesiones o Molestias Físicas", value=d.get("Lesiones", ""), height=80)
        enfermedades = st.text_area("💊 Patologías o Medicamentos", value=d.get("Enfermedades", ""), height=80)
        col3, col4 = st.columns(2)
        opciones_exp = ["Principiante", "Intermedio", "Avanzado"]
        exp_actual = d.get("Experiencia", "Principiante")
        experiencia = col3.selectbox("🏋️ Experiencia", opciones_exp, index=opciones_exp.index(exp_actual) if exp_actual in opciones_exp else 0)
        objetivo_prin = col4.text_input("🎯 Objetivo Principal", value=d.get("Objetivo_Prin", ""))
        if st.button("Guardar Anamnesis"):
            st.session_state.db_clientes[c].update({"Telefono": fono, "Emergencia": emergencia, "Lesiones": lesiones, "Enfermedades": enfermedades, "Experiencia": experiencia, "Objetivo_Prin": objetivo_prin})
            guardar_datos_disco(); st.toast("Anamnesis guardada correctamente", icon="🏥")

# =====================================================
# PESTAÑA 2: ENTRENAMIENTO
# =====================================================
elif menu == "2. 💪 Entrenamiento":
    if not st.session_state.cliente_activo: st.stop()
    c = st.session_state.cliente_activo
    
    fecha_sel = st.date_input("📅 Fecha de la Sesión:", date.today())
    dia_nombre = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"][fecha_sel.weekday()]
    
    plan_foco = st.session_state.planes_semanales.get(c, {}).get(dia_nombre, "Sin planificar")
    plan_det = st.session_state.detalles_planes.get(c, {}).get(dia_nombre, "")
    
    if plan_foco == "Descanso": st.success(f"🛌 **{dia_nombre}:** Descanso.")
    else:
        st.info(f"🔥 **{dia_nombre}:** {plan_foco}")
        if plan_det:
            with st.expander("👀 Ver Detalles Planificados", expanded=True):
                partes = plan_det.split("||")
                if len(partes) == 3:
                    if partes[0].strip(): st.markdown("**1️⃣ Calentamiento:**\n" + partes[0])
                    if partes[1].strip(): st.markdown("**2️⃣ Desarrollo:**\n" + partes[1])
                    if partes[2].strip(): st.markdown("**3️⃣ Vuelta a la Calma:**\n" + partes[2])
                else: st.text(plan_det)
    st.divider()
    
    col_ent, col_timer = st.columns([3, 1])
    with col_ent:
        obj_sel = st.selectbox("🎯 Objetivo Sesión:", list(SUGERENCIAS_OBJETIVO.keys()))
        sug = SUGERENCIAS_OBJETIVO[obj_sel]
        st.caption(f"Guía: {sug['Reps']} reps | RM: {sug['RM']} | Pausa: {sug['Pausa']} | RPE: {sug['RPE']}")

        ej_sel = st.selectbox("Ejercicio:", list(st.session_state.biblioteca_videos.keys()) + ["✍️ Otro..."])
        if ej_sel != "✍️ Otro...":
            ultimo = obtener_ultimo_registro(c, ej_sel)
            if ultimo: st.info(f"💡 Última vez: {ultimo['Series']}x{ultimo['Reps']} ({ultimo['Carga']}kg)")
        
        nom = st.text_input("Nombre:", value=ej_sel if ej_sel != "✍️ Otro..." else "")
        c1, c2, c3 = st.columns(3)
        se = c1.number_input("Series", 1, 10, 4)
        re = c2.number_input("Reps", 1, 50, 10)
        kg = c3.number_input("Carga (kg)", 0.0)
        pt = st.text_input("Pausa", value=sug["Pausa"].split("-")[0])
        
        if st.button("➕ Guardar Serie", type="primary"):
            st.session_state.historial_global.append({"Cliente":c, "Fecha":fecha_es(fecha_sel), "Ejercicio":nom, "Series":se, "Reps":re, "Carga":kg, "Link":"", "Tipo":"Fuerza", "Objetivo": obj_sel})
            guardar_datos_disco(); st.toast("Serie agregada con éxito", icon="💪")
            st.rerun()
            
        hist = [h for h in st.session_state.historial_global if h['Cliente']==c and h['Fecha']==fecha_es(fecha_sel)]
        if hist:
            st.markdown("---")
            st.subheader(f"📝 Registros del {fecha_es(fecha_sel)}")
            for i, h in enumerate(st.session_state.historial_global):
                if h['Cliente'] == c and h['Fecha'] == fecha_es(fecha_sel):
                    col_info, col_del = st.columns([4, 1])
                    col_info.write(f"✅ {h['Ejercicio']}: {h['Series']}x{h['Reps']} ({h['Carga']}kg)")
                    if col_del.button("🗑️", key=f"del_dia_{i}"):
                        del st.session_state.historial_global[i]; guardar_datos_disco(); st.rerun()

    with col_timer:
        st.write("⏱️ Cronómetro")
        seg = interpretar_tiempo(pt)
        if st.button(f"Iniciar {seg}s"):
            ph = st.empty(); bar = st.progress(0)
            for i in range(seg, -1, -1):
                ph.metric("Restante", f"{i}s"); bar.progress(1-(i/seg)); time.sleep(1)
            ph.success("¡Tiempo!")

# =====================================================
# PESTAÑA 3: PLAN SEMANAL
# =====================================================
elif menu == "3. 🧠 Plan Semanal":
    if not st.session_state.cliente_activo: st.stop()
    c = st.session_state.cliente_activo
    
    c_head1, c_head2 = st.columns([3, 1])
    with c_head1: st.subheader(f"Planificación - {c}")
    with c_head2:
        if st.button("🔄 Cargar de Historial"): importar_historial_al_plan(c); st.toast("Historial importado", icon="✅"); st.rerun()
            
    tipos_semana = ["Ajuste (Descarga)", "Carga (Desarrollo)", "Impacto (Choque)"]
    tipo_guardado = st.session_state.planes_semanales.get(c, {}).get("tipo_semana", "Carga (Desarrollo)")
    microciclo_sel = st.select_slider("📊 Intensidad del Microciclo:", options=tipos_semana, value=tipo_guardado if tipo_guardado in tipos_semana else "Carga (Desarrollo)")
    
    if microciclo_sel == "Ajuste (Descarga)": st.info("📉 Recuperación y técnica. RPE 5-7. Volumen bajo.")
    elif microciclo_sel == "Carga (Desarrollo)": st.success("📈 Mejorar rendimiento. RPE 7-8.5. Cargas progresivas.")
    else: st.error("🔥 Sobrecarga máxima. RPE 9-10. Series al fallo o volumen alto.")

    with st.expander("🤖 Consultar a Dante (IA)"):
        datos_ficha = st.session_state.db_clientes.get(c, {})
        perfil = f"Edad: {datos_ficha.get('Edad', 'N/A')}, Experiencia: {datos_ficha.get('Experiencia', 'N/A')}, Lesiones: {datos_ficha.get('Lesiones', 'Ninguna')}."
        c_dia, c_btn = st.columns([2, 1])
        dia_dante = c_dia.selectbox("Enfoque:", ["Pierna", "Torso", "Full Body", "Cardio"])
        if c_btn.button("✨ Preguntar a Dante") and modelo_dante:
            with st.spinner("Dante está pensando..."):
                prompt = f"Eres Dante, entrenador. Perfil atleta: {perfil}. Sugiere rutina breve para: {dia_dante}. Estructura: 1. Calentamiento 2. Desarrollo 3. Vuelta a la calma. Evita agravar lesiones."
                try:
                    respuesta = modelo_dante.generate_content(prompt)
                    st.markdown(respuesta.text)
                except Exception as e: st.error(f"Error: {e}")

    opciones = ["Descanso", "Pierna", "Pecho/Hombro", "Espalda", "Glúteo", "Full Body", "Torso", "Brazo", "Cardio"]
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    nuevo_focos, nuevo_detalles = {"tipo_semana": microciclo_sel}, {}
    
    for dia in dias:
        with st.expander(f"📅 {dia}", expanded=False):
            val_def = st.session_state.planes_semanales.get(c, {}).get(dia, "Descanso")
            if val_def not in opciones: opciones.append(val_def)
            nuevo_focos[dia] = st.selectbox(f"Enfoque {dia}", opciones, index=opciones.index(val_def), key=f"foco_{dia}")
            
            if nuevo_focos[dia] != "Descanso":
                partes = st.session_state.detalles_planes.get(c, {}).get(dia, "||").split("||")
                calentamiento_def = partes[0] if len(partes) > 0 else ""
                desarrollo_def = partes[1] if len(partes) > 1 else ""
                vuelta_def = partes[2] if len(partes) > 2 else ""

                col1, col2, col3 = st.columns(3)
                calentamiento = col1.text_area("1️⃣ Calentamiento", value=calentamiento_def, key=f"cal_{dia}", height=150)
                desarrollo = col2.text_area("2️⃣ Desarrollo (Bloque Principal)", value=desarrollo_def, key=f"des_{dia}", height=150)
                vuelta = col3.text_area("3️⃣ Vuelta a la Calma", value=vuelta_def, key=f"vue_{dia}", height=150)
                nuevo_detalles[dia] = f"{calentamiento}||{desarrollo}||{vuelta}"
            else: nuevo_detalles[dia] = ""

    if st.button("💾 Guardar Plan", type="primary"):
        st.session_state.planes_semanales[c], st.session_state.detalles_planes[c] = nuevo_focos, nuevo_detalles
        guardar_datos_disco(); st.toast("Plan semanal guardado", icon="📅")

# =====================================================
# PESTAÑA 4: CARDIO Y 5: PROGRESO (INTELIGENTE)
# =====================================================
elif menu == "4. 🏃‍♂️ Cardio":
    st.title("Cardio y VAM")
    c = st.session_state.cliente_activo
    if not c: st.stop()
    v = st.session_state.db_clientes[c].get("VAM", 0.0)
    st.info(f"VAM Actual: {v} m/s")
    dist = st.number_input("Distancia (m)", 100)
    pct = st.slider("% Intensidad", 50, 120, 90)
    if v > 0: st.metric("Tiempo Objetivo", f"{int(dist / (v * (pct/100)))} seg")
    
elif menu == "5. 📈 Progreso":
    if not st.session_state.cliente_activo: st.stop()
    c = st.session_state.cliente_activo
    df = pd.DataFrame([r for r in st.session_state.historial_global if r['Cliente']==c])
    
    if not df.empty:
        st.subheader("Evolución de Cargas")
        df['Tipo'] = 'Fuerza'
        ej_sel = st.selectbox("Selecciona Ejercicio para Gráfico:", df['Ejercicio'].unique())
        datos_graf = df[df['Ejercicio'] == ej_sel].copy()
        
        if not datos_graf.empty: 
            st.line_chart(datos_graf, x="Fecha", y="Carga")
            
            # INTELIGENCIA DE ESTANCAMIENTO
            if len(datos_graf) >= 3:
                st.subheader("🧠 Análisis Automático de Progreso")
                ult = datos_graf['Carga'].tail(3).tolist()
                c1, c2, c3_carga = ult[-3], ult[-2], ult[-1]
                
                if c1 == c2 == c3_carga: st.warning(f"⚠️ **Estancamiento:** El atleta ha mantenido {c3_carga}kg en las últimas 3 sesiones. Considera dar una semana de Descarga.")
                elif c3_carga < c1: st.error(f"📉 **Baja de Rendimiento:** La carga actual ({c3_carga}kg) bajó respecto a antes. Revisa fatiga.")
                elif c3_carga > c2: st.success(f"🔥 **¡Excelente Progreso!** La carga sigue subiendo.")
                else: st.info("📊 Tendencia de carga estable.")
    else: st.info("Sin datos para analizar")

# =====================================================
# PESTAÑA 6 Y 7: GUÍAS Y NOTAS
# =====================================================
elif menu == "6. 📚 Guías Completas":
    t1, t2 = st.tabs(["Fuerza (Badillo)", "Zonas Cardio"])
    with t1: st.table(TABLA_BADILLO)
    with t2: st.table(GUIA_ZONAS_CARDIO)

elif menu == "7. 📝 Notas":
    st.title("Notas Personales")
    notas = st.text_area("Escribe tus apuntes (Privado):", value=st.session_state.notas_personales, height=300)
    if st.button("Guardar Notas"):
        st.session_state.notas_personales = notas
        guardar_datos_disco(); st.toast("Notas guardadas en la nube", icon="☁️")

elif menu == "👑 Panel Admin":
    mostrar_panel_admin()
