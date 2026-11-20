"""Adaptador Lambda para el Action Group de Amazon Bedrock Agents *Classic*.

Ruta alternativa (Anexo A de la capacitacion): solo para cuentas que ya usan
Bedrock Agents Classic. La ruta principal es AgentCore Runtime (agente_runtime.py).

La logica de negocio vive en agente_carpetas/herramientas.py; este archivo solo
traduce el contrato "function details" (messageVersion 1.0) de Bedrock Agents.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from agente_carpetas.herramientas import FUNCIONES, ErrorPlantilla

log = logging.getLogger()
log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def _respuesta(evento: dict[str, Any], cuerpo: dict[str, Any], estado: str | None = None) -> dict[str, Any]:
    function_response: dict[str, Any] = {
        "responseBody": {"TEXT": {"body": json.dumps(cuerpo, ensure_ascii=False)}}
    }
    if estado:
        function_response["responseState"] = estado  # FAILURE | REPROMPT
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": evento.get("actionGroup"),
            "function": evento.get("function"),
            "functionResponse": function_response,
        },
        "sessionAttributes": evento.get("sessionAttributes", {}),
        "promptSessionAttributes": evento.get("promptSessionAttributes", {}),
    }


def lambda_handler(evento: dict[str, Any], _contexto: Any = None) -> dict[str, Any]:
    funcion = evento.get("function", "")
    params = {p["name"]: p.get("value", "") for p in evento.get("parameters", [])}
    log.info("Agente invoca %s con %s", funcion, sorted(params))

    manejador = FUNCIONES.get(funcion)
    if manejador is None:
        return _respuesta(evento, {"error": f"Funcion desconocida: {funcion}"}, "FAILURE")
    try:
        return _respuesta(evento, manejador(params))
    except ErrorPlantilla as exc:
        # REPROMPT: el modelo ve el error y puede pedir el dato correcto al usuario.
        return _respuesta(evento, {"error": str(exc)}, "REPROMPT")
    except Exception as exc:  # noqa: BLE001
        log.exception("Error inesperado")
        return _respuesta(evento, {"error": f"Error interno: {type(exc).__name__}"}, "FAILURE")
