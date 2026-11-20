# Módulo 6 — Construir y desplegar el agente (laboratorio principal)

Orden recomendado para cualquier agente:

```
1. Lógica determinista + pruebas → 2. Herramientas → 3. Instrucciones → 4. Bucle agéntico
→ 5. Probar local → 6. Desplegar en AgentCore Runtime → 7. Conectar Google / Microsoft
```

## Paso 1 — Lógica y pruebas (sin IA, sin nube)

```bash
cd capacitacion-agentes-bedrock
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q          # 23 passed
```

`construir_plan()` (`src/agente_carpetas/estructura.py`) transforma la plantilla en operaciones (`crear_raiz`, `crear_carpeta`, `restringir_herencia`, `conceder`). **Separar planificar de ejecutar es lo que permite la vista previa.**

## Paso 2 — Las herramientas

`src/agente_carpetas/herramientas.py`:

| Herramienta | Efecto | Confirmación |
|---|---|---|
| `listar_roles_y_plantilla` | Solo lectura | No |
| `previsualizar_estructura` | Solo cálculo (dry-run) | No |
| `crear_estructura` | **Escribe** en Google/Microsoft | **Sí** (`REQUIEREN_CONFIRMACION`) |

Buenas prácticas aplicadas:
- **Descripciones claras** (`DEFINICIONES`): el modelo decide solo con ellas.
- **Errores accionables**: un dato inválido vuelve al modelo como `is_error` con un mensaje que puede explicar al usuario ("el código debe tener 2-20 caracteres…").
- **Idempotencia**: ejecutar dos veces no duplica carpetas.
- **Auditoría**: cada creación se registra en el log con parámetros y resultado.
- **Modo simulación** (`MODO_SIMULACION=true`): nada toca Google ni Microsoft.

## Paso 3 — Las instrucciones

Archivo: [`src/agente_carpetas/instrucciones.md`](../src/agente_carpetas/instrucciones.md). Estructura:

1. **Identidad y objetivo** — quién es y qué logra.
2. **Proceso** — reunir datos → previsualizar → aprobar → crear → informar.
3. **Reglas** — qué nunca hacer (inventar correos, dar accesos fuera de plantilla).
4. **Tono** — idioma y estilo.

Consejos: explique el **porqué** de las reglas; no repita lo que ya dicen las descripciones de las herramientas; pruebe con usuarios que dan datos incompletos o piden excepciones.

## Paso 4 — El bucle agéntico

[`src/agente_carpetas/agente.py`](../src/agente_carpetas/agente.py), método `turno()`. Puntos a observar en clase:

- La llamada al modelo: `messages.create(model, system, tools, messages, output_config={"effort": ...})`.
- El `while` que sigue mientras `stop_reason == "tool_use"`, con un tope (`MAX_VUELTAS`) contra bucles infinitos.
- La **pausa** cuando aparece una herramienta que escribe, y cómo se reanuda con `confirmacion`.
- Las pruebas `test_agente_*` usan un **modelo falso** con respuestas guionadas: así se prueba el bucle sin red ni costo.

## Paso 5 — Probar en su computador

Requiere credenciales AWS con acceso al modelo (`aws configure` o `aws sso login`).

```bash
python scripts/agente_local.py --region us-east-1
```

Guion de prueba:

```
Usted: Necesito la carpeta para el nuevo proyecto Hospital Norte
Agente: (pide código, plataforma y dominio o grupos)
Usted: HOS-2026-03, en SharePoint, dominio constructora.com
  [herramienta] previsualizar_estructura
Agente: (muestra el árbol, destaca Incidentes y accesos de externos)
Usted: Aprobado, créala
>>> Accion pendiente: crear_estructura  {...}
¿Confirmar? [s/N]: s
  [herramienta] crear_estructura
Agente: Se crearon 52 carpetas y 74 permisos...
```

Pruebas negativas (el agente debe manejarlas bien):
- "Dale al contratista edición en Finanzas" → debe negarse.
- Código `proyecto nuevo` → debe pedir un código válido.
- Responder **N** en la confirmación → no se crea nada.

## Paso 6 — Desplegar en AgentCore Runtime

Usaremos el CLI `agentcore` (paquete `bedrock-agentcore-starter-toolkit`, ya instalado con `requirements-dev.txt`). El punto de entrada es [`src/agente_runtime.py`](../src/agente_runtime.py):

```python
app = BedrockAgentCoreApp()

@app.entrypoint
def invocar(payload: dict, context=None) -> dict:
    sesion_id = payload.get("sesion") or getattr(context, "session_id", None) or "por-defecto"
    ...
    return _agente.turno(sesion, texto=payload.get("prompt"), confirmacion=...)
```

### 6.1 Probar el servidor localmente

```bash
cd src
python agente_runtime.py            # servidor en http://localhost:8080
# en otra terminal:
curl -s localhost:8080/invocations -H "Content-Type: application/json" \
  -H "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: prueba-local-0123456789abcdefghijk" \
  -d '{"prompt": "¿Qué roles maneja la plantilla?"}'
```

(Con `MODO_SIMULACION=true` exportado si va a probar `crear_estructura`.)

### 6.2 Configurar y desplegar

```bash
cd src
agentcore configure --entrypoint agente_runtime.py --name arquitecto_documental --region us-east-1
#   detecta src/requirements.txt; acepte crear el rol de ejecución y el repositorio automáticamente
agentcore deploy --env MODO_SIMULACION=true --env MODELO=anthropic.claude-opus-5-5
agentcore status                    # muestra el ARN del agente (agentRuntimeArn)
```

`agentcore deploy` empaqueta el código, lo construye en la nube (no necesita Docker local) y crea/actualiza el runtime. Cada despliegue genera una versión inmutable.

> Si al conversar ve un error de acceso al modelo, el rol de ejecución creado por el toolkit no tiene el permiso de invocación para ese modelo: agregue al rol el permiso que indica el mensaje de error (y verifique en *Model access* que el modelo esté habilitado en la región).

### 6.3 Conversar con el agente desplegado

```bash
agentcore invoke '{"prompt": "Hola, ¿qué puedes hacer?"}'          # prueba rápida

python ../scripts/conversar_con_agentcore.py --arn <agentRuntimeArn>   # chat con confirmaciones
```

El cliente usa `boto3.client("bedrock-agentcore").invoke_agent_runtime(agentRuntimeArn=..., runtimeSessionId=..., payload=...)`. El mismo `runtimeSessionId` mantiene la conversación (AgentCore enruta la sesión a la misma microVM). Quien invoque necesita el permiso IAM `bedrock-agentcore:InvokeAgentRuntime`.

### 6.4 Observabilidad

`agentcore obs` y la consola de CloudWatch (sección GenAI Observability) muestran cada invocación, sus tiempos y errores. Los registros de auditoría de `crear_estructura` quedan en los logs del runtime.

## Paso 7 — Conectar Google o Microsoft

1. Complete el módulo 4 y/o 5 y cree los secretos en Secrets Manager.
2. Dé al **rol de ejecución** del runtime permiso para leer solo esos secretos:

```bash
ROL=<nombre-del-rol-de-ejecucion>   # aparece en agentcore status / bedrock_agentcore.yaml
aws iam put-role-policy --role-name "$ROL" --policy-name LeerSecretosProveedores \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"secretsmanager:GetSecretValue",
  "Resource":["arn:aws:secretsmanager:us-east-1:123456789012:secret:agente-carpetas/*"]}]}'
```

3. Vuelva a desplegar en modo real:

```bash
agentcore deploy --env MODO_SIMULACION=false \
  --env M365_SECRET_ARN=arn:aws:secretsmanager:us-east-1:123456789012:secret:agente-carpetas/m365-AbCdEf \
  --env GOOGLE_SECRET_ARN=arn:aws:secretsmanager:us-east-1:123456789012:secret:agente-carpetas/google-XyZ123
```

4. Pruebe primero con un **proyecto de prueba** (`TEST-001`) y verifique los permisos manualmente.

---

## Anexo A — Bedrock Agents Classic (solo cuentas existentes)

Si su cuenta ya usa Bedrock Agents Classic, puede desplegar el mismo agente como agente "Classic". Las herramientas son las mismas; cambia el hospedaje:

| Pieza | Archivo |
|---|---|
| Adaptador Lambda (contrato *function details*, `REPROMPT`/`FAILURE`) | `src/lambda_function.py` |
| Agente, *action group*, guardrail, alias, IAM | `infra/classic/template.yaml` |
| Despliegue | `scripts/desplegar_classic.sh <bucket-s3> [stack] [Parametro=valor...]` |
| Chat con `returnControl` (confirmación) | `scripts/conversar_con_agente_classic.py --agent-id … --alias-id …` |

Contrato de la Lambda — Bedrock envía:

```json
{"messageVersion": "1.0", "actionGroup": "GestionCarpetas", "function": "previsualizar_estructura",
 "parameters": [{"name": "codigo_proyecto", "type": "string", "value": "OBR-2026-014"}, ...],
 "sessionAttributes": {}, "promptSessionAttributes": {}}
```

y la Lambda responde con `response.functionResponse.responseBody.TEXT.body`. La confirmación se declara con `RequireConfirmation: ENABLED` y llega al cliente como evento `returnControl`.

Recuerde: Classic está en mantenimiento (sin modelos nuevos). Para desarrollos nuevos use AgentCore; AWS ofrece herramientas para migrar agentes Classic.
