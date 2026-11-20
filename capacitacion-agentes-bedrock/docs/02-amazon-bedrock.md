# Módulo 2 — Amazon Bedrock y Amazon Bedrock AgentCore

## 2.1 El panorama de agentes en AWS (noviembre 2026)

| Servicio | Qué es | Estado |
|---|---|---|
| **Amazon Bedrock** | Acceso administrado por API a modelos fundacionales (Anthropic Claude, Amazon Nova, Llama, Mistral…). Sus datos no se usan para entrenar modelos. | Activo |
| **Amazon Bedrock AgentCore** | Plataforma para **hospedar y operar agentes** en producción: runtime, herramientas, memoria, identidad, observabilidad, políticas. Funciona con cualquier framework y cualquier modelo. | **Activo — ruta recomendada** |
| **Bedrock Guardrails / Knowledge Bases** | Filtros de seguridad y RAG administrado. | Activos |
| **Bedrock Agents (ahora "Classic")** | Agentes configurados por consola con *action groups* en Lambda (lanzado en 2023). | **Modo mantenimiento desde el 30-07-2026**: cerrado a clientes nuevos, catálogo de modelos congelado. Las cuentas existentes pueden seguir usándolo. |

> **Consecuencia para esta capacitación:** construimos el agente sobre **AgentCore Runtime**. Si su cuenta ya usa Bedrock Agents Classic, el [Anexo A del módulo 6](06-construir-y-desplegar.md#anexo-a--bedrock-agents-classic-solo-cuentas-existentes) trae la versión equivalente (CloudFormation + Lambda), y AWS ofrece herramientas para migrar agentes Classic a AgentCore.

## 2.2 Componentes de AgentCore

| Componente | Para qué sirve | ¿Lo usamos? |
|---|---|---|
| **Runtime** | Hospeda el código del agente en microVMs aisladas **por sesión**, escala solo, sesiones de hasta 8 h. Endpoint `InvokeAgentRuntime`. | ✅ Núcleo del curso |
| **Gateway** | Convierte Lambdas y APIs en herramientas MCP reutilizables por varios agentes. | Lab avanzado |
| **Memory** | Memoria de corto y largo plazo administrada. | Lab avanzado (hoy: memoria de sesión en el proceso) |
| **Identity** | Gestión de credenciales/OAuth hacia servicios de terceros (Google, Microsoft) y autenticación de usuarios. | Mención (hoy: Secrets Manager) |
| **Observability** | Trazas, métricas y logs de cada paso del agente (OpenTelemetry → CloudWatch). | ✅ Activado por defecto |
| **Policy / Evaluations** | Reglas sobre qué herramientas puede invocar el agente; evaluación de calidad. | Mención |

## 2.3 Anatomía de nuestro agente

```
AgentCore Runtime  ("arquitecto_documental")
└── agente_runtime.py           ← @app.entrypoint: recibe {"prompt"} / {"confirmacion"}
    └── AgenteCarpetas.turno()  ← el bucle agéntico (src/agente_carpetas/agente.py)
        ├── Modelo: Claude en Bedrock (anthropic.claude-opus-5-5)
        ├── Instrucciones: src/agente_carpetas/instrucciones.md
        └── Herramientas (src/agente_carpetas/herramientas.py)
            ├── listar_roles_y_plantilla     (lectura)
            ├── previsualizar_estructura     (cálculo, sin escribir)
            └── crear_estructura             (escribe → requiere confirmación humana)
                 └── Proveedores: Google Drive API / Microsoft Graph + SharePoint REST
```

### Las herramientas, vistas por el modelo

Cada herramienta se describe con un nombre, una descripción y un **JSON Schema** de parámetros. El modelo **solo ve esto** para decidir cuándo y cómo usarla:

```json
{
  "name": "previsualizar_estructura",
  "description": "Calcula SIN crear nada el arbol de carpetas y los accesos efectivos por rol. Usar siempre antes de crear y mostrar el resultado al usuario.",
  "input_schema": {
    "type": "object",
    "properties": {
      "codigo_proyecto": {"type": "string", "description": "Codigo unico del proyecto... Ej. OBR-2026-014"},
      "nombre_proyecto": {"type": "string", "description": "Nombre descriptivo del proyecto"},
      "dominio": {"type": "string", "description": "Dominio de correo para la convencion de grupos..."},
      "asignaciones_json": {"type": "string", "description": "JSON rol -> lista de correos..."}
    },
    "required": ["codigo_proyecto", "nombre_proyecto", "dominio", "asignaciones_json"],
    "additionalProperties": false
  },
  "strict": true
}
```

`strict: true` garantiza que los argumentos que genera el modelo cumplan el esquema.

### Una vuelta del bucle

1. Enviamos al modelo: instrucciones + herramientas + historial.
2. El modelo responde con texto y/o bloques `tool_use` (`stop_reason: "tool_use"`).
3. Ejecutamos las herramientas y devolvemos **todos** los `tool_result` en un solo mensaje.
4. Repetimos hasta `stop_reason: "end_turn"` (el agente espera al usuario).

### Confirmación humana (*human-in-the-loop*)

Si el modelo pide `crear_estructura`, el bucle **se detiene** y devuelve `pendiente` al cliente. El cliente muestra los parámetros, y en el siguiente turno envía `{"confirmacion": true}` o `false`. Solo entonces se ejecuta (o se informa al modelo que el usuario no autorizó).

## 2.4 Elección del modelo

- Usamos **Claude** en Bedrock, ID `anthropic.claude-opus-5-5` (variable `MODELO` para cambiarlo).
- Habilítelo antes en *Bedrock → Model access* de su región.
- El parámetro `effort` (`low`/`medium`/`high`) controla cuánto "piensa" el modelo: `medium` es suficiente para este agente; súbalo si ve errores de razonamiento.
- Costo: se cobra por tokens. Un flujo completo (preguntar → previsualizar → crear) son pocas llamadas al modelo.

## 2.5 AgentCore vs. Bedrock Agents Classic

| | AgentCore Runtime (este curso) | Bedrock Agents Classic (Anexo A) |
|---|---|---|
| Disponibilidad | Todos los clientes | Solo cuentas existentes; en mantenimiento |
| Cómo se define el agente | Código (Python, cualquier framework) | Configuración (consola / CloudFormation) |
| Herramientas | Funciones en el mismo código, o Gateway (MCP) | *Action groups* en Lambda |
| Confirmación humana | Patrón propio (pausa del bucle) | `RequireConfirmation` + `returnControl` |
| Modelos | Todo el catálogo de Bedrock | Catálogo congelado al 30-07-2026 |

## Preguntas de repaso

1. ¿Qué ve el modelo de una herramienta y qué **no** ve?
2. ¿Por qué `crear_estructura` exige confirmación y `previsualizar_estructura` no?
3. ¿Qué aporta AgentCore Runtime frente a ejecutar el agente en su propio servidor?
