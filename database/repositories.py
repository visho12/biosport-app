import json
import gspread
from typing import List, Optional
from domain.models import Cliente, RegistroSerie

# Importamos tu conexión actual a Google Sheets para no reinventar la rueda
from database.sheets_db import _gs_client, URL_SHEET

class BioSportRepository:
    """
    La Bóveda central. Administra la conexión con Google Sheets y
    garantiza que cada entrenador solo toque su propia pestaña (su propia base de datos).
    """
    def __init__(self):
        self.client = _gs_client()
        self.sheet = self.client.open_by_url(URL_SHEET)

    def _obtener_hoja(self, entrenador_id: str):
        """Busca la pestaña del entrenador. Si el entrenador es nuevo y no tiene, se la crea en blanco."""
        try:
            return self.sheet.worksheet(entrenador_id)
        except gspread.exceptions.WorksheetNotFound:
            ws = self.sheet.add_worksheet(title=entrenador_id, rows="100", cols="2")
            # Inicializamos su base de datos vacía pero estructurada
            ws.update_acell("A1", json.dumps({"clientes": {}, "historial": []}))
            return ws

    def leer_datos(self, entrenador_id: str) -> dict:
        """Lee y une los datos JSON de la columna A, exclusivamente del entrenador solicitado."""
        ws = self._obtener_hoja(entrenador_id)
        vals = ws.col_values(1)
        if vals:
            try:
                return json.loads("".join(vals))
            except json.JSONDecodeError:
                return {"clientes": {}, "historial": []}
        return {"clientes": {}, "historial": []}

    def guardar_datos(self, entrenador_id: str, datos: dict) -> bool:
        """Guarda los datos JSON en la columna A de forma segura, sin importar cuán largos sean."""
        try:
            ws = self._obtener_hoja(entrenador_id)
            json_str = json.dumps(datos, ensure_ascii=False)
            
            # Dividimos el texto en trozos de 40,000 caracteres (Google Sheets tiene un límite de 50k por celda)
            trozos = [json_str[i:i+40000] for i in range(0, len(json_str), 40000)]
            celdas = [[trozo] for trozo in trozos]
            
            ws.clear()
            ws.update("A1", celdas)
            return True
        except Exception as e:
            print(f"Error guardando en la BD: {e}")
            return False

class ClienteRepository:
    """
    Repositorio específico para manejar a los Atletas. 
    Usa la Bóveda central para asegurar que los datos no se crucen.
    """
    def __init__(self, db: BioSportRepository):
        self.db = db

    def listar_por_entrenador(self, entrenador_id: str) -> List[Cliente]:
        """Devuelve la lista de atletas convertidos a nuestro Modelo seguro."""
        datos = self.db.leer_datos(entrenador_id)
        clientes_raw = datos.get("clientes", {})
        
        lista = []
        for nombre, info in clientes_raw.items():
            info["id"] = nombre
            info["entrenador_id"] = entrenador_id
            lista.append(Cliente(**info))
        return lista

    def obtener(self, cliente_id: str, entrenador_id: str) -> Optional[Cliente]:
        """Busca un atleta específico. Falla intencionalmente si el atleta no es de este entrenador."""
        atletas = self.listar_por_entrenador(entrenador_id)
        for atleta in atletas:
            if atleta.id == cliente_id:
                return atleta
        return None

    def guardar(self, cliente: Cliente) -> bool:
        """Guarda o actualiza un atleta directamente en la hoja de SU entrenador."""
        datos = self.db.leer_datos(cliente.entrenador_id)
        
        if "clientes" not in datos:
            datos["clientes"] = {}
            
        # Convertimos el modelo a diccionario. Excluimos id y entrenador_id para no repetir datos en el JSON
        datos["clientes"][cliente.id] = cliente.dict(exclude={"id", "entrenador_id"})
        
        return self.db.guardar_datos(cliente.entrenador_id, datos)
