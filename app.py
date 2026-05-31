# =====================================================
# BIO SPORT PRO TRAINER — VERSIÓN COMPLETA v3.0
# =====================================================
import streamlit as st
import pandas as pd
import math
import time
import json
import io
import hashlib
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, datetime, timedelta

import google.generativeai as genai

try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    modelos_validos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    modelo_dante = genai.GenerativeModel(modelos_validos[0]) if modelos_validos else None
except Exception:
    modelo_dante = None

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.colors import HexColor
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

try:
    import openpyxl
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False

# =====================================================
# CONFIGURACION DE PAGINA
# =====================================================
st.set_page_config(page_title="Bio Sport Pro", layout="wide", page_icon="⚡")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
h1, h2, h3 { font-family: 'Bebas Neue', sans-serif; letter-spacing: 2px; }
.stButton > button { border-radius: 4px; font-weight: 600; transition: all 0.2s ease; }
.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 15px rgba(57,255,20,0.3); }
.alert-box { padding: 12px 16px; border-radius: 6px; margin: 8px 0; font-size: 0.9rem; }
.alert-success { background:#0d2b0d; border-left:3px solid #39FF14; color:#39FF14; }
.alert-warning { background:#2b2200; border-left:3px solid #FFD700; color:#FFD700; }
.alert-danger  { background:#2b0000; border-left:3px solid #FF4B4B; color:#FF4B4B; }
.alert-info    { background:#001a2b; border-left:3px solid #00BFFF; color:#00BFFF; }
.live-card { background:linear-gradient(135deg,#1a1a1a,#2d2d2d); border:2px solid #39FF14; border-radius:12px; padding:24px; text-align:center; }
.live-exercise { font-family:'Bebas Neue',sans-serif; font-size:2.8rem; color:#39FF14; letter-spacing:3px; }
.live-detail { color:#aaa; font-size:1.1rem; margin-top:6px; }
.adherencia-bar { height:14px; border-radius:7px; background:#2d2d2d; overflow:hidden; margin:6px 0; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# AUTENTICACION
# =====================================================
def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()

def validar_usuario(usuario, clave):
    try:
        us = st.secrets.get("usuarios", {})
        if us:
            stored = us.get(usuario)
            return stored == hash_password(clave) if stored else False
    except Exception:
        pass
    fallback = {
        "visho":    st.secrets.get("PW_VISHO",    "Bio2026"),
        "eduardo":  st.secrets.get("PW_EDUARDO",  "Bio2026"),
        "davidp":   st.secrets.get("PW_DAVIDP",   "Davidp2026"),
        "clemente": st.secrets.get("PW_CLEMENTE", "Clemente2026"),
    }
    return fallback.get(usuario) == clave

def login():
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False
    if not st.session_state["autenticado"]:
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.markdown("""
            <div style='text-align:center;padding:40px 0 20px'>
                <span style='font-family:Bebas Neue,sans-serif;font-size:3rem;color:#39FF14;letter-spacing:4px'>⚡ BIO SPORT</span><br>
                <span style='color:#888;font-size:0.9rem;letter-spacing:2px'>PLATAFORMA DE ALTO RENDIMIENTO</span>
            </div>""", unsafe_allow_html=True)
            with st.form("login"):
                usuario = st.text_input("Usuario", placeholder="tu usuario").lower().strip()
                clave   = st.text_input("Contrasena", type="password", placeholder="...")
                if st.form_submit_button("ENTRAR AL SISTEMA", type="primary", use_container_width=True):
                    if validar_usuario(usuario, clave):
                        st.session_state["autenticado"]    = True
                        st.session_state["usuario_actual"] = usuario
                        st.rerun()
                    else:
                        st.error("Credenciales incorrectas")
        return False
    return True

if not login(): st.stop()

st.sidebar.markdown(f"**Entrenador: {st.session_state['usuario_actual'].capitalize()}**")
if st.sidebar.button("Cerrar Sesion"):
    for k in list(st.session_state.keys()): del st.session_state[k]
    st.rerun()

# =====================================================
# DATOS TECNICOS
# =====================================================
VIDEOS_BASE = {
    "Sentadilla Goblet":  "https://www.youtube.com/watch?v=MeIiIdhvXT4",
    "Sentadilla Libre":   "https://www.youtube.com/watch?v=1OoMs3MaXI4",
    "Flexiones":          "https://www.youtube.com/watch?v=e_K0yT3t3IM",
    "Jalon al Pecho":     "https://www.youtube.com/watch?v=HSoHeSrp-j4",
    "Peso Muerto Rumano": "https://www.youtube.com/watch?v=JCXUYuzwNrM",
    "Plancha Abdominal":  "https://www.youtube.com/watch?v=ASdvN_XEl_c",
    "Press Banca":        "https://www.youtube.com/watch?v=VmB1G1K7v94",
    "Zancadas":           "https://www.youtube.com/watch?v=0_ZmM-J7y_M",
    "Remo Mancuerna":     "https://www.youtube.com/watch?v=D7KaRcCIQms",
    "Press Militar":      "https://www.youtube.com/watch?v=M2rwvNhTOu0",
}
SUGERENCIAS_OBJETIVO = {
    "Hipertrofia":   {"Reps":"6-12",  "Pausa":"1:30-2:00","RPE":"7-9",      "RM":"65-80%"},
    "Fuerza Maxima": {"Reps":"1-5",   "Pausa":"3:00-5:00","RPE":"8-10",     "RM":"85-100%"},
    "Resistencia":   {"Reps":"15-20+","Pausa":"0:30-1:00","RPE":"6-8",      "RM":"< 60%"},
    "Potencia":      {"Reps":"1-5",   "Pausa":"2:00-3:00","RPE":"Explosivo","RM":"30-70%"},
}
TABLA_BADILLO = pd.DataFrame({
    "Zona":["Fuerza Max","Fuerza-Hipertrofia","Hipertrofia Alta","Hipertrofia Media","Resistencia"],
    "% 1RM":["85-100%","80-85%","70-80%","60-75%","<60%"],
    "Reps":["1-5","5-7","6-12","12-20","20+"],
    "Descanso":["3-5 min","3 min","2 min","1-2 min","<1 min"],
})
GUIAS_BOMPA = pd.DataFrame({
    "Fase":["Adaptacion","Hipertrofia","Fuerza Max","Potencia","Transicion"],
    "Intensidad":["30-60%","60-80%","85-100%","30-80%","Baja"],
    "Reps":["12-20","6-12","1-5","1-10","Libre"],
    "Descanso":["1-2 min","1-3 min","3-5+ min","3-5+ min","Libre"],
})
GUIA_TEMPO     = pd.DataFrame({"Objetivo":["Hipertrofia","Fuerza Max","Potencia","Resistencia"],"Tempo":["3-0-1-0","X-0-X-0","X-X-X","2-0-2-0"],"Explicacion":["Bajada lenta","Max velocidad","Explosivo","Continuo"]})
GUIA_DESCANSOS = pd.DataFrame({"Objetivo":["Fuerza/Potencia","Hipertrofia","Resistencia"],"Tiempo":["3 a 5+ min","60 a 90 seg","30 a 60 seg"],"Por que":["Recuperar ATP","Estres Metabolico","Limpiar lactato"]})
ESCALA_RPE     = pd.DataFrame({"RPE":[10,9,8,7,6],"RIR":["0 (Fallo)","1","2","3","4"],"Sensacion":["Imposible","1 mas","2 mas","3 mas","Calentamiento"]})
ESCALA_BORG    = pd.DataFrame({"Nivel":["Muy Suave","Suave","Moderado","Duro","Muy Duro","Maximo"],"Escala 0-10":["0-2","3","4-5","6-7","8-9","10"],"Test Habla":["Cantar","Fluida","Frases","Palabras","Apenas","Sin aliento"]})
GUIA_ZONAS_CARDIO = pd.DataFrame({"Zona":["Z1 Regenerativo","Z2 Aerobico","Z3 Umbral","Z4 VO2Max","Z5 Anaerobico"],"% VAM":["<60%","60-75%","75-90%","95-105%",">110%"],"Sensacion":["Muy facil","Facil","Duro","Muy duro","Agonia"]})
TIPOS_CARDIO  = ["Carrera","Bicicleta","Eliptica","Remo","Natacion","HIIT","Caminata","Otro"]
TESTS_FISICOS = ["Test de Cooper (12 min)","Test Yo-Yo","Salto CMJ","Flexibilidad (Sit & Reach)","Fuerza Relativa","1RM Estimado","Test de 1km","Otro"]

# =====================================================
# GOOGLE SHEETS
# =====================================================
URL_SHEET = "https://docs.google.com/spreadsheets/d/1NxZNe_1GjunjcpJs91tHJIAnZievTsNuVTTFe6uMqik/edit#gid=0"

def get_gsheets_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds  = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)
    return gspread.authorize(creds)

def cargar_datos_disco():
    usuario = st.session_state.get("usuario_actual","default")
    try:
        client = get_gsheets_client()
        sheet  = client.open_by_url(URL_SHEET)
        try:    ws = sheet.worksheet(usuario)
        except: ws = sheet.add_worksheet(title=usuario, rows="100", cols="20"); return None
        vals = ws.col_values(1)
        if vals: return json.loads("".join(vals))
    except Exception as e: st.sidebar.error(f"Error carga: {e}")
    return None

def guardar_datos_disco():
    usuario = st.session_state.get("usuario_actual","default")
    try:
        datos = {
            "clientes":        st.session_state.db_clientes,
            "historial":       st.session_state.historial_global,
            "videos":          st.session_state.biblioteca_videos,
            "planes":          st.session_state.planes_semanales,
            "detalles_planes": st.session_state.detalles_planes,
            "notas":           st.session_state.notas_personales,
            "tests":           st.session_state.tests_fisicos,
            "mesociclos":      st.session_state.mesociclos,
        }
        js = json.dumps(datos, ensure_ascii=False)
        client = get_gsheets_client()
        sheet  = client.open_by_url(URL_SHEET)
        try:    ws = sheet.worksheet(usuario)
        except: ws = sheet.add_worksheet(title=usuario, rows="100", cols="20")
        chunks = [js[i:i+40000] for i in range(0, len(js), 40000)]
        ws.clear()
        cells = ws.range(1,1,len(chunks),1)
        for i,cell in enumerate(cells): cell.value = chunks[i]
        ws.update_cells(cells)
        _backup_automatico(js, sheet)
        return True
    except Exception as e: st.sidebar.error(f"Error guardando: {e}"); return False

def _backup_automatico(json_str, sheet):
    try:
        usuario   = st.session_state.get("usuario_actual","default")
        nombre_bk = f"BK_{usuario}_{date.today().strftime('%Y-%m-%d')}"
        try: sheet.worksheet(nombre_bk); return
        except: pass
        ws_bk = sheet.add_worksheet(title=nombre_bk, rows="100", cols="20")
        chunks = [json_str[i:i+40000] for i in range(0, len(json_str), 40000)]
        cells  = ws_bk.range(1,1,len(chunks),1)
        for i,cell in enumerate(cells): cell.value = chunks[i]
        ws_bk.update_cells(cells)
    except Exception: pass

def registrar_auditoria_cobro(nombre_alumno):
    usuario = st.session_state.get("usuario_actual","")
    if usuario == "visho": return
    try:
        client = get_gsheets_client(); sheet = client.open_by_url(URL_SHEET)
        meses  = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        nh = f"Auditoria_{meses[datetime.now().month-1]}_{datetime.now().year}"
        try:    ws = sheet.worksheet(nh)
        except: ws = sheet.add_worksheet(title=nh,rows="1000",cols="4"); ws.append_row(["Fecha","Preparador","Alumno","Estado"])
        for fila in ws.get_all_values():
            if len(fila)>=3 and fila[1].lower()==usuario and fila[2].lower()==nombre_alumno.lower(): return
        ws.append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), usuario.capitalize(), nombre_alumno, "Pendiente"])
    except Exception: pass

# =====================================================
# CALCULOS Y UTILIDADES
# =====================================================
def calcular_1rm(p,r): return p*(1+(r/30))

def calcular_durnin(edad, sexo, s4):
    if s4 <= 0: raise ValueError("Pliegues deben ser > 0")
    c,m = (1.1631,0.0632) if sexo=="Masculino" else (1.1599,0.0717)
    d   = c-(m*math.log10(s4))
    if d<=0: raise ValueError("Densidad invalida")
    return (495/d)-450

def evaluar_grasa(edad, sexo, grasa):
    if sexo=="Masculino":
        t = [3,9,19,23] if edad<=24 else [3,10,20,24] if edad<=29 else [3,11,21,25] if edad<=34 else \
            [3,12,22,26] if edad<=39 else [3,13,23,27] if edad<=44 else [3,15,25,28] if edad<=49 else \
            [3,17,26,29] if edad<=54 else [3,19,28,30] if edad<=59 else [3,20,29,31]
    else:
        t = [8,15,25,30] if edad<=24 else [8,16,26,31] if edad<=29 else [8,17,27,32] if edad<=34 else \
            [8,19,28,33] if edad<=39 else [8,21,29,34] if edad<=44 else [8,23,31,36] if edad<=49 else \
            [8,25,33,37] if edad<=54 else [8,26,34,38] if edad<=59 else [8,27,35,39]
    if grasa<=t[0]:   return "Grasa Esencial","#FF4B4B"
    elif grasa<=t[1]: return "Graso Disminuido","#00C853"
    elif grasa<=t[2]: return "Graso Adecuado","#00BFFF"
    elif grasa<=t[3]: return "Graso Aumentado","#FFD700"
    else:             return "Grasa Muy Alta","#DC143C"

def calcular_tmb(peso, talla, edad, sexo):
    if sexo=="Masculino": return 10*peso + 6.25*talla - 5*edad + 5
    return 10*peso + 6.25*talla - 5*edad - 161

def calcular_get(tmb, actividad):
    f = {"Sedentario":1.2,"Ligero (1-3 dias)":1.375,"Moderado (3-5 dias)":1.55,"Activo (6-7 dias)":1.725,"Muy Activo (2x/dia)":1.9}
    return tmb * f.get(actividad, 1.55)

def analizar_progreso_avanzado(datos_ej):
    if len(datos_ej)<3: return "sin_datos","Necesitas al menos 3 registros para analizar.","alert-info"
    cargas = datos_ej["Carga"].tolist(); ult3 = cargas[-3:]
    n=len(cargas)
    if n>=5:
        xs=list(range(n)); mx=sum(xs)/n; my=sum(cargas)/n
        num=sum((x-mx)*(y-my) for x,y in zip(xs,cargas)); den=sum((x-mx)**2 for x in xs)
        pendiente=num/den if den!=0 else 0; tasa=(pendiente/my)*100 if my>0 else 0
    else: tasa=None
    if ult3[0]==ult3[1]==ult3[2]:
        return "estancamiento",f"Estancamiento: {ult3[0]}kg en 3 sesiones. Considera descarga o variacion de estimulo.","alert-warning"
    if ult3[2]<ult3[0]:
        return "baja",f"Bajada: -{ult3[0]-ult3[2]:.1f}kg vs sesion de referencia. Revisa fatiga, sueno o nutricion.","alert-danger"
    if tasa and tasa>1.5:
        return "progreso_rapido",f"Progreso solido: +{tasa:.1f}% por sesion en promedio.","alert-success"
    if ult3[2]>ult3[1]:
        return "progreso",f"Progresando: {ult3[1]}kg a {ult3[2]}kg en la ultima sesion.","alert-success"
    return "estable","Carga estable. Evalua si es momento de aplicar sobrecarga progresiva.","alert-info"

def calcular_adherencia(cliente, planes_semanales):
    hoy=date.today(); ini=hoy-timedelta(days=30)
    dp=0; de=0
    for i in range(30):
        dia=ini+timedelta(days=i)
        nd=["Lunes","Martes","Miercoles","Jueves","Viernes","Sabado","Domingo"][dia.weekday()]
        foco=planes_semanales.get(cliente,{}).get(nd,"Descanso")
        if foco not in ["Descanso",""]:
            dp+=1
            fs=dia.strftime("%d/%m/%Y")
            if any(h["Cliente"]==cliente and h["Fecha"]==fs for h in st.session_state.historial_global):
                de+=1
    pct=(de/dp*100) if dp>0 else 0
    return de,dp,pct

def interpretar_tiempo(t):
    try:
        t=str(t).strip()
        if ":" in t: return int(t.split(":")[0])*60+int(t.split(":")[1])
        return int(float(t)*60) if float(t)<10 else int(float(t))
    except: return 90

def fecha_es(f): return f.strftime("%d/%m/%Y")

def obtener_ultimo_registro(cliente, ejercicio):
    for r in reversed(st.session_state.historial_global):
        if r["Cliente"]==cliente and r["Ejercicio"]==ejercicio and r.get("Tipo")=="Fuerza": return r
    return None

def importar_historial_al_plan(cliente):
    dias_map={0:"Lunes",1:"Martes",2:"Miercoles",3:"Jueves",4:"Viernes",5:"Sabado",6:"Domingo"}
    nd=st.session_state.detalles_planes.get(cliente,{}).copy()
    nf=st.session_state.planes_semanales.get(cliente,{}).copy()
    rt={d:[] for d in dias_map.values()}; ft={d:"Descanso" for d in dias_map.values()}
    hoy=date.today()
    for reg in reversed(st.session_state.historial_global):
        if reg["Cliente"]==cliente:
            try:
                fd=datetime.strptime(reg["Fecha"],"%d/%m/%Y").date()
                if (hoy-fd).days<14:
                    dia=dias_map[fd.weekday()]
                    txt=f"{reg['Ejercicio']}: {reg['Series']}x{reg['Reps']} ({reg['Carga']}kg)" if reg.get("Tipo")=="Fuerza" else f"Cardio: {reg['Ejercicio']} ({reg['Carga']}min)"
                    if txt not in rt[dia]: rt[dia].insert(0,txt)
                    if "Objetivo" in reg and ft[dia]=="Descanso": ft[dia]=reg["Objetivo"]
            except: pass
    for dia,lista in rt.items():
        if lista:
            nd[dia]=f"||{chr(10).join(lista)}||"
            nf[dia]=ft[dia] if ft[dia]!="Descanso" else "Entrenamiento"
    st.session_state.planes_semanales[cliente]=nf
    st.session_state.detalles_planes[cliente]=nd
    guardar_datos_disco()

# =====================================================
# GENERADORES DE ARCHIVOS
# =====================================================
def generar_pdf_plan(cliente, plan_focos, plan_detalles):
    if not REPORTLAB_OK: return None
    buf=io.BytesIO(); c=canvas.Canvas(buf,pagesize=letter); W,H=letter
    NEON=HexColor("#39FF14"); OSC=HexColor("#1E1E1E"); GRS=HexColor("#2D2D2D"); NEG=HexColor("#222222"); SUB=HexColor("#555555")
    c.setFillColor(OSC); c.rect(0,H-90,W,90,fill=1,stroke=0)
    c.setFillColor(NEON); c.setFont("Helvetica-Bold",22); c.drawString(50,H-45,"PLAN DE ENTRENAMIENTO")
    c.setFont("Helvetica",13); c.drawString(50,H-68,f"Atleta: {cliente}")
    c.setFont("Helvetica",9); c.drawRightString(W-50,H-45,"BIO SPORT PRO")
    c.setFillColor(HexColor("#AAAAAA")); c.drawRightString(W-50,H-60,f"Fecha: {date.today().strftime('%d/%m/%Y')}")
    y=H-115; dias=["Lunes","Martes","Miercoles","Jueves","Viernes","Sabado","Domingo"]
    tipo_sem=plan_focos.get("tipo_semana","")
    if tipo_sem:
        c.setFont("Helvetica-Bold",11); c.setFillColor(NEON); c.drawString(50,y,f"Microciclo: {tipo_sem}"); y-=25
    for dia in dias:
        foco=plan_focos.get(dia,"Descanso"); det=plan_detalles.get(dia,"")
        lineas=len(det.split("\n")) if det else 0; altura=55+lineas*13
        if y-altura<50: c.showPage(); y=H-50
        if foco!="Descanso":
            c.setFillColor(GRS); c.rect(50,y-18,W-100,22,fill=1,stroke=0)
            c.setFillColor(NEON); c.setFont("Helvetica-Bold",11); c.drawString(58,y-11,f"{dia.upper()}  .  {foco}")
            c.setStrokeColor(NEON); c.setLineWidth(0.5); c.line(50,y-18,W-50,y-18); y-=30
            if det:
                partes=det.split("||")
                if len(partes)==3:
                    for i,bloque in enumerate(partes):
                        if bloque.strip():
                            if y<60: c.showPage(); y=H-50
                            c.setFont("Helvetica-Bold",9); c.setFillColor(NEON)
                            c.drawString(65,y,f"[ {['Calentamiento','Desarrollo','Vuelta a la Calma'][i]} ]"); y-=13
                            c.setFont("Helvetica",10); c.setFillColor(NEG)
                            for l in bloque.split("\n"):
                                if l.strip():
                                    if y<50: c.showPage(); y=H-50
                                    c.drawString(75,y,f"- {l.strip()}"); y-=13
                            y-=5
                else:
                    c.setFont("Helvetica",10); c.setFillColor(NEG)
                    for l in det.split("\n"):
                        if l.strip():
                            if y<50: c.showPage(); y=H-50
                            c.drawString(65,y,f"- {l.strip()}"); y-=13
            else:
                c.setFont("Helvetica-Oblique",9); c.setFillColor(SUB); c.drawString(65,y,"(Sin detalles)"); y-=13
            y-=12
        else:
            c.setFont("Helvetica-Oblique",9); c.setFillColor(SUB); c.drawString(58,y-8,f"{dia}: Descanso / Recuperacion"); y-=25
    c.setFont("Helvetica",8); c.setFillColor(SUB); c.drawCentredString(W/2,25,"La constancia es la clave del exito - Bio Sport Pro"); c.save()
    buf.seek(0); return buf

def generar_excel_historial(cliente, historial):
    if not OPENPYXL_OK: return None
    regs=[r for r in historial if r["Cliente"]==cliente]
    if not regs: return None
    df=pd.DataFrame(regs); buf=io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer,index=False,sheet_name="Historial")
        ws=writer.sheets["Historial"]
        for col in ws.columns:
            ml=max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width=min(ml+4,40)
    buf.seek(0); return buf

def generar_mesociclo_ia(cliente, objetivo, semanas=4):
    if not modelo_dante: return None
    datos=st.session_state.db_clientes.get(cliente,{})
    perfil=f"Edad:{datos.get('Edad','N/A')}, Experiencia:{datos.get('Experiencia','N/A')}, Lesiones:{datos.get('Lesiones','Ninguna')}, Objetivo:{objetivo}"
    prompt=f"""Eres Dante, experto en periodizacion deportiva. Genera un mesociclo de {semanas} semanas para:
Perfil: {perfil}
Para cada semana indica: tipo de semana, intensidad (% RM), volumen (series por grupo muscular), ejercicios principales (3-5), RPE objetivo, y nota del entrenador.
Formato: semana por semana, claro y estructurado."""
    try:
        resp=modelo_dante.generate_content(prompt); return resp.text
    except Exception as e: return f"Error: {e}"

# =====================================================
# PANEL ADMIN
# =====================================================
def mostrar_panel_admin():
    st.title("Panel de Control Bio Sport")
    try:
        client=get_gsheets_client(); sheet=client.open_by_url(URL_SHEET)
        reglas={"eduardo":{"tipo":"por_alumno","valor":2500},"davidp":{"tipo":"fijo","valor":10000},"clemente":{"tipo":"por_alumno","valor":2500}}
        cobros=[]; total=0
        for prep,regla in reglas.items():
            try:
                ws=sheet.worksheet(prep); vals=ws.col_values(1)
                if vals:
                    jd=json.loads("".join(vals)); n=len(jd.get("clientes",{}))
                    monto=n*regla["valor"] if regla["tipo"]=="por_alumno" else regla["valor"]
                    cobros.append({"Preparador":prep.capitalize(),"Alumnos":n,"Trato":f"${regla['valor']:,}/alumno" if regla["tipo"]=="por_alumno" else "Fijo","Monto":f"${monto:,}"})
                    total+=monto
            except: continue
        if cobros:
            c1,c2=st.columns(2); c1.metric("Alumnos Totales",sum(d["Alumnos"] for d in cobros)); c2.metric("Total a Recaudar",f"${total:,}")
            st.table(pd.DataFrame(cobros))
            st.subheader("Ranking de Actividad (30 dias)")
            ranking=[]
            for prep in reglas:
                try:
                    ws=sheet.worksheet(prep); vals=ws.col_values(1)
                    if vals:
                        jd=json.loads("".join(vals))
                        for nombre in jd.get("clientes",{}):
                            r30=[r for r in jd.get("historial",[]) if r["Cliente"]==nombre and (date.today()-datetime.strptime(r["Fecha"],"%d/%m/%Y").date()).days<=30]
                            ranking.append({"Atleta":nombre,"Preparador":prep.capitalize(),"Sesiones 30d":len(r30)})
                except: continue
            if ranking:
                df_r=pd.DataFrame(ranking).sort_values("Sesiones 30d",ascending=False)
                st.dataframe(df_r,use_container_width=True,hide_index=True)
    except Exception as e: st.error(f"Error: {e}")

# =====================================================
# INICIALIZACION DE ESTADO
# =====================================================
datos = cargar_datos_disco()
def _init(key, default):
    if key not in st.session_state:
        st.session_state[key] = (datos.get(key) if datos and datos.get(key) is not None else default)

_init("db_clientes",       {})
_init("historial_global",  [])
_init("biblioteca_videos", VIDEOS_BASE)
_init("planes_semanales",  {})
_init("detalles_planes",   {})
_init("notas_personales",  "")
_init("tests_fisicos",     {})
_init("mesociclos",        {})
if "cliente_activo"  not in st.session_state: st.session_state.cliente_activo  = None
if "confirm_delete"  not in st.session_state: st.session_state.confirm_delete  = False
if "modo_live"       not in st.session_state: st.session_state.modo_live       = False
if "live_idx"        not in st.session_state: st.session_state.live_idx        = 0

# =====================================================
# SIDEBAR
# =====================================================
st.sidebar.header("Bio Sport Pro")
lista = ["Crear Nuevo..."] + list(st.session_state.db_clientes.keys())
sel   = st.sidebar.selectbox("Atleta:", lista)

if sel == "Crear Nuevo...":
    nom = st.sidebar.text_input("Nombre del nuevo atleta:")
    if st.sidebar.button("Guardar Atleta", type="primary"):
        if nom and nom.strip() not in st.session_state.db_clientes:
            st.session_state.db_clientes[nom.strip()] = {"Peso":70,"Talla":170,"Edad":25,"Sexo":"Masculino"}
            guardar_datos_disco(); registrar_auditoria_cobro(nom.strip())
            st.toast("Atleta registrado",icon="OK"); time.sleep(0.8); st.rerun()
        elif nom.strip() in st.session_state.db_clientes:
            st.sidebar.warning("Ese atleta ya existe.")
else:
    st.session_state.cliente_activo = sel
    with st.sidebar.expander("Gestion", expanded=False):
        if not st.session_state.confirm_delete:
            if st.button("Eliminar Atleta"):
                st.session_state.confirm_delete=True; st.rerun()
        else:
            st.warning(f"Eliminar {sel} permanentemente?")
            c1,c2=st.columns(2)
            if c1.button("Si, eliminar"):
                del st.session_state.db_clientes[sel]
                st.session_state.historial_global=[h for h in st.session_state.historial_global if h["Cliente"]!=sel]
                for dd in [st.session_state.planes_semanales,st.session_state.detalles_planes,st.session_state.tests_fisicos,st.session_state.mesociclos]:
                    if sel in dd: del dd[sel]
                guardar_datos_disco(); st.session_state.cliente_activo=None; st.session_state.confirm_delete=False; st.rerun()
            if c2.button("Cancelar"):
                st.session_state.confirm_delete=False; st.rerun()
        js=json.dumps({"clientes":st.session_state.db_clientes,"historial":st.session_state.historial_global},indent=2,ensure_ascii=False)
        st.download_button("Backup JSON",data=js,file_name="backup_biosport.json",mime="application/json")

with st.sidebar.expander("Calculadora RM", expanded=False):
    p_=st.number_input("Peso kg",0.0,step=0.5,key="rm_p"); r_=st.number_input("Reps",1,20,8,key="rm_r")
    if p_>0:
        rm=calcular_1rm(p_,r_); st.write(f"1RM: {rm:.1f} kg")
        c1,c2=st.columns(2); c1.caption(f"90%: {rm*.9:.1f}\n80%: {rm*.8:.1f}"); c2.caption(f"70%: {rm*.7:.1f}\n60%: {rm*.6:.1f}")

opciones_menu = [
    "0. Dashboard",
    "1. Ficha & Antropo",
    "2. Entrenamiento",
    "3. Modo En Vivo",
    "4. Plan Semanal",
    "5. Mesociclo IA",
    "6. Cardio",
    "7. Tests Fisicos",
    "8. Nutricion",
    "9. Progreso",
    "10. Guias",
    "11. Notas",
    "12. Videoteca",
]
if st.session_state.get("usuario_actual")=="visho": opciones_menu.append("Panel Admin")
menu = st.sidebar.radio("Menu:", opciones_menu)
st.sidebar.divider()
if st.session_state.cliente_activo:
    st.sidebar.success(f"Atleta: {st.session_state.cliente_activo}")

# =====================================================
# 0. DASHBOARD
# =====================================================
if menu == "0. Dashboard":
    st.title("Dashboard Bio Sport")
    total=len(st.session_state.db_clientes); hoy_str=date.today().strftime("%d/%m/%Y")
    hoy_s=len([h for h in st.session_state.historial_global if h["Fecha"]==hoy_str])
    total_r=len(st.session_state.historial_global)
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Atletas Activos",total); c2.metric("Sesiones Hoy",hoy_s)
    c3.metric("Registros Totales",total_r); c4.metric("Fecha",hoy_str)
    st.divider()
    if st.session_state.db_clientes:
        st.subheader("Estado de Atletas")
        filas=[]
        for nombre,d in st.session_state.db_clientes.items():
            regs=[h for h in st.session_state.historial_global if h["Cliente"]==nombre]
            ult=regs[-1]["Fecha"] if regs else "Sin registros"
            de,dp,pct=calcular_adherencia(nombre,st.session_state.planes_semanales)
            filas.append({"Atleta":nombre,"Objetivo":d.get("Objetivo_Prin",""),"Experiencia":d.get("Experiencia",""),"Sesiones":len(regs),"Ultimo Registro":ult,"Adherencia 30d":f"{pct:.0f}%"})
        st.dataframe(pd.DataFrame(filas),use_container_width=True,hide_index=True)
        st.subheader("Adherencia por Atleta (30 dias)")
        for nombre in st.session_state.db_clientes:
            de,dp,pct=calcular_adherencia(nombre,st.session_state.planes_semanales)
            color="#39FF14" if pct>=80 else "#FFD700" if pct>=50 else "#FF4B4B"
            fill_w=min(int(pct),100)
            st.markdown(f"""<div style='margin-bottom:8px'>
                <span style='font-size:0.9rem;font-weight:600'>{nombre}</span>
                <span style='float:right;color:{color};font-weight:700'>{pct:.0f}% ({de}/{dp} dias)</span>
                <div class='adherencia-bar'><div style='height:14px;border-radius:7px;background:{color};width:{fill_w}%'></div></div>
            </div>""", unsafe_allow_html=True)

# =====================================================
# 1. FICHA Y ANTROPOMETRIA
# =====================================================
elif menu == "1. Ficha & Antropo":
    if not st.session_state.cliente_activo: st.warning("Selecciona un atleta."); st.stop()
    c=st.session_state.cliente_activo; d=st.session_state.db_clientes[c]
    t1,t2,t3=st.tabs(["Datos Basicos","Antropometria","Anamnesis"])
    with t1:
        col1,col2,col3,col4=st.columns(4)
        np_=col1.number_input("Peso kg",0.1,250.0,float(d.get("Peso",70)),step=0.5)
        nt_=col2.number_input("Talla cm",50.0,250.0,float(d.get("Talla",170)),step=0.5)
        ne_=col3.number_input("Edad",5,100,int(d.get("Edad",25)))
        ns_=col4.selectbox("Sexo",["Masculino","Femenino"],index=0 if d.get("Sexo","Masculino")=="Masculino" else 1)
        imc=np_/((nt_/100)**2); st.caption(f"IMC: {imc:.1f}")
        if st.button("Actualizar Datos",type="primary"):
            st.session_state.db_clientes[c].update({"Peso":np_,"Talla":nt_,"Edad":ne_,"Sexo":ns_})
            guardar_datos_disco(); st.toast("Datos actualizados")
        st.divider()
        if st.checkbox("Calcular FCM (Tanaka)"):
            fcm=208-(0.7*ne_); st.info(f"FCM: {fcm:.0f} lpm")
            cols=st.columns(5)
            for i,(pct,zona) in enumerate([(60,"Z1"),(75,"Z2"),(85,"Z3"),(95,"Z4"),(100,"Z5")]):
                cols[i].metric(zona,f"{fcm*(pct/100):.0f}")
    with t2:
        st.subheader("Durnin 4 Pliegues + Siri")
        col_i,col_o=st.columns(2)
        with col_i:
            p1=st.number_input("Biceps mm",0.0,100.0,0.0,step=0.1); p2=st.number_input("Triceps mm",0.0,100.0,0.0,step=0.1)
            p3=st.number_input("Subescapular mm",0.0,100.0,0.0,step=0.1); p4=st.number_input("Suprailiaco mm",0.0,100.0,0.0,step=0.1)
            suma=p1+p2+p3+p4
        with col_o:
            if suma>0:
                try:
                    gr=calcular_durnin(d.get("Edad",25),d.get("Sexo","Masculino"),suma)
                    if not(2<=gr<=60): st.warning(f"Resultado fuera de rango: {gr:.1f}%")
                    else:
                        mm=d.get("Peso",70)*(1-gr/100)
                        st.metric("% Grasa",f"{gr:.1f}%"); st.metric("Masa Magra",f"{mm:.1f} kg"); st.metric("Masa Grasa",f"{d.get('Peso',70)-mm:.1f} kg")
                        cat,color=evaluar_grasa(d.get("Edad",25),d.get("Sexo","Masculino"),gr)
                        st.markdown(f'<div style="background:#2D2D2D;padding:15px;border-radius:8px;text-align:center;border:1px solid {color}"><div style="color:#aaa;font-size:12px">Clasificacion</div><div style="color:{color};font-size:1.4rem;font-weight:700">{cat}</div></div>',unsafe_allow_html=True)
                except ValueError as e: st.error(f"Error: {e}")
            else: st.info("Ingresa los 4 pliegues.")
    with t3:
        col1,col2=st.columns(2)
        fono=col1.text_input("Telefono",value=d.get("Telefono","")); eme=col2.text_input("Contacto Emergencia",value=d.get("Emergencia",""))
        les=st.text_area("Lesiones",value=d.get("Lesiones",""),height=80); enf=st.text_area("Enfermedades / Medicamentos",value=d.get("Enfermedades",""),height=70)
        col3,col4=st.columns(2)
        ops=["Principiante","Intermedio","Avanzado"]; ea=d.get("Experiencia","Principiante"); ea=ea if ea in ops else "Principiante"
        exp=col3.selectbox("Experiencia",ops,index=ops.index(ea)); obj=col4.text_input("Objetivo Principal",value=d.get("Objetivo_Prin",""))
        est=st.text_area("Estilo de Vida",value=d.get("Estilo_Vida",""),height=70)
        if st.button("Guardar Anamnesis",type="primary"):
            st.session_state.db_clientes[c].update({"Telefono":fono,"Emergencia":eme,"Lesiones":les,"Enfermedades":enf,"Experiencia":exp,"Objetivo_Prin":obj,"Estilo_Vida":est})
            guardar_datos_disco(); st.toast("Historial guardado")

# =====================================================
# 2. ENTRENAMIENTO
# =====================================================
elif menu == "2. Entrenamiento":
    if not st.session_state.cliente_activo: st.stop()
    c=st.session_state.cliente_activo
    fecha_sel=st.date_input("Fecha:",date.today())
    dia_nom=["Lunes","Martes","Miercoles","Jueves","Viernes","Sabado","Domingo"][fecha_sel.weekday()]
    pf=st.session_state.planes_semanales.get(c,{}).get(dia_nom,"Sin planificar")
    pd_=st.session_state.detalles_planes.get(c,{}).get(dia_nom,"")
    if pf=="Descanso": st.success(f"{dia_nom}: Descanso")
    else:
        st.info(f"{dia_nom}: {pf}")
        if pd_:
            with st.expander("Ver Plan",expanded=True):
                partes=pd_.split("||")
                if len(partes)==3:
                    if partes[0].strip(): st.markdown("**Calentamiento:**\n"+partes[0])
                    if partes[1].strip(): st.markdown("**Desarrollo:**\n"+partes[1])
                    if partes[2].strip(): st.markdown("**Vuelta:**\n"+partes[2])
                else: st.text(pd_)
    st.divider()
    col_e,col_t=st.columns([3,1])
    with col_e:
        obj_=st.selectbox("Objetivo:",list(SUGERENCIAS_OBJETIVO.keys()))
        sug=SUGERENCIAS_OBJETIVO[obj_]; st.caption(f"Guia: {sug['Reps']} reps | {sug['RM']} | Pausa: {sug['Pausa']} | RPE: {sug['RPE']}")
        ej_=st.selectbox("Ejercicio:",list(st.session_state.biblioteca_videos.keys())+["Otro..."])
        if ej_!="Otro...":
            ult=obtener_ultimo_registro(c,ej_)
            if ult:
                st.info(f"Ultimo: {ult['Series']}x{ult['Reps']} @ {ult['Carga']}kg")
                rm_=calcular_1rm(ult["Carga"],ult["Reps"]); st.caption(f"1RM est: {rm_:.1f}kg | 80%: {rm_*.8:.1f}kg | 70%: {rm_*.7:.1f}kg")
        nom=st.text_input("Nombre:",value=ej_ if ej_!="Otro..." else "")
        c1,c2,c3=st.columns(3)
        se=c1.number_input("Series",1,10,4); re=c2.number_input("Reps",1,50,10); kg=c3.number_input("Carga kg",0.0,step=0.5)
        pt=st.text_input("Pausa",value=sug["Pausa"].split("-")[0]); rpe=st.slider("RPE",1,10,7)
        if st.button("Registrar Serie",type="primary"):
            if nom.strip():
                st.session_state.historial_global.append({"Cliente":c,"Fecha":fecha_es(fecha_sel),"Ejercicio":nom.strip(),"Series":se,"Reps":re,"Carga":kg,"RPE":rpe,"Tipo":"Fuerza","Objetivo":obj_})
                guardar_datos_disco(); st.toast("Serie registrada"); st.rerun()
            else: st.warning("Escribe el nombre del ejercicio.")
        hist_dia=[h for h in st.session_state.historial_global if h["Cliente"]==c and h["Fecha"]==fecha_es(fecha_sel)]
        if hist_dia:
            st.divider(); st.subheader(f"Sesion {fecha_es(fecha_sel)}")
            vol=sum(h["Series"]*h["Reps"]*h["Carga"] for h in hist_dia if h.get("Tipo")=="Fuerza")
            st.caption(f"Volumen sesion: {vol:.0f} kg*rep")
            for i,h in enumerate(st.session_state.historial_global):
                if h["Cliente"]==c and h["Fecha"]==fecha_es(fecha_sel):
                    ci,cd=st.columns([4,1])
                    ci.write(f"{h['Ejercicio']}: {h['Series']}x{h['Reps']} @ {h['Carga']}kg (RPE {h.get('RPE','-')})")
                    if cd.button("X",key=f"del_{i}"):
                        del st.session_state.historial_global[i]; guardar_datos_disco(); st.rerun()
    with col_t:
        st.write("Timer")
        seg=interpretar_tiempo(pt); st.write(f"Pausa: {seg}s")
        if st.button("Iniciar"):
            ph=st.empty(); bar=st.progress(0.0)
            for i in range(seg,-1,-1):
                ph.metric("Restante",f"{i}s"); bar.progress(1.0-(i/seg) if seg>0 else 1.0); time.sleep(1)
            ph.success("Tiempo!"); bar.empty()

# =====================================================
# 3. MODO EN VIVO
# =====================================================
elif menu == "3. Modo En Vivo":
    if not st.session_state.cliente_activo: st.warning("Selecciona un atleta."); st.stop()
    c=st.session_state.cliente_activo
    st.title(f"Modo Entrenamiento En Vivo - {c}")
    hoy=date.today()
    dia_nom=["Lunes","Martes","Miercoles","Jueves","Viernes","Sabado","Domingo"][hoy.weekday()]
    det=st.session_state.detalles_planes.get(c,{}).get(dia_nom,"")
    foco=st.session_state.planes_semanales.get(c,{}).get(dia_nom,"Sin planificar")
    ejercicios_hoy=[]
    if det:
        partes=det.split("||"); bloque=partes[1] if len(partes)>1 else partes[0] if partes else ""
        for linea in bloque.split("\n"):
            linea=linea.strip()
            if linea: ejercicios_hoy.append(linea)
    if not ejercicios_hoy:
        st.info(f"No hay ejercicios planificados para hoy ({dia_nom}). Ve al Plan Semanal para agregar."); st.stop()
    total_ej=len(ejercicios_hoy); idx=st.session_state.live_idx % total_ej; ej_actual=ejercicios_hoy[idx]
    st.markdown(f"""<div class='live-card'>
        <div style='color:#888;font-size:0.85rem;letter-spacing:2px;text-transform:uppercase'>{dia_nom} - {foco} - Ejercicio {idx+1}/{total_ej}</div>
        <div class='live-exercise'>{ej_actual}</div>
        <div class='live-detail'>Controla el movimiento. Mantente concentrado.</div>
    </div>""", unsafe_allow_html=True)
    st.markdown("<br>",unsafe_allow_html=True)
    c1,c2,c3=st.columns(3)
    with c1:
        if st.button("Anterior",use_container_width=True):
            st.session_state.live_idx=max(0,idx-1); st.rerun()
    with c2:
        pausa_live=st.selectbox("Pausa:",["60s","90s","120s","180s","300s"],index=1,label_visibility="collapsed")
        if st.button(f"Descanso {pausa_live}",use_container_width=True):
            seg_live=int(pausa_live.replace("s",""))
            ph=st.empty(); bar=st.progress(0.0)
            for i in range(seg_live,-1,-1):
                ph.metric("Descanso",f"{i}s"); bar.progress(1.0-(i/seg_live)); time.sleep(1)
            ph.success("A por la siguiente serie!")
    with c3:
        if st.button("Siguiente",use_container_width=True,type="primary"):
            st.session_state.live_idx=min(total_ej-1,idx+1); st.rerun()
    st.divider()
    st.subheader("Registrar Serie Rapida")
    cq1,cq2,cq3=st.columns(3)
    se_q=cq1.number_input("Series",1,10,4,key="live_se"); re_q=cq2.number_input("Reps",1,50,10,key="live_re"); kg_q=cq3.number_input("Carga kg",0.0,step=0.5,key="live_kg")
    if st.button("Guardar Serie",type="primary"):
        ej_limpio=ej_actual.split(":")[0].strip()
        st.session_state.historial_global.append({"Cliente":c,"Fecha":fecha_es(hoy),"Ejercicio":ej_limpio,"Series":se_q,"Reps":re_q,"Carga":kg_q,"RPE":7,"Tipo":"Fuerza","Objetivo":foco})
        guardar_datos_disco(); st.toast(f"Serie de {ej_limpio} guardada")
    st.divider(); st.subheader("Todos los ejercicios de hoy")
    for i,ej in enumerate(ejercicios_hoy):
        color="#39FF14" if i==idx else "#555"
        st.markdown(f"<div style='padding:6px 12px;border-left:3px solid {color};margin:3px 0;font-size:0.9rem'>{i+1}. {ej}</div>",unsafe_allow_html=True)

# =====================================================
# 4. PLAN SEMANAL
# =====================================================
elif menu == "4. Plan Semanal":
    if not st.session_state.cliente_activo: st.stop()
    c=st.session_state.cliente_activo
    ch1,ch2=st.columns([3,1]); ch1.subheader(f"Plan Semanal - {c}")
    with ch2:
        if st.button("Cargar Historial"): importar_historial_al_plan(c); st.toast("Historial importado"); st.rerun()
    tipos=["Ajuste (Descarga)","Carga (Desarrollo)","Impacto (Choque)"]
    tg=st.session_state.planes_semanales.get(c,{}).get("tipo_semana","Carga (Desarrollo)")
    mc=st.select_slider("Microciclo:",options=tipos,value=tg if tg in tipos else tipos[1])
    if mc=="Ajuste (Descarga)": st.info("Recuperacion. RPE 5-7.")
    elif mc=="Carga (Desarrollo)": st.success("Desarrollo. RPE 7-8.5.")
    else: st.error("Maximo esfuerzo. RPE 9-10.")
    with st.expander("Dante (IA) - Sugerir Rutina"):
        datos_f=st.session_state.db_clientes.get(c,{}); perfil=f"Edad:{datos_f.get('Edad','?')}, Exp:{datos_f.get('Experiencia','?')}, Lesiones:{datos_f.get('Lesiones','Ninguna')}"
        cd,cb=st.columns([2,1]); dia_d=cd.selectbox("Enfoque:",["Pierna","Torso","Full Body","Cardio","Gluteo","Brazo"])
        if cb.button("Generar Rutina") and modelo_dante:
            with st.spinner("Dante disenando..."):
                try:
                    r=modelo_dante.generate_content(f"Eres Dante, entrenador. Perfil:{perfil}. Microciclo:{mc}. Rutina para {dia_d}:\n1.Calentamiento\n2.Bloque principal\n3.Vuelta calma. Se especifico.")
                    st.markdown(r.text)
                except Exception as e: st.error(f"Error: {e}")
    ops=["Descanso","Pierna","Pecho/Hombro","Espalda","Gluteo","Full Body","Torso","Brazo","Cardio"]
    dias=["Lunes","Martes","Miercoles","Jueves","Viernes","Sabado","Domingo"]
    nf={"tipo_semana":mc}; nd={}
    for dia in dias:
        with st.expander(f"{dia}",expanded=False):
            vd=st.session_state.planes_semanales.get(c,{}).get(dia,"Descanso")
            if vd not in ops: ops.append(vd)
            nf[dia]=st.selectbox(f"Enfoque {dia}",ops,index=ops.index(vd),key=f"f_{dia}")
            if nf[dia]!="Descanso":
                pt=st.session_state.detalles_planes.get(c,{}).get(dia,"||").split("||")
                cd_=pt[0] if len(pt)>0 else ""; dd_=pt[1] if len(pt)>1 else ""; vv_=pt[2] if len(pt)>2 else ""
                cc1,cc2,cc3=st.columns(3)
                cal=cc1.text_area("Calentamiento",value=cd_,key=f"c_{dia}",height=150)
                des=cc2.text_area("Desarrollo",value=dd_,key=f"d_{dia}",height=150)
                vue=cc3.text_area("Vuelta a la Calma",value=vv_,key=f"v_{dia}",height=150)
                nd[dia]=f"{cal}||{des}||{vue}"
            else: nd[dia]=""
    cg,cp=st.columns(2)
    with cg:
        if st.button("Guardar Plan",type="primary"):
            st.session_state.planes_semanales[c]=nf; st.session_state.detalles_planes[c]=nd
            ok=guardar_datos_disco(); st.toast("Plan guardado" if ok else "Error")
    with cp:
        if REPORTLAB_OK:
            try:
                pdf=generar_pdf_plan(c,nf,nd)
                if pdf: st.download_button("Descargar PDF",data=pdf,file_name=f"Rutina_{c.replace(' ','_')}.pdf",mime="application/pdf")
            except Exception as e: st.error(f"PDF error: {e}")

# =====================================================
# 5. MESOCICLO IA
# =====================================================
elif menu == "5. Mesociclo IA":
    if not st.session_state.cliente_activo: st.stop()
    c=st.session_state.cliente_activo
    st.title(f"Periodizacion con IA - {c}")
    st.info("Dante generara un plan completo de 4-12 semanas basado en el perfil del atleta.")
    cm1,cm2,cm3=st.columns(3)
    obj_meso=cm1.selectbox("Objetivo:",["Hipertrofia","Fuerza Maxima","Resistencia","Potencia","Perdida de Grasa","Rendimiento General"])
    semanas=cm2.slider("Semanas:",4,12,8)
    datos_c=st.session_state.db_clientes.get(c,{})
    ops_niv=["Principiante","Intermedio","Avanzado"]; niv_actual=datos_c.get("Experiencia","Principiante")
    if niv_actual not in ops_niv: niv_actual="Principiante"
    cm3.selectbox("Nivel:",ops_niv,index=ops_niv.index(niv_actual))
    mesociclos_guardados=st.session_state.mesociclos.get(c,[])
    if st.button("Generar Mesociclo con Dante",type="primary"):
        if modelo_dante:
            with st.spinner(f"Dante disenando {semanas} semanas..."):
                resultado=generar_mesociclo_ia(c,obj_meso,semanas)
                if resultado:
                    nuevo={"fecha":date.today().strftime("%d/%m/%Y"),"objetivo":obj_meso,"semanas":semanas,"contenido":resultado}
                    if c not in st.session_state.mesociclos: st.session_state.mesociclos[c]=[]
                    st.session_state.mesociclos[c].insert(0,nuevo)
                    guardar_datos_disco(); st.success("Mesociclo generado y guardado")
        else: st.warning("Dante no disponible. Verifica la API key.")
    if mesociclos_guardados:
        st.divider(); st.subheader("Mesociclos Guardados")
        for i,meso in enumerate(mesociclos_guardados):
            with st.expander(f"{meso['fecha']} - {meso['objetivo']} ({meso['semanas']} semanas)",expanded=(i==0)):
                st.markdown(meso["contenido"])
                st.download_button("Descargar TXT",data=meso["contenido"],file_name=f"Mesociclo_{c.replace(' ','_')}_{meso['fecha']}.txt",mime="text/plain",key=f"dl_{i}")
    else: st.info("No hay mesociclos generados aun.")

# =====================================================
# 6. CARDIO
# =====================================================
elif menu == "6. Cardio":
    if not st.session_state.cliente_activo: st.stop()
    c=st.session_state.cliente_activo; d=st.session_state.db_clientes[c]
    st.title(f"Cardio - {c}")
    t1,t2=st.tabs(["Calculadora VAM","Registrar Sesion"])
    with t1:
        vam=float(d.get("VAM",0.0)); cv1,cv2=st.columns(2)
        nueva_vam=cv1.number_input("VAM m/s",0.0,10.0,vam,step=0.1)
        if cv2.button("Actualizar VAM"):
            st.session_state.db_clientes[c]["VAM"]=nueva_vam; guardar_datos_disco(); st.toast("VAM actualizada"); vam=nueva_vam
        if vam>0:
            st.divider(); cd,cp=st.columns(2)
            dist=cd.number_input("Distancia m",100,10000,400,step=100); pct=cp.slider("% VAM",50,120,90)
            vel=vam*(pct/100); t_seg=dist/vel if vel>0 else 0; m,s=divmod(int(t_seg),60)
            cr1,cr2,cr3=st.columns(3)
            cr1.metric("Velocidad",f"{vel:.2f} m/s"); cr2.metric("Tiempo",f"{m}:{s:02d}")
            cr3.metric("Ritmo /km",f"{int(1000/vel//60)}:{int(1000/vel%60):02d}" if vel>0 else "-")
            st.divider(); st.subheader("Zonas Personalizadas")
            zonas=[]
            for z,lo,hi in [("Z1 Regenerativo",0.0,0.60),("Z2 Aerobico",0.60,0.75),("Z3 Umbral",0.75,0.90),("Z4 VO2Max",0.95,1.05),("Z5 Anaerobico",1.10,1.20)]:
                zonas.append({"Zona":z,"Vel Min":f"{vam*lo:.2f} m/s","Vel Max":f"{vam*hi:.2f} m/s","% VAM":f"{lo*100:.0f}-{hi*100:.0f}%"})
            st.dataframe(pd.DataFrame(zonas),use_container_width=True,hide_index=True)
    with t2:
        fecha_c=st.date_input("Fecha:",date.today(),key="fc")
        cc1,cc2=st.columns(2); tipo_c=cc1.selectbox("Actividad:",TIPOS_CARDIO); zona_c=cc2.selectbox("Zona:",["Z1","Z2","Z3","Z4","Z5"])
        cc3,cc4,cc5=st.columns(3)
        dur=cc3.number_input("Duracion min",1,300,30); dist_c=cc4.number_input("Distancia km",0.0,200.0,0.0,step=0.1); fc_p=cc5.number_input("FC Prom lpm",0,250,0)
        notas_c=st.text_area("Notas:",height=70)
        if st.button("Registrar Cardio",type="primary"):
            st.session_state.historial_global.append({"Cliente":c,"Fecha":fecha_es(fecha_c),"Ejercicio":tipo_c,"Series":1,"Reps":1,"Carga":dur,"Tipo":"Cardio","Objetivo":f"Cardio {zona_c}","Zona":zona_c,"Distancia":dist_c,"FC_Prom":fc_p,"Notas":notas_c})
            guardar_datos_disco(); st.toast("Cardio registrado"); st.rerun()
        hc=[h for h in st.session_state.historial_global if h["Cliente"]==c and h.get("Tipo")=="Cardio"]
        if hc:
            st.divider(); st.subheader("Historial Cardio")
            df_hc=pd.DataFrame(hc); cols_c=[col for col in ["Fecha","Ejercicio","Carga","Zona","Distancia","FC_Prom"] if col in df_hc.columns]
            st.dataframe(df_hc[cols_c].tail(20),use_container_width=True,hide_index=True)

# =====================================================
# 7. TESTS FISICOS
# =====================================================
elif menu == "7. Tests Fisicos":
    if not st.session_state.cliente_activo: st.stop()
    c=st.session_state.cliente_activo
    st.title(f"Tests Fisicos - {c}")
    t1,t2=st.tabs(["Nuevo Registro","Historial"])
    with t1:
        ct1,ct2=st.columns(2)
        tipo_test=ct1.selectbox("Tipo de Test:",TESTS_FISICOS); fecha_test=ct2.date_input("Fecha:",date.today())
        resultado=st.number_input("Resultado:",step=0.1)
        if tipo_test=="Test de Cooper (12 min)" and resultado>0:
            vo2=(resultado-504.9)/44.73; st.metric("VO2Max estimado",f"{vo2:.1f} ml/kg/min")
        notas_test=st.text_area("Observaciones:",height=80)
        condicion=st.selectbox("Condicion del Atleta:",["Descansado","Normal","Cansado"])
        if st.button("Guardar Test",type="primary"):
            if c not in st.session_state.tests_fisicos: st.session_state.tests_fisicos[c]=[]
            st.session_state.tests_fisicos[c].append({"Fecha":fecha_es(fecha_test),"Test":tipo_test,"Resultado":resultado,"Condicion":condicion,"Notas":notas_test})
            guardar_datos_disco(); st.toast("Test guardado")
    with t2:
        tests_c=st.session_state.tests_fisicos.get(c,[])
        if tests_c:
            df_t=pd.DataFrame(tests_c); tipos_reg=df_t["Test"].unique().tolist()
            test_sel=st.selectbox("Ver evolucion de:",tipos_reg); df_ts=df_t[df_t["Test"]==test_sel].copy()
            if len(df_ts)>1:
                st.line_chart(df_ts,x="Fecha",y="Resultado")
                mejor=df_ts["Resultado"].max(); actual=df_ts["Resultado"].iloc[-1]
                ct1,ct2,ct3=st.columns(3)
                ct1.metric("Mejor Marca",f"{mejor:.1f}"); ct2.metric("Ultimo",f"{actual:.1f}")
                ct3.metric("Diferencia",f"{actual-df_ts['Resultado'].iloc[-2]:+.1f}" if len(df_ts)>1 else "-")
            st.dataframe(df_t.sort_values("Fecha",ascending=False),use_container_width=True,hide_index=True)
            with st.expander("Eliminar registro"):
                idx_del=st.number_input("Numero de registro (0=primero):",0,len(tests_c)-1,0)
                if st.button("Eliminar"):
                    st.session_state.tests_fisicos[c].pop(idx_del); guardar_datos_disco(); st.rerun()
        else: st.info("No hay tests registrados.")

# =====================================================
# 8. NUTRICION
# =====================================================
elif menu == "8. Nutricion":
    if not st.session_state.cliente_activo: st.stop()
    c=st.session_state.cliente_activo; d=st.session_state.db_clientes[c]
    st.title(f"Nutricion - {c}")
    st.caption("Estimaciones orientativas. No reemplaza a un nutricionista certificado.")
    t1,t2=st.tabs(["Gasto Energetico","Distribucion de Macros"])
    with t1:
        peso=float(d.get("Peso",70)); talla=float(d.get("Talla",170)); edad=int(d.get("Edad",25)); sexo=d.get("Sexo","Masculino")
        tmb=calcular_tmb(peso,talla,edad,sexo); st.metric("TMB (Mifflin-St Jeor)",f"{tmb:.0f} kcal/dia")
        actividad=st.selectbox("Nivel de Actividad:",["Sedentario","Ligero (1-3 dias)","Moderado (3-5 dias)","Activo (6-7 dias)","Muy Activo (2x/dia)"])
        get=calcular_get(tmb,actividad); st.metric("GET (Gasto Total)",f"{get:.0f} kcal/dia")
        objetivo_nut=st.selectbox("Objetivo:",["Mantenimiento","Deficit (Perder Grasa)","Superavit (Ganar Masa)"])
        if objetivo_nut=="Deficit (Perder Grasa)":
            deficit=st.slider("Deficit:",200,700,400,step=50); meta=get-deficit; st.success(f"Meta: {meta:.0f} kcal/dia (deficit {deficit})")
        elif objetivo_nut=="Superavit (Ganar Masa)":
            superavit=st.slider("Superavit:",100,500,250,step=50); meta=get+superavit; st.success(f"Meta: {meta:.0f} kcal/dia (superavit {superavit})")
        else: meta=get; st.info(f"Meta: {meta:.0f} kcal/dia")
        st.session_state.db_clientes[c]["meta_calorica"]=meta
    with t2:
        meta_c=float(st.session_state.db_clientes[c].get("meta_calorica",2000)); peso_c=float(d.get("Peso",70))
        perfil_macro=st.selectbox("Perfil:",["Hipertrofia (Alta Proteina)","Fuerza (Balanceado)","Resistencia (Alta Carbohidrato)","Perdida de Grasa"])
        if perfil_macro=="Hipertrofia (Alta Proteina)": prot_g=peso_c*2.2; grasa_g=meta_c*0.25/9
        elif perfil_macro=="Resistencia (Alta Carbohidrato)": prot_g=peso_c*1.6; grasa_g=meta_c*0.20/9
        elif perfil_macro=="Perdida de Grasa": prot_g=peso_c*2.5; grasa_g=meta_c*0.30/9
        else: prot_g=peso_c*2.0; grasa_g=meta_c*0.25/9
        carb_g=max((meta_c-prot_g*4-grasa_g*9)/4,50)
        nm1,nm2,nm3=st.columns(3)
        nm1.metric("Proteinas",f"{prot_g:.0f}g",f"{prot_g*4:.0f} kcal")
        nm2.metric("Carbohidratos",f"{carb_g:.0f}g",f"{carb_g*4:.0f} kcal")
        nm3.metric("Grasas",f"{grasa_g:.0f}g",f"{grasa_g*9:.0f} kcal")
        st.caption(f"Total: {prot_g*4+carb_g*4+grasa_g*9:.0f} kcal | Meta: {meta_c:.0f} kcal")
        if st.button("Guardar Macros",type="primary"):
            st.session_state.db_clientes[c].update({"macros_prot":prot_g,"macros_carb":carb_g,"macros_grasa":grasa_g})
            guardar_datos_disco(); st.toast("Macros guardados")

# =====================================================
# 9. PROGRESO
# =====================================================
elif menu == "9. Progreso":
    if not st.session_state.cliente_activo: st.stop()
    c=st.session_state.cliente_activo
    df_all=pd.DataFrame([r for r in st.session_state.historial_global if r["Cliente"]==c])
    if df_all.empty: st.info("Sin datos. Registra sesiones primero."); st.stop()
    t1,t2,t3=st.tabs(["Fuerza","Cardio","Historial Completo"])
    with t1:
        df_f=df_all[df_all["Tipo"]=="Fuerza"] if "Tipo" in df_all.columns else df_all
        if not df_f.empty:
            ejs=df_f["Ejercicio"].unique().tolist(); ej_=st.selectbox("Ejercicio:",ejs)
            dej=df_f[df_f["Ejercicio"]==ej_].copy()
            if not dej.empty:
                st.line_chart(dej,x="Fecha",y="Carga")
                cs1,cs2,cs3=st.columns(3)
                cs1.metric("Carga Max",f"{dej['Carga'].max():.1f}kg"); cs2.metric("Promedio",f"{dej['Carga'].mean():.1f}kg"); cs3.metric("Sesiones",len(dej))
                estado,msg,clase=analizar_progreso_avanzado(dej)
                st.markdown(f'<div class="alert-box {clase}">{msg}</div>',unsafe_allow_html=True)
        else: st.info("Sin datos de fuerza.")
    with t2:
        df_c=df_all[df_all["Tipo"]=="Cardio"] if "Tipo" in df_all.columns else pd.DataFrame()
        if not df_c.empty:
            st.line_chart(df_c,x="Fecha",y="Carga"); cc1,cc2,cc3=st.columns(3)
            cc1.metric("Sesiones",len(df_c)); cc2.metric("Duracion Prom",f"{df_c['Carga'].mean():.0f} min"); cc3.metric("Duracion Max",f"{df_c['Carga'].max():.0f} min")
        else: st.info("Sin sesiones cardio.")
    with t3:
        cf1,cf2=st.columns(2)
        fi=cf1.date_input("Desde:",date.today()-timedelta(days=30)); ff=cf2.date_input("Hasta:",date.today())
        df_fil=df_all.copy()
        try:
            df_fil["Fecha_dt"]=pd.to_datetime(df_fil["Fecha"],format="%d/%m/%Y")
            df_fil=df_fil[(df_fil["Fecha_dt"]>=pd.Timestamp(fi))&(df_fil["Fecha_dt"]<=pd.Timestamp(ff))]
        except: pass
        bus=st.text_input("Buscar ejercicio:","")
        if bus and "Ejercicio" in df_fil.columns: df_fil=df_fil[df_fil["Ejercicio"].str.contains(bus,case=False,na=False)]
        cols_m=[col for col in ["Fecha","Ejercicio","Series","Reps","Carga","RPE","Tipo","Objetivo"] if col in df_fil.columns]
        st.dataframe(df_fil[cols_m].sort_values("Fecha",ascending=False),use_container_width=True,hide_index=True)
        st.caption(f"{len(df_fil)} registros")
        if OPENPYXL_OK:
            xlsx=generar_excel_historial(c,st.session_state.historial_global)
            if xlsx: st.download_button("Exportar Excel",data=xlsx,file_name=f"Historial_{c.replace(' ','_')}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with st.expander("Eliminar registros por fecha"):
            fb=st.date_input("Fecha:",date.today())
            regs_f=[h for h in st.session_state.historial_global if h["Cliente"]==c and h["Fecha"]==fecha_es(fb)]
            if regs_f:
                st.warning(f"{len(regs_f)} registros del {fecha_es(fb)}")
                if st.button("Confirmar eliminacion"):
                    st.session_state.historial_global=[h for h in st.session_state.historial_global if not(h["Cliente"]==c and h["Fecha"]==fecha_es(fb))]
                    guardar_datos_disco(); st.rerun()
            else: st.info("No hay registros en esa fecha.")

# =====================================================
# 10. GUIAS
# =====================================================
elif menu == "10. Guias":
    t1,t2,t3,t4,t5=st.tabs(["Fuerza (Badillo)","Planif. (Bompa)","Tempo & Pausa","RPE & Borg","Zonas Cardio"])
    with t1: st.table(TABLA_BADILLO)
    with t2: st.table(GUIAS_BOMPA)
    with t3: c1,c2=st.columns(2); c1.table(GUIA_TEMPO); c2.table(GUIA_DESCANSOS)
    with t4: c1,c2=st.columns(2); c1.table(ESCALA_RPE); c2.table(ESCALA_BORG)
    with t5: st.table(GUIA_ZONAS_CARDIO)

# =====================================================
# 11. NOTAS
# =====================================================
elif menu == "11. Notas":
    st.title("Notas Personales")
    notas=st.text_area("Tus apuntes (privado):",value=st.session_state.notas_personales,height=400)
    if st.button("Guardar",type="primary"):
        st.session_state.notas_personales=notas; ok=guardar_datos_disco(); st.toast("Guardado" if ok else "Error")

# =====================================================
# 12. VIDEOTECA
# =====================================================
elif menu == "12. Videoteca":
    st.title("Videoteca")
    st.dataframe(pd.DataFrame(list(st.session_state.biblioteca_videos.items()),columns=["Ejercicio","Enlace"]),use_container_width=True,hide_index=True)
    st.divider()
    ca,cd=st.columns(2)
    with ca:
        st.subheader("Agregar")
        ne_=st.text_input("Nombre:"); nl_=st.text_input("Enlace:")
        if st.button("Guardar",type="primary"):
            if ne_.strip(): st.session_state.biblioteca_videos[ne_.strip()]=nl_.strip(); guardar_datos_disco(); st.rerun()
    with cd:
        st.subheader("Eliminar")
        lista_=list(st.session_state.biblioteca_videos.keys())
        if lista_:
            eb=st.selectbox("Selecciona:",lista_)
            if st.button("Eliminar"): del st.session_state.biblioteca_videos[eb]; guardar_datos_disco(); time.sleep(0.5); st.rerun()
        else: st.info("Videoteca vacia.")

# =====================================================
# PANEL ADMIN
# =====================================================
elif menu == "Panel Admin":
    mostrar_panel_admin()
