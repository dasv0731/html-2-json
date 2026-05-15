# Changelog — oxygen-json-v3

Registro de cambios incrementales aplicados al skill `oxygen-json-v3` después de su release inicial. Cada entrada documenta qué se cambió, por qué, y cómo se validó. Backups de versiones previas viven en `.backup-YYYYMMDD-HHMMSS/` en la raíz del skill.

---

## 2026-05-15 — Sesión de fixes y validaciones empíricas

**Backup**: `.backup-20260515-145200/`

### Bugs arreglados

**1. Shorthand con funciones CSS (`calc`, `var`, `clamp`, `min`, `max`, `rgb`, etc.)**

Antes: `padding: calc(10px + 1vw)` se rompía silenciosamente en 4 tokens basura porque el expansor hacía `val.split()` sin respetar paréntesis. Lo mismo para `margin`, `gap`, `border-radius` y `border`.

Ahora: nuevo helper `_split_top_level(val)` que tokeniza respetando paréntesis balanceados. Funciones CSS quedan como un único token aunque contengan espacios o comas internas. Aplicado a:
- `_expand_box` (padding/margin)
- `_expand_border_radius`
- `_parse_border_value`
- Expansor de `gap` en `expand_shorthands`

Verificado con: `padding: calc(10px + 1vw)`, `padding: clamp(10px, 2vw, 20px)`, `padding: var(--y) var(--x)`, `border: 2px solid rgb(255, 0, 0)`, `border-radius: clamp(4px, 1vw, 12px)`.

**2. Shorthand `border` con colores por palabra**

Antes: `border: 2px solid green` producía `width=green, style=solid, color=None` porque la heurística asignaba "todo lo no-style y no-color-hex" como width, dejando que la palabra de color sobrescribiera el valor numérico.

Ahora: `_parse_border_value` reordena la clasificación. Detecta width explícitamente (numérico con/sin unidad, o keyword `thin/medium/thick` vía helper nuevo `_is_border_width_numeric`), style por keyword, y color como fallback final.

Verificado con: `border: 2px solid green`, `border: thin dashed red`, `border: 2px solid rgb(255, 0, 0)`, `border: 1px solid var(--accent)`, `border: medium dashed currentcolor`.

**3. Custom-attributes duplicados en `ct_code_block` con HTML literal**

Antes: cuando un tag se mapeaba a `ct_code_block` (Rutas B/C de iconos), los atributos viajaban dentro del `code-php` Y también se duplicaban como `custom-attributes` del bloque.

Ahora: `_build_component` detecta el caso `ct_code_block` con `code-php` y omite la emisión de `custom-attributes` (que de todos modos ya están dentro del HTML literal).

### Cambios de diseño

**4. `<button>` HTML mapeado a `useCustomTag: button` (cambio mayor)**

Diseño previo: `<button>` siempre iba a `ct_link_button`, que internamente renderiza un `<a>`. Perdía la semántica HTML del button (no enviaba forms, perdía handlers, no era accesible como botón).

Diseño nuevo: trío de mapeos según contenido, paralelo a `<li>`:

| Contenido del button | Bloque emitido |
|---|---|
| Texto plano puro | `ct_text_block` con `useCustomTag: true, tag: "button"` |
| HTML inline mixto (`<em>`, `<strong>`, etc.) | `oxy_rich_text` con `useCustomTag: true, tag: "button"` |
| Hijos estructurales (`<svg>`, `<div>`, `<span>` con bloques) | `ct_div_block` con `useCustomTag: true, tag: "button"` |

Atributos del button (`type`, `onclick`, `aria-*`, `data-*`, `name`, `value`, `formaction`, etc.) se preservan automáticamente como `custom-attributes`, editables desde el panel "Advanced > Custom Attributes" de Oxygen.

**Código eliminado**: helpers `_is_functional_button`, `_serialize_button_for_codeblock`, constantes `_BUTTON_FUNCTIONAL_TYPES`, `_BUTTON_FUNCTIONAL_ARIA`, `_BUTTON_FUNCTIONAL_DATA`. Estos existían en un diseño intermedio (heurística funcional → code_block) que fue obsoletado por la solución `useCustomTag`.

Validación empírica: los tres casos del trío fueron pegados en Oxygen y el frontend renderiza `<button>` HTML real con atributos aplicados (incluyendo `aria-expanded`).

### Validaciones empíricas (sin cambios de código)

**5. Pseudoclases `nth-of-type`, `nth-last-child`, `nth-last-of-type` validadas**

Estaban implementadas pero marcadas como "no validado" en la doc. En esta sesión se pegó el caso de prueba `/nth-test-case/nth_test.json` en Oxygen y se verificó visualmente que las cuatro pseudoclases nth-* aplican correctamente en frontend, incluso sin el marker vacío que Oxygen genera desde su UI nativa.

Actualizada la doc:
- Tabla de pseudoclases marca las cuatro como "Validado empíricamente en frontend de Oxygen".
- Advertencia agregada sobre `nth-of-type` / `nth-last-of-type`: cuentan solo elementos del MISMO tag. Para que apliquen como esperás, los hermanos deben compartir tag HTML.

### Decisiones sin acción

**6. "Fase 3" como nomenclatura documental**: se planteó como problema "el código no separa por fases internamente". Decisión: no es un bug a corregir. Las "fases" son metadata histórica del proceso de descubrimiento del skill, no arquitectura. El código se organiza por responsabilidad funcional (parsing, mapping, emission), no por cronología de descubrimiento.

### Archivos modificados

- `scripts/transform.py`: +109 líneas neto. Helpers nuevos, lógica de button reescrita, fix de duplicación de custom-attributes.
- `SKILL.md`: +15 líneas neto. Nueva sección "Fixes recientes (post-v3 release)", entrada de `<button>` reescrita, tabla de pseudoclases actualizada con validación empírica.
- `references/block-types.md`: +3 líneas neto. Entrada de `<button>` separada en tres filas (una por caso del trío) más entrada de `<a class="btn">` separada.
- `references/property-mappings.md`: -4 líneas neto. Sección "Bug pendiente" del shorthand reemplazada por documentación del soporte para funciones CSS.

### Archivos NO tocados

- `references/oxygen-quirks.md`: sin cambios.
