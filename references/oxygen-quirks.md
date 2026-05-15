# Anomalías de Oxygen Builder

Comportamientos no obvios o inconsistentes de Oxygen Builder clásico 4.x descubiertos durante la construcción del skill. Documentar aquí cualquier cosa que parezca rara para que cuando un usuario tenga un problema, busques aquí primero antes de asumir que es bug del skill.

## Inconsistencias de serialización

### `[]` vs `{}` para "vacío"

Oxygen usa **arrays vacíos `[]`** y **objetos vacíos `{}`** en distintos contextos para representar "sin contenido". El uso NO es uniforme, pero después de validar empíricamente contra JSONs reales devueltos por Oxygen tras pegado, identificamos las reglas:

- En `options.original` cuando el bloque no tiene tag custom ni otras propiedades: **`[]`** (array vacío). Validado en múltiples casos reales.
- En `options.original` cuando hay propiedades (incluido `tag` solo): **`{...}`** (objeto con esas propiedades).
- En `classes[<key>].original` cuando la clase no tiene propiedades pero se preserva como referencia: **`{}`** (objeto vacío). Validado contra clases como `logos-marquee` en JSONs reales.
- En `options.media.<bp>.original` cuando está vacío: **`[]`** (mismo criterio que el de bloque). El skill ya no emite breakpoints vacíos para evitar el dilema.

Causa probable: serialización de PHP. PHP serializa arrays asociativos vacíos como `[]` y, si el array tiene claves no numéricas, como `{}`. La conversión no es uniforme y Oxygen heredó la inconsistencia.

**Regla aplicada por el script (v3)**: post-procesa el árbol de componentes y reemplaza `options.original = {}` por `[]` antes de serializar. En clases top-level mantiene `{}`. Validado empíricamente que Oxygen acepta y preserva el formato `[]` tras pegado.

### `nicename` y la numeración interna

`nicename` en los JSONs vistos a veces tiene un número que NO coincide con `ct_id`. Por ejemplo: `"nicename": "Heading (#4)"` con `"ct_id": 3`.

Causa: Oxygen mantiene un contador interno por tipo de bloque que se incrementa con cada bloque creado en la sesión, incluso si luego se elimina. El `ct_id` global es independiente.

**Regla aplicada por el script**: usar `ct_id` para el `nicename`. Si Oxygen lo renombra al pegar, sin problema. El nombre es para el panel del editor, no afecta funcionalidad.

### `activeselector` puede ser string o `false` booleano

- Si el bloque tiene clases: `activeselector` es la última clase (string).
- Si el bloque no tiene clases: `activeselector` es `false` (booleano JSON), no `""` (string vacío) ni `null`.
- También se ha visto `activeselector` como string vacío `""` en casos raros — probablemente residuo de sesiones de edición.

**Regla aplicada por el script**: emitir `false` (booleano) para bloques sin clases, y la última clase para bloques con clases. Cuando Oxygen devuelve el JSON tras pegado, a veces el `activeselector` aparece con valores de selectores que estaban "abiertos" en otra sesión del editor (residuo de UI); eso no afecta el render.

### El sufijo del selector — confirmado: es el post_id

Cada selector tiene la forma `<tipo-base>-<ct_id>-<sufijo>`. Por mucho tiempo el sufijo `1912` fue una hipótesis sin explicación. **Validado empíricamente en v3**: el sufijo es el `post_id` de WordPress del template o página donde el bloque fue creado originalmente.

Evidencia:
- Una página exportada como "Header y footer" tenía sufijo `-11` y `outerTemplateData.edit_link` apuntaba a `post.php?post=11`.
- Página home con `post_id=1195` → sufijo `-1195`.
- Blog posts comparten template y todos llevan sufijo del template post_id.

**Implicación para el skill**:
- El sufijo se pasa por flag CLI `--selector-suffix VALUE`. Si conocés el `post_id` de destino, pasalo. Si no, el script genera un aleatorio de 4 dígitos por ejecución.
- **Oxygen reasigna automáticamente el sufijo al pegar el bloque** en una página distinta. Validado pegando bloques con sufijo `-1914` que terminaron en `-1915` en la página destino. Es decir: el valor exacto del sufijo no es crítico, solo que sea numérico y único.

## Comportamientos del panel UI vs JSON

### Border-radius con unidades mezcladas

El panel de Oxygen permite poner unidades distintas en cada esquina del border-radius. El JSON las refleja como propiedades separadas con sus respectivos `*-unit`. **Caso confirmado** durante el descubrimiento.

### Tag custom en Div vs Section

Cuando creas un Div en Oxygen y le cambias el tag a `section` desde el panel, queda como `ct_div_block` con `original.tag = "section"`. Cuando creas una "Section" del menú principal de Oxygen, queda como `ct_section`.

Son **bloques distintos internamente**, aunque renderizan ambos como `<section>` en el HTML. El skill solo emite `ct_div_block` con tag, nunca `ct_section`, por decisión arquitectónica (más editable, menos legacy).

### `useCustomTag` solo aparece en algunos tipos

- `ct_div_block` con tag custom (section, article, etc.): NO emite `useCustomTag`. Solo `tag`.
- `ct_text_block` con tag custom (span, p custom): SÍ emite `useCustomTag: "true"` además de `tag`.

Asimetría no documentada. Regla aplicada: ver tabla en `block-types.md`.

### `original.tag` para `<p>` en `ct_text_block`

Vimos un caso: `"original":{"useCustomTag":"true","tag":"p"}`. Eso significa que aunque `<p>` es el tag default de `ct_text_block`, si Oxygen detecta que el usuario "fijó" explícitamente el tag desde el panel custom, emite `useCustomTag: true` igualmente.

**Regla aplicada por el script**: para `<p>`, NO emitir `useCustomTag`. Usar `original: []` (vacío). Si el usuario quiere forzar el comportamiento "custom-tag-explícito", no es algo que el HTML/CSS de entrada exprese, así que no lo soportamos.

## Comportamiento de propiedades

### `padding-top-unit: "px"` aparece aunque sea default

Vimos en un ejemplo: `"padding-top-unit":"px"` co-existiendo con `"padding-top":"10"`. Aunque `px` es el default de Oxygen para padding, el JSON lo emitió.

Causa probable: el panel de Oxygen registró "el usuario tocó la unidad" aunque la dejó en px.

**Regla aplicada por el script**: NO emitir `<prop>-unit` cuando es el default. El JSON resultante será más limpio. Si Oxygen produce inconsistencias, no es nuestra preocupación; nuestro JSON será coherente.

### `width-unit` se emite siempre

Para `width`, `height`, `max-width`, `max-height`, `min-width`, `min-height`: emitir `<prop>-unit` siempre, incluso para `px`. Razón: estas propiedades a menudo se usan con `%`, `vw`, `vh`, y la falta del unit causa ambigüedad.

### `flex-basis` se pierde

Oxygen no tiene propiedad `flex-basis` en su panel. Si pones `flex: 1 1 200px` en el panel, Oxygen guarda solo `flex-grow: 1` y `flex-shrink: 1`. El `200px` se pierde.

**Regla aplicada por el script**: si el CSS tiene `flex-basis` o un shorthand `flex` con tres valores, mandar `flex-basis` al `custom-css` y avisar.

### `flex-direction: row-reverse` se descompone

Oxygen serializa `row-reverse` como `flex-direction: "row"` + `flex-reverse: "reverse"`. `flex-reverse` es propiedad propia de Oxygen, no estándar.

### Grid no es CSS Grid estándar

Oxygen Grid es un sistema simplificado:
- Solo columnas de igual ancho (`grid-column-count`).
- Posicionamiento de hijos por span (`column-span`, `row-span`), NO por celda absoluta.
- No soporta `grid-template-areas`, `grid-template-rows` con valores explícitos.

**Regla aplicada por el script**: ver `property-mappings.md` sección "CSS Grid".

### `display: flex` en breakpoints — sí se repite

Cuando un breakpoint tiene `flex-direction`, `flex-wrap` o `justify-content` y la clase top-level es `display: flex`, Oxygen necesita el `display: flex` también en ese breakpoint para mostrar los controles flex en su panel UI.

**Regla aplicada por el script**: si `media.<bp>.original` tiene cualquiera de esas propiedades flex y la clase top-level es flex, se inyecta `display: flex` en el breakpoint.

### `display: grid` en breakpoints — NO se repite (asimetría intencional)

A diferencia de flex, el skill **no** repite `display: grid` en cada breakpoint que cambia props de grid. Razón: el `display: grid` de top-level se hereda en cascada CSS y emitirlo en cada breakpoint generaba el "bug del display:grid espurio" (un media query que solo cambiaba `grid-row-gap` recibía un `display: grid` innecesario).

**Si tu grid cambia de comportamiento por breakpoint y necesita `display: grid` explícito**: escribilo en el CSS del media query.

### `grid-child-rules` en breakpoints — limitación actual

Cuando un grid cambia su layout por breakpoint (ej. de 6 columnas en desktop a 1 columna en mobile, o spans distintos), Oxygen espera el array `grid-child-rules` repetido COMPLETO en cada breakpoint (no como diff).

**Hoy el skill NO replica automáticamente el array** desde top-level a los breakpoints. Si necesitás layout grid responsive con spans, escribí explícitamente las clases con sus spans dentro del media query (lo cual tampoco es soportado al 100% — está pendiente).

**Para grid uniforme sin spans** (típicamente cambiar `grid-column-count`), basta con poner la nueva count en el breakpoint y funciona.

### `gradient` como objeto estructurado

Oxygen serializa gradientes CSS como un objeto estructurado, no como string:

```json
"gradient": {
  "colors": [{"position-unit": "%", "value": "#ffffff", "position": "80"}],
  "gradient-type": "linear",
  "linear-angle": "90"
}
```

**Limitación actual del skill**: si el CSS tiene `background: linear-gradient(...)`, el skill lo manda a `custom-css`. No parsea el gradient para descomponerlo en el formato estructurado. Para soporte nativo habría que parsear `linear-gradient()` y mapear a `gradient.{colors, gradient-type, linear-angle}`.

### `transform` como objeto indexado

Oxygen serializa `transform` (cuando hay múltiples transformaciones) como objeto con keys numéricas string:

```json
"transform": {
  "0": {"transform-type": "translateX", "translateX": "10"}
}
```

**Limitación**: el skill no parsea funciones `transform()`. Va a `custom-css`.

### `color(N)` para colores globales de Oxygen

Si tu sitio tiene colores definidos en Manage → Colors de Oxygen, Oxygen los referencia internamente como `color(7)`, `color(12)`, etc. — el número es el ID del color global.

**Limitación inherente**: el skill emite el valor literal (hex, rgb, var) que el usuario escribió en el CSS. No tiene conocimiento de los colores globales del sitio. Si querés usar colores globales, hay que reasignar manualmente desde el panel tras pegar.

## Comportamiento de imágenes

### `attachment_id: 0` y reasignación

Si emites un `ct_image` con `attachment_id: 0` y solo `attachment_url`, Oxygen pega el bloque pero la imagen aparece como rota o como placeholder. El usuario debe entrar al panel de la imagen y seleccionar la imagen del media library.

**El skill avisa al usuario** que esto pasa con cada imagen. No es bug, es consecuencia de no poder mapear URLs a IDs sin acceso a WordPress.

### `alt` no tiene campo evidente

El atributo `alt` del `<img>` no aparece en `options.original` de `ct_image` en los ejemplos vistos. Probablemente Oxygen lo deriva del media library del attachment. **El skill avisa** que el alt no se transfiere.

## Pseudo-clases y pseudo-elementos como states nativos (validado en v3)

Oxygen acepta varias pseudo-clases y pseudo-elementos CSS como **states nativos** del selector, emitidos como keys paralelas a `original` y `hover` en `classes[<key>]`. Validado empíricamente configurando states en el panel de Oxygen y observando el JSON exportado:

```json
"mi-clase": {
  "original": {...},
  "hover":    {...},
  "focus":    {...},
  "active":   {...},
  "before":   {"content": "X", ...},
  "after":    {"content": "Y", ...},
  "disabled": {...},
  "checked":  {...},
  "first-child": {...},
  "last-child":  {...},
  "nth-child(2)":     {...},
  "nth-child(2n+1)":  {...},
  "nth-child(odd)":   {...},
  "key": "mi-clase"
}
```

**Mapeo CSS → key Oxygen** (lo que el skill v3 implementa):

| CSS | Key Oxygen | Notas |
|---|---|---|
| `:hover` | `hover` | |
| `:focus` | `focus` | |
| `:active` | `active` | |
| `:disabled` | `disabled` | |
| `:checked` | `checked` | Inputs |
| `:first-child` | `first-child` | |
| `:last-child` | `last-child` | |
| `:before` / `::before` | `before` | Ambas sintaxis aceptadas |
| `:after` / `::after` | `after` | Ambas sintaxis aceptadas |
| `:nth-child(N)` | `nth-child(N)` | N puede ser número, expresión (2n+1), o keyword (odd/even). El argumento se preserva literal. |
| `:nth-of-type(N)` | `nth-of-type(N)` | Por simetría (NO validado en frontend) |
| `:nth-last-child(N)` | `nth-last-child(N)` | Por simetría (NO validado en frontend) |
| `:nth-last-of-type(N)` | `nth-last-of-type(N)` | Por simetría (NO validado en frontend) |

**Lo que va al Code Block** (NO se mapea a state nativo):
- Selectores con combinadores: `.foo > .bar`, `.foo .bar`, `.foo + .bar`, `.foo ~ .bar`.
- Selectores con atributos: `.foo[disabled]`, `[data-x="y"]`.
- `:not(...)` (su argumento es otro selector, no un state).
- Pseudo-clases no listadas: `:focus-visible`, `:focus-within`, `:placeholder`, `:read-only`, `:required`, `:valid`, `:invalid`, etc.

**Normalización de `content`**: cuando una regla CSS define `content: "X"` en `:before` o `:after`, el valor "X" se emite SIN las comillas externas dentro del JSON Oxygen, porque ese es el formato canónico que el panel produce. Es decir: `content: "▸"` (CSS) → `"content": "▸"` (JSON, sin comillas internas escapadas). Validado empíricamente.

### States también pueden vivir en `options` del bloque

Además de aparecer en `classes[<key>].<state>`, los states también pueden aparecer al nivel `options.<state>` dentro de un bloque individual. Ese es el patrón que usa Oxygen cuando configurás un state directamente para un componente específico (no para una clase compartida).

**Estado actual del skill**: el skill v3 emite states solo a nivel de clase (en `classes[<key>].<state>`), no en `options.<state>` por bloque. Los CSS que llegan al skill son siempre regla de clase (`.foo:state`), no propiedad de bloque, así que esto no debería ser limitación en práctica.

## Custom-attributes (validado en v3)

Oxygen acepta atributos HTML arbitrarios en bloques individuales vía `original.custom-attributes`, formato:

```json
"original": {
  "custom-attributes": [
    {"name": "aria-label", "value": "Cerrar"},
    {"name": "data-action", "value": "open-modal"},
    {"name": "role", "value": "button"}
  ]
}
```

**Validado empíricamente**: Oxygen acepta este formato al pegar, preserva los atributos tras reasignación de IDs, y los renderiza en el HTML del frontend.

**Regla aplicada por el skill v3**: atributos HTML que NO están en la lista negra de "atributos manejados por otra lógica" se preservan automáticamente. La lista negra:
- `class`, `id` — estructurales
- `href`, `target` — ya van por `<a>`
- `src`, `alt`, `srcset`, `width`, `height`, `loading` — ya van por `<img>`
- `xlink:href` — ya va por `<svg><use>`

Todo lo demás (`aria-*`, `data-*`, `role`, `tabindex`, `title`, `lang`, `dir`, `rel`, `type`, `name`, `placeholder`, `for`, `value`, `disabled`, `hidden`, etc.) se preserva como custom-attribute.

## Comportamiento de Code Block

### `code-css` aplica a la página entera

El CSS dentro de `code-css` de un `ct_code_block` se inyecta en la página y aplica vía sus selectores. **No** está scoped al bloque que contiene el Code Block.

Implicación: si el bloque reusable se pega en una página y luego se pega en OTRA página, el CSS del Code Block aplica a las dos. Esto es lo que esperamos para un bloque reusable.

### El panel de Oxygen NO muestra los estilos del Code Block

Si una clase tiene reglas en el Code Block (porque el skill las desvió ahí), al editar la clase desde el panel, NO verás esas reglas. Vivirás un "doble origen de verdad": lo que ves en el panel + lo que está en el Code Block.

**Implicación para el usuario**: si edita una propiedad desde el panel y esa propiedad ya estaba en el Code Block, las dos pueden conflictuar. Generalmente la del Code Block gana (porque carga después), pero puede sorprender.

**El skill avisa** al usuario qué propiedades están en el Code Block para que lo tenga presente al editar.

## Workarounds frecuentes

Esta sección documenta problemas recurrentes y sus soluciones empíricas, descubiertos al validar el skill contra Oxygen real. Cada uno tiene: el problema, la causa, la solución. La mayoría son responsabilidad del USUARIO al escribir su CSS; los que el skill resuelve automáticamente están marcados como tal.

### Workaround 1: `margin: auto` no centra en flex-item

**Problema**: cuando un elemento con `max-width` y `margin-left: auto; margin-right: auto` está dentro de un padre que es `ct_div_block`, no se centra. Queda alineado al inicio.

**Causa**: Oxygen aplica `.ct-div-block { margin: 0px; display: flex; flex-flow: column; align-items: flex-start }` con prioridad CSS a TODOS los div blocks. El `margin: 0` sobrescribe el `auto` del usuario, y el `display: flex` del padre convierte al hijo en flex-item donde `margin auto` se comporta distinto.

**Soluciones** (elegir una):

- **Solución A** — Centrado vía padre con `justify-content`:
  ```css
  .padre { display: flex; flex-direction: row; justify-content: center; }
  .hijo  { max-width: 1240px; width: 100%; }
  ```
  Más limpio. Recomendado cuando el padre es un wrapper sin otro propósito.

- **Solución B** — `width: 100%` + `margin auto` en el hijo:
  ```css
  .hijo { width: 100%; max-width: 1240px; margin-left: auto; margin-right: auto; }
  ```
  Funciona porque al definir `width: 100%`, el flex-grow del item no afecta y los márgenes auto se distribuyen.

- **Solución C** — Forzar con `!important` en `custom-css`:
  Ver Workaround 8 (margin numérico en `ct_div_block`) que es la solución que el skill aplica automáticamente.

### Workaround 2: Iconos `ct_fancy_icon` requieren `icon-size`

**Problema**: cuando definís `.btn-ico { width: 18px; height: 18px }` y la clase se aplica a un `ct_fancy_icon`, el icono SVG interno NO respeta el tamaño. El wrapper div del fancy_icon mide 18×18 pero el SVG interno tiene tamaño default (puede ser ~55px), desbordando el wrapper.

**Causa**: `ct_fancy_icon` renderiza como `<div class="ct-fancy-icon"><svg></svg></div>`. La clase aplica al wrapper, no al SVG. Oxygen tiene una propiedad propia `icon-size` que controla el SVG interno.

**Solución implementada por el skill**: el script auto-detecta cuando una clase con `width` o `height` se aplica a un `ct_fancy_icon` y emite además `icon-size` con el valor de `width` (o `height` si solo hay height). El usuario no necesita hacer nada.

### Workaround 3: `<a>` con icono + texto

**Problema**: HTML como `<a class="btn"><svg></svg> Reservar</a>` perdía el texto "Reservar" cuando el SVG y el texto eran hermanos directos del `<a>`.

**Causa**: el parser anterior solo procesaba tags hijos, ignoraba text nodes sueltos entre tags.

**Solución implementada por el skill**: text nodes sueltos dentro de `ct_link` o `ct_div_block` se procesan como `ct_text_block` hijos. Además, cuando se detecta el patrón icono+texto en un link, el skill auto-añade `display: flex; flex-direction: row; gap: 8` a las clases del link.

**Estructura objetivo**:
```
ct_link [clases-del-link]
├── ct_fancy_icon / ct_code_block [clases-del-icono]
└── ct_text_block "texto del link"
```

### Workaround 4: Bug auto-flex en múltiples clases (pendiente)

**Problema actual del skill**: cuando un link tiene múltiples clases (`class="btn btn--whatsapp btn--sm nav__cta"`), el skill marca TODAS las clases con auto-flex en lugar de solo la modifier. Si `.nav__cta` se usa en otro contexto sin icono, ese contexto recibe flex erróneamente.

**Estado**: bug conocido pendiente de fix.

**Workaround temporal**: revisar las clases auto-flex emitidas en el JSON y limpiar las que no correspondan, o usar clases únicas por componente (Workaround 5).

### Workaround 5: Clases CSS únicas por componente

**Problema**: Oxygen tiene una **tabla global única de selectores**. Si pegás un componente con `.btn` y luego otro componente que también usa `.btn` con valores distintos, el segundo pegado NO sobrescribe el primero. Las clases ya existentes mantienen sus valores originales y el nuevo componente queda referenciando una clase que no tiene los estilos esperados.

**Solución**: usar clases únicas por componente. Si dos componentes necesitan estilos similares, **NO compartir clases base** (`.btn`) sino crear clases distintas (`.heroCta__btn`, `.navCta__btn`) aunque tengan CSS casi idéntico. Se acepta duplicación de CSS a cambio de aislamiento garantizado.

**Síntoma de chocar**: las clases aparecen en Manage → Selectors pero el componente no se ve estilizado. Es porque las propiedades vienen del primer pegado, no del segundo.

### Workaround 6: Centrado de wrapper con max-width

Variante práctica del Workaround 1 cuando se tiene un wrapper tipo `.nav__inner` o `.section__inner` con `max-width`:

| Estrategia | Cuando usarla | Trade-off |
|---|---|---|
| Padre con `justify-content: center` | Padre es wrapper simple sin otro contenido | Limpio pero requiere tocar padre |
| Hijo con `width: 100% + max-width + margin auto` | Padre tiene otros contenidos hermanos | Funciona pero verboso |
| Eliminar wrapper, aplicar todo al padre | Estructura simple | Menos clases, menos editable |

### Workaround 7: `font-family` con comillas anidadas

**Problema potencial** (no validado empíricamente): cuando CSS tiene `font-family: "'Quicksand', system-ui, sans-serif"` o similar con comillas internas, Oxygen puede romper el parseo.

**Solución**: usar nombres sin comillas internas si es posible: `font-family: Quicksand, system-ui, sans-serif`. Si necesitás comillas (espacios en el nombre), usar comillas simples sin envolver: `font-family: 'Helvetica Neue', sans-serif`.

### Workaround 8: `margin` numérico en `ct_div_block` se sobrescribe a 0

**Problema confirmado empíricamente con DevTools.** Oxygen aplica con prioridad CSS:
```css
.ct-div-block { display: flex; flex-flow: column; align-items: flex-start; margin: 0px; }
```

Esta regla viene del CSS compilado de Oxygen (URL del tipo `?xlink=css&ver=X`), es universal en cualquier instalación. Implicación: cualquier `margin-top/bottom/left/right` numérico que el skill emita en una clase aplicada a `ct_div_block` es ignorado al renderizar.

**Diferencia importante:** `ct_text_block` NO recibe esta regla, por lo tanto `margin-top` en `ct_text_block` SÍ funciona nativamente.

**Solución implementada por el skill**: cuando el `block_type` es `ct_div_block` y se procesa una clase con `margin-top/bottom/left/right` numérico, el skill redirige automáticamente esas propiedades a `custom-css` con `!important`. Validado empíricamente: el `custom-css` con `!important` SÍ se aplica visualmente y SÍ se preserva al re-exportar.

**Excepción mantenida:** `margin-X: auto` sigue emitiéndose como `margin-X-unit: auto` (formato nativo). El fix no toca los `auto`, solo los numéricos.

**Trade-off:** el margen pierde editabilidad nativa del panel para esa clase. Vive en `Advanced > Custom CSS` del editor.

### Workaround 9: Listas `<ul>/<ol>/<li>` con useCustomTag

**Validado empíricamente.** Oxygen acepta `useCustomTag: true` con `tag: ul/ol/li` tanto en `ct_div_block` como en `ct_text_block` y `oxy_rich_text`. El DOM resultante es semánticamente correcto: `<ul><li>...</li></ul>`.

**Mapeo implementado por el skill:**
- `<ul>` y `<ol>` → `ct_div_block` con `useCustomTag: true, tag: ul/ol`.
- `<li>` con texto plano simple → `ct_text_block` con `useCustomTag: true, tag: li`.
- `<li>` con HTML inline mixto (incluye `<a>`, `<em>`, `<strong>`, `<span>`, `<small>`, `<br>`, `<i>`, `<b>`, `<u>`, `<code>`) → `oxy_rich_text` con `useCustomTag: true, tag: li`.
- `<li>` con tags estructurales hijos (`<div>`, `<h1-h6>`, `<ul>` anidado, etc.) → `ct_div_block` con `useCustomTag: true, tag: li`.

**Detalle de `oxy_rich_text` con `useCustomTag`:** el skill detecta cuando el `oxy_rich_text` lleva `useCustomTag` y emite el `ct_content` SIN envolver en `<p>`. El wrapper externo ya es el tag custom (ej. `<li>`). Esto produce DOM limpio: `<li><a href="...">link</a></li>` en lugar de `<li><p><a href="...">link</a></p></li>`.

**Caso especial: `<a>` se considera inline para `<li>`.** Aunque semánticamente es un tag estructural, en el contexto de un `<li>` se trata como inline. Esto permite que `<li><a>text</a></li>` mapee a `oxy_rich_text[li]` con `<a>` directo, en lugar de `ct_div_block[li]` con un `ct_link_text` hijo.

### Workaround 10: `oxy_rich_text` con `useCustomTag` no envuelve en `<p>`

Cuando un `oxy_rich_text` tiene `useCustomTag: true` con un tag distinto de `<p>` (ej. `<li>`, `<h2>`, `<blockquote>`), el contenido del `ct_content` se emite SIN envolver en `<p>`. Solo el contenido inline crudo.

Esto fue validado empíricamente: si el skill emite `<p>texto</p>` en un `oxy_rich_text` con tag `li`, Oxygen normaliza al pegar y quita el `<p>`. Por lo tanto, el skill anticipa esa normalización y emite directo lo que Oxygen va a guardar.

## Comportamiento de Oxygen por default

Reglas CSS que Oxygen aplica automáticamente a todos los componentes, descubiertas vía DevTools inspeccionando el frontend renderizado. **Importante**: estas reglas tienen prioridad sobre lo que el usuario escribe en sus clases.

### `.ct-div-block` recibe estilos base

Toda instancia de `ct_div_block` recibe:
```css
.ct-div-block {
  display: flex;
  flex-flow: column;
  align-items: flex-start;
  margin: 0px;
}
```

**Implicaciones**:
- Cualquier div es flex container con dirección column por default. Para layout horizontal hay que añadir `flex-direction: row` explícito.
- `align-items: flex-start` significa que items multilinea quedan alineados a la izquierda por default.
- `margin: 0` sobrescribe `margin auto` del usuario (ver Workaround 1).

### Tabla global de selectores

Oxygen mantiene UN solo registry global de clases CSS. Pegar dos veces el mismo nombre de clase con propiedades distintas NO sobrescribe: el primer pegado gana. Ver Workaround 5.

### `nav` y otros tags semánticos

Cuando un `ct_div_block` tiene `original.tag = "header"`, `"nav"`, `"footer"`, etc., Oxygen lo renderiza como ese tag pero **sigue aplicando los estilos base de `.ct-div-block`**. No hay tratamiento especial por tag semántico.

### Metadata UI: `selector-locked` y `globalconditions`

- `selector-locked: false` aparece en algunos exports. Es preferencia del editor humano (bloqueo de ediciones via UI). **No afecta render**. El skill puede ignorarlo.
- `globalconditions: []` array vacío en algunos exports. Para render condicional (solo si usuario logueado, solo en cierta página, etc.). Array vacío = sin condiciones. **El skill puede ignorarlo**.

### Propiedades nativas vs custom-css: lista actualizada

Tras validación empírica, la lista de propiedades nativas en Oxygen es más grande de lo originalmente documentado. Notables:

**Confirmadas nativas pero no obvio**:
- `oklch()`, `color-mix()`, `hsl()` moderno como string opaco en propiedades de color.
- `var()` en propiedades de color (no en numéricas).
- `box-shadow` como string (preservado, no descompuesto en el panel).
- `cursor`, `white-space` como propiedades de texto.
- `content` (para `:before`/`:after`).

**NO nativas (van a custom-css)**:
- `calc()`, `clamp()`, `dvh`, `svh`, otras unidades modernas.
- `outline-*` (Oxygen lo convierte a `border-*` automáticamente al pegar).
- Cualquier función de cálculo en propiedades numéricas (`padding: calc(...)`, `width: clamp(...)`).
- `flex-basis`.
- `grid-template-areas`, `grid-template-rows` explícitos, `grid-template-columns` no uniformes.

**Decisión arquitectónica**: efectos (filter, backdrop-filter, transforms encadenados, múltiples box-shadows, animations) siempre van a custom-css aunque algunos tengan propiedades nativas parciales. La razón: las propiedades nativas son inconsistentes en el render final.

## Pendientes técnicos

Bugs y limitaciones conocidas vigentes. La lista anterior contenía varios ya resueltos — ver CHANGELOG para historia.

1. **`grid-child-rules` en breakpoints**: el array de spans no se replica automáticamente del top-level a cada breakpoint. Para grids con spans que cambian por viewport, el usuario tiene que escribir explícitamente las clases dentro del media query (soporte parcial). Pendiente: decisión sobre si replicar automáticamente o requerir declaración explícita.

2. **Detector de clases usadas en SVG inline**: cuando un `<svg class="X">` se mapea a `ct_fancy_icon`, la clase `X` puede reportarse como "definida pero no usada en HTML". Falso positivo — la clase sí se aplica al fancy_icon. Pendiente.

3. **Variables CSS (`:root`)**: hoy el contrato exige que el usuario expanda manualmente. Decisión pendiente entre: a) resolver `var()` automáticamente a su valor; b) emitir el `:root` en un code block; c) mantener manual y avisar.

4. **Heurística de `ct_link_button` con BEM `__btn`**: el regex `\b(btn|button|boton)\b` usa word boundary, y `_` es char de palabra. Esto significa que `class="hero__btn"` NO matchea — el `<a>` cae a `ct_link_text` en lugar de `ct_link_button`. Si querés `ct_link_button`, usá guión: `class="hero-btn"`. Pendiente: decisión sobre si extender el regex para reconocer `__btn` o documentar como convención.

5. **`<i class="fa-...">` absorbido por wrapper inline**: cuando un FA icon vive como único hijo de un wrapper cuyos hijos son todos inline, el detector de rich text del padre lo absorbe a `oxy_rich_text` en lugar de Ruta B (`ct_code_block` independiente). Funcionalmente equivalente pero pierde editabilidad como bloque. Workaround: el `<i>` debe ser root del HTML o tener al menos un hermano block-level. Documentado en SKILL.md.

6. **`background-image: linear-gradient(...)` y `box-shadow` múltiple**: aparecen como NATIVOS en el output (no en custom-css) porque `_is_property_native` solo filtra funciones `calc/clamp/var/min/max/env`, no `linear-gradient/radial-gradient/conic-gradient`. Si Oxygen no respeta esos valores en su campo nativo, hay que moverlos manualmente a custom-css tras pegar. Pendiente: decisión sobre si tratar gradientes y multi-shadow como funciones complejas.

## Reglas confirmadas que no requieren acción

Para evitar redescubrirlas:

- **`var()` en colores funciona como string opaco** (`color: var(--primary)` se emite como `color: "var(--primary)"`). El panel de Oxygen lo muestra como texto, no como color picker.
- **`var()` en propiedades numéricas NO funciona** (va a custom-css).
- **`oklch()`, `color-mix()`, `hsl()` moderno son nativos** como string opaco en propiedades de color.
- **`calc()`, `clamp()`, `dvh`, `svh`, `min()`, `max()`** van a custom-css.
- **`outline-*` se convierte a `border-*`** por Oxygen al pegar.
- **`flex-direction: row-reverse`** se descompone a `flex-direction: row` + `flex-reverse: reverse`.
- **`flex-basis`** va a custom-css (Oxygen no lo soporta nativo).
- **`grid-template-columns: repeat(N, 1fr)`** mapea a `grid-column-count: N`. Otros patrones van a custom-css.
- **Solo 4 breakpoints nativos**: 1120 (page-width), 992 (tablet), 768 (phone-landscape), 480 (phone-portrait) con `max-width`.
- **`min-width` en media queries**: va al Code Block con WARN (NO rechaza el input).
- **Pseudo-elementos en clases internas de rich text imposibles vía panel**: se serializan como CSS literal dentro del Code Block.
- **El sufijo del selector se reasigna al pegar**: el valor exacto no es crítico, solo que sea numérico y único.
- **Oxygen acepta `original: []` y `original: {}` indistintamente al pegar**, pero el skill emite `[]` para bloques individuales sin propiedades (formato canónico observado en exports reales).
