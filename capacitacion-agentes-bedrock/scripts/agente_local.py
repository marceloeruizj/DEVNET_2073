"""Ejecuta el agente en su computador (consola), en modo simulacion.

Es el MISMO bucle que corre en AgentCore Runtime (src/agente_carpetas/agente.py),
llamando a Claude en Amazon Bedrock. Ideal para desarrollar y depurar antes de
desplegar. No toca Google ni Microsoft: MODO_SIMULACION=true.

Requisitos:
    pip install -r requirements-dev.txt
    Credenciales AWS con acceso al modelo en Bedrock (aws configure / aws sso login).

Uso:
    python scripts/agente_local.py --region us-east-1
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("MODO_SIMULACION", "true")  # Seguridad para el laboratorio

from anthropic import AnthropicBedrockMantle  # noqa: E402

from agente_carpetas.agente import MODELO_POR_DEFECTO, AgenteCarpetas, Sesion  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    ap.add_argument("--modelo", default=MODELO_POR_DEFECTO)
    args = ap.parse_args()

    agente = AgenteCarpetas(AnthropicBedrockMantle(aws_region=args.region), modelo=args.modelo)
    sesion = Sesion()
    print("Arquitecto Documental (local, simulacion). Escriba 'salir' para terminar.\n")
    confirmacion = None
    while True:
        texto = input("Usted: ").strip()
        if texto.lower() in {"salir", "exit"}:
            break
        r = agente.turno(sesion, texto=texto, confirmacion=confirmacion)
        confirmacion = None
        for h in r["herramientas"]:
            print(f"  [herramienta] {h}")
        print(f"Agente: {r['respuesta']}")
        if r["pendiente"]:
            print(f"\n>>> Accion pendiente: {r['pendiente']['herramienta']}")
            print(json.dumps(r["pendiente"]["parametros"], indent=2, ensure_ascii=False))
            confirmacion = input("¿Confirmar? [s/N]: ").strip().lower() == "s"
            r = agente.turno(sesion, confirmacion=confirmacion)
            confirmacion = None
            for h in r["herramientas"]:
                print(f"  [herramienta] {h}")
            print(f"Agente: {r['respuesta']}")


if __name__ == "__main__":
    main()
