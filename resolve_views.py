import re

with open('apps/estudios/views.py', 'r', encoding='utf-8') as f:
    text = f.read()

tree_logic = '''
        # --- Construcción del árbol (agregado) ---
        archivos_list = list(archivos)
        contexto["total_archivos"] = len(archivos_list)
        if not archivos_list:
            contexto["tree"] = None
        else:
            tree = {"nombre": "Raíz", "archivos": [], "subcarpetas": {}, "tamano_total": 0, "total_archivos_recursivo": 0}
            for archivo in archivos_list:
                partes = archivo.ruta_relativa.split("/") if archivo.ruta_relativa else []
                if partes and partes[-1] == archivo.nombre_archivo:
                    partes_carpeta = partes[:-1]
                else:
                    partes_carpeta = partes

                current = tree
                current["tamano_total"] += archivo.tamano
                current["total_archivos_recursivo"] += 1
                
                for parte in partes_carpeta:
                    if parte not in current["subcarpetas"]:
                        current["subcarpetas"][parte] = {
                            "nombre": parte, 
                            "archivos": [], 
                            "subcarpetas": {}, 
                            "tamano_total": 0,
                            "total_archivos_recursivo": 0
                        }
                    current = current["subcarpetas"][parte]
                    current["tamano_total"] += archivo.tamano
                    current["total_archivos_recursivo"] += 1
                    
                current["archivos"].append(archivo)

            while not tree["archivos"] and len(tree["subcarpetas"]) == 1:
                unica_llave = list(tree["subcarpetas"].keys())[0]
                tree = tree["subcarpetas"][unica_llave]

            contexto["tree"] = tree
        return contexto
'''

text = text.replace('        return contexto\n\n\nclass AgregarAccesoEstudioView', tree_logic + '\n\nclass AgregarAccesoEstudioView')

with open('apps/estudios/views.py', 'w', encoding='utf-8') as f:
    f.write(text)
