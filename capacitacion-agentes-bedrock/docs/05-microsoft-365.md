# Módulo 5 — Integración con Microsoft 365 (SharePoint / OneDrive)

## 5.1 Modelo elegido: sitio "Proyectos" + carpeta raíz por proyecto

- Un **sitio de SharePoint** (p. ej. `https://constructora.sharepoint.com/sites/Proyectos`) con una **biblioteca de documentos**.
- Cada proyecto es una **carpeta raíz** dentro de la biblioteca, con la herencia **cortada** (solo DIR y los roles indicados).
- Alternativa para empresas grandes: un sitio por proyecto (más aislamiento; requiere crear sitios vía Graph/PnP, ejercicio avanzado).

¿Por qué dos APIs?

| Operación | API |
|---|---|
| Crear carpetas, conceder accesos (`invite`) | **Microsoft Graph** |
| Cortar herencia (`breakroleinheritance`) | **SharePoint REST** (Graph no la expone) |

## 5.2 Configuración paso a paso

### 1. Registro de aplicación en Entra ID (Azure AD)
1. <https://entra.microsoft.com> → *Aplicaciones → Registros de aplicaciones → Nuevo registro* → `agente-carpetas`.
2. Copie **ID de inquilino (tenant)** y **ID de aplicación (cliente)**.

### 2. Certificado (obligatorio para SharePoint REST con permisos de aplicación)

```bash
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout agente.key -out agente.crt -subj "/CN=agente-carpetas"
openssl x509 -in agente.crt -noout -fingerprint -sha1 | sed 's/.*=//; s/://g'   # huella (thumbprint)
```

Suba `agente.crt` en *Certificados y secretos → Certificados*.

### 3. Permisos de API (de **aplicación**, con consentimiento de administrador)

Recomendado — **mínimo privilegio**:
- Microsoft Graph → `Sites.Selected`
- SharePoint → `Sites.Selected`

Luego conceda a la app acceso `fullcontrol` **solo** al sitio Proyectos (un administrador, con Graph Explorer o PowerShell):

```http
POST https://graph.microsoft.com/v1.0/sites/{site-id}/permissions
{
  "roles": ["fullcontrol"],
  "grantedToIdentities": [{"application": {"id": "<client-id>", "displayName": "agente-carpetas"}}]
}
```

(Para un laboratorio rápido se puede usar `Sites.FullControl.All`, pero da acceso a **todos** los sitios del tenant: no lo use en producción.)

### 4. Obtener `site-id` y `drive_id`

```http
GET https://graph.microsoft.com/v1.0/sites/constructora.sharepoint.com:/sites/Proyectos
GET https://graph.microsoft.com/v1.0/sites/{site-id}/drives        ← id de la biblioteca "Documentos"
```

### 5. Grupos por rol
Cree grupos de Microsoft 365 o de seguridad **con correo** según la convención. Para externos, invítelos como invitados B2B y agréguelos al grupo correspondiente. Verifique que el uso compartido externo del sitio lo permita.

### 6. Guardar credenciales en Secrets Manager

```bash
python - <<'EOF' > /tmp/m365-secret.json
import json
print(json.dumps({
  "tenant_id": "<tenant-id>",
  "client_id": "<client-id>",
  "certificado_pem": open("agente.key").read(),
  "huella_certificado": "<thumbprint-sin-dos-puntos>",
  "sitio_url": "https://constructora.sharepoint.com/sites/Proyectos",
  "drive_id": "<drive-id>"
}))
EOF
aws secretsmanager create-secret --name agente-carpetas/m365 \
  --secret-string file:///tmp/m365-secret.json
rm /tmp/m365-secret.json agente.key
```

Use el ARN resultante en la variable `M365_SECRET_ARN` al desplegar (módulo 6, paso 7).

## 5.3 Qué hace el código (`proveedores/microsoft_365.py`)

| Paso del plan | Llamada |
|---|---|
| `crear_raiz` / `crear_carpeta` | `GET /drives/{d}/items/{padre}:/{nombre}` → 404 → `POST /drives/{d}/items/{padre}/children` |
| `restringir_herencia` | `GET …?$select=sharepointIds` → `POST {sitio}/_api/web/lists(guid'…')/items(n)/breakroleinheritance(copyRoleAssignments=false,clearSubscopes=true)` |
| `conceder` | `POST /drives/{d}/items/{id}/invite` con `roles: ["read"|"write"]`, `requireSignIn: true`, `sendInvitation: false` |

Notas:
- `copyRoleAssignments=false` deja la carpeta **solo** con los accesos que concede el agente. Los administradores de la colección de sitios mantienen acceso.
- Al invitar en una carpeta que hereda, SharePoint crea permisos únicos copiando los heredados y sumando el nuevo: el resultado coincide con la matriz del plan.
- Tokens: MSAL con certificado, uno para Graph y otro para `https://{tenant}.sharepoint.com`.

## 5.4 Verificación manual

1. En la biblioteca, abra `OBR-2026-014_Edificio_Mirador/02_Finanzas_Costos` → *Administrar acceso*.
2. Debe ver solo los grupos DIR y ADM (y administradores del sitio).
3. *Configuración avanzada de permisos* en `07_Seguridad_SSOMA/02_Incidentes_Accidentes`: aparece "Esta carpeta tiene permisos únicos".
