# Mapeo de propiedades CSS a Oxygen

Reglas para traducir cada propiedad CSS al formato que usa Oxygen Builder clásico 4.x en el JSON.

## La jerarquía de tres niveles

Para cada propiedad CSS, el skill decide a cuál de tres destinos enviarla:

1. **Nativo**: a `classes[<key>].original` (o a `media.<bp>.original`, o a uno de los states `hover`/`focus`/`active`/`before`/`after`/`disabled`/`checked`/`first-child`/`last-child`/`nth-child(N)`/etc. — ver "Pseudo-clases y states" abajo).
2. **`custom-css`**: dentro del mismo objeto que el nativo, en una clave `custom-css` que es un string CSS plano. Concatenar declaraciones con `;`.
3. **Code Block agregado**: un `ct_code_block` adicional al final del bloque reusable, con CSS completo (incluyendo selectores).

La regla general:
- **Nivel 1** si la propiedad está en la tabla "Propiedades nativas" abajo Y el selector es una clase simple o una pseudo-clase soportada (ver tabla en "Pseudo-clases y states").
- **Nivel 2** si la propiedad NO es nativa pero la regla CSS es una declaración plana sobre una clase con un selector soportado.
- **Nivel 3** si la regla involucra selectores complejos (`>`, `+`, `~`, atributos, descendiente, `:not(...)`), pseudo-clases NO listadas en "Pseudo-clases y states" (ej. `:focus-visible`), at-rules distintos de `@media`, o nesting CSS.

## Formato general de valores nativos

- **Valores numéricos**: como string, sin unidad. `padding-top: 15px` → `"padding-top":"15"`.
- **Unidades no-default**: en clave paralela `<prop>-unit` con la unidad como string. Solo emitir si NO es la unidad default de Oxygen para esa propiedad.
- **Valores no numéricos** (`auto`, `inherit`, etc.): en la clave `<prop>-unit` con el valor textual; la clave principal NO se emite. Ejemplo: `margin: auto` → `"margin-top-unit":"auto"`, `"margin-right-unit":"auto"`, `"margin-bottom-unit":"auto"`, `"margin-left-unit":"auto"`. Sin `margin-top`, `margin-right`, etc.
  - **CAVEAT — margin numérico en `ct_div_block`**: Oxygen aplica `.ct-div-block { margin: 0 }` con prioridad. Cualquier `margin-top/bottom/left/right` numérico que se aplique a una clase usada en `ct_div_block` es ignorado. El skill redirige automáticamente a `custom-css` con `!important`. Solo numéricos: `margin-X: auto` sigue con su formato `margin-X-unit: auto` (sin tocar).
- **Valores con keywords** (como `flex-direction: row` o `text-align: center`): como string tal cual. `"flex-direction":"row"`.
- **Colores hex**: como string con `#`. `"color":"#ffffff"`.
- **Valores `content` (en `:before`/`:after`)**: las comillas externas se quitan. `content: "▸"` → `"content": "▸"` (sin las comillas internas). Validado empíricamente contra el formato que Oxygen produce.

## Defaults de unidades

Para cada propiedad, la unidad default de Oxygen. Si la unidad del CSS coincide, NO emitir `<prop>-unit`. Si difiere, sí emitir.

| Propiedad | Default | Notas |
|---|---|---|
| `padding-*`, `margin-*` | `px` | |
| `border-*-width`, `border-radius`, `border-*-radius` | `px` | |
| `font-size` | `px` | Si viene en `rem`, `em`, `%`, emitir unit |
| `letter-spacing` | `px` | |
| `width`, `height`, `max-width`, `min-width`, `max-height`, `min-height` | (sin default fijo) | **Siempre emitir `<prop>-unit`**, incluso para `px`, para evitar ambigüedad. Oxygen es estricto aquí. |
| `top`, `right`, `bottom`, `left` | `px` | |
| `gap`, `column-gap`, `row-gap` | `px` | |
| `line-height` | (unitless) | Si viene sin unidad (`1.6`), emitir como string `"1.6"` sin `*-unit`. Si viene con unidad (`1.6em`, `24px`), emitir con `<prop>-unit`. |

Cualquier propiedad no listada arriba: tratar como sin unidad (emitir el valor tal cual como string).

## Expansión de shorthands

El skill expande estos shorthands en propiedades individuales. NO emite el shorthand original.

### `padding` y `margin`

| Forma CSS | Expansión |
|---|---|
| `padding: 15px` | `padding-top: 15`, `padding-right: 15`, `padding-bottom: 15`, `padding-left: 15` |
| `padding: 10px 20px` | top/bottom = 10, left/right = 20 |
| `padding: 10px 20px 30px` | top = 10, left/right = 20, bottom = 30 |
| `padding: 10px 20px 30px 40px` | top = 10, right = 20, bottom = 30, left = 40 |

Mismo patrón para `margin`.

**Soporte para funciones CSS (`calc`, `var`, `clamp`, `min`, `max`)**: el expansor usa un splitter top-level que respeta paréntesis balanceados (`_split_top_level`). Casos soportados:

- `padding: calc(10px + 1vw)` → los cuatro lados reciben `calc(10px + 1vw)` íntegro.
- `padding: clamp(8px, 1vw, 16px)` → idem, el `clamp(...)` se preserva como un solo token a pesar de las comas internas.
- `padding: var(--p1) var(--p2)` → top/bottom reciben `var(--p1)`, left/right reciben `var(--p2)`.
- `padding: calc(...) 20px` → mezcla de función y valor literal, también funciona.

**Importante sobre destino del valor**: aunque el shorthand ahora se expande correctamente, las funciones CSS en propiedades numéricas (`padding`, `margin`, `gap`, `width`, etc.) siguen yendo a `custom-css`, no a propiedades nativas de Oxygen. Lo que cambia con el fix es que el valor llega al `custom-css` íntegro y por lado correcto, en lugar de fragmentos corruptos.

### `border`

`border: 1px solid #ccc` se expande a TRES propiedades por cada lado:

```
border-<side>-width: 1
border-<side>-style: solid
border-<side>-color: #cccccc
```

Si el CSS especifica solo un lado (`border-top: 1px solid red`), expandir solo ese lado.

**Soporte para colores por palabra y funciones de color**: el parser de border (`_parse_border_value`) clasifica cada token por tipo en este orden:
1. **style**: keyword de border-style (`solid`, `dashed`, `dotted`, etc.).
2. **width**: número con o sin unidad, o keyword (`thin`, `medium`, `thick`).
3. **color**: todo lo demás. Incluye hex (`#fff`), funciones (`rgb(...)`, `rgba(...)`, `hsl(...)`, `oklch(...)`, `var(--c)`), keywords (`transparent`, `currentcolor`), y palabras de color (`red`, `green`, `blue`).

Casos validados:
- `border: 2px solid green` → width=2px, style=solid, color=green ✓
- `border: thin solid blue` → width=thin, style=solid, color=blue ✓
- `border: 2px solid rgb(255, 0, 0)` → width=2px, style=solid, color=rgb(255, 0, 0) ✓
- `border: 1px solid var(--accent)` → width=1px, style=solid, color=var(--accent) ✓

**Limitación residual**: si el shorthand `border` no especifica width pero usa una **función para width** (ej. `border: calc(1px + 0.1em) solid red`), el `calc(...)` se clasificará como color por la heurística de fallback. Es un caso muy raro; workaround es escribir las propiedades expandidas manualmente.

### `border-radius`

| Forma CSS | Expansión |
|---|---|
| `border-radius: 8px` | `border-top-left-radius: 8`, `border-top-right-radius: 8`, `border-bottom-left-radius: 8`, `border-bottom-right-radius: 8` |
| `border-radius: 8px 4px` | TL/BR = 8, TR/BL = 4 |
| `border-radius: 8px 4px 2px` | TL = 8, TR/BL = 4, BR = 2 |
| `border-radius: 8px 4px 2px 1px` | TL = 8, TR = 4, BR = 2, BL = 1 |

### `flex` shorthand

| Forma CSS | Tratamiento |
|---|---|
| `flex: 1` | `flex-grow: 1`, `flex-shrink: 1`. Sin `flex-basis` (Oxygen no soporta). |
| `flex: 2 1` | `flex-grow: 2`, `flex-shrink: 1`. |
| `flex: 1 1 200px` | `flex-grow: 1`, `flex-shrink: 1`. **Avisar**: `flex-basis: 200px` se omite. Si el usuario lo necesita, va a `custom-css`. |

### `flex-direction` con reverse

| Forma CSS | Tratamiento |
|---|---|
| `flex-direction: row` | `flex-direction: "row"` |
| `flex-direction: column` | `flex-direction: "column"` |
| `flex-direction: row-reverse` | `flex-direction: "row"` + `flex-reverse: "reverse"` |
| `flex-direction: column-reverse` | `flex-direction: "column"` + `flex-reverse: "reverse"` |

`flex-reverse` es una propiedad propia de Oxygen, no estándar CSS.

### Otros shorthands

- `font`: NO expandir, demasiado complejo. Mandar al `custom-css` o pedir al usuario que lo descomponga.
- `background` shorthand: el skill expande automáticamente para casos de color simple. Casos manejados:
  - `background: #fff` → `background-color: "#fff"` nativo.
  - `background: rgba(...)`, `hsl(...)`, `oklch(...)`, `color-mix(...)`, `transparent`, `currentcolor`, o palabra (`red`, `blue`) → `background-color` nativo.
  - `background: linear-gradient(...)`, `background: url(...)`, o cualquier shorthand con múltiples valores compuestos → se mantiene como `background: ...` en `custom-css`.
- `transition`, `animation`: `custom-css` siempre. Oxygen tiene panel propio pero no es trivial mapear.

## CSS Grid

Oxygen Grid NO es CSS Grid estándar. Modelo de Oxygen:

- `grid-column-count`: número de columnas (todas iguales en ancho).
- `grid-column-gap` / `grid-row-gap`: gaps.
- `grid-child-rules`: array de objetos describiendo el span de cada hijo.

### Cuándo mapear nativo a Oxygen Grid

El skill mapea a Oxygen Grid cuando TODAS estas condiciones se cumplen:

1. `grid-template-columns` es de la forma `repeat(N, 1fr)` o `1fr 1fr ... 1fr` (N veces el mismo valor).
2. No hay `grid-template-rows` con valores explícitos.
3. No hay `grid-template-areas`.
4. Los items usan solo `grid-column: span N` o `grid-row: span N`, NO posicionamiento absoluto.
5. No hay custom properties ni `calc()` en propiedades de grid.

### Cómo emitir Oxygen Grid

```json
"display": "grid",
"grid-column-count": "<N>",
"grid-column-gap": "<gap-en-px>",
"grid-row-gap": "<row-gap-en-px>",
"grid-child-rules": [
  null,
  {"child-index": 1, "column-span": "<N>", "row-span": "<N>"},
  {"child-index": 2, "column-span": "<N>", "row-span": "<N>"}
]
```

- El primer elemento del array es siempre `null`. Los hijos comienzan en índice 1.
- Si un hijo no tiene span configurado, se emite con `column-span: ""` y `row-span: ""` (strings vacíos).
- En breakpoints, **repetir el array completo de `grid-child-rules`** y también `display: grid`.

### Cuándo no mapea nativo

Si el grid es complejo (anchos desiguales, posicionamiento absoluto, áreas), enviar a `custom-css`:

- `grid-template-columns`, `grid-template-rows`, `grid-template-areas`, `grid-area`, `grid-column`, `grid-row` con valores no soportados → `custom-css` de la clase.
- Pero el `display: grid` sí va nativo (Oxygen lo entiende).
- Y `gap`, `column-gap`, `row-gap` van nativos como `grid-column-gap`, `grid-row-gap` cuando son simples.

## Pseudo-clases y states

Oxygen acepta varias pseudo-clases y pseudo-elementos como **states nativos** del selector. Esta tabla muestra el destino de cada tipo de selector CSS:

| Selector CSS | Destino |
|---|---|
| `.foo { ... }` | `classes[foo].original` |
| `.foo:hover { ... }` | `classes[foo].hover` |
| `.foo:focus { ... }` | `classes[foo].focus` |
| `.foo:active { ... }` | `classes[foo].active` |
| `.foo:disabled { ... }` | `classes[foo].disabled` |
| `.foo:checked { ... }` | `classes[foo].checked` |
| `.foo:first-child { ... }` | `classes[foo].first-child` |
| `.foo:last-child { ... }` | `classes[foo].last-child` |
| `.foo:before { ... }` o `.foo::before { ... }` | `classes[foo].before` |
| `.foo:after { ... }` o `.foo::after { ... }` | `classes[foo].after` |
| `.foo:nth-child(2)` | `classes[foo].nth-child(2)` |
| `.foo:nth-child(2n+1)` | `classes[foo].nth-child(2n+1)` |
| `.foo:nth-child(odd)` | `classes[foo].nth-child(odd)` |
| `.foo:nth-of-type(N)` | `classes[foo].nth-of-type(N)` (por simetría, NO validado en frontend) |
| `.foo:nth-last-child(N)` | `classes[foo].nth-last-child(N)` (por simetría, NO validado) |
| `.foo:nth-last-of-type(N)` | `classes[foo].nth-last-of-type(N)` (por simetría, NO validado) |
| `@media (max-width: 992px) { .foo { ... } }` | `classes[foo].media.tablet.original` |
| `@media (max-width: 992px) { .foo:hover { ... } }` | `classes[foo].media.tablet.hover` |
| `@media (max-width: 992px) { .foo:state { ... } }` | `classes[foo].media.tablet.<state>` |
| `.foo:focus-visible`, `.foo:focus-within`, `.foo:placeholder`, etc. (no validados) | Code Block |
| `.foo:not(...)` | Code Block (el argumento es un selector, no un state) |
| `.foo > .bar`, `.foo + .bar`, `.foo ~ .bar`, `.foo .bar` | Code Block |
| `.foo[data-x]`, `.foo[disabled]` | Code Block |
| `@keyframes ...`, `@font-face`, etc. | Code Block |
| `@media (min-width: ...) { .foo { ... } }` | Code Block (con WARN: Oxygen solo soporta max-width nativo) |

### Formato de states en breakpoints

Cuando un state aparece dentro de un media query:

```css
.foo:hover { background: red; }

@media (max-width: 768px) {
  .foo:hover { background: darkred; }
  .foo:focus { background: green; }
}
```

Se emite:

```json
"foo": {
  "original": {...},
  "hover": {"background-color": "red"},
  "media": {
    "phone-landscape": {
      "original": {...},
      "hover": {"background-color": "darkred"},
      "focus": {"background-color": "green"}
    }
  },
  "key": "foo"
}
```

## Excepciones por tipo de bloque

Algunas propiedades CSS se renombran cuando aplican a tipos específicos.

### `ct_link_button`

| CSS | Oxygen |
|---|---|
| `color` | `button-text-color` |
| `background-color` | `background-color` (igual) |
| Otras: probablemente sigan el patrón estándar | Verificar caso por caso |

Si el CSS aplica a una clase usada por un `ct_link_button`, traducir `color` → `button-text-color`. Si la misma clase se usa también en otros bloques (no botones), considerar que el CSS aplica al botón Y a los otros con sintaxis distinta. **Caso problemático**: el skill avisa y deja la clase con `color` para los no-botones y duplica la clase con `button-text-color` para los botones. O simplemente avisa al usuario que use clases distintas para botones.

## Propiedades nativas de Oxygen (lista incompleta)

Esta lista crece a medida que descubrimos propiedades. Si una propiedad CSS NO está aquí Y no es de un caso especial (grid, flex, etc.), el skill la manda a `custom-css`.

### Layout
- `display`, `flex-direction`, `flex-wrap`, `justify-content`, `align-items`, `align-content`, `align-self`
- `flex-grow`, `flex-shrink`, `flex-reverse` (propio de Oxygen)
- `gap`, `column-gap`, `row-gap` (en flex), `grid-column-gap`, `grid-row-gap` (en grid). **Importante:** el skill distingue: si `display: flex` emite `gap` directo; si `display: grid` emite `grid-row-gap` + `grid-column-gap`.
- `grid-column-count`, `grid-child-rules` (propios de Oxygen)
- `position`, `top`, `right`, `bottom`, `left`, `z-index`
- `overflow`, `overflow-x`, `overflow-y`

### Espaciado
- `padding-*`, `margin-*`
- `width`, `height`, `min-width`, `min-height`, `max-width`, `max-height`

### Tipografía
- `font-family`, `font-size`, `font-weight`, `font-style`
- `color`, `line-height`, `letter-spacing`
- `text-align`, `text-transform`, `text-decoration`

### Visual
- `background-color`, `background-image`, `background-position`, `background-repeat`, `background-size`
- `border-*-width`, `border-*-style`, `border-*-color`
- `border-radius`, `border-*-radius`
- `opacity`, `box-shadow`

### Pseudo-elementos
- `content` (para `:before` y `:after`). Las comillas externas se quitan al emitir.

### Botones (excepción)
- `button-text-color` (en lugar de `color` para `ct_link_button`)

### Iconos (ct_fancy_icon)
- `icon-size` (propio de Oxygen). El skill la auto-emite cuando una clase con `width` o `height` se aplica a `ct_fancy_icon`. Sin esta propiedad, el SVG interno queda en tamaño default ignorando `width`/`height` del wrapper.

### Funciones de color modernas (nativas como string opaco)
- `oklch(...)`, `color-mix(...)`, `hsl(...) moderno`, `hsla(...)`: validado empíricamente que Oxygen las acepta nativas en propiedades de color. El panel las muestra como texto, no como color picker.
- `var(--nombre)`: nativo SOLO en propiedades de color. En numéricas (`padding`, `width`, etc.) va a `custom-css`.

### Imágenes
- `object-fit`, `object-position`

## Propiedades que van a `custom-css` por defecto

Lista no exhaustiva. Cualquier propiedad CSS válida pero no soportada nativamente por Oxygen:

- `aspect-ratio`
- `clip-path`
- `mask`, `mask-image`, `-webkit-mask`
- `backdrop-filter`, `filter` (con valores complejos)
- `flex-basis`
- `grid-template-columns`, `grid-template-rows`, `grid-template-areas` (cuando son complejos)
- `grid-area`, `grid-column`, `grid-row` (con posicionamiento absoluto)
- Custom properties (`--var`)
- `calc()`, `clamp()`, `min()`, `max()` en cualquier valor
- `transform` (Oxygen tiene serialización propia compleja, ver `oxygen-quirks.md`)
- `transition`, `animation`
- `cursor`
- `pointer-events`
- `user-select`
- `will-change`
- `mix-blend-mode`, `isolation`
- `linear-gradient(...)` y similares en `background` (Oxygen tiene formato `gradient` estructurado, ver `oxygen-quirks.md`)

## Formato del `custom-css`

El valor de `custom-css` es un string CSS plano. Ejemplo:

```json
"custom-css": "aspect-ratio: 16/9; flex-basis: 200px; clip-path: circle(50%);"
```

Reglas:
- Cada declaración termina con `;`.
- Separadas por un espacio.
- Sin saltos de línea.
- Sin comentarios CSS (no se ha probado si Oxygen los acepta; mejor no incluir).
- El selector NO se incluye: `custom-css` aplica al selector de la clase automáticamente.

## Formato del `ct_code_block` agregado

Si hay reglas que necesitan ir al Code Block, se emite UN único `ct_code_block` al final del nodo raíz del bloque reusable, como último hijo. Su contenido:

```json
{
  "id": <ct_id_siguiente>,
  "name": "ct_code_block",
  "options": {
    "ct_id": <id>,
    "ct_parent": <ct_id del nodo raíz del bloque reusable>,
    "selector": "code_block-<id>-<sufijo>",
    "original": {
      "code-css": "<CSS completo con todos los selectores>",
      "code-js": "",
      "code-php": ""
    },
    "nicename": "Code Block (#<id>)",
    "activeselector": false
  },
  "depth": 3
}
```

El `code-css` contiene CSS completo (con selectores), agrupado por clase y media query, en el orden en que aparecen en el CSS de entrada.

Si NO hay reglas para el Code Block, NO emitir el bloque.

## Reglas operativas del skill

Comportamientos automáticos del skill que NO vienen del CSS del usuario.

### Auto-adición de propiedades

- **`flex-direction: row` por default cuando hay `display: flex`**: Oxygen no asume row por default. El skill lo añade automáticamente si la clase no lo trae explícito.
- **Auto-flex en links con icono + texto**: cuando un `<a>` tiene icono + texto hermanos, el skill marca las clases del link y les añade `display: flex; flex-direction: row; gap: 8`. Solo si esas propiedades NO estaban en el CSS.
- **Auto-`icon-size` en `ct_fancy_icon`**: cuando una clase con `width` o `height` se aplica a un fancy_icon, el skill emite también `icon-size` con el valor de `width` (asume icono cuadrado).
- **Auto-`margin !important` para `ct_div_block`**: cuando una clase con `margin-top/bottom/left/right` numérico se aplica a un `ct_div_block`, el skill redirige a `custom-css` con `!important`. Necesario porque Oxygen sobrescribe `margin: 0` por default.
- **Auto-`custom-attributes` desde atributos HTML**: cualquier atributo HTML que no esté en la lista negra (`class`, `id`, `href`, `target`, `src`, `alt`, `srcset`, `width`, `height`, `loading`, `xlink:href`) se preserva como `original.custom-attributes`.

### Pseudo-clases y pseudo-elementos como states nativos (Fase 3)

Lo soportado por el skill v3 como sub-keys de una clase (validado empíricamente):

| CSS | Oxygen sub-key | Estado |
|---|---|---|
| `:hover` | `hover` | Validado |
| `:focus` | `focus` | Validado |
| `:active` | `active` | Validado |
| `:disabled` | `disabled` | Validado |
| `:checked` | `checked` | Validado |
| `:first-child` | `first-child` | Validado |
| `:last-child` | `last-child` | Validado |
| `:before` / `::before` | `before` | Validado (con `content`) |
| `:after` / `::after` | `after` | Validado (con `content`) |
| `:nth-child(N)` | `nth-child(N)` | Validado (con N=número, expresión, keyword) |
| `:nth-of-type(N)` | `nth-of-type(N)` | Por simetría (NO validado) |
| `:nth-last-child(N)` | `nth-last-child(N)` | Por simetría (NO validado) |
| `:nth-last-of-type(N)` | `nth-last-of-type(N)` | Por simetría (NO validado) |

Cualquier otra pseudo-clase no listada va al Code Block agregado.

### Funciones CSS modernas

| Función | Destino |
|---|---|
| `var()` en color | **Nativo** como string opaco |
| `var()` en numérico | `custom-css` |
| `oklch()`, `color-mix()`, `hsl()` moderno | **Nativo** como string opaco |
| `calc()`, `clamp()`, `min()`, `max()` en cualquier valor | `custom-css` (el shorthand expansion respeta los paréntesis) |
| `dvh`, `svh`, otras unidades modernas | `custom-css` |

### Conversiones implícitas de Oxygen

Cosas que Oxygen hace al pegar el JSON, independiente de lo que emita el skill:

- **`outline-*` → `border-*`**: Oxygen lo convierte automáticamente. Si el skill emite `outline-width: 2`, Oxygen lo guarda como `border-width: 2`.
- **`oxy_rich_text` con `useCustomTag` quita `<p>` envolvente**: si el skill emite `<p>texto</p>` en un rich text con tag `li`, Oxygen normaliza a `texto` (sin `<p>`). El skill anticipa esto y emite directo sin `<p>`.
- **Sufijo del selector reasignado**: cualquier valor que envíes en `--selector-suffix` Oxygen lo cambia al `post_id` de la página destino al pegar. El valor exacto del input no es crítico, solo que sea único.

### Manejo de espaciado vertical

Workaround documentado en oxygen-quirks.md. Resumen:
- `margin-top/bottom` numérico en `ct_div_block` → custom-css con !important (auto-redirigido por skill).
- `margin-top/bottom` numérico en `ct_text_block` → nativo (funciona).
- `margin: auto` en flex-item → no funciona aunque emita formato correcto. Usar `justify-content: center` en el padre o `width: 100% + margin auto`.
