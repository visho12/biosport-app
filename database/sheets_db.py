import json
import gspread
import streamlit as st
from google.oauth2.service_account import Credentials
from datetime import date, datetime
from core.constants import VIDEOS_BASE

URL_SHEET = "https://docs.google.com/spreadsheets/d/1NxZNe_1GjunjcpJs91tHJIAnZievTsNuVTTFe6uMqik/edit#gid=0"

def _gs_client():
    sc = ["https://www.googleapis.com/auth/spreadsheets"]
    cr = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=sc)
    return gspread.authorize(cr)

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
    except gspread.exceptions.APIError as e:
        st.sidebar.warning(f"⚠️ Sheets API: {e}")
    except json.JSONDecodeError:
        st.sidebar.error("⚠️ Datos corruptos. Contacta al administrador.")
    except Exception as e:
        st.sidebar.warning(f"⚠️ Error al cargar: {e}")

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

        # Backup diario
        try:
            nb = f"BK_{usuario}_{date.today()}"
            try:
                sheet.worksheet(nb)
            except gspread.exceptions.WorksheetNotFound:
                bws    = sheet.add_worksheet(title=nb, rows="200", cols="20")
                bchunk = [js[i:i+40000] for i in range(0, len(js), 40000)]
                bcells = bws.range(1, 1, len(bchunk), 1)
                for i, cell in enumerate(bcells):
                    cell.value = bchunk[i]
                bws.update_cells(bcells)
        except Exception:
            pass

        return True
    except gspread.exceptions.APIError as e:
        st.sidebar.error(f"⚠️ Sheets: {e}")
    except Exception as e:
        st.sidebar.error(f"⚠️ Error al guardar: {e}")
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
