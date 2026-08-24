from pydantic import BaseModel
from typing import Optional

# ==========================================
# 1. MODELOS DE USUARIO (LOS QUE INICIAN SESIÓN)
# ==========================================
class Usuario(BaseModel):
    id: str                 # El usuario de login (ej. "visho", "eduardo")
    nombre_completo: str
    es_admin: bool = False

class UsuarioLinkAtleta(Usuario):
    """
    Usuario especial de solo-escritura. 
    Se activa cuando un atleta entra por el link de WhatsApp.
    Solo tiene permiso para tocar la rutina de SU cliente.
    """
    cliente_id_permitido: str
    es_admin: bool = False


# ==========================================
# 2. MODELO DEL CLIENTE (EL ATLETA)
# ==========================================
class Cliente(BaseModel):
    id: str                 # Nombre del atleta (ej. "Luis Enrique")
    entrenador_id: str      # EL CAMPO CLAVE: Quién es el dueño de este atleta
    peso: float = 70.0
    talla: float = 170.0
    edad: int = 25
    sexo: str = "Masculino"
    
    # Datos de la Ficha (pueden estar vacíos al principio)
    telefono: Optional[str] = ""
    emergencia: Optional[str] = ""
    lesiones: Optional[str] = ""
    enfermedades: Optional[str] = ""
    experiencia: Optional[str] = "Principiante"
    objetivo_prin: Optional[str] = ""
    estilo_vida: Optional[str] = ""
    vam: Optional[float] = 0.0
    meta_calorica: Optional[float] = 2000.0


# ==========================================
# 3. MODELO DEL HISTORIAL (LA RUTINA)
# ==========================================
class RegistroSerie(BaseModel):
    cliente_id: str
    fecha: str              # Formato DD/MM/YYYY
    ejercicio: str
    series: int
    reps: int
    carga: float
    rpe: Optional[int] = 7
    tipo: str = "Fuerza"    # "Fuerza" o "Cardio"
    objetivo: str = ""
