"""Árbol acotado a una página: no materializar toda una tomografía en HTML."""

from django.core.paginator import Paginator


def contexto_archivos(archivos, numero_pagina):
    pagina = Paginator(archivos, 100).get_page(numero_pagina)
    tree = {"nombre": "Raíz", "archivos": [], "subcarpetas": {}, "tamano_total": 0, "total_archivos_recursivo": 0}
    for archivo in pagina.object_list:
        partes = archivo.ruta_relativa.split("/") if archivo.ruta_relativa else []
        carpetas = partes[:-1] if partes and partes[-1] == archivo.nombre_archivo else partes
        actual = tree
        for parte in [None, *carpetas]:
            if parte is not None:
                actual = actual["subcarpetas"].setdefault(parte, {
                    "nombre": parte, "archivos": [], "subcarpetas": {},
                    "tamano_total": 0, "total_archivos_recursivo": 0,
                })
            actual["tamano_total"] += archivo.tamano
            actual["total_archivos_recursivo"] += 1
        actual["archivos"].append(archivo)
    while not tree["archivos"] and len(tree["subcarpetas"]) == 1:
        tree = next(iter(tree["subcarpetas"].values()))
    return {
        "archivos_pagina": pagina, "total_archivos": pagina.paginator.count,
        "tree": tree if pagina.paginator.count else None,
    }
