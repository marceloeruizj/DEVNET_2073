"""Planificador de estructura de carpetas con permisos por rol.

Este modulo NO habla con ninguna nube. Lee la plantilla, calcula los permisos
efectivos de cada carpeta y produce un *plan* (lista de operaciones). Los
proveedores (Google Drive / Microsoft 365) solo ejecutan ese plan.

Separar "decidir" de "ejecutar" permite:
  * previsualizar (dry-run) lo que el agente va a hacer antes de confirmarlo,
  * probar toda la logica de permisos sin credenciales,
  * reutilizar la misma plantilla en varias plataformas.

Reglas de herencia
------------------
* Cada carpeta hereda los permisos de su carpeta padre, salvo que declare
  ``"heredar": false``. En ese caso parte de cero.
* Los ``permisos`` declarados en una carpeta se suman a lo heredado.
  Si un rol ya tenia acceso, se queda con el nivel MAS ALTO.
* ``roles_globales`` (p. ej. el Director de Proyecto) se aplican en la raiz y en
  toda carpeta que corte la herencia, de modo que nunca pierden acceso.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

NIVELES = ("lectura", "comentario", "edicion", "gestion")
_RANGO = {nivel: i for i, nivel in enumerate(NIVELES)}

RUTA_PLANTILLA = Path(__file__).resolve().parent / "plantillas" / "plantilla_construccion.json"

_CODIGO_VALIDO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{1,19}$")
_CARACTERES_PROHIBIDOS = re.compile(r'[\\/:*?"<>|#%]')
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ErrorPlantilla(ValueError):
    """La plantilla o los datos de entrada no son validos."""


@dataclass
class Principal:
    """Un grupo o usuario que recibe acceso."""

    email: str
    tipo: str = "group"  # "group" | "user"

    @classmethod
    def desde_texto(cls, texto: str) -> "Principal":
        texto = texto.strip()
        tipo = "group"
        if texto.lower().startswith("usuario:"):
            tipo, texto = "user", texto.split(":", 1)[1].strip()
        elif texto.lower().startswith("grupo:"):
            texto = texto.split(":", 1)[1].strip()
        if not _EMAIL.match(texto):
            raise ErrorPlantilla(f"'{texto}' no es un correo valido")
        return cls(email=texto.lower(), tipo=tipo)


@dataclass
class Operacion:
    """Un paso del plan. ``tipo`` es crear_raiz | crear_carpeta | restringir_herencia | conceder."""

    tipo: str
    ruta: str
    padre: str | None = None
    rol: str | None = None
    nivel: str | None = None
    principal: Principal | None = None

    def a_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"tipo": self.tipo, "ruta": self.ruta}
        if self.padre is not None:
            d["padre"] = self.padre
        if self.rol:
            d["rol"] = self.rol
            d["nivel"] = self.nivel
        if self.principal:
            d["principal"] = self.principal.email
            d["tipo_principal"] = self.principal.tipo
        return d


@dataclass
class Plan:
    raiz: str
    operaciones: list[Operacion] = field(default_factory=list)
    matriz: dict[str, dict[str, str]] = field(default_factory=dict)  # ruta -> rol -> nivel

    def resumen(self) -> dict[str, Any]:
        conteo: dict[str, int] = {}
        for op in self.operaciones:
            conteo[op.tipo] = conteo.get(op.tipo, 0) + 1
        return {"raiz": self.raiz, "carpetas": len(self.matriz), "operaciones": conteo}

    def como_arbol(self) -> str:
        """Texto legible para que el agente muestre al usuario antes de confirmar."""
        lineas = []
        for ruta, permisos in self.matriz.items():
            profundidad = ruta.count("/")
            nombre = ruta.rsplit("/", 1)[-1]
            accesos = ", ".join(f"{rol}:{nivel}" for rol, nivel in sorted(permisos.items()))
            lineas.append(f"{'    ' * profundidad}{nombre}/  [{accesos}]")
        return "\n".join(lineas)


def cargar_plantilla(ruta: str | Path | None = None) -> dict[str, Any]:
    with open(ruta or RUTA_PLANTILLA, encoding="utf-8") as fh:
        plantilla = json.load(fh)
    validar_plantilla(plantilla)
    return plantilla


def validar_plantilla(plantilla: dict[str, Any]) -> None:
    roles = set(plantilla.get("roles", {}))
    if not roles:
        raise ErrorPlantilla("La plantilla no define roles")

    def revisar(nodos: list[dict[str, Any]], ruta: str) -> None:
        vistos: set[str] = set()
        for nodo in nodos:
            nombre = nodo.get("nombre", "")
            if not nombre or _CARACTERES_PROHIBIDOS.search(nombre):
                raise ErrorPlantilla(f"Nombre de carpeta invalido en '{ruta}': {nombre!r}")
            if nombre in vistos:
                raise ErrorPlantilla(f"Carpeta duplicada en '{ruta}': {nombre}")
            vistos.add(nombre)
            for rol, nivel in nodo.get("permisos", {}).items():
                if rol not in roles:
                    raise ErrorPlantilla(f"Rol desconocido '{rol}' en {ruta}/{nombre}")
                if nivel not in _RANGO:
                    raise ErrorPlantilla(f"Nivel desconocido '{nivel}' en {ruta}/{nombre}")
            revisar(nodo.get("subcarpetas", []), f"{ruta}/{nombre}")

    for rol, nivel in plantilla.get("roles_globales", {}).items():
        if rol not in roles or nivel not in _RANGO:
            raise ErrorPlantilla(f"roles_globales invalido: {rol}={nivel}")
    revisar(plantilla.get("carpetas", []), "")


def _fusionar(base: dict[str, str], extra: dict[str, str]) -> dict[str, str]:
    """Une dos mapas rol->nivel quedandose con el nivel mas alto."""
    resultado = dict(base)
    for rol, nivel in extra.items():
        if rol not in resultado or _RANGO[nivel] > _RANGO[resultado[rol]]:
            resultado[rol] = nivel
    return resultado


def validar_codigo(codigo: str) -> None:
    if not _CODIGO_VALIDO.match(codigo or ""):
        raise ErrorPlantilla("El codigo de proyecto debe tener 2-20 caracteres alfanumericos o guiones (ej. OBR-2026-014)")


def nombre_raiz(plantilla: dict[str, Any], codigo: str, nombre: str) -> str:
    validar_codigo(codigo)
    limpio = re.sub(r"\s+", "_", _CARACTERES_PROHIBIDOS.sub("", (nombre or "").strip()))
    if not limpio:
        raise ErrorPlantilla("El nombre del proyecto esta vacio")
    return plantilla.get("formato_raiz", "{codigo}_{nombre}").format(codigo=codigo.upper(), nombre=limpio[:60])


def resolver_asignaciones(
    plantilla: dict[str, Any],
    codigo: str,
    asignaciones: dict[str, list[str] | str] | None = None,
    dominio: str | None = None,
) -> dict[str, list[Principal]]:
    """Devuelve rol -> principales.

    Prioridad: asignaciones explicitas; si un rol no viene, se usa la convencion
    de grupos de la plantilla (requiere ``dominio``). Roles sin asignacion quedan
    vacios y el plan los informa como advertencia (no se concede nada).
    """
    validar_codigo(codigo)
    roles = plantilla["roles"]
    asignaciones = asignaciones or {}
    desconocidos = set(asignaciones) - set(roles)
    if desconocidos:
        raise ErrorPlantilla(f"Roles desconocidos en asignaciones: {sorted(desconocidos)}")

    resultado: dict[str, list[Principal]] = {}
    for rol in roles:
        valor = asignaciones.get(rol)
        if valor:
            lista = [valor] if isinstance(valor, str) else list(valor)
            resultado[rol] = [Principal.desde_texto(v) for v in lista]
        elif dominio:
            email = plantilla["convencion_grupos"].format(codigo=codigo.lower(), rol=rol.lower(), dominio=dominio)
            resultado[rol] = [Principal.desde_texto(email)]
        else:
            resultado[rol] = []
    return resultado


def construir_plan(
    plantilla: dict[str, Any],
    codigo: str,
    nombre: str,
    asignaciones: dict[str, list[Principal]],
) -> Plan:
    """Recorre la plantilla y genera las operaciones en orden ejecutable.

    En carpetas que heredan solo se conceden los accesos NUEVOS (el delta),
    porque el resto ya llega por herencia. En la raiz y en carpetas con
    ``heredar: false`` se restringe la herencia y se concede el set completo.
    """
    globales = plantilla.get("roles_globales", {})
    raiz = nombre_raiz(plantilla, codigo, nombre)
    plan = Plan(raiz=raiz)

    def conceder(ruta: str, permisos: dict[str, str]) -> None:
        for rol, nivel in sorted(permisos.items()):
            for principal in asignaciones.get(rol, []):
                plan.operaciones.append(Operacion("conceder", ruta, rol=rol, nivel=nivel, principal=principal))

    efectivos_raiz = dict(globales)
    plan.operaciones.append(Operacion("crear_raiz", raiz))
    plan.operaciones.append(Operacion("restringir_herencia", raiz))
    conceder(raiz, efectivos_raiz)
    plan.matriz[raiz] = efectivos_raiz

    def recorrer(nodos: list[dict[str, Any]], ruta_padre: str, heredados: dict[str, str]) -> None:
        for nodo in nodos:
            ruta = f"{ruta_padre}/{nodo['nombre']}"
            propios = nodo.get("permisos", {})
            plan.operaciones.append(Operacion("crear_carpeta", ruta, padre=ruta_padre))
            if nodo.get("heredar", True):
                efectivos = _fusionar(heredados, propios)
                delta = {r: n for r, n in efectivos.items() if heredados.get(r) != n}
                conceder(ruta, delta)
            else:
                efectivos = _fusionar(globales, propios)
                plan.operaciones.append(Operacion("restringir_herencia", ruta))
                conceder(ruta, efectivos)
            plan.matriz[ruta] = efectivos
            recorrer(nodo.get("subcarpetas", []), ruta, efectivos)

    recorrer(plantilla.get("carpetas", []), raiz, efectivos_raiz)
    return plan


def roles_sin_asignar(asignaciones: dict[str, list[Principal]]) -> list[str]:
    return sorted(rol for rol, principales in asignaciones.items() if not principales)
