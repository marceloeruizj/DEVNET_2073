# Capacitación: Agentes de IA con Amazon Bedrock

### Caso práctico: un agente que crea la estructura documental de proyectos de construcción con accesos por rol (Google Drive / Microsoft 365)

Al terminar esta capacitación usted sabrá:

1. Qué es un agente de IA y en qué se diferencia de un chatbot o de un script.
2. Cómo funcionan **Amazon Bedrock** y **Amazon Bedrock AgentCore** (modelo, instrucciones, herramientas, bucle agéntico, confirmación humana, despliegue).
3. Diseñar una **estructura estándar de carpetas** para proyectos de construcción y una **matriz de accesos por rol**.
4. Conectar el agente con **Google Drive** (unidades compartidas) y **Microsoft 365** (SharePoint vía Microsoft Graph).
5. Desplegar el agente en **AgentCore Runtime**, probarlo y operarlo con seguridad.

---

## Agenda (≈ 8 horas, en 2 jornadas o 4 bloques)

| # | Módulo | Duración | Tipo |
|---|--------|----------|------|
| 1 | [¿Qué es un agente de IA?](docs/01-que-es-un-agente.md) | 45 min | Teoría |
| 2 | [Amazon Bedrock y AgentCore](docs/02-amazon-bedrock.md) | 60 min | Teoría + consola |
| 3 | [Diseño de la estructura documental y la matriz de roles](docs/03-estructura-y-roles.md) | 60 min | Diseño + lab |
| 4 | [Integración con Google Workspace](docs/04-google-workspace.md) | 45 min | Configuración |
| 5 | [Integración con Microsoft 365](docs/05-microsoft-365.md) | 45 min | Configuración |
| 6 | [Construir y desplegar el agente](docs/06-construir-y-desplegar.md) | 90 min | Lab principal |
| 7 | [Seguridad, gobierno y operación](docs/07-seguridad-y-gobierno.md) | 45 min | Buenas prácticas |
| 8 | [Laboratorios y ejercicios](docs/08-laboratorios.md) | 90 min | Práctica |

> **Ruta rápida (30 min, sin nube):** módulos 1 → 3 → laboratorio 1 y 2 del módulo 8. Todo corre en modo simulación en su computador.

---

## Arquitectura de la solución

```
 Usuario (PM / Oficina de Proyectos)
        │  "Crea la estructura del proyecto OBR-2026-014 en SharePoint"
        ▼
 ┌─────────────── Amazon Bedrock AgentCore Runtime ────────────────┐
 │  Agente "Arquitecto Documental"  (src/agente_runtime.py)        │
 │   • Bucle agéntico (agente.py) + instrucciones                  │
 │   • Modelo: Claude en Amazon Bedrock                            │
 │   • Herramientas:                                               │
 │       - listar_roles_y_plantilla                                │
 │       - previsualizar_estructura   (dry-run)                    │
 │       - crear_estructura           (pausa → confirmación humana)│
 │   • Observability (trazas) · sesión aislada por usuario         │
 └──────────────────────────────┬──────────────────────────────────┘
                                │  plantilla JSON + planificador de permisos
                                │  credenciales en AWS Secrets Manager
                 ┌──────────────┴─────────────┐
                 ▼                            ▼
        Google Drive API v3          Microsoft Graph + SharePoint REST
        (unidad compartida)          (biblioteca de documentos)
```

**Idea clave:** el modelo *decide* (qué preguntar, qué herramienta usar, cómo explicar); el código *ejecuta* de forma determinista (qué carpetas y permisos exactos). El agente nunca inventa permisos: los calcula la plantilla.

> **Nota (nov. 2026):** Amazon Bedrock Agents pasó a llamarse *Bedrock Agents Classic* y está en modo mantenimiento desde el 30-07-2026 (cerrado a clientes nuevos). Por eso la ruta principal de este curso es **AgentCore Runtime**. La variante Classic se incluye como anexo para cuentas que ya la usan.

---

## Contenido del repositorio

```
capacitacion-agentes-bedrock/
├── README.md                       ← este índice
├── docs/                           ← los 8 módulos
├── src/
│   ├── agente_runtime.py           ← punto de entrada en AgentCore Runtime
│   ├── requirements.txt            ← dependencias del runtime
│   ├── lambda_function.py          ← (Anexo A) adaptador Lambda para Bedrock Agents Classic
│   └── agente_carpetas/
│       ├── agente.py               ← el bucle agéntico + confirmación humana
│       ├── instrucciones.md        ← "prompt de sistema" del agente
│       ├── herramientas.py         ← herramientas + sus definiciones (JSON Schema)
│       ├── estructura.py           ← planificador: herencia y permisos efectivos
│       ├── ejecutor.py             ← aplica el plan (idempotente) + proveedor simulado
│       ├── plantillas/plantilla_construccion.json   ← estructura estándar + roles
│       └── proveedores/
│           ├── google_drive.py     ← Google Drive API v3
│           └── microsoft_365.py    ← Microsoft Graph + SharePoint REST
├── scripts/
│   ├── vista_previa.py             ← ver el árbol sin IA ni nube
│   ├── agente_local.py             ← conversar con el agente en su computador
│   ├── conversar_con_agentcore.py  ← chat con el agente desplegado en AgentCore
│   ├── desplegar_classic.sh        ← (Anexo A) despliegue Classic
│   └── conversar_con_agente_classic.py
├── infra/classic/template.yaml     ← (Anexo A) CloudFormation Classic
└── tests/test_agente.py            ← 23 pruebas sin nube (incluye el bucle con un modelo falso)
```

## Inicio rápido

```bash
cd capacitacion-agentes-bedrock
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# 1) Pruebas (sin nube, sin costo)
python -m pytest -q

# 2) Ver la estructura que crearía el agente
python scripts/vista_previa.py OBR-2026-014 "Edificio Mirador" constructora.com

# 3) Conversar con el agente en su computador (usa Claude en Bedrock; modo simulación)
python scripts/agente_local.py --region us-east-1

# 4) Desplegar en AgentCore Runtime
cd src
agentcore configure --entrypoint agente_runtime.py --name arquitecto_documental --region us-east-1
agentcore deploy --env MODO_SIMULACION=true
agentcore status                                   # copie el agentRuntimeArn
python ../scripts/conversar_con_agentcore.py --arn <agentRuntimeArn>
```

## Requisitos previos

- Cuenta AWS con acceso a Amazon Bedrock, a un modelo Claude habilitado en su región (*Bedrock → Model access*) y a AgentCore.
- AWS CLI v2 configurado, Python 3.12+.
- Para producción: administrador de Google Workspace **o** de Microsoft 365 (Entra ID + SharePoint).
