"""Pruebas sin nube: logica de permisos, ejecutor, Lambda y proveedores con clientes falsos."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import lambda_function  # noqa: E402
from agente_carpetas.agente import AgenteCarpetas, Sesion  # noqa: E402
from agente_carpetas.ejecutor import ProveedorSimulado, ejecutar_plan  # noqa: E402
from agente_carpetas.estructura import (  # noqa: E402
    ErrorPlantilla,
    Principal,
    cargar_plantilla,
    construir_plan,
    resolver_asignaciones,
    validar_plantilla,
)
from agente_carpetas.proveedores.microsoft_365 import ProveedorMicrosoft365  # noqa: E402

DOMINIO = "constructora.com"


@pytest.fixture(scope="module")
def plantilla():
    return cargar_plantilla()


def plan_por_convencion(plantilla, codigo="OBR-2026-014", nombre="Edificio Mirador"):
    asign = resolver_asignaciones(plantilla, codigo, None, DOMINIO)
    return construir_plan(plantilla, codigo, nombre, asign)


# --- Plantilla / planificador ----------------------------------------------
def test_raiz_y_convencion_de_grupos(plantilla):
    asign = resolver_asignaciones(plantilla, "OBR-2026-014", None, DOMINIO)
    assert asign["ING"][0].email == "proy-obr-2026-014-ing@constructora.com"
    plan = construir_plan(plantilla, "obr-2026-014", "Edificio  Mirador/Norte", asign)
    assert plan.raiz == "OBR-2026-014_Edificio_MiradorNorte"


def test_director_tiene_gestion_en_todas_las_carpetas(plantilla):
    plan = plan_por_convencion(plantilla)
    assert all(permisos.get("DIR") == "gestion" for permisos in plan.matriz.values())


def test_herencia_suma_y_toma_nivel_mas_alto(plantilla):
    m = plan_por_convencion(plantilla).matriz
    base = "OBR-2026-014_Edificio_Mirador/04_Planos"
    assert m[base]["ARQ"] == "lectura"
    assert m[f"{base}/01_En_Revision"]["ARQ"] == "edicion"
    assert "CON" not in m[f"{base}/01_En_Revision"]
    assert m[f"{base}/02_Aprobados_Para_Construccion"]["CON"] == "lectura"


def test_carpeta_sensible_no_hereda(plantilla):
    plan = plan_por_convencion(plantilla)
    ruta = "OBR-2026-014_Edificio_Mirador/07_Seguridad_SSOMA/02_Incidentes_Accidentes"
    assert plan.matriz[ruta] == {"DIR": "gestion", "SSO": "edicion", "LEG": "lectura"}
    tipos = [op.tipo for op in plan.operaciones if op.ruta == ruta]
    assert "restringir_herencia" in tipos


def test_finanzas_no_visible_para_externos(plantilla):
    m = plan_por_convencion(plantilla).matriz
    for ruta, permisos in m.items():
        if "/02_Finanzas_Costos" in ruta:
            assert not {"CON", "CLI", "ARQ"} & set(permisos), ruta


def test_solo_se_concede_el_delta_en_carpetas_que_heredan(plantilla):
    plan = plan_por_convencion(plantilla)
    ruta = "OBR-2026-014_Edificio_Mirador/03_Diseno_Ingenieria/01_Arquitectura"
    assert not [op for op in plan.operaciones if op.tipo == "conceder" and op.ruta == ruta]


@pytest.mark.parametrize("codigo", ["", "A", "con espacios", "X" * 30])
def test_codigo_invalido(plantilla, codigo):
    with pytest.raises(ErrorPlantilla):
        construir_plan(plantilla, codigo, "Proyecto", {})


def test_plantilla_con_rol_desconocido_es_rechazada():
    with pytest.raises(ErrorPlantilla):
        validar_plantilla({"roles": {"DIR": {}}, "carpetas": [{"nombre": "A", "permisos": {"XXX": "lectura"}}]})


def test_asignaciones_explicitas_y_usuarios(plantilla):
    asign = resolver_asignaciones(plantilla, "P-01", {"CLI": "usuario:Ana@Cliente.cl"}, None)
    assert asign["CLI"] == [Principal("ana@cliente.cl", "user")]
    assert asign["ING"] == []
    with pytest.raises(ErrorPlantilla):
        resolver_asignaciones(plantilla, "P-01", {"CLI": "no-es-correo"}, None)


# --- Ejecutor ---------------------------------------------------------------
def test_ejecucion_simulada_respeta_matriz_e_idempotencia(plantilla):
    plan = plan_por_convencion(plantilla)
    prov = ProveedorSimulado()
    r1 = ejecutar_plan(plan, prov)
    assert r1["completado"] and r1["carpetas_creadas"] == len(plan.matriz) - 1

    # El ACL efectivo calculado por el "almacenamiento" coincide con la matriz del plan.
    por_ruta = {}
    for cid, c in prov.carpetas.items():
        partes, actual = [], cid
        while actual:
            partes.insert(0, prov.carpetas[actual]["nombre"])
            actual = prov.carpetas[actual]["padre"]
        por_ruta["/".join(partes)] = prov.acceso_efectivo(cid)
    for ruta, permisos in plan.matriz.items():
        esperado = {f"proy-obr-2026-014-{rol.lower()}@{DOMINIO}": nivel for rol, nivel in permisos.items()}
        assert por_ruta[ruta] == esperado, ruta

    r2 = ejecutar_plan(plan, prov)
    assert r2["carpetas_creadas"] == 0 and r2["carpetas_existentes"] == len(plan.matriz) - 1


# --- Lambda (contrato Bedrock Agents) ---------------------------------------
def evento(funcion, **params):
    return {
        "messageVersion": "1.0",
        "actionGroup": "GestionCarpetas",
        "function": funcion,
        "parameters": [{"name": k, "type": "string", "value": v} for k, v in params.items()],
        "sessionAttributes": {"usuario": "pm"},
        "promptSessionAttributes": {},
    }


def cuerpo(resp):
    return json.loads(resp["response"]["functionResponse"]["responseBody"]["TEXT"]["body"])


def test_lambda_listar():
    resp = lambda_function.lambda_handler(evento("listar_roles_y_plantilla"))
    assert resp["messageVersion"] == "1.0"
    assert resp["response"]["function"] == "listar_roles_y_plantilla"
    assert resp["sessionAttributes"] == {"usuario": "pm"}
    assert "DIR" in cuerpo(resp)["roles"]


def test_lambda_previsualizar_advierte_roles_sin_grupo():
    resp = lambda_function.lambda_handler(
        evento("previsualizar_estructura", codigo_proyecto="OBR-1", nombre_proyecto="Puente",
               asignaciones_json='{"DIR": ["pm@x.com"]}')
    )
    datos = cuerpo(resp)
    assert "ING" in datos["roles_sin_asignar"]
    assert "07_Seguridad_SSOMA/" in datos["arbol"]


def test_lambda_crear_en_simulacion():
    resp = lambda_function.lambda_handler(
        evento("crear_estructura", plataforma="simulacion", codigo_proyecto="OBR-2",
               nombre_proyecto="Hospital", dominio=DOMINIO)
    )
    datos = cuerpo(resp)
    assert datos["completado"] is True and datos["plataforma"] == "simulacion"


def test_lambda_errores_de_entrada_piden_reprompt():
    resp = lambda_function.lambda_handler(
        evento("crear_estructura", plataforma="dropbox", codigo_proyecto="OBR-2", nombre_proyecto="X")
    )
    assert resp["response"]["functionResponse"]["responseState"] == "REPROMPT"
    resp = lambda_function.lambda_handler(
        evento("previsualizar_estructura", codigo_proyecto="OBR-2", nombre_proyecto="X", asignaciones_json="{malo")
    )
    assert resp["response"]["functionResponse"]["responseState"] == "REPROMPT"


def test_lambda_funcion_desconocida():
    resp = lambda_function.lambda_handler(evento("borrar_todo"))
    assert resp["response"]["functionResponse"]["responseState"] == "FAILURE"


# --- Proveedor Microsoft con HTTP falso -------------------------------------
class GraphFalso:
    def __init__(self):
        self.llamadas = []
        self.items = {}

    def __call__(self, metodo, url, cab, body):
        self.llamadas.append((metodo, url, body))
        if metodo == "GET" and ":/" in url.split("/items/", 1)[-1]:
            return 404, {"error": {"code": "itemNotFound"}}
        if metodo == "POST" and url.endswith("/children"):
            nuevo = f"id{len(self.items)}"
            self.items[nuevo] = body["name"]
            return 201, {"id": nuevo}
        if "sharepointIds" in url:
            return 200, {"sharepointIds": {"listId": "L1", "listItemId": "7"}}
        return 200, {}


def test_microsoft_flujo_de_llamadas():
    http = GraphFalso()
    prov = ProveedorMicrosoft365(
        {"drive_id": "D1", "sitio_url": "https://empresa.sharepoint.com/sites/Proyectos/"},
        http=http, obtener_token=lambda recurso: f"token-{recurso}",
    )
    raiz = prov.obtener_o_crear_raiz("OBR-1_Puente")
    prov.restringir_herencia(raiz)
    prov.conceder(raiz, Principal("pm@empresa.com"), "gestion")

    urls = [u for _, u, _ in http.llamadas]
    assert any("/drives/D1/items/root/children" in u for u in urls)
    assert any("lists(guid'L1')/items(7)/breakroleinheritance(copyRoleAssignments=false" in u for u in urls)
    invite = [b for m, u, b in http.llamadas if u.endswith("/invite")][0]
    assert invite["roles"] == ["write"] and invite["sendInvitation"] is False


# --- Bucle agentico con un modelo falso (sin red, sin costo) -----------------
from types import SimpleNamespace as NS  # noqa: E402


class ModeloFalso:
    """Devuelve respuestas guionadas, como si fuera Claude, y registra lo recibido."""

    def __init__(self, guion):
        self.guion = list(guion)
        self.recibido = []
        self.messages = self

    def create(self, **kwargs):
        self.recibido.append({**kwargs, "messages": list(kwargs["messages"])})  # copia en el instante
        return self.guion.pop(0)


def texto(t):
    return NS(content=[NS(type="text", text=t)], stop_reason="end_turn")


def herramienta(id_, nombre, entrada, t=""):
    bloques = [NS(type="text", text=t)] if t else []
    return NS(content=bloques + [NS(type="tool_use", id=id_, name=nombre, input=entrada)], stop_reason="tool_use")


PARAMS = {"codigo_proyecto": "HOS-2026-03", "nombre_proyecto": "Hospital Norte",
          "dominio": DOMINIO, "asignaciones_json": ""}


def test_agente_previsualiza_pide_confirmacion_y_crea(monkeypatch):
    monkeypatch.setenv("MODO_SIMULACION", "true")
    modelo = ModeloFalso([
        herramienta("t1", "previsualizar_estructura", PARAMS),
        texto("Esta es la vista previa. ¿La apruebas?"),
        herramienta("t2", "crear_estructura", {"plataforma": "microsoft", **PARAMS}),
        texto("Listo: 52 carpetas creadas."),
    ])
    agente, sesion = AgenteCarpetas(modelo), Sesion()

    r1 = agente.turno(sesion, texto="Crea el proyecto Hospital Norte")
    assert r1["herramientas"] == ["previsualizar_estructura"] and r1["pendiente"] is None
    resultado_preview = modelo.recibido[1]["messages"][-1]["content"][0]
    assert resultado_preview["tool_use_id"] == "t1" and "07_Seguridad_SSOMA" in resultado_preview["content"]

    r2 = agente.turno(sesion, texto="Aprobado")
    assert r2["pendiente"] == {"herramienta": "crear_estructura", "parametros": {"plataforma": "microsoft", **PARAMS}}
    assert len(modelo.recibido) == 3  # se detuvo: NO llamo de nuevo al modelo ni ejecuto

    r3 = agente.turno(sesion, confirmacion=True)
    assert r3["herramientas"] == ["crear_estructura"] and "52 carpetas" in r3["respuesta"]
    resultado = json.loads(modelo.recibido[3]["messages"][-1]["content"][0]["content"])
    assert resultado["completado"] is True and resultado["plataforma"] == "simulacion"


def test_agente_respeta_el_rechazo_humano():
    modelo = ModeloFalso([
        herramienta("t1", "crear_estructura", {"plataforma": "google", **PARAMS}),
        texto("Entendido, no cree nada."),
    ])
    agente, sesion = AgenteCarpetas(modelo), Sesion()
    assert agente.turno(sesion, texto="crea todo ya")["pendiente"]
    # Sin respuesta explicita no se avanza
    assert agente.turno(sesion, texto="mmm")["pendiente"]
    r = agente.turno(sesion, confirmacion=False)
    assert r["herramientas"] == []
    ultimo = modelo.recibido[-1]["messages"][-1]["content"][0]
    assert ultimo["is_error"] is True and "NO autorizo" in ultimo["content"]


def test_agente_devuelve_errores_de_datos_al_modelo():
    modelo = ModeloFalso([
        herramienta("t1", "previsualizar_estructura", {**PARAMS, "codigo_proyecto": "codigo invalido"}),
        texto("El codigo no es valido, ¿cual es el correcto?"),
    ])
    r = AgenteCarpetas(modelo).turno(Sesion(), texto="Proyecto nuevo")
    ultimo = modelo.recibido[1]["messages"][-1]["content"][0]
    assert ultimo["is_error"] is True and "codigo de proyecto" in ultimo["content"]
    assert "no es valido" in r["respuesta"]


# --- Proveedor Google con cliente Drive falso --------------------------------
from agente_carpetas.proveedores.google_drive import ProveedorGoogleDrive  # noqa: E402


class DriveFalso:
    """Imita la interfaz encadenada de googleapiclient: drive.files().create(...).execute()."""

    def __init__(self):
        self.llamadas = []

    def _recurso(self, nombre):
        drive = self

        class Recurso:
            def __getattr__(self, metodo):
                def llamar(**kw):
                    drive.llamadas.append((nombre, metodo, kw))
                    resultados = {
                        ("drives", "list"): {"drives": []},
                        ("drives", "create"): {"id": "UNIDAD1"},
                        ("files", "list"): {"files": []},
                        ("files", "create"): {"id": f"C{len(drive.llamadas)}"},
                    }
                    return NS(execute=lambda: resultados.get((nombre, metodo), {}))
                return llamar
        return Recurso()

    def drives(self):
        return self._recurso("drives")

    def files(self):
        return self._recurso("files")

    def permissions(self):
        return self._recurso("permissions")


def test_google_flujo_de_llamadas():
    drive = DriveFalso()
    prov = ProveedorGoogleDrive({}, servicio=drive)
    raiz = prov.obtener_o_crear_raiz("OBR-1_Puente")
    prov.restringir_herencia(raiz)  # la unidad compartida no necesita corte
    prov.conceder(raiz, Principal("pm@x.com"), "gestion")
    carpeta, creada = prov.obtener_o_crear_carpeta("02_Incidentes", raiz)
    prov.restringir_herencia(carpeta)
    prov.conceder(carpeta, Principal("ana@x.com", "user"), "lectura")

    assert raiz == "UNIDAD1" and creada
    permisos = [kw for r, m, kw in drive.llamadas if r == "permissions"]
    assert permisos[0]["body"]["role"] == "organizer"
    assert permisos[1]["body"] == {"type": "user", "role": "reader", "emailAddress": "ana@x.com"}
    assert all(kw["sendNotificationEmail"] is False and kw["supportsAllDrives"] for kw in permisos)
    updates = [kw for r, m, kw in drive.llamadas if (r, m) == ("files", "update")]
    assert updates == [{"fileId": carpeta, "body": {"inheritedPermissionsDisabled": True}, "supportsAllDrives": True}]
