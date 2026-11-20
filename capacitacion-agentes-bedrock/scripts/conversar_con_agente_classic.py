"""Chat de consola con el agente desplegado en Amazon Bedrock Agents Classic (Anexo A).

Uso:
    python scripts/conversar_con_agente_classic.py --agent-id XXXX --alias-id YYYY [--region us-east-1]

Muestra:
  * como se invoca un agente (bedrock-agent-runtime InvokeAgent, respuesta en streaming),
  * como se maneja la *confirmacion humana* (RequireConfirmation=ENABLED): Bedrock
    devuelve un evento ``returnControl`` y el cliente responde CONFIRM o DENY,
  * como ver la traza (razonamiento y llamadas a herramientas) con --traza.
"""

from __future__ import annotations

import argparse
import json
import uuid

import boto3


def invocar(cliente, args, sesion: str, texto: str | None, estado_sesion: dict | None = None) -> dict | None:
    """Envia un turno y devuelve el bloque returnControl si el agente pide confirmacion."""
    peticion = {
        "agentId": args.agent_id,
        "agentAliasId": args.alias_id,
        "sessionId": sesion,
        "enableTrace": args.traza,
    }
    if texto:
        peticion["inputText"] = texto
    if estado_sesion:
        peticion["sessionState"] = estado_sesion

    respuesta = cliente.invoke_agent(**peticion)
    control = None
    for evento in respuesta["completion"]:
        if "chunk" in evento:
            print(evento["chunk"]["bytes"].decode(), end="", flush=True)
        elif "returnControl" in evento:
            control = evento["returnControl"]
        elif "trace" in evento and args.traza:
            print(f"\n[traza] {json.dumps(evento['trace'].get('trace', {}), default=str)[:400]}")
    print()
    return control


def pedir_confirmacion(control: dict) -> dict:
    resultados = []
    for entrada in control["invocationInputs"]:
        fn = entrada["functionInvocationInput"]
        params = {p["name"]: p["value"] for p in fn.get("parameters", [])}
        print(f"\n>>> El agente quiere ejecutar '{fn['function']}' con:\n{json.dumps(params, indent=2, ensure_ascii=False)}")
        ok = input("¿Confirmar? [s/N]: ").strip().lower() == "s"
        resultados.append(
            {
                "functionResult": {
                    "actionGroup": fn["actionGroup"],
                    "function": fn["function"],
                    "confirmationState": "CONFIRM" if ok else "DENY",
                }
            }
        )
    return {"invocationId": control["invocationId"], "returnControlInvocationResults": resultados}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent-id", required=True)
    ap.add_argument("--alias-id", required=True)
    ap.add_argument("--region", default=None)
    ap.add_argument("--traza", action="store_true", help="Mostrar la traza de orquestacion")
    args = ap.parse_args()

    cliente = boto3.client("bedrock-agent-runtime", region_name=args.region)
    sesion = str(uuid.uuid4())
    print("Arquitecto Documental listo. Escriba 'salir' para terminar.\n")
    while True:
        texto = input("Usted: ").strip()
        if texto.lower() in {"salir", "exit"}:
            break
        print("Agente: ", end="")
        control = invocar(cliente, args, sesion, texto)
        while control:  # el agente puede encadenar mas de una confirmacion
            control = invocar(cliente, args, sesion, None, pedir_confirmacion(control))


if __name__ == "__main__":
    main()
