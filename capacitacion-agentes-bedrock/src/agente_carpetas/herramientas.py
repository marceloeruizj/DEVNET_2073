"""Herramientas de negocio del agente, independientes de como se hospede.

Las usan:
  * el agente en AgentCore Runtime (agente_runtime.py, via agente.py),
  * la Lambda del Action Group de Bedrock Agents Classic (lambda_function.py),
  * el agente local de consola (scripts/agente_local.py).

Cada herramienta recibe un dict de parametros (texto) y devuelve un dict JSON.
Los errores de datos se lanzan como ErrorPlantilla para que el agente pida el
dato correcto al usuario.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable

from .ejecutor import ProveedorSimulado, ejecutar_plan
from .estructura import (
    ErrorPlantilla,
    cargar_plantilla,
    construir_plan,
    resolver_asignaciones,
    roles_sin_asignar,
)

log = logging.getLogger(__name__)

PLATAFORMAS = ("google", "microsoft", "simulacion")
_PLANTILLA: dict[str, Any] | None = None

__all__ = ["ErrorPlantilla", "FUNCIONES", "REQUIEREN_CONFIRMACION", "DEFINICIONES"]


def _plantilla() -> dict[str, Any]:
    global _PLANTILLA
    if _PLANTILLA is None:
        _PLANTILLA = cargar_plantilla(os.environ.get("RUTA_PLANTILLA") or None)
    return _PLANTILLA


def _secreto(arn_env: str) -> dict[str, Any]:
    import boto3

    arn = os.environ.get(arn_env)
    if not arn:
        raise ErrorPlantilla(f"Falta la variable {arn_env}: esa plataforma no esta configurada")
    valor = boto3.client("secretsmanager").get_secret_value(SecretId=arn)["SecretString"]
    return json.loads(valor)


def crear_proveedor(plataforma: str):
    if plataforma == "google":
        from .proveedores.google_drive import ProveedorGoogleDrive

        return ProveedorGoogleDrive(_secreto("GOOGLE_SECRET_ARN"))
    if plataforma == "microsoft":
        from .proveedores.microsoft_365 import ProveedorMicrosoft365

        return ProveedorMicrosoft365(_secreto("M365_SECRET_ARN"))
    return ProveedorSimulado()


def listar_roles_y_plantilla(_: dict[str, str]) -> dict[str, Any]:
    p = _plantilla()
    return {
        "roles": {codigo: datos["nombre"] for codigo, datos in p["roles"].items()},
        "niveles_acceso": p["niveles_acceso"],
        "carpetas_principales": [c["nombre"] for c in p["carpetas"]],
        "convencion_grupos": p["convencion_grupos"],
        "plataformas": list(PLATAFORMAS),
    }


def _preparar(params: dict[str, str]):
    p = _plantilla()
    codigo = params.get("codigo_proyecto", "")
    nombre = params.get("nombre_proyecto", "")
    dominio = (params.get("dominio") or "").strip().lower() or None
    texto = (params.get("asignaciones_json") or "").strip()
    try:
        asign_raw = json.loads(texto) if texto else {}
    except json.JSONDecodeError as exc:
        raise ErrorPlantilla(f"asignaciones_json no es JSON valido: {exc.msg}") from exc
    if not isinstance(asign_raw, dict):
        raise ErrorPlantilla('asignaciones_json debe ser un objeto: {"ING": ["grupo@dominio"], ...}')
    asignaciones = resolver_asignaciones(p, codigo, asign_raw, dominio)
    plan = construir_plan(p, codigo, nombre, asignaciones)
    return plan, roles_sin_asignar(asignaciones)


def previsualizar_estructura(params: dict[str, str]) -> dict[str, Any]:
    plan, sin_asignar = _preparar(params)
    return {
        "resumen": plan.resumen(),
        "arbol": plan.como_arbol(),
        "roles_sin_asignar": sin_asignar,
        "advertencia": (
            f"Los roles {sin_asignar} no recibiran acceso porque no tienen grupo asignado."
            if sin_asignar
            else None
        ),
    }


def crear_estructura(params: dict[str, str]) -> dict[str, Any]:
    plataforma = (params.get("plataforma") or "").strip().lower()
    if plataforma not in PLATAFORMAS:
        raise ErrorPlantilla(f"plataforma debe ser una de {PLATAFORMAS}")
    if os.environ.get("MODO_SIMULACION", "false").lower() == "true":
        plataforma = "simulacion"
    plan, sin_asignar = _preparar(params)
    resultado = ejecutar_plan(plan, crear_proveedor(plataforma))
    resultado["roles_sin_asignar"] = sin_asignar
    log.info(json.dumps({"auditoria": "crear_estructura", "params": params, "resultado": resultado}))
    return resultado


FUNCIONES: dict[str, Callable[[dict[str, str]], dict[str, Any]]] = {
    "listar_roles_y_plantilla": listar_roles_y_plantilla,
    "previsualizar_estructura": previsualizar_estructura,
    "crear_estructura": crear_estructura,
}

# Herramientas que escriben en sistemas externos: requieren aprobacion humana.
REQUIEREN_CONFIRMACION = {"crear_estructura"}

# ---------------------------------------------------------------------------
# Definicion de las herramientas para el modelo (JSON Schema).
# La descripcion es lo que el modelo lee para decidir cuando usar cada una.
# ---------------------------------------------------------------------------
_PARAMS_PROYECTO = {
    "codigo_proyecto": {"type": "string", "description": "Codigo unico del proyecto, 2-20 caracteres alfanumericos o guiones. Ej. OBR-2026-014"},
    "nombre_proyecto": {"type": "string", "description": "Nombre descriptivo del proyecto. Ej. Edificio Mirador"},
    "dominio": {"type": "string", "description": "Dominio de correo para armar los grupos por convencion (ej. constructora.com). Cadena vacia si se usan asignaciones explicitas."},
    "asignaciones_json": {"type": "string", "description": 'JSON rol -> lista de correos; prefijo usuario: para personas. Ej. {"DIR":["pm@x.com"],"CLI":["usuario:ana@cliente.cl"]}. Cadena vacia si se usa la convencion.'},
}

DEFINICIONES: list[dict[str, Any]] = [
    {
        "name": "listar_roles_y_plantilla",
        "description": "Devuelve los roles del proyecto, niveles de acceso, carpetas principales y la convencion de nombres de grupos.",
        "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "previsualizar_estructura",
        "description": "Calcula SIN crear nada el arbol de carpetas y los accesos efectivos por rol. Usar siempre antes de crear y mostrar el resultado al usuario.",
        "input_schema": {
            "type": "object",
            "properties": _PARAMS_PROYECTO,
            "required": list(_PARAMS_PROYECTO),
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "crear_estructura",
        "description": "Crea la estructura y aplica los permisos en la plataforma indicada. Es idempotente. El sistema pedira confirmacion humana antes de ejecutarla.",
        "input_schema": {
            "type": "object",
            "properties": {
                "plataforma": {"type": "string", "enum": list(PLATAFORMAS)},
                **_PARAMS_PROYECTO,
            },
            "required": ["plataforma", *_PARAMS_PROYECTO],
            "additionalProperties": False,
        },
        "strict": True,
    },
]
