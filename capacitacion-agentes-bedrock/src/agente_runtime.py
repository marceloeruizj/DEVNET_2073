"""Punto de entrada del agente en Amazon Bedrock AgentCore Runtime.

AgentCore Runtime hospeda el agente en un entorno aislado por sesion (microVM),
escala solo y expone el endpoint InvokeAgentRuntime. Nosotros solo escribimos
la funcion ``invocar`` marcada con ``@app.entrypoint``.

Contrato (payload JSON):
    {"prompt": "texto del usuario"}                 -> turno normal
    {"confirmacion": true|false, "prompt": "..."}   -> respuesta a una accion pendiente
    {"sesion": "id"}  (opcional; por defecto se usa el runtimeSessionId)

Respuesta:
    {"respuesta": "...", "pendiente": {"herramienta": ..., "parametros": {...}} | null,
     "herramientas": [...], "sesion": "..."}

Memoria: para la capacitacion la conversacion se guarda en la memoria del
proceso, que AgentCore mantiene viva mientras dure la sesion. En produccion
use AgentCore Memory o DynamoDB (ejercicio del modulo 8).

Despliegue: ver docs/06-construir-y-desplegar.md (agentcore configure / launch).
"""

from __future__ import annotations

import logging
import os

from anthropic import AnthropicBedrockMantle
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from agente_carpetas.agente import MODELO_POR_DEFECTO, AgenteCarpetas, Sesion

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

app = BedrockAgentCoreApp()
_agente = AgenteCarpetas(
    AnthropicBedrockMantle(aws_region=os.environ.get("AWS_REGION", "us-east-1")),
    modelo=os.environ.get("MODELO", MODELO_POR_DEFECTO),
)
_sesiones: dict[str, Sesion] = {}


@app.entrypoint
def invocar(payload: dict, context=None) -> dict:
    sesion_id = payload.get("sesion") or getattr(context, "session_id", None) or "por-defecto"
    sesion = _sesiones.setdefault(sesion_id, Sesion())
    confirmacion = payload.get("confirmacion")
    resultado = _agente.turno(
        sesion,
        texto=payload.get("prompt"),
        confirmacion=bool(confirmacion) if confirmacion is not None else None,
    )
    resultado["sesion"] = sesion_id
    return resultado


if __name__ == "__main__":
    app.run()  # Servidor local en http://localhost:8080/invocations para pruebas
