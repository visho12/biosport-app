import pandas as pd

VIDEOS_BASE = {
    "Sentadilla Goblet":  "https://www.youtube.com/watch?v=MeIiIdhvXT4",
    "Sentadilla Libre":   "https://www.youtube.com/watch?v=1OoMs3MaXI4",
    "Flexiones":          "https://www.youtube.com/watch?v=e_K0yT3t3IM",
    "Jalón al Pecho": "https://raw.githubusercontent.com/hasaneyldrm/exercises-dataset/refs/heads/main/videos/0001-2gPfomN.gif",
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
    "Zona": [
        "Z1 - Recuperación", 
        "Z2 - Oxidación de Grasa", 
        "Z3 - Aeróbica", 
        "Z4 - Umbral Anaeróbico", 
        "Z5 - VO2 Máx"
    ],
    "% FCM": [
        "50 - 60%", 
        "60 - 70%", 
        "70 - 80%", 
        "80 - 90%", 
        "90 - 100%"
    ],
    "Beneficio Principal": [
        "Recuperación activa y calentamiento", 
        "Mayor % de uso de grasa como energía (Lipólisis)", 
        "Mejora la resistencia cardiovascular y capacidad pulmonar", 
        "Tolerancia al lactato (mejora umbral)", 
        "Desarrollo de potencia y velocidad máxima"
    ]
})
