"""El bucle agentico del "Arquitecto Documental".

    usuario -> modelo -> (tool_use?) -> ejecutar herramienta -> tool_result -> modelo -> ...

Una sola clase sirve para la consola local y para AgentCore Runtime. El estado
de la conversacion vive en un objeto ``Sesion`` que guarda quien hospeda el
agente (memoria del proceso, AgentCore Memory, DynamoDB...).

Confirmacion humana (human-in-the-loop)
---------------------------------------
Si el modelo pide una herramienta de REQUIEREN_CONFIRMACION, el bucle se
DETIENE y devuelve ``pendiente`` al cliente. El siguiente turno trae
``confirmacion=True/False``: si se aprueba se ejecuta; si no, el modelo recibe
"el usuario no autorizo" y continua la conversacion. Es el mismo patron que
"return of control" de Bedrock Agents Classic.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .herramientas import DEFINICIONES, FUNCIONES, REQUIEREN_CONFIRMACION, ErrorPlantilla

log = logging.getLogger(__name__)

MODELO_POR_DEFECTO = "anthropic.claude-opus-5-5"  # ID de Claude en Amazon Bedrock
INSTRUCCIONES = (Path(__file__).resolve().parent / "instrucciones.md").read_text(encoding="utf-8")
MAX_VUELTAS = 10  # freno de seguridad contra bucles infinitos


@dataclass
class Sesion:
    mensajes: list[Any] = field(default_factory=list)
    # Herramienta esperando aprobacion: {"bloque": tool_use, "resultados": [tool_result ya listos]}
    pendiente: dict[str, Any] | None = None


def _texto_resultado(nombre: str, entrada: dict[str, Any]) -> tuple[str, bool]:
    """Ejecuta una herramienta y devuelve (contenido, es_error)."""
    funcion = FUNCIONES.get(nombre)
    if funcion is None:
        return f"Herramienta desconocida: {nombre}", True
    try:
        params = {k: "" if v is None else str(v) for k, v in entrada.items()}
        return json.dumps(funcion(params), ensure_ascii=False), False
    except ErrorPlantilla as exc:
        return f"Error de datos: {exc}", True
    except Exception as exc:  # noqa: BLE001 - el modelo debe saber que fallo
        log.exception("Fallo la herramienta %s", nombre)
        return f"Error interno al ejecutar {nombre}: {type(exc).__name__}", True


def _resultado(bloque: Any, contenido: str, es_error: bool) -> dict[str, Any]:
    return {"type": "tool_result", "tool_use_id": bloque.id, "content": contenido, "is_error": es_error}


class AgenteCarpetas:
    def __init__(self, cliente: Any, modelo: str = MODELO_POR_DEFECTO, esfuerzo: str = "medium") -> None:
        """``cliente``: AnthropicBedrockMantle (o un doble de pruebas con .messages.create)."""
        self.cliente = cliente
        self.modelo = modelo
        self.esfuerzo = esfuerzo

    def turno(self, sesion: Sesion, texto: str | None = None, confirmacion: bool | None = None) -> dict[str, Any]:
        """Procesa un turno del usuario. Devuelve {"respuesta": str, "pendiente": dict|None, "herramientas": [...]}."""
        usadas: list[str] = []

        if sesion.pendiente is not None:
            if confirmacion is None:
                return {
                    "respuesta": "Hay una accion esperando su confirmacion. Responda si o no.",
                    "pendiente": self._describir(sesion.pendiente),
                    "herramientas": usadas,
                }
            bloque = sesion.pendiente["bloque"]
            resultados = sesion.pendiente["resultados"]
            if confirmacion:
                usadas.append(bloque.name)
                resultados.append(_resultado(bloque, *_texto_resultado(bloque.name, bloque.input)))
            else:
                resultados.append(_resultado(bloque, "El usuario NO autorizo esta accion. No se creo nada.", True))
            sesion.pendiente = None
            contenido: list[Any] = list(resultados)
            if texto:
                contenido.append({"type": "text", "text": texto})
            sesion.mensajes.append({"role": "user", "content": contenido})
        elif texto:
            sesion.mensajes.append({"role": "user", "content": texto})
        else:
            return {"respuesta": "Escriba su solicitud.", "pendiente": None, "herramientas": usadas}

        textos: list[str] = []
        for _ in range(MAX_VUELTAS):
            respuesta = self.cliente.messages.create(
                model=self.modelo,
                max_tokens=16000,
                system=INSTRUCCIONES,
                tools=DEFINICIONES,
                output_config={"effort": self.esfuerzo},
                messages=sesion.mensajes,
            )
            sesion.mensajes.append({"role": "assistant", "content": respuesta.content})
            textos += [b.text for b in respuesta.content if b.type == "text" and b.text.strip()]

            if respuesta.stop_reason == "refusal":
                textos.append("(El modelo declino esta solicitud.)")
                break
            if respuesta.stop_reason != "tool_use":
                break  # end_turn: el agente espera al usuario

            resultados: list[dict[str, Any]] = []
            for bloque in [b for b in respuesta.content if b.type == "tool_use"]:
                if bloque.name in REQUIEREN_CONFIRMACION:
                    # Pausa: las demas herramientas de esta vuelta ya se ejecutan,
                    # la que escribe espera la aprobacion humana.
                    sesion.pendiente = {"bloque": bloque, "resultados": resultados}
                    continue
                usadas.append(bloque.name)
                resultados.append(_resultado(bloque, *_texto_resultado(bloque.name, bloque.input)))

            if sesion.pendiente is not None:
                return {
                    "respuesta": "\n".join(textos),
                    "pendiente": self._describir(sesion.pendiente),
                    "herramientas": usadas,
                }
            # Todos los resultados vuelven juntos en UN mensaje de usuario.
            sesion.mensajes.append({"role": "user", "content": resultados})
        else:
            textos.append("(Se alcanzo el limite de pasos; revise la solicitud.)")

        return {"respuesta": "\n".join(textos), "pendiente": None, "herramientas": usadas}

    @staticmethod
    def _describir(pendiente: dict[str, Any]) -> dict[str, Any]:
        bloque = pendiente["bloque"]
        return {"herramienta": bloque.name, "parametros": dict(bloque.input)}
