"""Proveedor Google Drive (Google Workspace).

Modelo usado
------------
* Una **unidad compartida (Shared Drive) por proyecto** = carpeta raiz.
  Solo el rol global (Director) es miembro de la unidad; el resto recibe
  acceso carpeta por carpeta. Asi nadie "hereda" toda la unidad.
* Carpetas con ``heredar: false`` se marcan como **carpetas de acceso limitado**
  (campo ``inheritedPermissionsDisabled`` de Drive API v3). Verifique que su
  edicion de Workspace tenga habilitada esta funcion; si no, el proveedor
  devuelve un error claro y el resto de la estructura se crea igual.

Autenticacion
-------------
Cuenta de servicio con *delegacion de todo el dominio* que actua en nombre de
un usuario administrador (``sujeto_delegado``). Alcance minimo:
``https://www.googleapis.com/auth/drive``.

Dependencias: ``google-api-python-client`` y ``google-auth``.
"""

from __future__ import annotations

import uuid
from typing import Any

from ..estructura import Principal

ROLES_DRIVE = {
    "lectura": "reader",
    "comentario": "commenter",
    "edicion": "writer",
    "gestion": "fileOrganizer",
}
CARPETA_MIME = "application/vnd.google-apps.folder"


def _escapar(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("'", "\\'")


class ProveedorGoogleDrive:
    nombre = "google"

    def __init__(self, credenciales: dict[str, Any], servicio: Any | None = None) -> None:
        """``credenciales``: {"cuenta_servicio": {...json...}, "sujeto_delegado": "admin@empresa.com"}.

        ``servicio`` permite inyectar un cliente falso en pruebas.
        """
        if servicio is None:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            creds = service_account.Credentials.from_service_account_info(
                credenciales["cuenta_servicio"],
                scopes=["https://www.googleapis.com/auth/drive"],
                subject=credenciales["sujeto_delegado"],
            )
            servicio = build("drive", "v3", credentials=creds, cache_discovery=False)
        self.drive = servicio
        self._unidad_id: str | None = None

    # --- raiz = unidad compartida ---------------------------------------
    def obtener_o_crear_raiz(self, nombre: str) -> str:
        q = f"name = '{_escapar(nombre)}'"
        existentes = self.drive.drives().list(q=q, pageSize=10).execute().get("drives", [])
        if existentes:
            self._unidad_id = existentes[0]["id"]
        else:
            unidad = self.drive.drives().create(requestId=str(uuid.uuid4()), body={"name": nombre}).execute()
            self._unidad_id = unidad["id"]
        return self._unidad_id

    # --- carpetas -------------------------------------------------------
    def obtener_o_crear_carpeta(self, nombre: str, padre_id: str) -> tuple[str, bool]:
        q = (
            f"'{padre_id}' in parents and name = '{_escapar(nombre)}' "
            f"and mimeType = '{CARPETA_MIME}' and trashed = false"
        )
        encontrados = (
            self.drive.files()
            .list(
                q=q,
                corpora="drive",
                driveId=self._unidad_id,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                fields="files(id,name)",
            )
            .execute()
            .get("files", [])
        )
        if encontrados:
            return encontrados[0]["id"], False
        carpeta = (
            self.drive.files()
            .create(
                body={"name": nombre, "mimeType": CARPETA_MIME, "parents": [padre_id]},
                supportsAllDrives=True,
                fields="id",
            )
            .execute()
        )
        return carpeta["id"], True

    # --- permisos -------------------------------------------------------
    def restringir_herencia(self, carpeta_id: str) -> None:
        if carpeta_id == self._unidad_id:
            return  # La unidad compartida es la raiz: no hereda de nadie.
        self.drive.files().update(
            fileId=carpeta_id,
            body={"inheritedPermissionsDisabled": True},
            supportsAllDrives=True,
        ).execute()

    def conceder(self, carpeta_id: str, principal: Principal, nivel: str) -> None:
        rol = ROLES_DRIVE[nivel]
        if carpeta_id == self._unidad_id and nivel == "gestion":
            rol = "organizer"  # Miembro administrador de la unidad compartida.
        self.drive.permissions().create(
            fileId=carpeta_id,
            body={"type": principal.tipo, "role": rol, "emailAddress": principal.email},
            supportsAllDrives=True,
            sendNotificationEmail=False,
        ).execute()

    def url(self, carpeta_id: str) -> str | None:
        # Sirve tanto para la unidad compartida como para carpetas.
        return f"https://drive.google.com/drive/folders/{carpeta_id}"
