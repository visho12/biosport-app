import io
import pandas as pd
import streamlit as st
from datetime import date

# --- IA (Dante) ---
import google.generativeai as genai
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    _mv = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
    modelo_dante = genai.GenerativeModel(_mv[0]) if _mv else None
except Exception:
    modelo_dante = None

# --- PDF PREMIUM ---
try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

# --- EXCEL ---
try:
    import openpyxl
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False


def pdf_plan(cliente, focos, detalles, dias):
    if not REPORTLAB_OK: return None
    
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    
    elementos = []
    estilos = getSampleStyleSheet()
    
    estilo_titulo = ParagraphStyle(
        'TituloPrincipal', parent=estilos['Heading1'], fontSize=22,
        textColor=colors.HexColor("#1E1E1E"), alignment=1, spaceAfter=5
    )
    estilo_sub = ParagraphStyle(
        'Subtitulo', parent=estilos['Normal'], fontSize=12,
        textColor=colors.HexColor("#666666"), alignment=1, spaceAfter=20
    )
    estilo_texto = ParagraphStyle(
        'TextoNormal', parent=estilos['Normal'], fontSize=10,
        textColor=colors.HexColor("#333333"), leading=14
    )

    elementos.append(Paragraph("<b>PLAN DE ENTRENAMIENTO PROFESIONAL</b>", estilo_titulo))
    elementos.append(Paragraph(f"Atleta: <b>{cliente}</b> &nbsp; | &nbsp; Fecha: {date.today().strftime('%d/%m/%Y')}", estilo_sub))
    elementos.append(Spacer(1, 0.2 * inch))
    
    ts = focos.get("tipo_semana", "")
    if ts:
        elementos.append(Paragraph(f"<b>Microciclo actual:</b> {ts}", estilo_texto))
        elementos.append(Spacer(1, 0.1 * inch))

    for dia in dias:
        foco = focos.get(dia, "Descanso")
        det = detalles.get(dia, "")
        
        if foco == "Descanso": continue
            
        datos_cabecera = [[f"{dia.upper()} — {foco.upper()}"]]
        tabla_cabecera = Table(datos_cabecera, colWidths=[doc.width])
        tabla_cabecera.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#1E1E1E")),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor("#39FF14")),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
        elementos.append(tabla_cabecera)
        elementos.append(Spacer(1, 0.05 * inch))
        
        if det:
            parts = det.split("||")
            labels = ["Calentamiento", "Bloque Principal", "Vuelta a la Calma"]
            datos_ejercicios = []
            
            if len(parts) == 3:
                for i, blk in enumerate(parts):
                    if not blk.strip(): continue
                    lineas = "<br/>".join([f"• {l.strip()}" for l in blk.split("\n") if l.strip()])
                    bloque_texto = Paragraph(lineas, estilo_texto)
                    datos_ejercicios.append([f"{labels[i]}:", bloque_texto])
            else:
                lineas = "<br/>".join([f"• {l.strip()}" for l in det.split("\n") if l.strip()])
                bloque_texto = Paragraph(lineas, estilo_texto)
                datos_ejercicios.append(["Ejercicios:", bloque_texto])
            
            if datos_ejercicios:
                tabla_ejercicios = Table(datos_ejercicios, colWidths=[doc.width * 0.25, doc.width * 0.75])
                tabla_ejercicios.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor("#444444")),
                    ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor("#EEEEEE")),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ]))
                elementos.append(tabla_ejercicios)
        else:
            elementos.append(Paragraph("<i>(Sin ejercicios detallados)</i>", estilo_texto))
            
        elementos.append(Spacer(1, 0.2 * inch))

    doc.build(elementos)
    buf.seek(0)
    return buf


def excel_historial(cliente, historial_global):
    if not OPENPYXL_OK: return None
    regs = [r for r in historial_global if r["Cliente"]==cliente]
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
