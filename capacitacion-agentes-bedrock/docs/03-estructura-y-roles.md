# Módulo 3 — Estructura documental estándar y matriz de roles

## 3.1 Objetivos de la estructura

- **Igual en todos los proyectos**: cualquier persona encuentra un documento sin preguntar.
- **Numerada** (`00_`, `01_`…): el orden no depende del alfabeto ni del idioma.
- **Separada por función** (administración, contratos, diseño, obra, calidad, seguridad…), porque los **accesos** siguen a las funciones.
- **Mínimo privilegio**: cada rol ve solo lo que necesita; los externos (arquitectos, contratistas, cliente) ven aún menos.

Referencias útiles: ISO 19650 (gestión de información en proyectos BIM), PMBOK (áreas de conocimiento) y la política documental de su empresa.

## 3.2 Roles del proyecto

| Código | Rol | Interno |
|---|---|---|
| DIR | Director / Gerente de Proyecto | Sí — **acceso de gestión en todo** (rol global) |
| ADM | Administración y Finanzas | Sí |
| LEG | Legal y Contratos | Sí |
| ING | Ingeniería / Oficina Técnica | Sí |
| ARQ | Arquitectura y Diseño (consultores) | **No** |
| OBR | Residente / Jefe de Obra | Sí |
| CAL | Calidad QA/QC | Sí |
| SSO | Seguridad, Salud Ocupacional y Medio Ambiente | Sí |
| CON | Contratistas y Subcontratistas | **No** |
| CLI | Cliente / Mandante | **No** |

### Niveles de acceso

| Nivel | Google Drive | SharePoint / OneDrive |
|---|---|---|
| `lectura` | Lector (`reader`) | Leer (`read`) |
| `comentario` | Comentador (`commenter`) | Leer (`read`)* |
| `edicion` | Editor (`writer`) | Editar (`write`) |
| `gestion` | Administrador de contenido (`fileOrganizer`) / Administrador de la unidad en la raíz | Editar (`write`)* |

\* SharePoint no tiene "comentador" ni "organizador" en las invitaciones de Graph; se mapea al nivel más cercano sin exceder privilegios.

## 3.3 La estructura (vista previa real del agente)

Generada con `python scripts/vista_previa.py OBR-2026-014 "Edificio Mirador" constructora.com`:

```
OBR-2026-014_Edificio_Mirador/  [DIR:gestion]
    00_Administracion_Proyecto/  [ADM:edicion, DIR:gestion, LEG:lectura, OBR:lectura]
        01_Acta_Constitucion/
        02_Cronograma/            (+ ING, CAL, SSO lectura)
        03_Actas_Reuniones/       (+ ING comentario)
        04_Informes_Gestion/      (+ CLI lectura)
    01_Contratos_Legal/  [ADM:lectura, DIR:gestion, LEG:edicion]
        01_Contrato_Principal/
        02_Subcontratos/          (+ OBR lectura)
        03_Garantias_Polizas/
        04_Permisos_Licencias/    (+ ING, OBR, SSO lectura)
    02_Finanzas_Costos/  [ADM:edicion, DIR:gestion]          ← ningún externo
        01_Presupuesto/  02_Estados_Pago/  03_Ordenes_Compra/  04_Facturacion/
    03_Diseno_Ingenieria/  [ARQ:edicion, CAL:lectura, DIR:gestion, ING:edicion, OBR:lectura]
        01_Arquitectura/  02_Estructuras/  03_Instalaciones_MEP/  04_Modelos_BIM/
        05_Especificaciones_Tecnicas/  (+ CON lectura)
    04_Planos/  [ARQ:lectura, DIR:gestion, ING:gestion, OBR:lectura]
        01_En_Revision/                    (+ ARQ edicion)
        02_Aprobados_Para_Construccion/    (+ CAL, SSO, CON, CLI lectura)
        03_As_Built/                       (+ CLI, CAL lectura)
    05_Construccion_Obra/  [CAL, ING, SSO lectura; OBR edicion]
        01_Libro_Obra/  02_Informes_Diarios/  03_Fotografias/ (+CLI)
        04_RFI_Consultas/ (+ CON, ING edicion)   05_Ordenes_Cambio/ (+ ADM, LEG lectura)
    06_Calidad_QAQC/  [CAL:edicion, ING, OBR lectura]
        01_Plan_Calidad/  02_Protocolos_Inspeccion/  03_No_Conformidades/  04_Ensayos_Laboratorio/
    07_Seguridad_SSOMA/  [SSO:edicion, OBR, CON lectura]
        01_Plan_Seguridad/
        02_Incidentes_Accidentes/  [DIR, SSO, LEG]   ← NO HEREDA (información sensible)
        03_Capacitaciones/ (+ CON edicion)   04_Inspecciones_Seguridad/
    08_Subcontratistas/  [OBR:edicion, ADM:lectura]
        01_Documentacion_Contratistas/   02_Entregables_Contratistas/ (+ CON edicion)
    09_Comunicaciones_Cliente/  [CLI, ADM lectura]
        01_Correspondencia_Enviada/  02_Correspondencia_Recibida/  03_Entregas_Cliente/
    10_Cierre_Proyecto/  [ADM, CAL edicion; OBR lectura]
        01_Recepcion_Obra/  02_Manuales_Operacion/  03_Lecciones_Aprendidas/
```

Resumen: **53 carpetas, 74 permisos, 2 cortes de herencia** (raíz y Incidentes).

## 3.4 Cómo se calculan los permisos (reglas de herencia)

La plantilla vive en [`src/agente_carpetas/plantillas/plantilla_construccion.json`](../src/agente_carpetas/plantillas/plantilla_construccion.json). Cada carpeta puede tener:

```json
{
  "nombre": "02_Incidentes_Accidentes",
  "heredar": false,
  "permisos": {"SSO": "edicion", "LEG": "lectura"}
}
```

1. **Herencia**: una carpeta recibe los permisos de su padre…
2. **…más** los suyos propios. Si un rol aparece en ambos, gana el **nivel más alto**.
3. `"heredar": false` **corta** la herencia: parte de cero (más los `roles_globales`).
4. `roles_globales` (DIR = gestión) se aplica en la raíz y en todo corte de herencia.

Optimización: en carpetas que heredan, el agente solo concede el **delta** (lo nuevo); el resto ya llega por herencia. Así hay menos permisos explícitos que auditar.

> ⚠️ Importante: la herencia solo **suma** accesos. Para *quitar* acceso a una subcarpeta hay que **cortar la herencia** (`heredar: false`). Úselo con moderación: cada corte es una excepción que hay que mantener.

## 3.5 Asignación de personas: grupos, no individuos

Siempre conceda acceso a **grupos**, nunca a personas sueltas:

- Convención: `proy-{codigo}-{rol}@{dominio}` → `proy-obr-2026-014-ing@constructora.com`.
- Cuando alguien entra o sale del proyecto, se cambia la **membresía del grupo**, no los permisos de 53 carpetas.
- Externos (CON, CLI, ARQ): grupos que contienen a las cuentas invitadas.

Si un rol no tiene grupo, el agente lo advierte en la vista previa y **no concede nada** a ese rol.

Formato de asignaciones explícitas (cuando no se usa la convención):

```json
{
  "DIR": ["pm.mirador@constructora.com"],
  "ING": ["oficina.tecnica@constructora.com"],
  "CLI": ["usuario:ana.perez@inmobiliaria.cl"]
}
```

El prefijo `usuario:` indica una persona en lugar de un grupo.

## 3.6 Laboratorio rápido

```bash
python scripts/vista_previa.py OBR-2026-014 "Edificio Mirador" constructora.com
python -m pytest -q tests/test_agente.py -k "herencia or sensible or finanzas"
```

Preguntas:
1. ¿Qué rol puede ver `05_Ordenes_Cambio` y por qué ADM tiene acceso ahí y no en el resto de la obra?
2. ¿Qué pasaría si quitamos `"heredar": false` de `02_Incidentes_Accidentes`?
3. Proponga una carpeta `11_BIM_Coordinacion` con sus permisos y valide con la vista previa.
