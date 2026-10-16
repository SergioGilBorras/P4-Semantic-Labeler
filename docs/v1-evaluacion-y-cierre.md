# P4-Semantic-Labeler — Evaluación y cierre de alcance V1

**Corte de evidencia:** 2026-10-12. **Paquete declarado:** `0.1.0` en `pyproject.toml`.
**Estado:** alcance funcional V1 cerrado y publicación GitHub `v0.1.0` completada, con limitaciones semánticas documentadas. La fecha del corte de evidencia no cambia por las verificaciones posteriores.
La expresión **V1** identifica el hito funcional acordado; no equivale automáticamente a una versión SemVer `1.0.0`.

## Alcance y cobertura

Servicio neutral respecto al dominio, disponible como biblioteca Python, CLI, FastAPI y MCP local, con proveedores `codex`, `mock` y `disabled`. El corpus original de 60 casos y las rúbricas estaban congelados durante la evaluación.

| Grupo | Casos | Evidencia |
|---|---:|---|
| Etiquetado real con Codex | 58 | Al menos una inferencia real exitosa por cada caso `SL-` válido |
| Validación negativa `SL-0053` y `SL-0054` | 2 | Rechazo validado localmente, sin inferencia de pago |
| **Cobertura total del corpus original** | **60/60** | **100 % de ejecución conforme a finalidad** |

La cobertura no demuestra que el 100 % de las etiquetas hayan obtenido una calificación semántica aprobatoria. Se ejecutaron además tres casos experimentales `MIN-0001` a `MIN-0003`, con tres resultados reales cada uno: **no pertenecen al corpus original de 60**.

## Consolidado histórico verificado

Fuente: `evaluacion/salida/evaluation-summary.json` generado el 2026-10-12T11:59:31Z, comprobado a partir de la copia final compartida, 231 ejecuciones, 258 resultados, `complete=true`, sin carpetas omitidas. Huella SHA-256 de la copia analizada: `6060b77dff23432fb2f30bc8ee52aa642b204a82cd2d0dfeda2fbd74a5cc7a86`.

| Resultado | Total |
|---|---:|
| Ejecuciones / resultados históricos | 231 / 258 |
| Resultados de Codex / mock | 250 / 8 |
| `COMPLETED` de Codex / mock | 231 / 8 |
| `SEMANTIC_REVIEW_REQUIRED` de Codex | 15 |
| `ERROR` de Codex (`CODEX_EXIT_NONZERO`) | 4 |
| Salidas reales con etiqueta de Codex | 246 |
| Salidas con `needs_semantic_review=true` | **17** |
| Comprobaciones objetivas positivas en resultados con etiqueta | **254/254** |
| Tasa observada de error técnico de Codex | **4/250 = 1,60 %** |
| Advertencias de revisión por salida de Codex | **17/246 = 6,91 %** |

Las 17 advertencias se distribuyen en `SL-0001` (1), `SL-0002` (6) y `SL-0047` (10). Quince figuran con estado explícito `SEMANTIC_REVIEW_REQUIRED`, y dos registros históricos aparecen como `COMPLETED` **pero igualmente contienen la advertencia**. Por ello **239 estados `COMPLETED` no significan 239 aprobaciones semánticas**.

Estas proporciones describen un histórico con repeticiones, distintos prompts y usos atípicos de Codex; **no son estimaciones de rendimiento en producción**. No se han cotejado las huellas de prompt de cada manifiesto nuevo con las versiones en uso al cierre, pues el consolidado no exporta esos hashes.

## Casos límite y anomalías

**`SL-0047` (permiso insuficiente):** 20 respuestas reales, 10 `COMPLETED` y 10 `SEMANTIC_REVIEW_REQUIRED`, sin errores técnicos. `Solicitud rechazada por falta de permisos` (41 caracteres) transmite la causa claramente; variantes recortadas como `Solicitud rechazada por permisos` (32) son menos precisas y se señalaron para revisión. Se utilizó `ReductionAttempts=0`, por lo que no se solicitó una reformulación cuando el candidato inicial excedía `max_chars=43`. El recorte preservó el límite, pero puede reducir fidelidad. No se ha demostrado que las ejecuciones concurrentes de otros proyectos causen las advertencias.

**`SL-0051` (límite extremo):** tres respuestas `COMPLETED` de un carácter: `→`, `R`, `R`. Todas cumplen `max_chars=1`, ninguna generó una advertencia de revisión automática, y ninguna es una descripción suficientemente informativa de una solicitud de red genérica. Es evidencia de la diferencia entre éxito técnico y utilidad semántica; no constituye una puntuación independiente de la rúbrica completa.

**`SL-0002`:** seis etiquetas históricas marcadas por truncamiento, incluidas frases incompletas como `Caché caducada: renovar antes de`; otras repeticiones generaron títulos completos. **`SL-0001`:** un resultado histórico `COMPLETED` con advertencia de truncamiento, y un error técnico histórico. Los cuatro errores `CODEX_EXIT_NONZERO` se registran en `SL-0001`, `SL-0019`, `SL-0038` y `SL-0049`, conservando las respuestas posteriores exitosas.

## Criterio semántico y alcance de la revisión

Las rúbricas congeladas puntúan funcionalidad (25 %), fidelidad (35 %), utilidad (20 %), cobertura (10 %), coherencia (5 %) y seguridad (5 %), en escala 0–4. Para aceptar una etiqueta exigen ponderada >=3,2, funcionalidad >=3, fidelidad >=3 y ningún fallo crítico.

El laboratorio confirma estados y controles objetivos; **no asigna por sí solo estas puntuaciones**. Existe una revisión asistida preliminar de una muestra de 87 etiquetas anteriores, pero no una evaluación humana independiente, ciega y exhaustiva de las 246 respuestas reales. No se declara una tasa global de aprobación semántica ni se convierten automáticamente `COMPLETED` en aprobados. Las salidas extremas, truncadas o con posible pérdida de negación/causalidad requieren revisión contextual antes de emplearlas en aplicaciones donde la fidelidad sea crítica.

## Verificaciones de desarrollo y limitaciones aceptadas

Últimos controles locales comunicados: `pip check` sin dependencias rotas; **114 pruebas pytest aprobadas y 1 omitida**; `ruff check .` sin infracciones; laboratorio validado con `initial_cases=60`, `accumulated_cases=60`. Son resultados locales documentados al cierre. Posteriormente se verificó que la CI del commit de publicación `0179888` superó los seis trabajos (Windows/Ubuntu, Python 3.11, 3.12 y 3.13); la ejecución de CI del commit de metadatos `820ad5b` también terminó correctamente. Estas verificaciones técnicas no equivalen a una auditoría semántica independiente.

Limitaciones explícitas de V1: estimación heurística y no exacta de tokens; truncamiento con posible pérdida de significado; ausencia de verificación automática completa de fidelidad, estilo e idioma; dependencia de autenticación/entorno del Codex CLI; falta de aislamiento de roles del puente y posible herencia de herramientas MCP externas; rate limit en memoria por proceso; evaluación sintética, sin acreditación de generalización a otra aplicación. El proveedor `mock` solo da formato y no razona semánticamente. No se propone un V2 o V3 para este cierre.

## Retención, reproducibilidad y publicación

El archivo versionado `evaluacion/evaluation-retention.json` protege **231 identificadores únicos**; se incorporó al commit de cierre `0179888` junto a este informe y al README. Las carpetas de `evaluacion/salida/` no se publican en Git; se mantiene el JSON consolidado fuera del repositorio como evidencia. **No ejecutar limpieza con `-Apply`** sobre el histórico.

La [Release `v0.1.0`](https://github.com/SergioGilBorras/P4-Semantic-Labeler/releases/tag/v0.1.0) está publicada como versión estable (no borrador ni prerelease), anclada al commit `0179888727f96796e7c0a44a5b6631f15a1b3a51`. La etiqueta y el historial de PR constituyen evidencia reproducible de esa publicación. El commit `820ad5b` modificó después en `main` la descripción y el autor de `pyproject.toml`; **ese cambio posterior no pertenece al tag `v0.1.0`**.

La Release todavía no tiene archivos wheel adjuntos. La disponibilidad para clientes y la instalación de dependencias alojadas en GitHub deben comprobarse en un entorno limpio antes de distribuir. Cualquier nueva entrega que incluya modificaciones posteriores al tag requiere su propia versión y CI; no se debe reconstruir un artefacto alterado y presentarlo como si fuera el contenido de la etiqueta histórica. Véase la [guía de distribución](distribution.md).

**Decisión de alcance:** el desarrollo funcional V1 quedó cerrado y publicado. Se conserva la evidencia desfavorable sin atribuir aprobación semántica universal ni ejecutar más inferencias de Codex.
