# Módulo 4 — Integración con Google Workspace (Google Drive)

## 4.1 Modelo elegido: una unidad compartida por proyecto

| Opción | Problema |
|---|---|
| Carpeta en "Mi unidad" de alguien | Si esa persona se va, los archivos quedan en su cuenta. |
| Una unidad compartida para todos los proyectos | Los miembros de la unidad ven **todo**; no se puede restringir. |
| **Una unidad compartida por proyecto** ✅ | Propiedad de la organización; los miembros se limitan al Director; el resto recibe acceso por carpeta. |

En Google Drive los permisos de una carpeta **se heredan** hacia abajo y, en una unidad compartida tradicional, **no se pueden quitar** en subcarpetas. Para restringir una subcarpeta sensible (p. ej. `02_Incidentes_Accidentes`) se usan las **carpetas de acceso limitado** (Drive API: campo `inheritedPermissionsDisabled`). Verifique con su administrador que la función esté disponible en su edición de Workspace; si no lo está, el agente reporta el error de esa carpeta y crea el resto.

## 4.2 Configuración paso a paso

### 1. Proyecto en Google Cloud
1. <https://console.cloud.google.com> → crear proyecto `agente-carpetas`.
2. *APIs y servicios* → habilitar **Google Drive API**.

### 2. Cuenta de servicio
1. *IAM y administración → Cuentas de servicio* → crear `agente-carpetas`.
2. *Claves → Agregar clave → JSON*. Guarde el archivo (no lo suba a Git).
3. Copie el **ID de cliente** (numérico) de la cuenta de servicio.

### 3. Delegación de todo el dominio (Admin console)
1. <https://admin.google.com> → *Seguridad → Acceso y control de datos → Controles de API → Delegación de todo el dominio*.
2. *Agregar nuevo* → ID de cliente + alcance `https://www.googleapis.com/auth/drive`.
3. Cree (o elija) un usuario técnico, p. ej. `svc-proyectos@constructora.com`, con permiso para **crear unidades compartidas**. El agente actúa en su nombre.

### 4. Grupos por rol
En *Directorio → Grupos*, cree los grupos del proyecto según la convención (`proy-obr-2026-014-ing@…`). Para externos, permita miembros externos en esos grupos y en la política de uso compartido.

> Automatizable: el agente podría crear también los grupos (Admin SDK Directory API). Queda como ejercicio avanzado (módulo 8).

### 5. Guardar credenciales en AWS Secrets Manager

```bash
python - <<'EOF' > /tmp/google-secret.json
import json
cuenta = json.load(open("ruta/clave-cuenta-servicio.json"))
print(json.dumps({"cuenta_servicio": cuenta, "sujeto_delegado": "svc-proyectos@constructora.com"}))
EOF
aws secretsmanager create-secret --name agente-carpetas/google \
  --secret-string file:///tmp/google-secret.json
rm /tmp/google-secret.json
```

Use el ARN resultante en la variable `GOOGLE_SECRET_ARN` al desplegar (módulo 6, paso 7).

## 4.3 Qué hace el código (`proveedores/google_drive.py`)

| Paso del plan | Llamada a Drive API v3 |
|---|---|
| `crear_raiz` | `drives.list(q="name = '…'")` → si no existe, `drives.create(requestId=…)` |
| `crear_carpeta` | `files.list(q="'padre' in parents and name = '…'")` → si no existe, `files.create(mimeType=folder)` |
| `restringir_herencia` | `files.update(body={"inheritedPermissionsDisabled": true})` |
| `conceder` | `permissions.create(type=group|user, role=reader|commenter|writer|fileOrganizer, sendNotificationEmail=false)` |

Todas las llamadas usan `supportsAllDrives=True`. La búsqueda previa hace que el proceso sea **idempotente**: si se corta a la mitad, se vuelve a ejecutar y continúa.

## 4.4 Verificación manual

1. Abra la unidad `OBR-2026-014_Edificio_Mirador` con el usuario del Director.
2. Clic derecho en `02_Finanzas_Costos` → *Compartir* → verifique que solo están ADM y DIR.
3. Inicie sesión con un usuario del grupo CON y confirme que **no** ve Finanzas ni Incidentes.
