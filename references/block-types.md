# Tipos de bloque de Oxygen Builder clásico

Tabla de mapeo HTML tag → tipo de bloque interno, con las propiedades específicas que cada tipo tiene en `options.original`.

## Tabla principal

| HTML tag | `name` interno | `options.original` específicos | `ct_content`? | Notas |
|---|---|---|---|---|
| `<div>` | `ct_div_block` | `[]` (vacío) | No | Default, sin tag custom |
| `<section>` | `ct_div_block` | `{"tag":"section"}` | No | Cualquier Div con tag custom |
| `<article>`, `<header>`, `<footer>`, `<aside>`, `<nav>`, `<main>`, `<blockquote>` | `ct_div_block` | `{"tag":"<tag>"}` | No | Mismo patrón que section |
| `<h1>`–`<h6>` | `ct_headline` | `{"tag":"hN"}` para N≠1; `[]` para h1 (h1 es default) | Sí | El texto va en `ct_content` |
| `<p>` | `ct_text_block` | `[]` (vacío, p es default) | Sí | El texto va en `ct_content` |
| `<span>` | `ct_text_block` | `{"useCustomTag":"true","tag":"span"}` | Sí | `useCustomTag` obligatorio para tags ≠ p |
| Otros tags inline (`<em>`, `<strong>`, `<small>`) | `ct_text_block` | `{"useCustomTag":"true","tag":"<tag>"}` | Sí | Mismo patrón que span |
| `<a>` con hijos | `ct_link` | `[]` o `{"url":"...","target":"..."}` | No | Es un wrapper, los hijos van en `children` |
| `<a>` solo con texto | `ct_link_text` | `[]` o con url/target | Sí | Hoja, no tiene children |
| `<a class="...boton...">` | `ct_link_button` | `{"url":"...","target":"..."}` o `[]` si vacío | Sí | El texto del botón en `ct_content`. Determinado por clase típica de botón (`btn`, `boton`, `button`). El `ct_link_button` renderiza un `<a>` HTML estilizado como botón — correcto para CTAs navegacionales. |
| `<button>` con texto plano | `ct_text_block` | `{"useCustomTag":"true","tag":"button"}` | Sí | El texto en `ct_content`. Renderiza un `<button>` HTML real. Atributos (`type`, `onclick`, `aria-*`, `data-*`, etc.) van como `custom-attributes`. Validado empíricamente. |
| `<button>` con HTML inline mixto | `oxy_rich_text` | `{"useCustomTag":"true","tag":"button"}` | Sí (sin `<p>` envolvente) | El contenido inline en `ct_content`. Inline incluye: `<em>`, `<strong>`, `<span>`, `<small>`, `<br>`, `<i>`, `<b>`, `<u>`, `<code>`. Atributos preservados como `custom-attributes`. Validado empíricamente. |
| `<button>` con hijos estructurales | `ct_div_block` | `{"useCustomTag":"true","tag":"button"}` | No | Si el `<button>` tiene `<svg>`, `<div>`, `<span>` con bloques, etc., se mapea como contenedor. Los hijos se procesan recursivamente. Atributos preservados como `custom-attributes`. Validado empíricamente. |
| `<ul>`, `<ol>` | `ct_div_block` | `{"useCustomTag":"true","tag":"ul"}` o `"ol"` | No | Validado empíricamente. Renderiza como `<ul>`/`<ol>` semántico. |
| `<li>` con texto plano puro | `ct_text_block` | `{"useCustomTag":"true","tag":"li"}` | Sí | El texto va en `ct_content`. Renderiza como `<li>texto</li>`. |
| `<li>` con HTML inline mixto | `oxy_rich_text` | `{"useCustomTag":"true","tag":"li"}` | Sí (sin `<p>` envolvente) | El contenido inline va en `ct_content` directo. Inline incluye: `<em>`, `<strong>`, `<span>`, `<small>`, `<br>`, `<i>`, `<b>`, `<u>`, `<code>`, `<a>`. |
| `<li>` con tags estructurales hijos | `ct_div_block` | `{"useCustomTag":"true","tag":"li"}` | No | Si el `<li>` tiene `<div>`, `<h1-h6>`, `<ul>` anidado, etc., se mapea como contenedor. |
| `<img>` | `ct_image` | Ver "Bloque ct_image" abajo | No | Hoja |
| Tag desconocido | `ct_div_block` | `[]` | No | El skill emite WARN. |

**Nota sobre `[]` vs `{}` en `original`** (cambio en v3): para bloques individuales sin propiedades, el formato canónico es `[]` (array vacío), no `{}`. Validado contra JSONs reales de Oxygen. Cuando el bloque tiene cualquier propiedad (incluso solo `tag`), pasa a `{...}` (objeto).

## Estructura común a todos los componentes

Todos los nodos del árbol llevan:

```json
{
  "id": <int>,
  "name": "<tipo>",
  "options": {
    "ct_id": <int igual a id>,
    "ct_parent": <ct_id del padre directo>,
    "selector": "<tipo-base>-<ct_id>-<sufijo>",
    "original": <objeto {...} o array vacío []>,
    "nicename": "<Tipo> (#<ct_id>)",
    "classes": [<lista de strings>],
    "activeselector": <string o false>
  },
  "depth": <int>,
  "children": [<lista>]
}
```

### Reglas de los campos comunes

- **`id` y `ct_id`**: enteros únicos en la página. Asignar secuencialmente comenzando en un valor que no choque con bloques existentes. El script empieza desde 2 (el 1 está reservado para el bloque raíz de la página normalmente). Oxygen reasigna estos IDs al pegar.
- **`ct_parent`**: el `ct_id` del padre directo. Para el nodo raíz del bloque reusable, usar `100007` como placeholder. Oxygen lo reasigna al pegar. **Nota**: este valor `100007` solo aplica a bloques reusables stand-alone exportados; para hijos directos de página es `0`. El skill emite formato bloque reusable.
- **`selector`**: patrón `<tipo-base>-<ct_id>-<sufijo>`. El `<tipo-base>` se obtiene removiendo `ct_` del `name`. Ejemplos:
  - `ct_div_block` → `div_block`
  - `ct_headline` → `headline`
  - `ct_text_block` → `text_block`
  - `ct_link_button` → `link_button`
  - `ct_link` → `link`
  - `ct_link_text` → `link_text`
  - `ct_image` → `image`
  - `oxy_rich_text` → `_rich_text` (caso especial: el prefijo es `oxy_` no `ct_`)
  - **Sufijo**: es el `post_id` de WordPress del template o página donde el bloque vive. Se pasa al script via `--selector-suffix VALUE`. Si no se pasa, se genera aleatorio de 4 dígitos. Oxygen reasigna el sufijo al pegar el bloque en una página distinta.
- **`nicename`**: patrón `"<Tipo capitalizado> (#<ct_id>)"`. Mapeo de tipos:
  - `ct_div_block` → `Div`
  - `ct_headline` → `Heading`
  - `ct_text_block` → `Text`
  - `ct_link_button` → `Button`
  - `ct_link` → `Link Wrapper`
  - `ct_link_text` → `Text Link`
  - `ct_image` → `Image`
  - `ct_section` → `Section` (no usado por el skill, pero documentado)
  - `ct_fancy_icon` → `Icon`
  - `ct_code_block` → `Code Block`
  - `oxy_rich_text` → `Rich Text`
- **`classes`**: array de strings con los nombres de clase tal como aparecen en el HTML, en el orden del atributo `class`. Si el elemento no tiene clases, omitir el campo.
- **`activeselector`**: la última clase del array si hay clases; `false` (booleano JSON) si el bloque no tiene clases.
- **`depth`**: entero, profundidad en el árbol. El nodo raíz del bloque reusable es `depth: 2`. Cada nivel hijo suma 1. **Nota**: el depth varía según contexto de exportación — bloque reusable empieza en 2, página completa empieza en 0. El skill emite formato bloque reusable.
- **`original`**: ver tabla principal y "Reglas de `original`" abajo.

### Reglas de `original`

- `ct_div_block` con tag custom (section, article, etc.): `{"tag":"<tag>"}`.
- `ct_div_block` sin tag custom y sin otras propiedades CSS directas: `[]` (array vacío).
- `ct_headline` h1: `[]` o `{"tag":"h1"}`. **Inconsistencia conocida**: el skill emite `[]` para h1 y `{"tag":"hN"}` para h2-h6. Pendiente decidir uniformar.
- `ct_text_block` con tag p y sin propiedades: `[]`.
- `ct_text_block` con tag distinto de p: `{"useCustomTag":"true","tag":"<tag>"}`. Incluye `<li>` con texto plano.
- `ct_link_button`: `{"url":"<url>","target":"<target>"}`. Si no hay URL, las keys quedan vacías.
- `ct_link`: `[]` o con url/target si hay.
- `ct_link_text`: `[]` o con url/target si hay.
- `ct_image`: ver bloque `ct_image` abajo.
- `ct_fancy_icon`: `{"icon-id":"<sprite-id>"}` para iconos via Ruta A (validado empíricamente).
- `ct_code_block`: `{"code-css":"...","code-js":"...","code-php":"..."}` con strings vacías para los campos no usados.
- `oxy_rich_text` con `<p>` default: `[]`. El `ct_content` se envuelve en `<p>` automáticamente.
- `oxy_rich_text` con `useCustomTag` (ej. `tag: li`): `{"useCustomTag":"true","tag":"li"}`. El `ct_content` se emite SIN envolver en `<p>`.
- `ct_div_block` con `useCustomTag` (ej. `tag: ul`): `{"useCustomTag":"true","tag":"ul"}`. NO confundir con `ct_div_block` con `tag` directo (que es para `<section>`, `<header>`, etc.).
- Cualquier bloque con `custom-attributes`: `original` se vuelve dict obligatoriamente para alojarlos. Ver sección "custom-attributes" abajo.

## custom-attributes (nuevo en v3)

Atributos HTML arbitrarios (`aria-*`, `data-*`, `role`, `rel`, `tabindex`, `title`, etc.) se preservan en `original.custom-attributes`:

```json
"original": {
  "custom-attributes": [
    {"name": "aria-label", "value": "Cerrar"},
    {"name": "data-action", "value": "open-modal"},
    {"name": "role", "value": "button"}
  ]
}
```

**Atributos NO incluidos como custom-attributes** (manejados por otra lógica):
- `class`, `id` (estructurales)
- `href`, `target` (ya manejados en `<a>`)
- `src`, `alt`, `srcset`, `width`, `height`, `loading` (ya manejados en `<img>`)
- `xlink:href` (ya manejado en `<svg><use>`)

Todo lo demás se preserva. Validado empíricamente: Oxygen acepta el formato y los atributos sobreviven al pegado.

## Bloque `ct_image`

Caso especial. Las propiedades de imagen viven en `options.original` y son:

```json
"original": {
  "image_type": "2",
  "attachment_size": "full",
  "attachment_id": 0,
  "attachment_height": <int o omitir>,
  "attachment_width": <int o omitir>,
  "attachment_url": "<URL completa>"
}
```

- `image_type: "2"`: tipo "imagen estándar de WordPress". Hardcoded.
- `attachment_size: "full"`: tamaño de imagen seleccionado. Hardcoded a `"full"` por defecto.
- `attachment_id`: **siempre 0**. El usuario debe reasignar la imagen al media library tras pegar.
- `attachment_height` y `attachment_width`: enteros si el HTML `<img>` tiene atributos `height` y `width`. Si no, omitir.
- `attachment_url`: la URL del `src` del `<img>`.

Si el `<img>` tiene `alt`, no hay un campo evidente para `alt` en `options.original`. Probablemente Oxygen lo guarda en otro lado o lo deriva del attachment de WordPress. Por ahora: el skill **avisa al usuario** que el alt no se transfiere y debe ponerlo manualmente tras pegar.

## Estructura de `classes` (top-level)

Las clases CSS no viven dentro de los componentes; viven en un objeto top-level del JSON, hermano de `component`:

```json
{
  "component": { ... árbol de bloques ... },
  "classes": {
    "<nombre-clase>": {
      "key": "<nombre-clase>",
      "original": {
        // propiedades nativas + custom-css
      },
      "media": {
        "<breakpoint>": {
          "original": { ... },
          "hover": { ... },
          "focus": { ... }
          // cualquier state nativo en breakpoint
        }
      },
      "hover":   { ... },
      "focus":   { ... },
      "active":  { ... },
      "before":  { ... },
      "after":   { ... },
      "disabled": { ... },
      "checked": { ... },
      "first-child": { ... },
      "last-child":  { ... },
      "nth-child(2)":     { ... },
      "nth-child(2n+1)":  { ... },
      "nth-child(odd)":   { ... }
    }
  }
}
```

### Cuándo emitir cada clave

- **`original`**: siempre, aunque sea `{}` vacío (si la clase es referenciada en HTML pero no tiene CSS, ver sección Fix 3 más abajo).
- **`media`**: solo si hay reglas en al menos un breakpoint. Dentro de `media`, solo emitir los breakpoints con reglas.
- **`hover`, `focus`, `active`, `before`, `after`, `disabled`, `checked`, `first-child`, `last-child`, `nth-child(N)`, etc.**: solo si hay reglas para esa pseudo-clase/elemento en el CSS del default. Ver `oxygen-quirks.md` sección "Pseudo-clases y pseudo-elementos como states nativos" para la lista completa.
- **`media.<bp>.<state>`**: solo si hay reglas para ese state dentro del media query.
- **`key`**: siempre, igual al nombre de la clase.

### Clases referenciadas en HTML sin CSS (nuevo en v3)

Si una clase aparece en el HTML pero no tiene reglas CSS asociadas (ej. `class="logos-marquee"` cuando el styling viene de JS, un stylesheet global, o un Code Block adicional), el skill la preserva en `classes` con `original: {}`:

```json
"logos-marquee": {
  "key": "logos-marquee",
  "original": {}
}
```

Esto evita que Oxygen pierda la asociación HTML → clase. El skill emite WARN cuando esto pasa, para que el usuario verifique si quiso poner CSS y se olvidó.

## Tipos de bloque NO soportados (deliberadamente)

El skill rechaza o redirige estos casos:

- `ct_section` (Section nativa de Oxygen): no se emite. Toda `<section>` es `ct_div_block` con tag section.
- `ct_columns` / `ct_column`: no se emiten. Layouts en columnas se hacen con `ct_div_block` y CSS flex/grid.
- `oxy_dynamic_list`, `oxy_gallery`, `oxy-shape-divider`: fuera de scope. Se mapean a `ct_div_block` con WARN.
- Bloques dinámicos (sliders, accordions, tabs, repeaters, dynamic data, gallery): fuera de scope. El skill avisa y sugiere crearlos manualmente.

## Bloques especiales descubiertos

### `ct_fancy_icon`

Para iconos via sprite SVG (`<svg><use xlink:href="#XxxIcon-nombre"/></svg>`). Validado empíricamente.

```json
{
  "id": <int>,
  "name": "ct_fancy_icon",
  "options": {
    "ct_id": <int>,
    "ct_parent": <int>,
    "selector": "fancy_icon-<id>-<sufijo>",
    "original": {"icon-id": "<sprite-id>"},
    "nicename": "Icon (#<id>)",
    "classes": [<...>],
    "activeselector": <...>
  },
  "depth": <int>
}
```

**Detalle crítico — `icon-size`**: el `<svg>` interno NO respeta el `width`/`height` del wrapper. Para que el ícono se vea al tamaño correcto, la clase aplicada al `ct_fancy_icon` debe tener una propiedad `icon-size` (propia de Oxygen). El skill la auto-emite cuando detecta `width` o `height` en una clase aplicada a fancy_icon. Sin `icon-size`, el SVG queda en tamaño default (~55px).

### `ct_code_block`

Para SVGs inline crudos, FontAwesome 6+ (`<i class="fa-...">`), o cualquier HTML que no mapee a otro tipo. También para CSS no mapeable (selectores complejos, pseudo-clases no soportadas, etc.).

```json
{
  "id": <int>,
  "name": "ct_code_block",
  "options": {
    "ct_id": <int>,
    "ct_parent": <int>,
    "selector": "code_block-<id>-<sufijo>",
    "original": {
      "code-css": "<CSS opcional>",
      "code-php": "<HTML del bloque o vacío>",
      "unwrap": "true"
    },
    "nicename": "Code Block (#<id>)",
    "classes": [<...>],
    "activeselector": <...>
  },
  "depth": <int>
}
```

**`unwrap: "true"`** evita que Oxygen envuelva el contenido en un wrapper extra. Validado empíricamente.

**Caso especial — Code Block agregado al final del bloque reusable** para clases internas del rich text o CSS no mapeable: usa `code-css` con CSS directo (no envolver en `<style>`), `code-php: ""`, `unwrap: "true"`. Validado empíricamente: emitir como `<style>...</style>` en `code-php` NO funciona; usar `code-css` directo SÍ funciona.

### `oxy_rich_text`

Para contenido con HTML inline mixto (texto + `<em>`, `<strong>`, `<span>`, `<br>`, `<a>`, etc.).

```json
{
  "id": <int>,
  "name": "oxy_rich_text",
  "options": {
    "ct_id": <int>,
    "ct_parent": <int>,
    "selector": "_rich_text-<id>-<sufijo>",
    "original": [] o {"useCustomTag": "true", "tag": "<tag>"},
    "nicename": "Rich Text (#<id>)",
    "ct_content": "<HTML inline o con <p> envolvente>",
    "classes": [<...>],
    "activeselector": <...>
  },
  "depth": <int>
}
```

**Reglas de `ct_content`:**
- **Sin `useCustomTag`**: envolver en `<p>`. El wrapper implícito es `<p>`. Caso típico: `<p>` y `<h1-h6>` con HTML inline.
- **Con `useCustomTag` (ej. `tag: li`)**: NO envolver en `<p>`. El wrapper externo ya es el tag custom. Caso típico: `<li>` con HTML inline mixto (validado: Oxygen normaliza al pegar quitando el `<p>` que esté de más).

## Cómo extender esta tabla

Si encuentras un tag HTML o un tipo de bloque Oxygen que no está aquí:

1. Crea el bloque en Oxygen manualmente.
2. Cópialo y mira el JSON.
3. Identifica las claves de `options.original` específicas y los nombres internos.
4. Añádelos a la tabla principal y, si tiene estructura especial (como `ct_image`), una sección dedicada.
