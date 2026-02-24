import streamlit as st
import pandas as pd
import math
import time
import json
import os
import io
from datetime import date, datetime, timedelta

# Intentamos importar reportlab.
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.colors import HexColor
except ImportError:
    st.error("⚠️ Falta la librería 'reportlab'. Instálala escribiendo: pip install reportlab")

# =====================================================
# 1. CONFIGURACIÓN E INICIO
# =====================================================
st.set_page_config(page_title="Pro Trainer Bio Sport", layout="wide", page_icon="💪")
ARCHIVO_DB = "basedatos_entrenador.json"

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
    "Press Banca": "https://www.youtube.com/watch?v=VmB1G1K7v94",
    "Zancadas": "https://www.youtube.com/watch?v=0_ZmM-J7y_M",
    "Remo Mancuerna": "https://www.youtube.com/watch?v=D7KaRcCIQms",
    "Press Militar": "https://www.youtube.com/watch?v=M2rwvNhTOu0"
}

SUGERENCIAS_OBJETIVO = {
    "Hipertrofia": {"Reps": "6-12", "Pausa": "1:30-2:00", "RPE": "7-9"},
    "Fuerza Máxima": {"Reps": "1-5", "Pausa": "3:00-5:00", "RPE": "8-10"},
    "Resistencia": {"Reps": "15-20+", "Pausa": "0:30-1:00", "RPE": "6-8"},
    "Potencia": {"Reps": "1-5", "Pausa": "2:00-3:00", "RPE": "Explosivo"}
}

TABLA_BADILLO = pd.DataFrame({
    "Zona": ["Fuerza Máx", "Fuerza-Hipertrofia", "Hipertrofia Alta", "Hipertrofia Media", "Resistencia"],
    "% 1RM": ["85-100%", "80-85%", "70-80%", "60-75%", "<60%"],
    "Reps": ["1-5", "5-7", "6-12", "12-20", "20+"],
    "Descanso": ["3-5 min", "3 min", "2 min", "1-2 min", "<1 min"]
})

GUIAS_BOMPA = pd.DataFrame({
    "Fase": ["Adaptación", "Hipertrofia", "Fuerza Máx", "Potencia", "Transición"],
    "Intensidad": ["30-60%", "60-80%", "85-100%", "30-80%", "Baja"],
    "Reps": ["12-20", "6-12", "1-5", "1-10", "Libre"],
    "Descanso": ["1-2 min", "1-3 min", "3-5+ min", "3-5+ min", "Libre"]
})

GUIA_TEMPO = pd.DataFrame({
    "Objetivo": ["Hipertrofia", "Fuerza Máx", "Potencia", "Resistencia"],
    "Tempo": ["3-0-1-0", "X-0-X-0", "X-X-X", "2-0-2-0"],
    "Explicación": ["Bajada lenta", "Máxima velocidad", "Explosivo", "Continuo"]
})

GUIA_DESCANSOS = pd.DataFrame({
    "Objetivo": ["Fuerza/Potencia", "Hipertrofia", "Resistencia"],
    "Tiempo": ["3 a 5+ min", "60 a 90 seg", "30 a 60 seg"],
    "¿Por qué?": ["Recuperar ATP", "Estrés Metabólico", "Limpiar lactato"]
})

ESCALA_RPE = pd.DataFrame({
    "RPE": [10, 9, 8, 7, 6],
    "RIR": ["0 (Fallo)", "1", "2", "3", "4"],
    "Sensación": ["Imposible más", "Podría 1 más", "Podría 2 más", "Podría 3 más", "Calentamiento"]
})

ESCALA_BORG = pd.DataFrame({
    "Nivel": ["Muy Suave", "Suave", "Moderado", "Duro", "Máximo"],
    "Escala 6-20": ["6-9", "10-11", "12-13", "14-16", "17-20"],
    "Test Habla": ["Cantar", "Hablar", "Frases cortas", "Palabras", "Agonía"]
})

GUIA_ZONAS_CARDIO = pd.DataFrame({
    "Zona": ["Z1 (Regenerativo)", "Z2 (Aeróbico)", "Z3 (Umbral)", "Z4 (VO2Max)", "Z5 (Anaeróbico)"],
    "% VAM": ["< 60%", "60-75%", "75-90%", "95-105%", "> 110%"],
    "Sensación": ["Muy fácil", "Fácil", "Duro", "Muy duro", "Agonía"]
})

# =====================================================
# 3. MOTORES, PDF Y PERSISTENCIA
# =====================================================
def cargar_datos_disco():
    if os.path.exists(ARCHIVO_DB):
        try:
            with open(ARCHIVO_DB, "r", encoding="utf-8") as f: return json.load(f)
        except: return None
    return None

def guardar_datos_disco():
    datos = {
        "clientes": st.session_state.db_clientes,
        "historial": st.session_state.historial_global,
        "videos": st.session_state.biblioteca_videos,
        "planes": st.session_state.planes_semanales,
        "detalles_planes": st.session_state.detalles_planes, 
        "notas": st.session_state.notas_personales
    }
    with open(ARCHIVO_DB, "w", encoding="utf-8") as f: json.dump(datos, f, indent=4)

# --- GENERADOR DE PDF PREMIUM ---
def generar_pdf_plan(cliente, plan_focos, plan_detalles):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Colores corporativos
    COLOR_PRIMARIO = HexColor("#1E3A8A") # Azul Oscuro
    COLOR_SECUNDARIO = HexColor("#F3F4F6") # Gris muy claro
    COLOR_TEXTO = HexColor("#111827") # Casi negro
    
    # --- ENCABEZADO ---
    c.setFillColor(COLOR_PRIMARIO)
    c.rect(0, height - 100, width, 100, fill=1, stroke=0) # Barra azul superior
    
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, height - 50, "PLAN DE ENTRENAMIENTO")
    
    c.setFont("Helvetica", 14)
    c.drawString(50, height - 80, f"Atleta: {cliente}")
    c.drawRightString(width - 50, height - 50, "PRO TRAINER BIO SPORT")
    c.setFont("Helvetica", 10)
    c.drawRightString(width - 50, height - 70, f"Fecha: {date.today().strftime('%d/%m/%Y')}")
    
    # --- CUERPO ---
    y = height - 130
    dias_orden = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    
    c.setFillColor(COLOR_TEXTO)
    
    for dia in dias_orden:
        foco = plan_focos.get(dia, "Descanso")
        detalle = plan_detalles.get(dia, "")
        
        # Calcular espacio necesario (aprox)
        lineas = len(detalle.split('\n')) if detalle else 0
        altura_necesaria = 40 + (lineas * 14) 
        
        # Salto de página si no cabe
        if y - altura_necesaria < 50:
            c.showPage()
            y = height - 50
        
        # Dibujar Tarjeta del Día
        if foco != "Descanso":
            # Fondo del encabezado del día
            c.setFillColor(COLOR_SECUNDARIO)
            c.roundRect(50, y - 20, width - 100, 20, 4, fill=1, stroke=0)
            
            # Texto del día (Título)
            c.setFillColor(COLOR_PRIMARIO)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(60, y - 15, f"{dia.upper()}  |  {foco}")
            
            # Línea separadora
            c.setStrokeColor(COLOR_PRIMARIO)
            c.setLineWidth(1)
            c.line(50, y - 20, width - 50, y - 20)
            
            # Detalles (Lista de ejercicios)
            y -= 35
            c.setFillColor(COLOR_TEXTO)
            c.setFont("Helvetica", 11)
            
            if detalle:
                for linea in detalle.split('\n'):
                    if linea.strip():
                        c.drawString(70, y, f"• {linea.strip()}")
                        y -= 14
            else:
                c.setFont("Helvetica-Oblique", 10)
                c.setFillColor(colors.gray)
                c.drawString(70, y, "(Sin detalles registrados)")
                y -= 14
            
            y -= 15 # Espacio extra entre días
            
        else:
            # Diseño minimalista para descanso
            c.setFillColor(colors.lightgrey)
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(60, y - 10, f"{dia}: Descanso / Recuperación Activa")
            y -= 30

    # --- PIE DE PÁGINA ---
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.grey)
    c.drawCentredString(width / 2, 30, "La constancia es la clave del éxito. ¡Vamos por más!")
    c.drawString(width - 50, 30, str(c.getPageNumber()))
    
    c.save()
    buffer.seek(0)
    return buffer

# --------------------------------------

def obtener_ultimo_registro(cliente, ejercicio):
    historial = st.session_state.historial_global
    for registro in reversed(historial):
        if registro['Cliente'] == cliente and registro['Ejercicio'] == ejercicio and registro.get('Tipo') == 'Fuerza':
            return registro
    return None

def importar_historial_al_plan(cliente):
    dias_semana = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
    nuevo_detalles = st.session_state.detalles_planes.get(cliente, {}).copy()
    nuevo_focos = st.session_state.planes_semanales.get(cliente, {}).copy()
    historial = st.session_state.historial_global
    rutinas_temp = {dia: [] for dia in dias_semana.values()}
    focos_temp = {dia: "Descanso" for dia in dias_semana.values()}
    hoy = date.today()
    
    for reg in reversed(historial):
        if reg['Cliente'] == cliente:
            try:
                fecha_reg = datetime.strptime(reg['Fecha'], "%d/%m/%Y").date()
                if (hoy - fecha_reg).days < 14:
                    dia_nombre = dias_semana[fecha_reg.weekday()]
                    if reg.get('Tipo') == 'Fuerza':
                        txt = f"{reg['Ejercicio']}: {reg['Series']}x{reg['Reps']} ({reg['Carga']}kg)"
                    else:
                        txt = f"Cardio: {reg['Ejercicio']} ({reg['Carga']}min)"
                    
                    if txt not in rutinas_temp[dia_nombre]:
                        rutinas_temp[dia_nombre].insert(0, txt)
                    
                    if 'Objetivo' in reg and focos_temp[dia_nombre] == "Descanso":
                        focos_temp[dia_nombre] = reg['Objetivo']
            except: pass
    
    for dia, lista in rutinas_temp.items():
        if lista:
            nuevo_detalles[dia] = "\n".join(lista)
            if focos_temp[dia] != "Descanso":
                nuevo_focos[dia] = focos_temp[dia]
            elif nuevo_focos.get(dia) == "Descanso":
                nuevo_focos[dia] = "Entrenamiento Realizado"

    st.session_state.planes_semanales[cliente] = nuevo_focos
    st.session_state.detalles_planes[cliente] = nuevo_detalles
    guardar_datos_disco()
    return True

def calcular_1rm(p, r): return p * (1 + (r / 30))

def calcular_jackson_3(edad, sexo, s3):
    if sexo == "Masculino": d = 1.10938 - (0.0008267 * s3) + (0.0000016 * (s3**2)) - (0.0002574 * edad)
    else: d = 1.0994921 - (0.0009929 * s3) + (0.0000023 * (s3**2)) - (0.0001392 * edad)
    return (495 / d) - 450

def calcular_durnin(edad, sexo, s4):
    c, m = (1.1631, 0.0632) if sexo == "Masculino" else (1.1599, 0.0717)
    d = c - (m * math.log10(s4))
    return (495 / d) - 450

def interpretar_tiempo(t):
    try:
        t = str(t).strip()
        if ":" in t: p = t.split(":"); return int(p[0]) * 60 + int(p[1])
        v = float(t); return int(v * 60) if v < 10 else int(v)
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
# 5. SIDEBAR
# =====================================================
st.sidebar.header("📇 Pro Trainer Bio Sport")
lista = ["Crear Nuevo..."] + list(st.session_state.db_clientes.keys())
sel = st.sidebar.selectbox("Atleta:", lista)

if sel == "Crear Nuevo...":
    nom = st.sidebar.text_input("Nombre:")
    if st.sidebar.button("Guardar Atleta"):
        if nom:
            st.session_state.db_clientes[nom] = {"Peso":70, "Talla":170, "Edad":25, "Sexo":"Masculino"}
            guardar_datos_disco(); st.rerun()
else:
    st.session_state.cliente_activo = sel
    st.sidebar.info(f"👤 **{sel}**")
    
    with st.sidebar.expander("⚙️ Gestión y Seguridad", expanded=False):
        if st.button("🗑️ Eliminar Atleta", type="primary"):
            del st.session_state.db_clientes[sel]
            st.session_state.historial_global = [h for h in st.session_state.historial_global if h['Cliente'] != sel]
            if sel in st.session_state.planes_semanales: del st.session_state.planes_semanales[sel]
            if sel in st.session_state.detalles_planes: del st.session_state.detalles_planes[sel]
            guardar_datos_disco()
            st.session_state.cliente_activo = None
            st.rerun()
        
        json_str = json.dumps({
            "clientes": st.session_state.db_clientes,
            "historial": st.session_state.historial_global,
            "planes": st.session_state.planes_semanales,
            "detalles": st.session_state.detalles_planes
        }, indent=4)
        st.download_button(label="💾 Backup", data=json_str, file_name="backup.json", mime="application/json")

with st.sidebar.expander("🧮 Calculadora RM", expanded=False):
    p_rm = st.number_input("Peso", 0.0, step=0.5); r_rm = st.number_input("Reps", 1, 20, 8)
    if p_rm > 0:
        rm = calcular_1rm(p_rm, r_rm)
        st.write(f"1RM: **{rm:.1f} kg**")
        c1, c2 = st.columns(2)
        with c1: st.caption(f"90%: {rm*0.9:.1f}"); st.caption(f"80%: {rm*0.8:.1f}"); st.caption(f"70%: {rm*0.7:.1f}")
        with c2: st.caption(f"60%: {rm*0.6:.1f}"); st.caption(f"50%: {rm*0.5:.1f}"); st.caption(f"40%: {rm*0.4:.1f}")

menu = st.sidebar.radio("Menú:", ["1. 📋 Ficha & Antropo", "2. 💪 Entrenamiento", "3. 🧠 Plan Semanal", "4. 🏃‍♂️ Cardio", "5. 📈 Progreso", "6. 📚 Guías Completas", "7. 📝 Notas", "8. 🎥 Videoteca"])

# =====================================================
# PESTAÑA 1: FICHA & ANTROPO
# =====================================================
if menu == "1. 📋 Ficha & Antropo":
    if not st.session_state.cliente_activo: st.warning("Selecciona atleta"); st.stop()
    c = st.session_state.cliente_activo
    d = st.session_state.db_clientes[c]
    
    t1, t2 = st.tabs(["📝 Datos", "📏 Antropometría"])
    
    with t1:
        c1, c2, c3, c4 = st.columns(4)
        np = c1.number_input("Peso (kg)", value=float(d['Peso']))
        nt = c2.number_input("Talla (cm)", value=float(d['Talla']))
        ne = c3.number_input("Edad", value=int(d['Edad']))
        ns = c4.selectbox("Sexo", ["Masculino", "Femenino"], index=0 if d['Sexo']=="Masculino" else 1)
        if st.button("Actualizar"):
            st.session_state.db_clientes[c].update({"Peso":np,"Talla":nt,"Edad":ne,"Sexo":ns})
            guardar_datos_disco(); st.success("Ok")

    with t2:
        st.subheader("Cálculo de Grasa (Siri)")
        metodo = st.radio("Protocolo:", ["Jackson (3 Pliegues)", "Durnin (4 Pliegues)"], horizontal=True)
        col_in, col_out = st.columns(2)
        suma = 0
        with col_in:
            if metodo == "Jackson (3 Pliegues)":
                if d['Sexo'] == "Masculino":
                    st.caption("Pectoral, Abdominal, Muslo")
                    p1 = st.number_input("Pectoral (mm)", 0.0); p2 = st.number_input("Abdominal (mm)", 0.0); p3 = st.number_input("Muslo (mm)", 0.0)
                else:
                    st.caption("Tríceps, Suprailiaco, Muslo")
                    p1 = st.number_input("Tríceps (mm)", 0.0); p2 = st.number_input("Suprailiaco (mm)", 0.0); p3 = st.number_input("Muslo (mm)", 0.0)
                suma = p1+p2+p3
                if suma > 0: grasa = calcular_jackson_3(d['Edad'], d['Sexo'], suma)
            else:
                st.caption("Bíceps, Tríceps, Subescapular, Suprailiaco")
                p1 = st.number_input("Bíceps (mm)", 0.0); p2 = st.number_input("Tríceps (mm)", 0.0); p3 = st.number_input("Subescapular (mm)", 0.0); p4 = st.number_input("Suprailiaco (mm)", 0.0)
                suma = p1+p2+p3+p4
                if suma > 0: grasa = calcular_durnin(d['Edad'], d['Sexo'], suma)
        with col_out:
            if suma > 0:
                st.metric("% Grasa", f"{grasa:.1f}%")
                st.metric("Masa Magra", f"{(d['Peso']*(1-grasa/100)):.1f} kg")

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
    
    if plan_foco == "Descanso":
        st.success(f"🛌 **{dia_nombre}:** Descanso.")
    else:
        st.info(f"🔥 **{dia_nombre}:** {plan_foco}")
        if plan_det:
            with st.expander("👀 Ver Detalles Planificados para hoy", expanded=True):
                st.text(plan_det)
    st.divider()
    
    col_ent, col_timer = st.columns([3, 1])
    with col_ent:
        obj_sel = st.selectbox("🎯 Objetivo Sesión:", list(SUGERENCIAS_OBJETIVO.keys()))
        sug = SUGERENCIAS_OBJETIVO[obj_sel]
        st.caption(f"Guía: {sug['Reps']} reps | Pausa: {sug['Pausa']} | RPE: {sug['RPE']}")

        ej_sel = st.selectbox("Ejercicio:", list(st.session_state.biblioteca_videos.keys()) + ["✍️ Otro..."])
        if ej_sel != "✍️ Otro...":
            ultimo = obtener_ultimo_registro(c, ej_sel)
            if ultimo: st.info(f"💡 Última vez: {ultimo['Series']}x{ultimo['Reps']} ({ultimo['Carga']}kg)")
        
        nom = st.text_input("Nombre:", value=ej_sel if ej_sel != "✍️ Otro..." else "")
        vid = st.text_input("Link:", value=st.session_state.biblioteca_videos.get(ej_sel, ""))
        
        c1, c2, c3 = st.columns(3)
        se = c1.number_input("Series", 1, 10, 4)
        re = c2.number_input("Reps", 1, 50, 10)
        kg = c3.number_input("Carga (kg)", 0.0)
        pt = st.text_input("Pausa", value=sug["Pausa"].split("-")[0])
        
        if st.button("➕ Guardar Serie"):
            st.session_state.historial_global.append({
                "Cliente":c, "Fecha":fecha_es(fecha_sel), 
                "Ejercicio":nom, "Series":se, "Reps":re, "Carga":kg, 
                "Link":vid, "Tipo":"Fuerza", "Objetivo": obj_sel 
            })
            guardar_datos_disco(); st.rerun()
            
        hist = [h for h in st.session_state.historial_global if h['Cliente']==c and h['Fecha']==fecha_es(fecha_sel)]
        if hist:
            st.markdown("---")
            st.subheader(f"📝 Registros del {fecha_es(fecha_sel)}")
            txt_wsp = f"*ENTRENAMIENTO - {c}*\n*Fecha:* {fecha_es(fecha_sel)}\n\n"
            for h in hist:
                st.write(f"✅ {h['Ejercicio']}: {h['Series']}x{h['Reps']} ({h['Carga']}kg)")
                txt_wsp += f"🔹 {h['Ejercicio']}: {h['Series']}x{h['Reps']} ({h['Carga']}kg)\n"
            st.text_area("📱 WhatsApp:", value=txt_wsp, height=150)

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
    with c_head1: st.subheader("Planificación Semanal")
    with c_head2:
        if st.button("🔄 Importar desde lo Entrenado"):
            importar_historial_al_plan(c)
            st.success("¡Datos cargados!")
            st.rerun()
    
    opciones = ["Descanso", "Pierna", "Pecho/Hombro", "Espalda", "Glúteo", "Full Body", "Torso", "Brazo", "Cardio", "Hipertrofia", "Fuerza Máxima", "Entrenamiento Realizado"]
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    
    plan_focos = st.session_state.planes_semanales.get(c, {})
    plan_detalles = st.session_state.detalles_planes.get(c, {})
    
    nuevo_focos = {}
    nuevo_detalles = {}
    
    for dia in dias:
        with st.expander(f"📅 {dia}", expanded=True):
            col1, col2 = st.columns([1, 2])
            val_def = plan_focos.get(dia, "Descanso")
            if val_def not in opciones: opciones.append(val_def)
            
            nuevo_focos[dia] = col1.selectbox(f"Enfoque {dia}", opciones, index=opciones.index(val_def), key=f"foco_{dia}")
            
            det_def = plan_detalles.get(dia, "")
            nuevo_detalles[dia] = col2.text_area(f"Detalle {dia}", value=det_def, key=f"det_{dia}", height=100)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Guardar Cambios"):
            st.session_state.planes_semanales[c] = nuevo_focos
            st.session_state.detalles_planes[c] = nuevo_detalles
            guardar_datos_disco(); st.success("Guardado")
    with c2:
        try:
            pdf_bytes = generar_pdf_plan(c, nuevo_focos, nuevo_detalles)
            st.download_button(label="📄 Descargar PDF Diseño Premium", data=pdf_bytes, file_name=f"Rutina_{c}.pdf", mime="application/pdf")
        except:
            st.warning("Instala 'reportlab' para generar PDF.")

# =====================================================
# PESTAÑA 4: CARDIO
# =====================================================
elif menu == "4. 🏃‍♂️ Cardio":
    st.title("Cardio")
    if not st.session_state.cliente_activo: st.stop()
    c = st.session_state.cliente_activo
    v = st.session_state.db_clientes[c].get("VAM", 0.0)
    
    t1, t2 = st.tabs(["Cálculo", "Test VAM"])
    with t1:
        st.info("Calculadora de Intensidad")
        if v > 0: st.write(f"VAM Actual: {v} m/s")
        else: st.warning("Calcula la VAM primero")
        dist = st.number_input("Distancia (m)", 100)
        pct = st.slider("% Intensidad", 50, 120, 90)
        if v > 0:
            t = dist / (v * (pct/100))
            st.metric("Tiempo Objetivo", f"{int(t)} seg")
    with t2:
        m = st.number_input("Metros en 6 min:", 1000)
        if st.button("Guardar VAM"):
            vm = (m/100)/3.6
            st.session_state.db_clientes[c]["VAM"] = round(vm, 2)
            guardar_datos_disco(); st.rerun()

# =====================================================
# PESTAÑA 5: PROGRESO
# =====================================================
elif menu == "5. 📈 Progreso":
    if not st.session_state.cliente_activo: st.stop()
    c = st.session_state.cliente_activo
    df = pd.DataFrame([r for r in st.session_state.historial_global if r['Cliente']==c])
    
    if not df.empty:
        st.subheader("Evolución de Cargas")
        if 'Tipo' not in df.columns: df['Tipo'] = 'Fuerza'
        lista_ejercicios = df['Ejercicio'].unique()
        ej_sel = st.selectbox("Selecciona Ejercicio para Gráfico:", lista_ejercicios)
        datos_graf = df[df['Ejercicio'] == ej_sel]
        if not datos_graf.empty: st.line_chart(datos_graf, x="Fecha", y="Carga")
        
        st.divider()
        st.subheader("🗑️ Gestionar Registros")
        for i, r in enumerate(reversed(st.session_state.historial_global)):
            idx_real = len(st.session_state.historial_global) - 1 - i
            if r['Cliente'] == c:
                col1, col2 = st.columns([4, 1])
                col1.text(f"📅 {r['Fecha']} - {r['Ejercicio']} | {r['Series']}x{r['Reps']} ({r['Carga']}kg)")
                if col2.button("Eliminar", key=f"del_hist_{idx_real}"):
                    del st.session_state.historial_global[idx_real]
                    guardar_datos_disco(); st.rerun()
    else:
        st.info("Sin datos")

# =====================================================
# PESTAÑA 6: GUÍAS
# =====================================================
elif menu == "6. 📚 Guías Completas":
    st.title("Biblioteca Técnica")
    t1, t2, t3, t4, t5 = st.tabs(["Fuerza (Badillo)", "Planif. (Bompa)", "Tempo & Pausa", "RPE & Borg", "Zonas Cardio"])
    with t1: st.table(TABLA_BADILLO)
    with t2: st.table(GUIAS_BOMPA)
    with t3: 
        c1, c2 = st.columns(2)
        c1.table(GUIA_TEMPO); c2.table(GUIA_DESCANSOS)
    with t4: 
        c1, c2 = st.columns(2)
        c1.table(ESCALA_RPE); c2.table(ESCALA_BORG)
    with t5: st.table(GUIA_ZONAS_CARDIO)

# =====================================================
# PESTAÑA 7: NOTAS
# =====================================================
elif menu == "7. 📝 Notas":
    st.title("Notas Personales")
    notas = st.text_area("Escribe aquí tus apuntes:", value=st.session_state.notas_personales, height=300)
    if st.button("Guardar Notas"):
        st.session_state.notas_personales = notas
        guardar_datos_disco(); st.success("Notas guardadas")

# =====================================================
# PESTAÑA 8: VIDEOTECA
# =====================================================
elif menu == "8. 🎥 Videoteca":
    st.title("Videoteca")
    df_v = pd.DataFrame(list(st.session_state.biblioteca_videos.items()), columns=["Ejer","Link"])
    st.dataframe(df_v, use_container_width=True)
    c1, c2 = st.columns([1,2])
    n_ej = c1.text_input("Nuevo Ejercicio:")
    n_li = c2.text_input("Enlace YouTube:")
    if st.button("Agregar"):
        st.session_state.biblioteca_videos[n_ej] = n_li; guardar_datos_disco(); st.rerun()