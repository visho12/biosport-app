import math

def calc_1rm(p, r):
    return p * (1 + r / 30)

def calc_durnin(edad, sexo, s4):
    if s4 <= 0:
        raise ValueError("La suma de pliegues debe ser > 0")
    c, m = (1.1631, 0.0632) if sexo == "Masculino" else (1.1599, 0.0717)
    d = c - m * math.log10(s4)
    if d <= 0:
        raise ValueError("Densidad inválida — revisa los pliegues")
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
    if g <= row[0]: return "Grasa Esencial",         "#FF4B4B"
    if g <= row[1]: return "Graso Disminuido",        "#00C853"
    if g <= row[2]: return "Graso Adecuado",          "#00BFFF"
    if g <= row[3]: return "Graso Aumentado",         "#FFD700"
    return              "Grasa Muy Alta",              "#DC143C"

def calc_tmb(peso, talla, edad, sexo):
    base = 10*peso + 6.25*talla - 5*edad
    return base + 5 if sexo == "Masculino" else base - 161

def calc_get(tmb, act):
    f = {"Sedentario":1.2,"Ligero (1-3 días)":1.375,"Moderado (3-5 días)":1.55,
         "Activo (6-7 días)":1.725,"Muy Activo (2x/día)":1.9}
    return tmb * f.get(act, 1.55)
