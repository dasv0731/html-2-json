# Changelog — oxygen-json-v3

Registro de cambios incrementales aplicados al skill `oxygen-json-v3` después de su release inicial. Cada entrada documenta qué se cambió, por qué, y cómo se validó. Backups de versiones previas viven en `.backup-YYYYMMDD-HHMMSS/` en la raíz del skill.

---

## 2026-05-15 — Selectores globales del sitio omitidos del code-block

### Bug encontrado en uso real

Usuario reportó que pegar el bloque rompía el sitio destino. Causa: el CSS de entrada tenía `:root` con variables CSS, `*, *::before, *::after { box-sizing }`, `body { ... }`, `html`, `a`, `p`, `img` — selectores que aplican GLOBALMENTE al sitio. El skill los metía en el `ct_code_block` agregado del bloque reusable, y al pegarlo en una página, ese CSS se inyectaba como global de la página, sobreescribiendo el reset del template Oxygen.

### Fix

Nueva función `_is_global_selector` en `_process_qualified_rule`. Detecta:
- `:root` y variantes
- `*`, `*::before`, `*::after`
- Tag puros sin clase (`body`, `html`, `a`, `p`, `img`, `h1-h6`, `div`, etc.)
- Tag con pseudo (`body::before`, `a:hover`, etc.)

Estos selectores **NO se emiten** al code-block. Se emite un WARN claro: "Selector global '<X>' omitido (rompe el sitio destino al pegar). Migra esas reglas a una clase específica del componente."

### Implicación para el usuario

Si necesita esos estilos en el componente, debe migrarlos a clases específicas:

```css
/* MAL: aplica al body de toda la página al pegar */
body { font-family: "Inter"; }
:root { --c-red: #E30613; }

/* BIEN: aplica solo a la clase del componente */
.miBloque__base {
  font-family: "Inter";
  --c-red: #E30613;
}
```

Fixture: `selectores-globales-omitidos`. Suite 21/21.

Doc actualizada en SKILL.md sección "Contrato de input" / CSS.

---

## 2026-05-15 — Spans vacíos decorativos → `ct_div_block` con `useCustomTag`

### Bug encontrado en uso real

Usuario reportó que un `<span class="heroBlog__dot" aria-hidden="true"></span>` (separador visual decorativo, sin texto) se mapeaba a `ct_text_block` con `useCustomTag: span`. Esto hacía que en el panel de Oxygen apareciera con un campo "Text Content" editable, confuso para algo puramente visual.

### Fix

Cuando `<span>`, `<em>`, `<strong>`, o `<small>` está **vacío** (sin texto ni hijos Tag), ahora se mapea a `ct_div_block` con `useCustomTag: true, tag: <el-tag>`. Si tiene contenido, sigue siendo `ct_text_block` como antes.

Resultado: el bloque sigue renderizando con el tag HTML correcto (`<span>`), pero el panel de Oxygen lo trata como contenedor en vez de bloque de texto. Sin campo "Text Content" innecesario.

Fixture: `span-vacio-decorativo` con 3 spans/em (2 vacíos + 1 con texto). Suite 20/20.

---

## 2026-05-15 — Auto-emisión de `grid-column-min-width-unit: auto` en grid containers

### Bug descubierto en uso real

Usuario reportó que un grid container con items intrínsecamente anchos hacía overflow horizontal (se salía del viewport). La solución que aplicó manualmente al JSON tras pegar: agregar `grid-column-min-width-unit: "auto"` al container.

Esto es una propiedad propia de Oxygen Grid que cuando vale `"auto"` permite que las columnas se ajusten al ancho disponible en lugar de respetar el min-content de los items.

### Fix

En `apply_grid_child_rules`, después de inyectar `grid-child-rules`, también inyectar `grid-column-min-width-unit: "auto"` en el container si el usuario no lo definió explícitamente. Aplica a TODOS los grid containers (con o sin spans).

Agregada `grid-column-min-width-unit` a `NATIVE_PROPERTIES`.

Fixtures afectados: `grid-child-rules-spans` y `bug-grid-display-espurio` (sus expected.json se regeneraron). Suite 19/19.

---

## 2026-05-15 — Fix: gradients van a `custom-css`, no a campo nativo

### Bug encontrado en uso real

Usuario reportó que `<div class="schematic__chevrons">` no renderizaba las rayas amarillas tras pegar el JSON en Oxygen. CSS original:

```css
.schematic__chevrons {
  background-color: #1F1A12;
  background-image: repeating-linear-gradient(75deg, #FFD60A 0, #FFD60A 14px, transparent 14px, transparent 28px);
}
```

El skill emitía el `background-image` como propiedad nativa. Oxygen tiene formato propio (`gradient` como objeto estructurado) y no respeta strings CSS de `gradient` en su campo nativo, por lo que el gradient simplemente no se aplicaba al pegar.

### Fix

Agregado al filtro de funciones complejas en `_is_property_native` (transform.py:803-810): `linear-gradient(`, `radial-gradient(`, `conic-gradient(`, `repeating-linear-gradient(`, `repeating-radial-gradient(`, `repeating-conic-gradient(`. Cualquier propiedad con esos valores ahora va a `custom-css` automáticamente, donde sí se renderiza como CSS plano por el frontend.

Fixture nuevo: `gradients-a-custom-css` con 3 clases que tienen los tres tipos de gradient. Suite 19/19.

### Implicación para el usuario

Los gradients siguen funcionando visualmente al pegar (vía `custom-css`), pero pierden la editabilidad desde el panel de Background de Oxygen. Si querés que el gradient sea editable nativo, tenés que reconstruirlo manualmente en Oxygen usando su UI de gradient (que produce el objeto estructurado).

---

## 2026-05-15 — Soporte de `grid-child-rules` para grids con spans

### Feature nuevo

Cuando un container `display: grid` tiene hijos con `grid-column: span N` y/o `grid-row: span N` en sus clases CSS, el skill ahora **construye automáticamente el array `grid-child-rules`** (formato propio de Oxygen) en el container, en vez de mandar esas propiedades a `custom-css` del hijo.

Formato emitido (validado empíricamente contra JSON real de Oxygen pegado por el usuario):

```json
"grid-child-rules": [
  {"child-index": 0, "column-span": "",  "row-span": ""},
  {"child-index": 1, "column-span": "3", "row-span": "2"},
  {"child-index": 2, "column-span": "2", "row-span": ""},
  {"child-index": 3, "column-span": "",  "row-span": "2"},
  {"child-index": 4, "column-span": "1", "row-span": "1"}
]
```

**Reglas del formato (descubiertas pegando JSONs reales):**

- Una entrada por hijo, **no truncar** al último no-default.
- Hijos sin span: `column-span: ""`, `row-span: ""` (Oxygen los interpreta como 1×1).
- Solo se inyecta el array si **al menos un hijo tiene span ≠ default**.
- Spans de un mismo hijo pueden venir de múltiples clases (BEM modifier mergea con base).

### Implementación

1. **Parser CSS** (`_extract_grid_span_metadata`): cuando una regla de clase tiene `grid-column: span N` o `grid-row: span N`, esas dos propiedades se sacan del dict normal y se guardan como metadata `__grid_span_column__` / `__grid_span_row__`. NO van a custom-css.

2. **Post-process** (`apply_grid_child_rules`): después de construir el árbol de componentes y antes de emitir el bloque de clases, recorre el árbol. Para cada `ct_div_block` cuyo CSS contiene `display: grid`, mira los hijos en orden posicional y construye el array `grid-child-rules` consultando la metadata de cada clase. Inyecta el array en `default_rules[container_class]` para que `build_classes_block` lo emita.

3. **Filtro de metadata**: `expand_shorthands` y `convert_properties` ignoran las keys `__grid_span_*` para que no contaminen el output.

4. **Caso especial en `convert_properties`**: `grid-child-rules` con valor `list` se emite tal cual (sin pasar por `_is_property_native` ni `_convert_value_with_unit` que asumen strings).

Fixture: `grid-child-rules-spans` — grid de 6 columnas con 5 hijos, 3 de ellos con spans. Suite 18/18.

### Limitaciones

- Solo se mapean spans en la forma `span N`. Otras formas (`grid-column: 2 / 4`, `grid-area: foo`) caen a `custom-css` por el flujo normal.
- Hijos inyectados automáticamente por el detector de rich text (no es el caso típico en grids) podrían descuadrar los índices. Validar empíricamente si aparece el caso.

---

## 2026-05-15 — Descubrimientos colaterales: blockquote, classes FA, absorción inline

Continuación de la sesión de tests. Tres descubrimientos surgidos al revisar baselines de la suite expandida; dos arreglados con TDD, uno documentado como comportamiento esperado.

### Bug `<blockquote>` sin `useCustomTag`

`<blockquote>` caía al fallback de "tag desconocido" en `_resolve_block_type` y se mapeaba a `ct_div_block` con `original: {}` (sin tag). El componente renderizaba un `<div>`, perdiendo la semántica HTML. Análogo a `<section>`, `<article>`, etc. que ya tienen branch propio.

Fix: agregada `"blockquote"` a la tupla de tags semánticos en `_resolve_block_type` (transform.py:1422). Ahora emite `original.tag: "blockquote"` igual que los otros tags semánticos. Atributos no manejados (`cite`) siguen viajando como `custom-attributes`.

Fixture: `bug-blockquote-sin-tag`.

### Bug classes FA duplicadas en `ct_code_block` Ruta B

Cuando un `<i class="fa-solid fa-envelope iconStack__icon">` se mapeaba a `ct_code_block` por Ruta B, las clases FA (`fa-solid`, `fa-envelope`) viajaban DOS veces:
1. Dentro del `original.code-php` literal (necesario).
2. En `options.classes` del bloque y en `classes` top-level con `original: {}` (redundante, ensucia la tabla global de selectores de Oxygen con `.fa-solid`, `.fa-envelope`, etc.).

Fix: cuando el bloque es `ct_code_block` con `code-php` (Rutas B/C), las clases que matchean el patrón FA o empiezan con `fa-` se filtran de `options.classes`. Las clases del usuario (no-FA) se preservan tal cual para que el panel "Manage > Selectors" siga ofreciéndolas. transform.py:1011-1015.

Fixture: `icono-fa6-codeblock` (actualizado con expected sin FA classes).

### Comportamiento documentado: absorción inline de `<i class="fa-...">` dentro de wrappers

Cuando `<i class="fa-...">` vive como único hijo (o junto a otros inline) de un `<div>` u otro tag, el detector de rich text del padre lo absorbe en un `oxy_rich_text` con HTML literal en `ct_content`. NO llega a la Ruta B. Funcionalmente se renderiza igual (las clases FA disparan los glifos vía la stylesheet de FontAwesome), pero pierde editabilidad como bloque independiente.

No es bug — es consecuencia consistente del detector de rich text que ya cubría `<em>`, `<span>`, etc. Pero SKILL.md describía Ruta B sin esa condición. Doc actualizada en SKILL.md sección "Iconos" con "Aclaración sobre cuándo aplica la Ruta B". Fixture descriptivo: `icono-fa6-absorbido-richtext` (NO failing — congela el comportamiento como baseline).

### Estado de la suite

16 fixtures, 16/16 pasan.

---

## 2026-05-15 — Reorg de filesystem + suite de tests + fix de 2 bugs documentados

### Reorganización del repo

- `transform.py` movido a `scripts/transform.py` y los tres `.md` de referencia movidos a `references/` (estaban aplanados en la raíz; SKILL.md y README ya documentaban estos paths, el comando `python scripts/transform.py …` no funcionaba antes).

### Suite de tests

Nueva: `tests/run.py` + `tests/fixtures/<caso>/` con `input.html`, `input.css`, `options.json`, `expected.json`. Comparación byte-a-byte, diff JSON pretty-printed al fallar, flag `--update` para regenerar baselines. Sin frameworks (stdlib pura).

Casos baseline: `card-basico`, `link-icono-texto`, `boton-text-customtag`, `lista-ul-li`, `pseudo-hover-focus`.

### Bugs arreglados con TDD

**Bug auto-flex multi-clase**: cuando un `<a>` con icono+texto tenía varias clases (ej. `btn btn--whatsapp`), el skill aplicaba el auto-flex inyectado (`display:flex`, `flex-direction:row`, `gap:8`) a TODAS las clases. Si la clase base (`.btn`) se reutilizaba en otros links sin icono, recibía flex sin motivo. Ahora se aplica solo a la **última** clase (convención BEM: modifier al final), y se emite WARN cuando hay más de una clase. Fix en `_maybe_add_flex_for_icon_text_link` (transform.py:1097-1108). Fixture que reproducía el bug: `bug-autoflex-multiclase`.

**Bug display:grid espurio en media queries**: cuando una clase tenía `display: grid` en top-level y un media query solo cambiaba alguna prop grid (ej. `grid-row-gap: 12px`), el skill inyectaba `display: grid` en el breakpoint aunque el usuario no lo escribió. Ruido al editar en Oxygen. El comportamiento paralelo para flex sí tiene motivación (el panel UI de Oxygen muestra los controles flex en el breakpoint), pero para grid el display se hereda en cascada y no aporta valor. Fix: eliminadas las 3 líneas que inyectaban display:grid (transform.py:1590-1592 ex). Fixture que reproducía el bug: `bug-grid-display-espurio`.

Ambos fixtures se commitearon primero en estado failing y luego pasaron tras el fix — TDD real. Estado final de la suite: 7/7.

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
