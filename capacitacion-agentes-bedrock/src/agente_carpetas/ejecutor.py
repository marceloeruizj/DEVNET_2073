"""Ejecuta un Plan contra un proveedor de almacenamiento.

Todo proveedor implementa la misma interfaz (``Proveedor``). Asi el agente y la
Lambda no saben si estan hablando con Google Drive, SharePoint o la simulacion.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from .estructura import Plan, Principal

log = logging.getLogger(__name__)


class Proveedor(Protocol):
    nombre: str

    def obtener_o_crear_raiz(self, nombre: str) -> str: ...

    def obtener_o_crear_carpeta(self, nombre: str, padre_id: str) -> tuple[str, bool]:
        """Devuelve (id, creada). ``creada`` es False si ya existia (idempotencia)."""
        ...

    def restringir_herencia(self, carpeta_id: str) -> None: ...

    def conceder(self, carpeta_id: str, principal: Principal, nivel: str) -> None: ...

    def url(self, carpeta_id: str) -> str | None: ...


class ProveedorSimulado:
    """Proveedor en memoria: ideal para laboratorios, pruebas y dry-run."""

    nombre = "simulacion"

    def __init__(self) -> None:
        self.carpetas: dict[str, dict[str, Any]] = {}
        self._contador = 0

    def _nuevo_id(self) -> str:
        self._contador += 1
        return f"sim-{self._contador:04d}"

    def obtener_o_crear_raiz(self, nombre: str) -> str:
        for cid, c in self.carpetas.items():
            if c["padre"] is None and c["nombre"] == nombre:
                return cid
        cid = self._nuevo_id()
        self.carpetas[cid] = {"nombre": nombre, "padre": None, "hereda": True, "acl": {}}
        return cid

    def obtener_o_crear_carpeta(self, nombre: str, padre_id: str) -> tuple[str, bool]:
        for cid, c in self.carpetas.items():
            if c["padre"] == padre_id and c["nombre"] == nombre:
                return cid, False
        cid = self._nuevo_id()
        self.carpetas[cid] = {"nombre": nombre, "padre": padre_id, "hereda": True, "acl": {}}
        return cid, True

    def restringir_herencia(self, carpeta_id: str) -> None:
        self.carpetas[carpeta_id]["hereda"] = False

    def conceder(self, carpeta_id: str, principal: Principal, nivel: str) -> None:
        self.carpetas[carpeta_id]["acl"][principal.email] = nivel

    def url(self, carpeta_id: str) -> str | None:
        return f"sim://{carpeta_id}"

    def acceso_efectivo(self, carpeta_id: str) -> dict[str, str]:
        """Calcula el ACL efectivo (herencia incluida) para verificar en pruebas."""
        c = self.carpetas[carpeta_id]
        base = self.acceso_efectivo(c["padre"]) if c["padre"] and c["hereda"] else {}
        return {**base, **c["acl"]}


def ejecutar_plan(plan: Plan, proveedor: Proveedor) -> dict[str, Any]:
    """Aplica el plan. Es idempotente: re-ejecutarlo no duplica carpetas.

    Un error al crear una carpeta detiene la ejecucion (las hijas dependen de
    ella). Un error al conceder un permiso se registra y se continua, para que
    el reporte final muestre exactamente que quedo pendiente.
    """
    ids: dict[str, str] = {}
    creadas, existentes, concedidos = 0, 0, 0
    errores: list[dict[str, str]] = []

    for op in plan.operaciones:
        try:
            if op.tipo == "crear_raiz":
                ids[op.ruta] = proveedor.obtener_o_crear_raiz(op.ruta)
            elif op.tipo == "crear_carpeta":
                nombre = op.ruta.rsplit("/", 1)[-1]
                ids[op.ruta], nueva = proveedor.obtener_o_crear_carpeta(nombre, ids[op.padre])
                creadas += nueva
                existentes += not nueva
            elif op.tipo == "restringir_herencia":
                proveedor.restringir_herencia(ids[op.ruta])
            elif op.tipo == "conceder":
                proveedor.conceder(ids[op.ruta], op.principal, op.nivel)
                concedidos += 1
        except Exception as exc:  # noqa: BLE001 - se reporta al agente
            log.exception("Fallo la operacion %s", op.a_dict())
            errores.append({"operacion": op.tipo, "ruta": op.ruta, "error": str(exc)[:300]})
            if op.tipo in ("crear_raiz", "crear_carpeta"):
                break

    return {
        "plataforma": proveedor.nombre,
        "raiz": plan.raiz,
        "url_raiz": proveedor.url(ids[plan.raiz]) if plan.raiz in ids else None,
        "carpetas_creadas": creadas,
        "carpetas_existentes": existentes,
        "permisos_concedidos": concedidos,
        "errores": errores,
        "completado": not errores,
    }
