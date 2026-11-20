"""Chat de consola con el agente desplegado en Amazon Bedrock AgentCore Runtime.

Uso:
    python scripts/conversar_con_agentcore.py --arn <agentRuntimeArn> [--region us-east-1]

Llama a InvokeAgentRuntime (cliente boto3 "bedrock-agentcore"). Cuando el agente
devuelve "pendiente", pide la confirmacion humana y la envia en el siguiente turno.
Requiere el permiso IAM bedrock-agentcore:InvokeAgentRuntime.
"""

import argparse
import json
import uuid

import boto3


def invocar(cliente, arn: str, sesion: str, payload: dict) -> dict:
    resp = cliente.invoke_agent_runtime(
        agentRuntimeArn=arn,
        runtimeSessionId=sesion,  # mismo id = misma sesion (memoria de la conversacion)
        payload=json.dumps(payload).encode(),
    )
    cuerpo = resp["response"].read().decode()
    return json.loads(cuerpo)


def mostrar(r: dict) -> None:
    for h in r.get("herramientas", []):
        print(f"  [herramienta] {h}")
    print(f"Agente: {r.get('respuesta', r)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arn", required=True, help="agentRuntimeArn que entrega 'agentcore launch'")
    ap.add_argument("--region", default=None)
    args = ap.parse_args()

    cliente = boto3.client("bedrock-agentcore", region_name=args.region)
    sesion = f"sesion-{uuid.uuid4()}"  # AgentCore exige ids de sesion largos (33+ caracteres)
    print("Arquitecto Documental (AgentCore). Escriba 'salir' para terminar.\n")
    while True:
        texto = input("Usted: ").strip()
        if texto.lower() in {"salir", "exit"}:
            break
        r = invocar(cliente, args.arn, sesion, {"prompt": texto})
        mostrar(r)
        while r.get("pendiente"):
            p = r["pendiente"]
            print(f"\n>>> El agente quiere ejecutar '{p['herramienta']}' con:")
            print(json.dumps(p["parametros"], indent=2, ensure_ascii=False))
            ok = input("¿Confirmar? [s/N]: ").strip().lower() == "s"
            r = invocar(cliente, args.arn, sesion, {"confirmacion": ok})
            mostrar(r)


if __name__ == "__main__":
    main()
