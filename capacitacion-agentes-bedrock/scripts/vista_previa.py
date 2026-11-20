"""Muestra el arbol de carpetas y accesos por rol SIN IA y SIN nube.

Uso:
    python scripts/vista_previa.py OBR-2026-014 "Edificio Mirador" constructora.com
    python scripts/vista_previa.py OBR-2026-014 "Edificio Mirador" constructora.com --crear-simulado
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agente_carpetas.ejecutor import ProveedorSimulado, ejecutar_plan  # noqa: E402
from agente_carpetas.estructura import cargar_plantilla, construir_plan, resolver_asignaciones  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("codigo")
ap.add_argument("nombre")
ap.add_argument("dominio", nargs="?")
ap.add_argument("--plantilla", help="Ruta a una plantilla JSON alternativa")
ap.add_argument("--crear-simulado", action="store_true")
args = ap.parse_args()

plantilla = cargar_plantilla(args.plantilla)
asignaciones = resolver_asignaciones(plantilla, args.codigo, None, args.dominio)
plan = construir_plan(plantilla, args.codigo, args.nombre, asignaciones)
print(plan.como_arbol())
print("\nResumen:", json.dumps(plan.resumen(), ensure_ascii=False))
if args.crear_simulado:
    print("Resultado:", json.dumps(ejecutar_plan(plan, ProveedorSimulado()), indent=2, ensure_ascii=False))
