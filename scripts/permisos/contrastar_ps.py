import sys
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {"m": "http://soap.sforce.com/2006/04/metadata"}
RAIZ = Path(__file__).resolve().parents[2] / "force-app/main/default/permissionsets"
ROLES = {
    "Integracion": "Conciliacion_Integracion",
    "Analista": "Conciliacion_Analista",
    "Responsable": "Conciliacion_Responsable",
    "Auditor": "Conciliacion_Auditor",
}
TABS = ["Factura__c", "Cobro__c", "AplicacionCobro__c", "Ajuste__c", "Incidencia__c"]
APP = "Conciliacin_de_cobros"
LECTURA = ["Factura__c", "Cobro__c", "Liquidacion__c", "CargaFichero__c", "AvisoPasarela__c"]

# Permisos que el PS concede y que ninguna historia justifica todavía: decisión pendiente, no norma
PENDIENTE = {"Integracion": {"editar": {"Cobro__c", "Liquidacion__c"}}}

# Esperado según doc 06, sección 5 (y tabla de doc 07)
ESPERADO = {
    "Integracion": {
        "app": False, "tabs": False,
        "leer": {"Factura__c", "Cobro__c", "Liquidacion__c", "CargaFichero__c", "AvisoPasarela__c"},
        "crear": {"Factura__c", "CargaFichero__c", "AvisoPasarela__c", "Cobro__c", "Liquidacion__c"},
        "editar": {"Factura__c"},
        "custom": False,
    },
    "Analista": {
        "app": True, "tabs": True,
        "leer": {"Factura__c", "Cobro__c", "Liquidacion__c"},
        "crear": {"Ajuste__c", "AplicacionCobro__c"},
        "editar": {"Incidencia__c"},
        "custom": False,
    },
    "Responsable": {
        "app": True, "tabs": True,
        "leer": {"Factura__c", "Cobro__c", "Liquidacion__c", "CargaFichero__c", "AvisoPasarela__c"},
        "crear": {"Ajuste__c", "AplicacionCobro__c"},
        "editar": {"Incidencia__c"},
        "custom": True,
    },
    "Auditor": {
        "app": True, "tabs": True,
        "leer": {"Factura__c", "Cobro__c", "Liquidacion__c", "CargaFichero__c", "AvisoPasarela__c"},
        "crear": set(),
        "editar": set(),
        "custom": False,
    },
}


def leer_ps(nombre):
    r = ET.parse(RAIZ / f"{nombre}.permissionset-meta.xml").getroot()
    obj = {}
    for o in r.findall("m:objectPermissions", NS):
        nombre_obj = o.findtext("m:object", namespaces=NS)
        obj[nombre_obj] = {
            "leer": o.findtext("m:allowRead", namespaces=NS) == "true",
            "crear": o.findtext("m:allowCreate", namespaces=NS) == "true",
            "editar": o.findtext("m:allowEdit", namespaces=NS) == "true",
        }
    tabs = {t.findtext("m:tab", namespaces=NS): t.findtext("m:visibility", namespaces=NS) == "Visible"
            for t in r.findall("m:tabSettings", NS)}
    apps = {a.findtext("m:application", namespaces=NS): a.findtext("m:visible", namespaces=NS) == "true"
            for a in r.findall("m:applicationVisibilities", NS)}
    custom = {c.findtext("m:name", namespaces=NS): c.findtext("m:enabled", namespaces=NS) == "true"
              for c in r.findall("m:customPermissions", NS)}
    return obj, tabs, apps, custom


def comprobar(rol, nombre_ps):
    esp = ESPERADO[rol]
    obj, tabs, apps, custom = leer_ps(nombre_ps)
    resultados = []

    def anotar(etiqueta, esperado, real, pendiente=False):
        if esperado == real:
            estado = "PASA"
        elif pendiente and real and not esperado:
            estado = "PENDIENTE"
        else:
            estado = "FALLA"
        resultados.append((etiqueta, esperado, real, estado))

    anotar("App Conciliación de cobros", esp["app"], apps.get(APP, False))
    for t in TABS:
        anotar(f"Pestaña {t}", esp["tabs"], tabs.get(t, False))
    for o in LECTURA:
        anotar(f"Leer {o}", o in esp["leer"], obj.get(o, {}).get("leer", False))
    for o in sorted(set(LECTURA) | {"Incidencia__c", "Ajuste__c", "AplicacionCobro__c", "Liquidacion__c"}):
        anotar(f"Crear {o}", o in esp["crear"], obj.get(o, {}).get("crear", False))
        pend = o in PENDIENTE.get(rol, {}).get("editar", set())
        anotar(f"Editar {o}", o in esp["editar"], obj.get(o, {}).get("editar", False), pend)
    anotar("Custom Conciliacion_CerrarEscaladas", esp["custom"], custom.get("Conciliacion_CerrarEscaladas", False))
    return resultados


def main():
    fallos = 0
    for rol, ps in ROLES.items():
        filas = comprobar(rol, ps)
        malas = [f for f in filas if f[3] == "FALLA"]
        pendientes = [f for f in filas if f[3] == "PENDIENTE"]
        fallos += len(malas)
        print(f"== {rol} ({ps}): {len(filas) - len(malas) - len(pendientes)}/{len(filas)} PASA")
        for etiqueta, esperado, real, estado in malas + pendientes:
            print(f"   {estado:<10} {etiqueta}: esperado={'Sí' if esperado else 'No'}, PS={'Sí' if real else 'No'}")
    print(f"\nTotal FALLA: {fallos}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
