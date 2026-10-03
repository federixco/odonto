from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from apps.core.mixins import AdminRequeridoMixin
from apps.core.enums import EstadoCuenta, EstadoImportacion
from apps.pacientes.models import Paciente
from apps.usuarios.models import Odontologo
from .models import ImportacionEstudio, Estudio
from .services.cancelacion import limpiar_cancelada


class EstadoImportacionView(AdminRequeridoMixin, View):
    def get(self, request, importacion_id):
        lote = get_object_or_404(ImportacionEstudio, pk=importacion_id, iniciada_por=request.user)
        trabajo = (lote.datos_detectados or {}).get("_analisis", {})
        response = JsonResponse({"estado": lote.estado, "trabajo": trabajo.get("estado", ""),
            "fase": trabajo.get("fase", ""),
            "procesados": trabajo.get("procesados", 0), "total": lote.cantidad_archivos,
            "detalle_url": f"/estudios/importaciones/{lote.pk}/"})
        response["Cache-Control"] = "no-store"
        return response


class CancelarImportacionView(AdminRequeridoMixin, View):
    def post(self, request, importacion_id):
        lote = get_object_or_404(ImportacionEstudio, pk=importacion_id, iniciada_por=request.user)
        try:
            lote.cancelar()
        except ValidationError as error:
            return JsonResponse({"error": " ".join(error.messages)}, status=409)
        # La cancelación es inmediata; el worker limpia S3 fuera de la petición.
        return JsonResponse({"estado": lote.estado, "limpieza_pendiente": True}, status=202)


class SelectorView(AdminRequeridoMixin, View):
    tipo = "pacientes"

    def get(self, request):
        paciente = self.tipo == "pacientes"
        qs = Paciente.objects.all() if paciente else Odontologo.objects.select_related("usuario").filter(usuario__estado=EstadoCuenta.HABILITADA)
        estudio = None
        if not paciente and request.GET.get("estudio"):
            try:
                estudio_id = int(request.GET["estudio"])
                if not 0 < estudio_id < 2**63:
                    raise ValueError()
            except ValueError:
                return JsonResponse({"error": "Estudio inválido."}, status=400)
            estudio = get_object_or_404(Estudio, pk=estudio_id)
            qs = qs.exclude(pk__in=estudio.autorizaciones.filter(estado_acceso="VIGENTE").values("odontologo_id"))
        q = request.GET.get("q", "").strip()[:150]
        exacto = request.GET.get("dni")
        if paciente and exacto is not None:
            qs = qs.filter(dni=exacto[:50])
        elif q:
            for termino in q.split()[:8]:
                filtros = Q(nombre__icontains=termino) | Q(apellido__icontains=termino)
                filtros |= Q(dni__icontains=termino) if paciente else (Q(matricula__icontains=termino) | Q(usuario__email__icontains=termino))
                qs = qs.filter(filtros)
        seleccionado = request.GET.get("seleccionado", "")
        try:
            seleccionado = int(seleccionado)
        except (ValueError, TypeError):
            seleccionado = None
        base = Paciente.objects.all() if paciente else Odontologo.objects.select_related("usuario").filter(usuario__estado=EstadoCuenta.HABILITADA)
        def datos(item):
            return {"id": item.pk, "nombre": f"{item.apellido}, {item.nombre}",
                "detalle": f"DNI {item.dni}" if paciente else f"Matrícula {item.matricula} · {item.usuario.email or ''}",
                "dni": item.dni if paciente else ""}
        elegido = base.filter(pk=seleccionado).first() if seleccionado else None
        pagina = Paginator(qs.order_by("apellido", "nombre", "pk"), 20).get_page(request.GET.get("page", 1))
        response = JsonResponse({"resultados": [datos(item) for item in pagina], "pagina": pagina.number,
            "paginas": pagina.paginator.num_pages, "total": pagina.paginator.count,
            "anterior": pagina.has_previous(), "siguiente": pagina.has_next(),
            "seleccionado": datos(elegido) if elegido else None})
        response["Cache-Control"] = "no-store"
        return response
