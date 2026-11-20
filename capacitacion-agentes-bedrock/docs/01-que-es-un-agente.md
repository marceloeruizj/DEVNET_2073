# Módulo 1 — ¿Qué es un agente de IA?

## 1.1 Del chatbot al agente

| | Chatbot | Script / automatización | **Agente de IA** |
|---|---|---|---|
| Entiende lenguaje natural | ✅ | ❌ | ✅ |
| Actúa sobre sistemas reales | ❌ | ✅ | ✅ |
| Decide los pasos según la situación | ❌ | ❌ (pasos fijos) | ✅ |
| Pide datos que faltan | Limitado | ❌ (falla) | ✅ |

Un **agente** es un modelo de lenguaje (LLM) al que se le dan:

1. **Un objetivo e instrucciones** — quién es, qué debe lograr, qué reglas seguir.
2. **Herramientas** — funciones que puede invocar (APIs, bases de datos, Lambda).
3. **Un bucle** — el modelo piensa, llama una herramienta, lee el resultado y decide el siguiente paso, hasta terminar.
4. **Memoria de la sesión** — recuerda lo conversado para no volver a preguntar.

## 1.2 El bucle agéntico

```
            ┌──────────────────────────────────────────┐
            ▼                                          │
 Usuario → Modelo ──¿necesita una herramienta?── sí ──► Ejecutar herramienta
            │                                     (resultado vuelve al modelo)
            no
            ▼
       Respuesta al usuario
```

Ejemplo real con nuestro agente:

1. **Usuario:** "Crea la carpeta del proyecto Hospital Norte en SharePoint".
2. **Modelo:** le falta el código y los grupos → *pregunta* (no llama herramientas).
3. **Usuario:** "Código HOS-2026-03, dominio constructora.com".
4. **Modelo:** llama `previsualizar_estructura` → recibe el árbol → lo muestra y pide aprobación.
5. **Usuario:** "Aprobado".
6. **Modelo:** pide `crear_estructura` → el agente **se detiene** y pide **confirmación humana** → solo si el usuario acepta, se ejecuta.
7. **Modelo:** resume: "Se crearon 52 carpetas y 74 permisos. URL: …".

> En [`src/agente_carpetas/agente.py`](../src/agente_carpetas/agente.py) este bucle está programado a mano (método `turno`, ~60 líneas, incluida la pausa para confirmación humana). Léalo: es exactamente lo que corre dentro de AgentCore Runtime.

## 1.3 ¿Cuándo SÍ conviene un agente?

Use un agente cuando la tarea:
- requiere **conversación** para reunir datos incompletos o ambiguos,
- tiene **varios pasos** cuyo orden depende del contexto,
- el valor justifica el costo/latencia del modelo,
- los errores **se pueden prevenir o revertir** (vista previa, confirmación, idempotencia).

No use un agente si un formulario o un script fijo resuelve el problema. En nuestro caso conviene porque:
los PM piden la estructura en lenguaje natural, con datos incompletos, y deben **ver y aprobar** los permisos antes de aplicarlos.

## 1.4 Principio de diseño de esta capacitación

> **El modelo decide, el código ejecuta.**

- El modelo: conversa, elige herramientas, explica resultados.
- El código: calcula los permisos **exactos** a partir de una plantilla versionada.

Así el agente nunca "improvisa" accesos, y la lógica crítica se prueba con tests unitarios (ver `tests/`).

## Preguntas de repaso

1. ¿Qué cuatro elementos convierten un LLM en un agente?
2. ¿Por qué la creación de permisos no debería decidirla el modelo libremente?
3. Nombre una tarea de su empresa donde un agente **no** sería la mejor solución.
