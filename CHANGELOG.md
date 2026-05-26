# Changelog — oxygen-json-v3

Registro de cambios incrementales aplicados al skill `oxygen-json-v3` después de su release inicial. Cada entrada documenta qué se cambió, por qué, y cómo se validó. Backups de versiones previas viven en `.backup-YYYYMMDD-HHMMSS/` en la raíz del skill.

---

## 2026-05-26 — Sesión "v3.2": cobertura extendida (filter, transform, tags, inline style)

Segunda iteración del mismo día. Cubre los pendientes deliberados de v3.1: filter broken-out, transform como array de steps, data-aos como nativo, mapeo de tags HTML faltantes (tablas/forms/blockquote/pre/hr), y soporte real de `style="..."` inline en lugar de rechazo. También arregla un bug pre-existente con comentarios HTML.

### Nuevas capacidades nativas

**1. `filter: <fn>(<arg>)` mapeado broken-out**

Antes (v3.1): `filter: blur(8px)` se emitía como string nativo, pero el panel Effects de Oxygen no podía editarlo (espera `filter` + `filter-amount-*`).

Ahora: `_expand_filter` parsea funciones soportadas (`blur`, `brightness`, `contrast`, `grayscale`, `hue-rotate`, `invert`, `saturate`, `sepia`) y emite `filter: "<nombre>"` + `filter-amount-<nombre>: <valor>` + `filter-amount-<nombre>-unit: <unit>` (si difiere del default). Verificado contra `getCSS` en `angular/controllers/controller.css.js:5383` (Oxygen ensambla `value + "(" + options["filter-amount-" + value] + ")"`).

Limitaciones conservadoras (van a custom-css):
- Múltiples funciones (Oxygen sólo soporta una por elemento)
- Funciones con default `%` pero el CSS las pasa sin unidad (ej. `brightness(0.8)` es multiplicador, no porcentaje — fallback evita renderizar `0.8%` incorrecto)
- `drop-shadow`, `opacity` como filter, `url()` y otras no soportadas por Oxygen

**2. `transform` como array de transform-step objects**

Nueva función `_expand_transform` parsea `transform: <fn1>(<args>) <fn2>(<args>) ...` y emite el array que Oxygen ensambla en `getTransformCSS` (`components/component.class.php:4153`).

Funciones soportadas: `translate`, `translateX/Y/Z`, `translate3d`, `rotate`, `rotateX/Y`, `scale`, `scaleX/Y/Z`, `scale3d`, `skew`, `skewX/Y`, `perspective`. Cada step preserva sus `-unit` paralelos cuando difieren del default (px para translate/perspective, deg para rotate/skew, unitless para scale). `matrix`, `matrix3d` y `rotate3d` con args sueltos van a custom-css.

Requirió:
- Agregar `transform` a `NATIVE_PROPERTIES`
- Branch especial en `convert_properties` para valores tipo `list` (no string)

**3. `data-aos-*` del HTML → keys `aos-*` nativas en `options.original`**

Nuevo mapper `_extract_aos_options` detecta `data-aos="fade-up"`, `data-aos-duration="600"`, etc. en el HTML y los emite como `aos-type`, `aos-duration`, etc. (editables desde el panel "Effects > Animation on Scroll"). Las correspondientes `data-aos-*` se excluyen de `custom-attributes` para no duplicar. Otros `data-*` siguen el camino normal.

### Tags HTML adicionales mapeados

Antes: `<table>`, `<tr>`, `<td>`, `<form>`, `<input>`, `<select>`, `<label>`, etc. caían al fallback "Tag desconocido" con WARN, emitiendo `ct_div_block` sin tag custom.

Ahora: tres categorías en `_resolve_block_type`:

- **`PURE_CONTAINER_TAGS`** (`table`, `thead`, `tbody`, `tfoot`, `tr`, `colgroup`, `form`, `fieldset`, `select`, `blockquote`, `pre`): siempre `ct_div_block` con `useCustomTag` + tag.
- **`VOID_TAGS`** (`input`, `hr`, `col`, `br`): igual, sin children. Atributos del input (`type`, `name`, `value`, `placeholder`, `required`, etc.) viajan como `custom-attributes` editables.
- **`TRIO_TAGS`** (`td`, `th`, `caption`, `label`, `legend`, `figcaption`, `summary`, `option`, `code`, `textarea`): mismo trío que `<li>`/`<button>` — estructural → `ct_div_block`, inline mixto → `oxy_rich_text`, texto plano → `ct_text_block`, todos con `useCustomTag` + tag.

### `style="..."` inline soportado

Antes: el contrato requería al user eliminar `style="..."` del HTML antes de pasar al script.

Ahora: nueva función `_parse_inline_style` parsea el atributo con `tinycss2` y mergea las propiedades en `options.original` del bloque específico (no en las clases — evita contaminar otros bloques que compartan clase). Inline tiene prioridad sobre lo que ya estaba en `original`. Si parte de las propiedades inline no son nativas, se concatenan al `custom-css` existente del bloque. El atributo `style` se agregó a `HANDLED_ATTRS` para no duplicarse en `custom-attributes`.

### Bug pre-existente arreglado

**Comentarios HTML (`<!-- ... -->`) generaban `ct_text_block` ruido**: BeautifulSoup expone `Comment` como subclase de `NavigableString`, y el código de hijos del div los iteraba como text nodes vacíos. Fix: importar `Comment` de bs4 y `continue` cuando aparece, tanto en `_build_component` (procesamiento de hijos) como en `_maybe_inject_text_child` (clasificación).

### Validación

Smoke test cubriendo todos los cambios nuevos:
- Inline style con padding/color/transform (transform queda como array, padding/color nativos)
- `data-aos` + `aria-label` (aos-* nativos, aria-label preservado en custom-attributes)
- `filter: blur(8px)` (broken-out) y `filter: blur(4px) brightness(80%)` (custom-css)
- `transform: translate(10px,20px) rotate(30deg) scale(1.2)` (array de 3 steps correctos)
- Tabla anidada `<table><thead><tr><th>` y `<tbody><tr><td>` con texto, inline mixto y bloques anidados
- Form con label (rich text con `<em>`), input void con 4 atributos, button
- `<hr>` y `<blockquote>` standalone

Sintaxis Python validada vía `ast.parse`.

### Archivos modificados

- `transform.py`: +~250 líneas neto.
- `SKILL.md`: actualizar capacidades + contrato (style ya no se rechaza).
- `CHANGELOG.md`: este registro.

---

## 2026-05-26 — Sesión "v3.1": auditoría contra código de Oxygen y polish

Sesión enfocada en cerrar la brecha entre lo que el skill emitía y lo que Oxygen Builder acepta como nativo en su panel editor. Se auditó el código PHP del plugin (`components/component.class.php`, `components/classes/*`, `includes/tree-shortcodes.php`, `includes/ajax.php`) y los controllers Angular (`angular/controllers/controller.tree.js`, `controller.templates.js`, `controller.classes.js`, `controller.states.js`, `controller.css.js`) para identificar mismatches.

### Bugs críticos arreglados

**1. `<img>` no renderizaba (image_type=2 + attachment_id=0)**

Antes: el skill emitía `image_type: "2"` (Media Library) + `attachment_id: 0` + `attachment_url`. El render de Oxygen (`components/classes/image.class.php:48`) cae a la rama de placeholder cuando `image_type=2 && !attachment_id` y usa `$options['src']`, que el skill nunca seteaba. Resultado: la imagen no aparecía hasta reasignación manual.

Ahora: emite `image_type: "1"` (URL-based) + `src: <url>` + `alt: <texto>` (que antes se descartaba con WARN). La imagen renderiza inmediatamente al pegar. El user puede reasignar a la media library desde el panel si quiere.

**2. `box-shadow` / `text-shadow` no editables en el panel**

Antes: el skill listaba `box-shadow` como nativa y la emitía como string CSS shorthand. Visualmente funcionaba (el CSS se aplicaba), pero el panel Effects de Oxygen no podía editarla porque espera las keys broken-out (`box-shadow-color`, `box-shadow-horizontal-offset`, `-vertical-offset`, `-blur`, `-spread`, `-inset`).

Ahora: parsers `_expand_box_shadow` y `_expand_text_shadow` descomponen el shorthand a las keys broken-out que Oxygen ensambla en CSS al renderizar. Multiples sombras (separadas por coma) o lengths con unidades distintas a `px` caen a custom-css completo (Oxygen hardcodea `px` al renderizar, otras unidades quedarían erróneas).

**3. Auto-flex en links contaminaba clases compartidas**

Antes: cuando un `<a>` tenía icono+texto, el skill marcaba TODAS las clases del link para auto-inyectar `display:flex / flex-direction:row / gap:8`. Si una de esas clases (ej. `.btn`) se reutilizaba en otro contexto sin icono, recibía flex erróneamente.

Ahora: la inyección va al `options.original` del bloque `ct_link` específico, no a las clases. Solo ese link recibe flex. Antes de inyectar, se chequea que ninguna clase del link haya definido `display` en el CSS del user (si lo hizo, se respeta su elección y no se inyecta). Implementado vía marca interna `__needs_auto_flex__` + post-proceso `apply_auto_flex_to_links()`.

### Cobertura ampliada

**4. NATIVE_PROPERTIES alineado con `$options_white_list` de Oxygen**

Sumadas como nativas (antes iban innecesariamente a `custom-css`):

- **Transitions**: `transition-duration` (con unit), `transition-timing-function`, `transition-delay` (con unit), `transition-property`.
- **Filters**: `filter`, `filter-amount-blur/brightness/contrast/grayscale/hue-rotate/invert/saturate/sepia` (cada uno con su `-unit`).
- **Text-shadow**: las 4 keys broken-out (ver fix 2).
- **Layout**: `float`, `clear`, `direction`, `list-style-type`, `visibility`, `order`, `-webkit-font-smoothing`.
- **Background**: `background-attachment`, `background-clip`, `background-blend-mode`, `mix-blend-mode`, `overlay-color`, `gradient`.
- **Grid completo**: `grid-columns-auto-fit`, `grid-column-min-width`, `grid-column-max-width`, `grid-row-count`, `grid-row-behavior`, `grid-row-min-height`, `grid-row-max-height`, `grid-all-children-rule`, `grid-justify-items`, `grid-align-items`, `grid-match-height-of-tallest-child`.
- **Container padding** (para `ct_section` si en algún momento se emite): `container-padding-{top,right,bottom,left}`.
- **AOS** (animations on scroll): todas las `aos-*` keys.
- **Botones extra**: `button-size`, `button-color`, `button-hover_color`.

**5. `grid-template-columns: repeat(auto-fit, minmax(Xpx, 1fr))` mapeado a nativo**

Antes: cualquier `grid-template-columns` que no fuera `repeat(N, 1fr)` o `1fr 1fr...` iba a `custom-css`. El patrón `repeat(auto-fit, minmax(200px, 1fr))` — muy común en grids responsivos — se perdía como editable.

Ahora: nueva función `_grid_template_to_oxygen` (reemplaza `_grid_template_to_count`) reconoce `repeat(auto-fit|auto-fill, minmax(Xunit, ANY))` y emite `grid-columns-auto-fit: "1"` + `grid-column-min-width: "X"` + `grid-column-min-width-unit: "unit"` (si distinto de px).

**6. `var()` en propiedades de color queda nativo**

Antes: cualquier valor con `var()/calc()/clamp()/etc.` iba a `custom-css`. Para sitios con design tokens (`color: var(--accent)`), esto generaba mucho ruido en custom-css.

Ahora: nuevo set `COLOR_PROPERTIES` (color, background-color, border-*-color, button-text-color, overlay-color, box-shadow-color, text-shadow-color, icon-color, icon-background-color, fill, stroke). Para estas propiedades, `var()` y funciones complejas se aceptan como valor nativo (Oxygen las preserva como string opaco en el panel y las renderiza tal cual). `transition-property` también acepta strings con `var()` por la misma razón.

**7. Pseudo-elementos extra y `:visited`**

Sumados a `NATIVE_PSEUDO_ELEMENTS`: `first-letter`, `first-line`, `selection` (los tres documentados en `is_pseudo_element()` de Oxygen). Sumado a `NATIVE_SIMPLE_PSEUDO`: `visited`. Antes iban a Code Block, ahora se emiten como state nativo.

### Limpieza arquitectónica

**8. Heurística `<a>` → `ct_link_button` más conservadora**

Antes: cualquier `<a class="...btn..."/...button.../...boton...">` se convertía en `ct_link_button`, que renderiza un `<a>` con estilos de botón propios de Oxygen que tapaban los del user.

Ahora: `ct_link_button` se emite solo si la clase explícita `is-oxy-button` está presente. Todo lo demás cae a `ct_link` (si tiene hijos Tag) o `ct_link_text` (si solo tiene texto). Menos sorpresas, comportamiento predecible.

**9. Removida la inyección de `original.tag` en las clases top-level**

Antes: si una clase pertenecía a un bloque con `useCustomTag`, el skill duplicaba el `tag` dentro de `classes[<key>].original.tag`. Esto era incorrecto conceptualmente: `tag` es opción del bloque, no de la clase. Si dos bloques con tags distintos compartían una clase, el último ganaba y forzaba su tag al otro.

Ahora: `tag` vive solo en `options.original` de cada bloque. Las clases nunca llevan `tag`.

### Validación

Smoke test end-to-end con CSS que ejercita los nueve cambios (grid auto-fit, box-shadow shorthand, var() en color, hover/before/nth-child states, transition-* nativo, `<img>` con `image_type=1`, `is-oxy-button`, auto-flex en `ct_link` con icono+texto). JSON resultante inspeccionado manualmente para confirmar shape correcto en cada caso. Sintaxis Python validada vía `ast.parse`.

### Archivos modificados

- `transform.py`: +~190 líneas neto.
- `SKILL.md`: actualizada sección "Capacidades específicas", "Cambios respecto a v2/v3", agregada sección "v3.1".
- `CHANGELOG.md`: este registro.

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
