from django.test import Client
from django.contrib.auth import get_user_model
from apps.usuarios.models import Odontologo
from apps.pacientes.models import Paciente
from apps.estudios.models import Estudio
from apps.accesos.models import Autorizacion
from apps.core.enums import EstadoEstudio, EstadoAcceso

User = get_user_model()

def run_test():
    print("--- INICIANDO TEST MANUAL ---")
    client = Client()
    
    # 1. Encontrar un odontólogo con usuario
    odontologos = Odontologo.objects.filter(usuario__isnull=False)
    if not odontologos.exists():
        print("No hay odontólogos con usuario para testear.")
        return
    odontologo = odontologos.first()
    user_odontologo = odontologo.usuario
    print(f"Test Odontólogo: {user_odontologo.email}")
    
    # 2. Login como odontólogo
    client.force_login(user_odontologo)
    
    # 3. Test Dashboard Odontólogo
    response = client.get('/usuarios/mi-consultorio/')
    print(f"Dashboard Odontólogo Status: {response.status_code}")
    if response.status_code == 200:
        estudios_en_contexto = response.context.get('estudios')
        print(f"Estudios en dashboard: {len(estudios_en_contexto) if estudios_en_contexto else 0}")
    
    # 4. Asignar un estudio al odontólogo para probar la vista (si hay alguno publicado)
    estudio = Estudio.objects.filter(estado=EstadoEstudio.PUBLICADO).first()
    if not estudio:
        print("No hay estudios publicados en la DB para probar.")
        return
        
    Autorizacion.objects.get_or_create(
        estudio=estudio,
        odontologo=odontologo,
        defaults={'estado_acceso': EstadoAcceso.VIGENTE, 'autorizado_por': User.objects.first()}
    )
    
    # 5. Test Ver Estudio
    response = client.get(f'/estudios/{estudio.pk}/ver/')
    print(f"Ver Estudio ({estudio.pk}) Status: {response.status_code}")
    if response.status_code == 200:
        print("¡El visor de archivos cargó correctamente!")
        tree = response.context.get('tree')
        if tree:
            print(f"Árbol cargado: {tree.get('nombre')}, Archivos: {tree.get('total_archivos_recursivo')}")
        else:
            print("El estudio no tiene archivos o el árbol es None.")
            
    print("--- TEST FINALIZADO ---")

run_test()
