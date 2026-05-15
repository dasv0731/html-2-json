---
name: oxygen-json-v3
description: Convierte HTML y CSS a JSON pegable en bloques reusables de Oxygen Builder clásico (4.x para WordPress). Mapea tags y propiedades CSS a bloques y propiedades nativas de Oxygen (ct_div_block, ct_headline, ct_text_block, ct_link, ct_link_button, ct_image, ct_fancy_icon, ct_code_block, oxy_rich_text). Soporta pseudo-clases y pseudo-elementos como states nativos (hover, focus, active, before, after, disabled, checked, first-child, last-child, nth-child, nth-of-type). Preserva atributos HTML (aria-*, data-*, role, etc.) como custom-attributes. Usa este skill cuando el usuario quiera transformar HTML/CSS en bloques nativos de Oxygen, mencione "JSON de Oxygen", "bloque reusable de Oxygen", "Oxygen Builder", nombres internos de bloques de Oxygen, o pegue HTML/CSS pidiendo convertirlo al formato del constructor. También aplica cuando el usuario quiera recrear un componente HTML usando bloques nativos de Oxygen para preservar editabilidad y comportamiento responsive.
---

# Oxygen JSON v3 (HTML/CSS → JSON)

Transforma un par HTML + CSS en el JSON que se pega en un bloque reusable de Oxygen Builder clásico (versión 4.x para WordPress).

**Versión v3** consolida descubrimientos de las tres fases:
- **Fase 1 y 2** (heredadas de v2): mapeo semántico de listas, fix arquitectónico de `margin: 0` en `ct_div_block`, auto-adiciones inteligentes (icon-size, flex en links icono+texto, flex-direction row por default), diferenciación de `gap` en flex vs grid, expansión correcta de `background` shorthand, `oxy_rich_text` sin `<p>` envolvente cuando hay `useCustomTag`.
- **Fase 3** (nueva en v3): sufijo de selector parametrizable por CLI, `original: []` cuando está vacío (formato correcto de Oxygen), clases referenciadas en HTML aunque no tengan CSS, atributos HTML arbitrarios preservados como `custom-attributes`, y soporte completo de pseudo-clases/elementos como states nativos de Oxygen.

## Cuándo usar este skill

El usuario quiere convertir HTML/CSS a JSON de Oxygen para pegar en un bloque reusable. Señales típicas:
- Pega HTML y CSS y pide "conviértelo a JSON de Oxygen".
- Menciona Oxygen Builder, bloques reusables, `ct_div_block`, `ct_headline`, etc.
- Quiere "preservar editabilidad nativa" en lugar de meter todo en un Code Block.

Si el usuario solo quiere copiar HTML crudo a un Code Block sin mapear a bloques nativos, este skill NO aplica: dile que use directamente un Code Block en Oxygen.

## Qué hace

Lee HTML + CSS, construye el árbol de componentes de Oxygen, mapea propiedades CSS a propiedades nativas de Oxygen cuando es posible, y produce un JSON pegable. Las propiedades que Oxygen no soporta nativamente se desvían a `custom-css` por clase (mecanismo nativo de Oxygen) o, en último caso, a un `ct_code_block` agregado al final del bloque reusable.

### Capacidades específicas

El skill incorpora detección automática de los siguientes patrones, descubiertos durante iteraciones reales:

**Iconos (3 rutas, evaluadas en este orden):**
- **Ruta A — `ct_fancy_icon` nativo**: detecta `<svg><use xlink:href="#XxxIcon-nombre"></use></svg>` y lo emite como `ct_fancy_icon` con `original.icon-id`. Es el patrón que usa Oxygen para iconos de FontAwesome 4 antiguo, Lineaicons, y otros sets cargados como sprites SVG.
- **Ruta B — `ct_code_block` con FA 6+**: detecta `<i class="fa-solid fa-XXX">`, `<i class="fa-brands fa-XXX">`, `<i class="fas fa-XXX">` y similares. Lo emite como `ct_code_block` con `original.code-php = "<i class=\"...\"></i>"` y `unwrap: true`. Las clases FA del wrapper (`fa-solid`, `fa-brands`, `fa-XXX`) se filtran de `options.classes` del bloque porque ya viajan en `code-php` (evita ensuciar la tabla global de selectores). Las clases del usuario (no-FA) sí se preservan. Soporta sintaxis FA 4/5/6.
- **Ruta C — `ct_code_block` con SVG inline**: cualquier SVG inline crudo (con `<path>`, `<ellipse>`, etc.) que no matchee Ruta A. Se emite como `ct_code_block` con el SVG completo en `code-php`, `unwrap: true`. Avisa al usuario.

**Aclaración sobre cuándo aplica la Ruta B**: la Ruta B se gatilla cuando el `<i class="fa-...">` se procesa como componente independiente. Si el `<i>` vive dentro de un `<div>` u otro wrapper cuyos hijos son **todos** inline (texto + tags inline como `<i>`, `<em>`, `<span>`), el detector de rich text del padre lo absorbe primero y los iconos terminan dentro de un `oxy_rich_text` con HTML literal en `ct_content`. Funcionalmente se renderizan igual (las clases FA siguen disparando los glifos), pero pierden la editabilidad como bloque independiente. Para forzar Ruta B, dejá el `<i>` como root del HTML o ponele al menos un hermano block-level dentro del wrapper. Ambos comportamientos están cubiertos por fixtures (`icono-fa6-codeblock` y `icono-fa6-absorbido-richtext`).

**Inyección de texto en divs**: cuando un `<div class="X">texto</div>` o un `<a class="X">texto <em>x</em></a>` tiene contenido textual, el skill inyecta automáticamente:
- Un `ct_text_block` hijo si el contenido es texto plano puro.
- Un `oxy_rich_text` hijo si el contenido tiene HTML inline mixto (`<em>`, `<span>`, `<br>`, etc.).
La clase del div padre se preserva en el div, y el text_block/rich_text hijo hereda los estilos por cascada CSS.

**Texto suelto en `<a>` con icono + texto**: cuando un link tiene `<a class="X"><svg>...</svg> Texto</a>`, el skill detecta el text node suelto entre tags y lo emite como `ct_text_block` hermano del icono. Resuelve el bug histórico del "WhatsApp perdido". Estructura objetivo:
```
ct_link [clases-del-link]
├── ct_fancy_icon / ct_code_block [clases-del-icono]
└── ct_text_block "texto"
```

**Auto-flex en links con icono + texto**: cuando se detecta el patrón anterior, el skill añade automáticamente a la **última clase** del link `display: flex`, `flex-direction: row`, `gap: 8` (solo si no estaban en el CSS). Esto resuelve que el icono y el texto aparezcan en columna en lugar de fila. Convención BEM: la última clase es típicamente la modifier (`btn btn--whatsapp` → `.btn--whatsapp`), y aplicar solo ahí evita contaminar la clase base que puede usarse en otros `<a>` sin icono. Si el link tiene más de una clase, se emite un WARN avisando dónde se aplicó el auto-flex para que el usuario verifique o reordene.

**Auto-`icon-size` en `ct_fancy_icon`**: el wrapper div de `ct_fancy_icon` recibe `width`/`height` de la clase, pero el SVG interno NO los respeta — usa `icon-size` (propiedad propia de Oxygen). Cuando una clase con `width` o `height` se aplica a un `ct_fancy_icon`, el skill emite también `icon-size` automáticamente con el valor de `width` (o `height` si solo hay height).

**Rich text para titulares con HTML inline**: `<h1>texto <em>mixto</em></h1>` y `<p>texto <em>mixto</em></p>` se mapean a `oxy_rich_text` directamente (no a `ct_headline`/`ct_text_block` aplanado). Preserva la estructura interna.

**Colapso conservador de wrappers de iconos**: cuando un `ct_div_block` envuelve solo a un `ct_fancy_icon` o `ct_code_block` Y sus clases CSS tienen únicamente propiedades "inocuas" (tamaño, color, opacidad, margin, display/flex/align/justify), el wrapper se colapsa: las clases se transfieren al icono y el div desaparece. Esto resuelve el problema de "iconos que se ven más grandes de lo esperado" porque las medidas del wrapper sí llegan al icono.

**Default `flex-direction: row`**: Oxygen no asume `row` por defecto cuando hay `display: flex` sin dirección explícita. El skill añade `flex-direction: row` automáticamente en esos casos.

**Estilos de clases internas de rich text**: las clases que viven dentro del HTML embebido en `oxy_rich_text` (ej. `<em class="hero__title-em">`) no se ven como clases de bloque. El skill detecta estas clases, busca sus reglas CSS, y emite un `ct_code_block` adicional al final del bloque reusable con `original.code-css` (las reglas CSS directas, sin wrap `<style>`). Así los estilos se aplican al renderizar.

### Nuevo en v3

**Sufijo de selector parametrizable**: cada bloque Oxygen tiene un selector tipo `div_block-5-1908` donde el último número es el `post_id` del template o página donde el bloque vive. Antes el skill usaba `1912` hardcoded. Ahora se pasa por flag CLI `--selector-suffix VALUE`. Si no se pasa, se genera un aleatorio de 4 dígitos por ejecución (con WARN). Oxygen reasigna ese sufijo al pegar el bloque, así que el valor concreto no es crítico, pero un valor único evita colisiones si pegás múltiples bloques en el mismo sitio.

**`original: []` cuando vacío**: en bloques individuales sin propiedades CSS directas, Oxygen serializa `options.original` como array vacío `[]`, no como objeto vacío `{}`. El skill ahora respeta esa convención. En las clases top-level, en cambio, `original: {}` se mantiene (otro contexto, otro formato).

**Clases referenciadas en HTML sin CSS**: si el HTML tiene `<div class="logos-marquee">` pero el CSS no define `.logos-marquee`, antes el skill descartaba la clase y avisaba. Ahora la preserva: aparece en `classes` top-level con `original: {}`. Esto permite que clases manejadas por JavaScript externo, stylesheet global de Oxygen, o un Code Block adicional, sigan asociadas al bloque correcto.

**`custom-attributes` HTML preservados**: atributos HTML que no son `class`, `id`, `href`, `src`, `alt`, `target`, `width`, `height`, `srcset`, `loading` o `xlink:href` se preservan automáticamente en `original.custom-attributes` como array de `{name, value}`. Esto cubre `aria-*`, `data-*`, `role`, `tabindex`, `rel`, `title`, `type`, etc. Validado empíricamente: Oxygen acepta este formato y los atributos sobreviven al pegado.

**Pseudo-clases y pseudo-elementos como states nativos**: ver sección dedicada más abajo. Es el cambio más sustantivo de la v3.

## Cómo se invoca

Hay un script Python determinista que hace el trabajo: `scripts/transform.py`. Tu rol como Claude es:

1. **Validar que el input cumple el contrato** (ver "Contrato de input"). Si no cumple, pide al usuario que ajuste el input antes de invocar el script.
2. **Invocar el script** pasándole el HTML y el CSS por archivos temporales, y el flag `--selector-suffix` si conocés el `post_id` de destino.
3. **Mostrar al usuario** el JSON resultante y la lista de avisos del script (qué se mapeó parcialmente, qué fue al `custom-css`, qué fue al Code Block, qué se preservó sin CSS, etc.).

## Contrato de input

El input es estricto. Si el HTML/CSS no cumple, NO ejecutes el script: dile al usuario qué arreglar.

### HTML
- **Una clase por elemento** en el atributo `class`. Múltiples clases son válidas si están separadas por espacio: `<div class="card card-large">`.
- **Sin `style="..."` inline**. Si el usuario lo incluye, pide que lo migre a una clase.
- **Solo tags soportados** (ver `references/block-types.md` para la tabla completa). Tags exóticos o componentes sin equivalente en Oxygen requieren ajuste manual.
- **Atributos HTML arbitrarios permitidos**: el skill preserva `aria-*`, `data-*`, `role`, `rel`, `title`, etc. automáticamente vía `custom-attributes`.

### CSS
- **Una regla por clase**. Selectores complejos con combinadores (`.foo > .bar`, `.foo + .bar`, `.foo .bar`, `[data-x]`, etc.) van automáticamente al Code Block agregado.
- **Pseudo-clases y pseudo-elementos soportados como states nativos** (ver tabla más abajo). Las no listadas van al Code Block.
- **Media queries con `max-width`** se mapean a breakpoints nativos de Oxygen. Las que usan `min-width` o cualquier otra forma van al Code Block con WARN — el skill NO rechaza el input, solo avisa.
- **Breakpoints aceptados** (con tolerancia ±1px):
  - `max-width: 1120px` → `page-width`
  - `max-width: 992px` → `tablet`
  - `max-width: 768px` → `phone-landscape`
  - `max-width: 480px` → `phone-portrait`
  - Cualquier otro valor de breakpoint va al Code Block con WARN.

### Pseudo-clases y pseudo-elementos soportados

Las siguientes pseudo-clases CSS se mapean a **states nativos de Oxygen** (paralelos a `original`, como `hover`). Validado empíricamente pegando JSONs en Oxygen y confirmando que se aplican visualmente al previsualizar:

| CSS | Key Oxygen | Notas |
|---|---|---|
| `:hover` | `hover` | |
| `:focus` | `focus` | |
| `:active` | `active` | |
| `:disabled` | `disabled` | |
| `:checked` | `checked` | Inputs tipo checkbox/radio |
| `:first-child` | `first-child` | |
| `:last-child` | `last-child` | |
| `:before` o `::before` | `before` | Ambas sintaxis CSS aceptadas |
| `:after` o `::after` | `after` | Ambas sintaxis CSS aceptadas |
| `:nth-child(N)` | `nth-child(N)` | N puede ser número (2), expresión (2n+1), o keyword (odd/even). Validado empíricamente en frontend de Oxygen. Cuenta TODOS los hijos del padre sin importar tag. |
| `:nth-of-type(N)` | `nth-of-type(N)` | Mismo formato que nth-child. Validado empíricamente en frontend de Oxygen. **Importante**: cuenta solo elementos del MISMO tag. Para que aplique como esperás, los hermanos del elemento deben compartir el mismo tag HTML. |
| `:nth-last-child(N)` | `nth-last-child(N)` | Mismo formato. Validado empíricamente en frontend de Oxygen. Cuenta hijos desde el final. |
| `:nth-last-of-type(N)` | `nth-last-of-type(N)` | Mismo formato. Validado empíricamente en frontend de Oxygen. **Importante**: cuenta solo elementos del MISMO tag, desde el final. |

Para `:before` y `::after`, el valor de `content` se normaliza quitando comillas externas: el CSS `content: "X"` se emite como `"content": "X"` (sin las comillas internas), que es el formato canónico de Oxygen.

**Lo que NO se mapea a state nativo** y va al Code Block:
- `:not(.x)` (argumento es otro selector, no un state)
- `:focus-visible`, `:focus-within` (no validados)
- `:placeholder`, `:read-only`, `:required`, `:valid`, `:invalid` (no validados)
- Cualquier otra pseudo-clase no listada arriba
- Selectores con combinadores (`.foo > .bar`, `.foo .bar`, `.foo + .bar`)
- Selectores con `[atributo]`

### CSS Grid: reglas para mapeo nativo

Oxygen Grid es más limitado que CSS Grid estándar. El skill mapea a propiedades nativas SI Y SOLO SI:

| Propiedad CSS | Mapeo Oxygen | Condición |
|---|---|---|
| `display: grid` | `display: grid` | Siempre |
| `grid-template-columns: repeat(N, 1fr)` o `1fr 1fr ... 1fr` (N iguales) | `grid-column-count: N` | Solo columnas de ancho uniforme |
| `gap: X` o `gap: X Y` (en grid container) | `grid-row-gap: X` + `grid-column-gap: Y` | El skill descompone automáticamente cuando el container es `display: grid` |
| `grid-column: span N` en un hijo | entrada con `column-span: "N"` en `grid-child-rules` del container | El hijo necesita una clase única donde declarar el span |
| `grid-row: span N` en un hijo | entrada con `row-span: "N"` en `grid-child-rules` del container | Igual |

**Cómo escribir el CSS para que el skill genere `grid-child-rules` correctamente:**

```css
/* Container */
.gridA { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; }

/* Hijos por clase modifier (BEM) */
.gridA__cell--wide { grid-column: span 2; }
.gridA__cell--tall { grid-row: span 2; }
.gridA__cell--big  { grid-column: span 3; grid-row: span 2; }
```

```html
<div class="gridA">
  <div class="gridA__cell"></div>                          <!-- 1×1 default -->
  <div class="gridA__cell gridA__cell--big"></div>         <!-- 3×2 -->
  <div class="gridA__cell gridA__cell--wide"></div>        <!-- 2×1 -->
  <div class="gridA__cell gridA__cell--tall"></div>        <!-- 1×2 -->
  <div class="gridA__cell"></div>                          <!-- 1×1 default -->
</div>
```

El skill consulta las clases de cada hijo del grid en orden posicional. Para hijos con varias clases (BEM base + modifier), mergea spans desde todas. Si ninguna clase del hijo declara span, queda como `column-span: "", row-span: ""` (1×1).

**Lo que va a `custom-css` (no soportado nativo):**

- `grid-template-columns: 1fr 2fr 1fr` y similares (anchos desiguales) — Oxygen Grid no acepta proporciones desiguales.
- `grid-template-columns: 200px 1fr` (mezcla unidades) — idem.
- `grid-template-rows` con valores explícitos.
- `grid-template-areas`.
- `grid-column: 2 / 4` (posicionamiento absoluto start/end) — usá `span N` en su lugar.
- `grid-area: foo`.
- `grid-row: N / M`.
- `grid-auto-flow`, `grid-auto-rows`, `grid-auto-columns`.

**Limitaciones del mapeo actual:**

- Si querés que el array `grid-child-rules` también se emita en breakpoints, escribí las spans dentro del media query con clases dedicadas. El skill **no replica automáticamente** el array de top-level a cada breakpoint hoy.
- Si un grid container tiene hijos sin clase (`<div></div>` desnudo), reciben `column-span: "", row-span: ""` (default 1×1).
- Hijos inyectados por el detector de rich text (caso raro en grids) podrían descuadrar los índices del array. Si tu grid contiene texto suelto, usá divs intermedios.

### Regla operativa: clases únicas por componente

Oxygen tiene una **tabla global única de selectores**. Si pegas dos componentes que usan la misma clase (ej. `.btn`) con propiedades distintas, el segundo pegado NO sobrescribe al primero — la clase mantiene los valores del primer pegado. El segundo componente quedará referenciando una clase que no tiene los estilos esperados.

**Regla**: usar nombres de clase únicos por componente. Si dos componentes necesitan estilos similares, NO compartir clases base (`.btn`) sino crear distintas (`.heroCta__btn`, `.navCta__btn`) aunque tengan CSS casi idéntico. Se acepta duplicación de CSS a cambio de aislamiento garantizado.

**Síntoma de chocar**: las clases aparecen en Manage → Selectors pero el componente se ve sin estilos (o con estilos viejos). Indica que la clase ya existía con valores distintos.

## Contrato de output

- **JSON válido**, copiable y pegable en un bloque reusable de Oxygen 4.x.
- **Lista de avisos** (no parte del JSON, sino texto adicional para el usuario): qué propiedades se mapearon nativamente, qué se mandó a `custom-css`, qué se mandó al Code Block, qué clases se preservaron sin CSS asociado.

## Flujo recomendado al usuario

1. Recibe el HTML y el CSS.
2. Valida el contrato. Si falla, explica al usuario qué corregir y termina aquí.
3. Crea un archivo temporal con el HTML y otro con el CSS en `/tmp/` o `/home/claude/`.
4. Si el usuario sabe el `post_id` de destino, pasalo como `--selector-suffix`. Si no, omitilo (el skill genera uno aleatorio).
5. Ejecuta:
   ```
   python scripts/transform.py --html /tmp/input.html --css /tmp/input.css --out /tmp/output.json [--selector-suffix 1908]
   ```
6. Lee `/tmp/output.json` y los avisos del script (stderr).
7. Muestra al usuario:
   - El JSON final (puedes copiarlo en el chat o ponerlo en un archivo si es muy largo).
   - La lista de avisos: qué se mapeó dónde, qué se perdió, qué clases vacías se preservaron.
   - Un recordatorio sobre las dos cosas que el usuario va a tener que arreglar manualmente: imágenes (reasignar attachments en Oxygen) y, si hay Code Block agregado, revisar que el CSS resultante hace lo que debe.

## Limitaciones conocidas

Sé honesto con el usuario sobre estas:

- **`ct_section` no se emite**: todas las `<section>` HTML se vuelven `ct_div_block` con `original.tag = "section"`. Si el usuario necesita una Section nativa de Oxygen, debe crearla manualmente.
- **`ct_columns` y `ct_column` no soportados**: layouts en columnas se mapean a Divs con `display: flex` o `display: grid`. Funciona visualmente pero pierde los controles específicos de Columns en el panel de Oxygen.
- **Imágenes con URL pero sin `attachment_id`**: el skill emite `attachment_id: 0`. Tras pegar, el usuario debe reasignar la imagen al media library de WordPress.
- **CSS Grid con anchos desiguales** (`grid-template-columns: 1fr 2fr 1fr`): Oxygen Grid solo soporta columnas iguales. Las proporciones desiguales van al `custom-css` o al Code Block. Avisar.
- **`flex-basis`**: no soportado nativamente en Oxygen. Va a `custom-css`.
- **`flex-direction: row-reverse` / `column-reverse`**: se descomponen en `flex-direction` + `flex-reverse: reverse` (propiedad propia de Oxygen).
- **`display: grid` con posicionamiento por `grid-area` o `grid-column: 2 / 4`**: Oxygen Grid usa un modelo distinto (`grid-child-rules` con `column-span` / `row-span`). El skill traduce `grid-column: span N` y `grid-row: span N` automáticamente al array `grid-child-rules` del container (ver "Generación automática de `grid-child-rules`" más abajo). Otras formas de posicionamiento (`grid-area: foo`, `grid-column: 2 / 4`) van al `custom-css` o al Code Block.

### Generación automática de `grid-child-rules`

Cuando un container `display: grid` tiene hijos con `grid-column: span N` y/o `grid-row: span N` en sus clases, el skill construye automáticamente el array `grid-child-rules` (formato propio de Oxygen) en el container.

Formato emitido (validado empíricamente contra JSONs reales de Oxygen):
```json
"grid-child-rules": [
  {"child-index": 0, "column-span": "",  "row-span": ""},   // default 1x1
  {"child-index": 1, "column-span": "3", "row-span": "2"},  // 3 cols x 2 rows
  {"child-index": 2, "column-span": "2", "row-span": ""},   // 2 cols, row default
  {"child-index": 3, "column-span": "",  "row-span": "2"},  // col default, 2 rows
  {"child-index": 4, "column-span": "1", "row-span": "1"}   // 1x1 explícito
]
```

Reglas:
- Una entrada por hijo (NO se trunca al último no-default).
- Hijos sin span declarado: `column-span: ""`, `row-span: ""` (Oxygen los interpreta como 1×1).
- Solo se emite el array si **al menos un hijo tiene span ≠ default** (evita ruido en grids puros 1×1).
- Las clases del hijo pueden distribuir spans (`.item--wide` aporta `column-span`, `.item--tall` aporta `row-span`). El skill mergea desde todas las clases del hijo.
- `grid-column: span N` y `grid-row: span N` se extraen de `custom-css` y no aparecen ahí — viven solo en el array.
- **`<ul>` y `<li>`**: mapeo semántico con `useCustomTag`. `<ul>/<ol>` → `ct_div_block` con `useCustomTag: true, tag: ul/ol`. `<li>` con texto plano → `ct_text_block[li]`. `<li>` con HTML inline mixto (incluyendo `<a>`, `<em>`, `<strong>`, `<br>`) → `oxy_rich_text[li]` con contenido inline directo (sin `<p>` envolvente). `<li>` con tags estructurales hijos (div, h1-h6, ul anidado) → `ct_div_block[li]`. Validado contra exports reales de Oxygen.
- **Inyección de display en media queries (asimétrica entre flex y grid)**: cuando un breakpoint tiene `flex-direction`/`flex-wrap`/`justify-content` y la clase top-level es `display: flex`, el skill inyecta `display: flex` en ese breakpoint para que el panel UI de Oxygen muestre los controles flex. Para grid NO se hace lo paralelo: el `display: grid` de top-level se hereda en cascada CSS y emitirlo en cada breakpoint generaba ruido al editar (era el "bug del display:grid espurio"). Si necesitas display:grid explícito en un breakpoint, escribilo en tu CSS.
- **`<button>` HTML: mapeo por trío según contenido** (paralelo a `<li>`):
  - `<button>Texto plano</button>` → `ct_text_block` con `useCustomTag: true, tag: "button"`.
  - `<button>Texto <em>inline mixto</em></button>` → `oxy_rich_text` con `useCustomTag: true, tag: "button"`.
  - `<button><svg/><span>...</span></button>` (hijos estructurales) → `ct_div_block` con `useCustomTag: true, tag: "button"`.

  En los tres casos, los atributos HTML del `<button>` (`type`, `onclick`, `aria-*`, `data-*`, `name`, `value`, `formaction`, etc.) se preservan automáticamente como `custom-attributes`, editables desde el panel "Advanced > Custom Attributes" de Oxygen. El componente renderiza un `<button>` HTML real (no un `<a>`), preservando la semántica funcional (form submit, handlers JS, toggles ARIA, accesibilidad). Los tres casos están validados empíricamente — Oxygen agrega su clase nativa al `class` renderizado (`ct-div-block`, `ct-text-block`) junto a las clases del usuario, pero el tag externo es siempre `<button>`.

### Nota sobre patrones de iconos no resueltos automáticamente

Algunas combinaciones de SVG no se detectan como iconos y caen a Ruta C (code block con SVG completo):
- SVG con múltiples `<use>` dentro.
- SVG con `<use>` y otros elementos hermanos.
- SVG con `xlink:href` que no empieza con `#` (referencias a sprites externos).

Funcionalmente se renderizan correctamente vía code block, pero pierden la editabilidad nativa de `ct_fancy_icon`.

## Workarounds frecuentes

Estos son problemas recurrentes al usar Oxygen que el skill NO puede resolver automáticamente. Son responsabilidad del usuario al escribir su CSS. Para detalle técnico y ejemplos, ver `references/oxygen-quirks.md` sección "Workarounds frecuentes".

- **`margin` numérico en `ct_div_block` lo resuelve el skill automáticamente**: Oxygen aplica `.ct-div-block { margin: 0 }` con prioridad CSS, descartando cualquier `margin-top/bottom/left/right` numérico. Para que sobreviva, el skill redirige automáticamente esos margins a `custom-css` con `!important` cuando la clase se aplica a un `ct_div_block`. Lo que vos escribís en CSS sigue siendo `margin-top: 36px;`; el output será `custom-css: "margin-top: 36px !important;"`. Trade-off: el margen ya no es editable desde el panel nativo de Oxygen para esa clase, vive en el campo Advanced > Custom CSS.
- **`margin: auto` no centra en flex-items**: dentro de Oxygen, los `ct_div_block` son flex containers por default. Para centrar un wrapper con `max-width`, usar `justify-content: center` en el padre o `width: 100% + max-width + margin auto` en el hijo. No uses solo `margin: auto`. El skill emite `margin-X-unit: auto` (formato nativo) pero igual no se aplica visualmente sin uno de los dos workarounds.
- **Texto suelto entre tags hermanos en `<a>`**: el skill detecta `<a><svg></svg> Texto</a>` y emite el texto como `ct_text_block` hermano. Auto-añade flex a la clase del link.
- **Iconos `ct_fancy_icon` requieren `icon-size`**: el skill lo auto-añade cuando hay `width`/`height` en una clase aplicada a fancy_icon.
- **`outline-*` se convierte a `border-*`**: Oxygen lo hace automáticamente al pegar. Si necesitas outline real (para accesibilidad), va a `custom-css` explícitamente.
- **`var()` numérico no funciona en el panel**: variables CSS en colores sí (preservadas como string), en propiedades numéricas (`padding`, `width`) van a `custom-css`.
- **Animaciones y efectos siempre a `custom-css`**: `@keyframes`, `animation`, `filter`, `backdrop-filter`, `transform` encadenado, múltiples `box-shadow`, `mix-blend-mode`. Decisión arquitectónica del skill: aunque algunos tienen propiedades nativas parciales, el resultado es inconsistente. Mejor `custom-css`.
- **Clases CSS únicas por componente**: Oxygen tiene una tabla global única de selectores. Si dos componentes usan la misma clase (ej. `.btn`) con propiedades distintas, el segundo pegado NO sobrescribe — la clase mantiene los valores del primer pegado. Usar prefijos por componente (`heroport__btn`, `footerv3__btn`) aunque haya duplicación de CSS.
- **`color(N)` para colores globales de Oxygen**: si tu sitio tiene colores definidos en Manage → Colors, Oxygen los referencia como `color(7)`, `color(12)`, etc. El skill emite el valor literal (hex, rgb, var) que escribiste en el CSS. Para usar colores globales hay que reasignar manualmente en el panel tras pegar.

## Lo que el skill auto-añade al CSS del usuario

Para que sepas qué propiedades aparecen en el output que NO escribiste en tu CSS:

- **`flex-direction: row`**: cuando una clase tiene `display: flex` pero no `flex-direction`, el skill añade `row` (Oxygen no asume row por default).
- **`display: flex; flex-direction: row; gap: 8`**: cuando un `<a>` tiene icono + texto, el skill añade estas tres propiedades a las clases del link (postura A confirmada).
- **`icon-size`**: cuando una clase con `width` o `height` se aplica a un `ct_fancy_icon`, el skill emite también `icon-size` con el valor de `width` para que el SVG interno respete el tamaño.
- **`margin-* !important` en `custom-css` para `ct_div_block`**: cuando una clase con `margin-top/bottom/left/right` numérico se aplica a un `ct_div_block`, el skill redirige a `custom-css` con `!important` para sobrevivir el `margin: 0` que Oxygen aplica por default.
- **`custom-attributes` desde atributos HTML**: cualquier atributo HTML que no sea `class`, `id`, `href`, `src`, `alt`, `target`, `width`, `height`, `srcset`, `loading` o `xlink:href` se preserva en `original.custom-attributes`.

Estas adiciones se aplican solo si el usuario NO escribió esas propiedades (excepto custom-attributes, que siempre se preservan tal cual estaban). Si querés controlarlas explícitamente, escribilas en tu CSS y el skill las respeta.

## Lo que el skill NO envuelve

- **`oxy_rich_text` con `useCustomTag` (ej. tag: li)**: el contenido se emite inline directo, sin `<p>` envolvente. El wrapper externo ya es el tag custom (ej. `<li>`).
- **`oxy_rich_text` sin `useCustomTag`** (caso default para `<p>` y `<h1-h6>` con HTML mixto): el contenido sí se envuelve en `<p>` porque ese es el tag implícito.

## Reference files

Documentación de consulta cuando necesites entender un mapeo específico o un comportamiento del skill:

- `references/block-types.md` — tabla de mapeo HTML tag → tipo de bloque Oxygen, con sus propiedades específicas.
- `references/property-mappings.md` — mapeo de propiedades CSS → propiedades de Oxygen, defaults de unidades, expansiones de shorthand, criterios para decidir nativo vs `custom-css` vs Code Block.
- `references/oxygen-quirks.md` — anomalías y comportamientos no obvios de Oxygen documentados durante el descubrimiento del skill. Léelo si algo se ve raro y no estás seguro de si es bug o feature.

## Cambios respecto a v2

Si venís usando la v2 del skill y querés saber qué cambió en v3, en orden de impacto:

1. **Pseudo-clases nativas (cambio mayor)**: `:hover`, `:focus`, `:active`, `:before`, `::after`, `:disabled`, `:checked`, `:first-child`, `:last-child`, `:nth-child(N)`, `:nth-of-type(N)`, `:nth-last-child(N)`, `:nth-last-of-type(N)` ahora se mapean a states nativos de Oxygen. La v2 solo mapeaba `:hover`; el resto iba al Code Block.

2. **Sufijo de selector parametrizable**: nuevo flag `--selector-suffix VALUE`. Antes era `1912` hardcoded. Si no se pasa, se genera aleatorio.

3. **`original: []` cuando vacío**: bloques sin propiedades CSS directas ahora emiten `[]` en lugar de `{}`. Formato verificado contra JSONs reales de Oxygen.

4. **Clases referenciadas en HTML sin CSS se preservan**: la v2 las descartaba con WARN. La v3 las emite con `original: {}` y avisa.

5. **`custom-attributes` HTML preservados**: la v2 perdía silenciosamente `aria-*`, `data-*`, `role`, `rel`, etc. La v3 los emite en `original.custom-attributes` como array de `{name, value}`.

6. **Documentación honesta sobre `min-width`**: la v2 prometía "rechazar con error", el código hacía WARN + Code Block. La v3 documenta el comportamiento real.

7. **Eliminadas referencias a `__CLAUDE_FIXME__`**: era un mecanismo de marcadores prometido en la v2 pero nunca implementado. Eliminado de la documentación.

## Fixes recientes (post-v3 release)

Cambios incrementales a la v3 ya publicada. Mantienen total compatibilidad con outputs previos para entradas que no toquen los casos de bug.

1. **Fix shorthand con funciones CSS (`calc`, `var`, `clamp`, `rgb`, etc.)**: el expansor de `padding`, `margin`, `gap`, `border-radius` y el parser de `border` ahora usan el helper `_split_top_level`, que tokeniza respetando paréntesis balanceados. Antes, `padding: calc(10px + 1vw)` se rompía silenciosamente en cuatro tokens basura; ahora se preserva como un solo valor por lado.

2. **Fix shorthand `border` con colores por palabra**: `border: 2px solid green` ahora se expande correctamente a `width=2px, style=solid, color=green`. Antes, palabras de color (red, green, blue) caían al branch `else` de la heurística y se asignaban como `width`, sobrescribiendo el valor numérico real. La lógica fue reordenada para detectar `width` explícitamente (numérico o keyword `thin/medium/thick`) y dejar `color` como fallback.

3. **`<button>` HTML mapeado a `useCustomTag: button`**: el skill ya no fuerza `<button>` a `ct_link_button` (que renderizaba como `<a>`, perdiendo la semántica). Ahora aplica un trío de mapeos según contenido — `ct_text_block` para texto plano, `oxy_rich_text` para HTML inline mixto, `ct_div_block` para hijos estructurales — todos con `useCustomTag: true, tag: "button"`. El componente renderiza un `<button>` HTML real y los atributos del button (`type`, `onclick`, `aria-*`, `data-*`, etc.) son editables vía `custom-attributes` desde el panel de Oxygen. Los tres casos del trío validados empíricamente con JSONs pegados en Oxygen.

4. **`ct_code_block` con HTML literal: sin duplicar `custom-attributes`**: cuando un tag se mapea a `ct_code_block` (Rutas B/C de iconos), los atributos HTML viajan dentro del `code-php`. Antes el skill los duplicaba también como `custom-attributes` del bloque, generando ruido. Ahora se omiten en ese caso.

## Si el usuario pide algo que está fuera de scope

Sé honesto y específico:
- Si pide soporte para Oxygen 4 nuevo (Breakdance-style): este skill es para Oxygen clásico 4.x, no para el reescrito reciente.
- Si pide convertir JSON de Oxygen → HTML/CSS (dirección inversa): este skill NO hace eso, dile que sería un skill distinto.
- Si pide soporte para sliders, accordions, tabs, repeaters, dynamic data: fuera de scope, sugiere crear esos bloques manualmente y luego envolver con un `ct_div_block`.
