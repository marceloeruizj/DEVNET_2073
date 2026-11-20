"""Proveedor Microsoft 365 (SharePoint Online / OneDrive).

Modelo usado
------------
* Un **sitio de SharePoint "Proyectos"** con una biblioteca de documentos
  (``drive_id``). Cada proyecto es una carpeta raiz dentro de la biblioteca.
* Las carpetas se crean con **Microsoft Graph**.
* Para *cortar la herencia* se usa la **API REST de SharePoint**
  (``breakroleinheritance``), porque Graph no expone esa operacion.
* Los accesos se conceden con Graph ``driveItem/invite`` a grupos de
  Microsoft 365 / grupos de seguridad con correo.

Autenticacion
-------------
Registro de aplicacion en Entra ID (Azure AD), permisos de *aplicacion*:
``Sites.Selected`` (recomendado, luego conceder ``fullcontrol`` sobre el sitio)
o ``Sites.FullControl.All``. La REST de SharePoint con token de aplicacion
exige **certificado** (no acepta secreto de cliente).

Niveles: SharePoint/Graph solo distinguen ``read`` y ``write`` en invitaciones;
``comentario`` se mapea a ``read`` y ``gestion`` a ``write``.

Dependencias: ``msal``.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from ..estructura import Principal

GRAPH = "https://graph.microsoft.com/v1.0"
ROLES_GRAPH = {"lectura": "read", "comentario": "read", "edicion": "write", "gestion": "write"}

Http = Callable[[str, str, dict[str, str], dict[str, Any] | None], tuple[int, dict[str, Any]]]


def _http_urllib(metodo: str, url: str, cabeceras: dict[str, str], cuerpo: dict[str, Any] | None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, method=metodo, headers=cabeceras)
    if datos is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            texto = resp.read().decode() or "{}"
            return resp.status, json.loads(texto)
    except urllib.error.HTTPError as err:
        texto = err.read().decode() or "{}"
        try:
            return err.code, json.loads(texto)
        except json.JSONDecodeError:
            return err.code, {"error": texto[:300]}


class ProveedorMicrosoft365:
    nombre = "microsoft"

    def __init__(
        self,
        credenciales: dict[str, Any],
        http: Http | None = None,
        obtener_token: Callable[[str], str] | None = None,
    ) -> None:
        """``credenciales``: tenant_id, client_id, certificado_pem, huella_certificado,
        sitio_url (https://empresa.sharepoint.com/sites/Proyectos) y drive_id."""
        self.drive_id = credenciales["drive_id"]
        self.sitio_url = credenciales["sitio_url"].rstrip("/")
        self._http = http or _http_urllib
        self._tokens: dict[str, str] = {}
        if obtener_token is None:
            import msal

            app = msal.ConfidentialClientApplication(
                credenciales["client_id"],
                authority=f"https://login.microsoftonline.com/{credenciales['tenant_id']}",
                client_credential={
                    "private_key": credenciales["certificado_pem"],
                    "thumbprint": credenciales["huella_certificado"],
                },
            )

            def obtener_token(recurso: str) -> str:
                res = app.acquire_token_for_client(scopes=[f"{recurso}/.default"])
                if "access_token" not in res:
                    raise RuntimeError(f"No se obtuvo token para {recurso}: {res.get('error_description')}")
                return res["access_token"]

        self._obtener_token = obtener_token

    # --- utilidades -----------------------------------------------------
    def _token(self, recurso: str) -> str:
        if recurso not in self._tokens:
            self._tokens[recurso] = self._obtener_token(recurso)
        return self._tokens[recurso]

    def _graph(self, metodo: str, ruta: str, cuerpo: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        cab = {"Authorization": f"Bearer {self._token('https://graph.microsoft.com')}"}
        return self._http(metodo, f"{GRAPH}{ruta}", cab, cuerpo)

    def _ok(self, estado: int, cuerpo: dict[str, Any], accion: str) -> dict[str, Any]:
        if estado >= 300:
            raise RuntimeError(f"{accion} fallo ({estado}): {json.dumps(cuerpo)[:300]}")
        return cuerpo

    # --- carpetas -------------------------------------------------------
    def _buscar_o_crear(self, nombre: str, padre: str) -> tuple[str, bool]:
        ruta_hijo = urllib.parse.quote(nombre)
        estado, cuerpo = self._graph("GET", f"/drives/{self.drive_id}/items/{padre}:/{ruta_hijo}")
        if estado == 200:
            return cuerpo["id"], False
        if estado != 404:
            self._ok(estado, cuerpo, f"Buscar carpeta {nombre}")
        estado, cuerpo = self._graph(
            "POST",
            f"/drives/{self.drive_id}/items/{padre}/children",
            {"name": nombre, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"},
        )
        return self._ok(estado, cuerpo, f"Crear carpeta {nombre}")["id"], True

    def obtener_o_crear_raiz(self, nombre: str) -> str:
        return self._buscar_o_crear(nombre, "root")[0]

    def obtener_o_crear_carpeta(self, nombre: str, padre_id: str) -> tuple[str, bool]:
        return self._buscar_o_crear(nombre, padre_id)

    # --- permisos -------------------------------------------------------
    def restringir_herencia(self, carpeta_id: str) -> None:
        estado, item = self._graph("GET", f"/drives/{self.drive_id}/items/{carpeta_id}?$select=id,sharepointIds")
        ids = self._ok(estado, item, "Leer sharepointIds")["sharepointIds"]
        url = (
            f"{self.sitio_url}/_api/web/lists(guid'{ids['listId']}')/items({ids['listItemId']})"
            "/breakroleinheritance(copyRoleAssignments=false,clearSubscopes=true)"
        )
        host = urllib.parse.urlsplit(self.sitio_url)
        cab = {
            "Authorization": f"Bearer {self._token(f'{host.scheme}://{host.netloc}')}",
            "Accept": "application/json;odata=nometadata",
        }
        estado, cuerpo = self._http("POST", url, cab, None)
        self._ok(estado, cuerpo, "Cortar herencia")

    def conceder(self, carpeta_id: str, principal: Principal, nivel: str) -> None:
        estado, cuerpo = self._graph(
            "POST",
            f"/drives/{self.drive_id}/items/{carpeta_id}/invite",
            {
                "recipients": [{"email": principal.email}],
                "roles": [ROLES_GRAPH[nivel]],
                "requireSignIn": True,
                "sendInvitation": False,
            },
        )
        self._ok(estado, cuerpo, f"Conceder {nivel} a {principal.email}")

    def url(self, carpeta_id: str) -> str | None:
        estado, item = self._graph("GET", f"/drives/{self.drive_id}/items/{carpeta_id}?$select=webUrl")
        return item.get("webUrl") if estado == 200 else None
