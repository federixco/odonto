"""Compara identidades del lote sin guardar listados de pacientes en logs/JSON."""

import unicodedata


def nombre_normalizado(nombre):
    texto = unicodedata.normalize("NFKD", str(nombre or "").replace("^", " "))
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).casefold().split())


class IdentidadesLote:
    def __init__(self):
        self.referencia = {}
        self.conflictos = set()
        self.registros = 0
        self.no_legibles = 0
        self.sin_identificador = 0

    def agregar(self, datos):
        identidad = {
            "identificador": str(datos.get("identificador_paciente", "") or "").strip(),
            "nombre": nombre_normalizado(datos.get("nombre_paciente", "")),
            "nacimiento": datos.get("fecha_nacimiento", "") or "",
        }
        if not identidad["identificador"] and not identidad["nombre"]:
            self.no_legibles += 1
            return
        self.registros += 1
        if not identidad["identificador"]:
            self.sin_identificador += 1
        for campo, valor in identidad.items():
            if not valor:
                continue
            anterior = self.referencia.setdefault(campo, valor)
            if anterior != valor:
                self.conflictos.add(campo)

    def resumen(self):
        estado = "mezclado" if self.conflictos else (
            "no_verificable" if not self.registros else "parcial" if self.no_legibles or self.sin_identificador else "consistente"
        )
        return {
            "estado": estado, "registros_con_identidad": self.registros,
            "fuentes_no_verificables": self.no_legibles,
            "registros_sin_identificador": self.sin_identificador,
            "campos_incompatibles": sorted(self.conflictos),
        }


class EstudiosLote:
    """Distingue estudios clínicos; una serie distinta NO es otro estudio.

    El resumen guarda contadores, no una lista de identificadores clínicos.
    Diferencias requieren revisión humana, no una separación automática.
    """

    def __init__(self):
        self.uids = set()
        self.fechas = set()

    def agregar(self, uid, fecha):
        uid = str(uid or "").strip()
        if uid:
            self.uids.add(uid)
        if fecha:
            self.fechas.add(fecha)

    def resumen(self):
        return {
            "requiere_revision": len(self.uids) > 1 or len(self.fechas) > 1,
            "cantidad_estudios": len(self.uids),
            "cantidad_fechas": len(self.fechas),
        }
