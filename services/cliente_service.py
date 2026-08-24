from domain.models import Usuario, UsuarioLinkAtleta, Cliente
from database.repositories import ClienteRepository

class PermisoDenegadoError(Exception):
    """Excepción de seguridad: Se lanza cuando alguien intenta espiar o modificar datos ajenos."""
    pass

class ClienteService:
    """
    El Cerebro (Servicio) para los Atletas.
    Su única misión es aplicar las reglas de seguridad ANTES de hablar con la Base de Datos.
    """
    def __init__(self, repo: ClienteRepository):
        self.repo = repo

    def mis_atletas(self, usuario_actual: Usuario) -> list[Cliente]:
        """
        Devuelve la lista de atletas, filtrando estrictamente por el entrenador que pregunta.
        """
        # 1. Si es un atleta entrando por su link, no tiene una "lista de alumnos", 
        # así que por seguridad le devolvemos solo a sí mismo (si es que existe).
        if isinstance(usuario_actual, UsuarioLinkAtleta):
            atleta_unico = self.obtener_atleta(usuario_actual.cliente_id_permitido, usuario_actual)
            return [atleta_unico] if atleta_unico else []
            
        # 2. Si es un entrenador real (normal), le pedimos a la Bóveda SOLO su pestaña
        return self.repo.listar_por_entrenador(usuario_actual.id)

    def obtener_atleta(self, cliente_id: str, usuario_actual: Usuario) -> Cliente:
        """
        Busca un atleta específico, blindando la seguridad.
        """
        # REGLA 1: Si entró por link, verificar que el nombre que busca sea el suyo.
        # Si el atleta "Luis" altera el link para poner "?atleta=Pedro", el sistema explota aquí.
        if isinstance(usuario_actual, UsuarioLinkAtleta):
            if cliente_id.lower() != usuario_actual.cliente_id_permitido.lower():
                raise PermisoDenegadoError(f"Bloqueo de seguridad: No tienes permiso para ver la rutina de '{cliente_id}'.")
                
        # REGLA 2: Vamos a la bóveda a buscar al atleta. 
        # La bóveda requiere el id del entrenador para saber en qué pestaña buscar.
        cliente = self.repo.obtener(cliente_id, usuario_actual.id)
        
        if not cliente:
            raise PermisoDenegadoError(f"El atleta '{cliente_id}' no existe o no pertenece al entrenador '{usuario_actual.id}'.")
            
        return cliente

    def guardar_atleta(self, cliente: Cliente, usuario_actual: Usuario) -> bool:
        """
        Guarda los datos personales de un atleta (Ficha, Antropometría, etc).
        """
        # REGLA 3: Los atletas no pueden editar sus propias fichas desde el link de WhatsApp.
        if isinstance(usuario_actual, UsuarioLinkAtleta):
            raise PermisoDenegadoError("Por seguridad, los atletas no pueden modificar sus propias fichas directamente.")
            
        # REGLA 4: Un entrenador no puede guardar a un atleta a nombre de otro profesor.
        if cliente.entrenador_id != usuario_actual.id:
            raise PermisoDenegadoError("No puedes guardar un atleta en la base de datos de otro entrenador.")
            
        return self.repo.guardar(cliente)
