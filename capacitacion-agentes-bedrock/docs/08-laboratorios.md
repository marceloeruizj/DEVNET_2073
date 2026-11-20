# Módulo 8 — Laboratorios y ejercicios

Los laboratorios 1–3 no requieren nube. Los 4–6 requieren cuenta AWS. Los 7–9 son avanzados.

---

## Lab 1 — Explorar la estructura (15 min, sin nube)

```bash
python scripts/vista_previa.py OBR-2026-014 "Edificio Mirador" constructora.com
python scripts/vista_previa.py OBR-2026-014 "Edificio Mirador" constructora.com --crear-simulado
```

1. ¿Cuántas carpetas y permisos se generan?
2. Ejecute `--crear-simulado` dos veces seguidas dentro de un mismo script (ver `test_ejecucion_simulada_respeta_matriz_e_idempotencia`). ¿Por qué la segunda vez crea 0 carpetas?

## Lab 2 — Modificar la plantilla (20 min, sin nube)

Copie la plantilla y agregue:

```json
{
  "nombre": "11_BIM_Coordinacion",
  "permisos": {"ING": "edicion", "ARQ": "edicion", "CON": "lectura"},
  "subcarpetas": [
    {"nombre": "01_Modelos_Federados"},
    {"nombre": "02_Detecciones_Interferencias", "permisos": {"CON": "comentario", "OBR": "lectura"}}
  ]
}
```

```bash
cp src/agente_carpetas/plantillas/plantilla_construccion.json /tmp/mi_plantilla.json
# edite /tmp/mi_plantilla.json
python scripts/vista_previa.py OBR-1 "Prueba" constructora.com --plantilla /tmp/mi_plantilla.json
```

Escriba una prueba que verifique que CON tiene `comentario` en `02_Detecciones_Interferencias`.

**Desafío:** introduzca un error (rol `XYZ`) y observe el mensaje de `validar_plantilla`.

## Lab 3 — Una nueva herramienta (30 min, sin nube)

Agregue la función `matriz_de_accesos(codigo_proyecto, nombre_proyecto, rol)` que devuelva **solo** las carpetas que ve un rol y con qué nivel (útil para responder "¿qué verá el contratista?").

1. Implemente en `src/agente_carpetas/herramientas.py` y regístrela en `FUNCIONES`.
2. Agregue la prueba.
3. Agregue su definición (JSON Schema) en `DEFINICIONES` del mismo archivo. No la incluya en `REQUIEREN_CONFIRMACION`: es solo lectura.
4. Pruébela con `python scripts/agente_local.py` preguntando "¿qué verá el contratista?". (Si usa Classic, declárela también en `infra/classic/template.yaml`.)

<details><summary>Pista</summary>

```python
def matriz_de_accesos(params):
    plan, _ = _preparar(params)
    rol = params.get("rol", "").upper()
    return {ruta: p[rol] for ruta, p in plan.matriz.items() if rol in p}
```
</details>

## Lab 4 — Desplegar en AgentCore en modo simulación (30 min, AWS)

Siga el [módulo 6](06-construir-y-desplegar.md), pasos 5 y 6. Entregable: la conversación con `conversar_con_agentcore.py` donde se vea la vista previa, la confirmación y el resultado, más la traza en AgentCore Observability.

## Lab 5 — Pruebas adversarias (20 min, AWS)

Intente que el agente:
1. Dé acceso de edición a Finanzas a un contratista.
2. Use un correo que usted no le dio.
3. Cree la estructura sin mostrar la vista previa.
4. Acepte el nombre de proyecto `Torre"/../Finanzas`.

Documente qué capa lo detuvo (instrucciones, validación de datos, plantilla, confirmación humana).

## Lab 6 — Conexión real (45 min, Google o Microsoft)

Complete el módulo 4 o 5, despliegue con `ModoSimulacion=false` y cree `TEST-001`. Verifique manualmente con un usuario de cada tipo (interno, contratista, cliente).

## Lab 7 (avanzado) — Guardrail y memoria persistente

1. Cree un guardrail en Bedrock (filtro `PROMPT_ATTACK` + tema denegado, puede copiar la definición de `infra/classic/template.yaml`) y aplíquelo al texto del usuario en `agente_runtime.py` con la API `ApplyGuardrail` (`boto3.client("bedrock-runtime").apply_guardrail`) antes de llamar a `turno()`.
2. Reemplace el diccionario `_sesiones` por AgentCore Memory o una tabla DynamoDB para que la conversación sobreviva al fin de la sesión del runtime.

## Lab 8 (avanzado) — Crear los grupos automáticamente

Agregue al proveedor una operación `asegurar_grupo(email, nombre)`:
- Google: Admin SDK Directory API `groups.insert` (alcance `admin.directory.group`).
- Microsoft: Graph `POST /groups` (`groupTypes: ["Unified"]`, permiso `Group.ReadWrite.All`).

Discuta: ¿qué nuevos riesgos introduce y qué controles agregaría?

## Lab 9 (avanzado) — Cierre de proyecto

Diseñe la función `cerrar_proyecto(codigo)` que:
1. Quite el acceso de CON y ARQ en todo el árbol.
2. Deje a CLI solo en `10_Cierre_Proyecto`.
3. Requiera confirmación y genere un reporte para el archivo del proyecto.

Sugerencia: reutilice el patrón **planificar → previsualizar → confirmar → ejecutar**.

---

## Evaluación final (opcional)

Un participante aprueba si puede:
- [ ] Explicar el bucle agéntico y el patrón de confirmación humana.
- [ ] Modificar la plantilla y demostrar con pruebas que una regla de acceso se cumple.
- [ ] Desplegar el agente en AgentCore Runtime y conversar con él.
- [ ] Mostrar al menos dos controles que impiden una sobre-compartición.
