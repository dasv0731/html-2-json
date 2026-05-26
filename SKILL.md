---
name: oxygen-json-v3
description: Convierte HTML y CSS a JSON pegable en bloques reusables de Oxygen Builder clásico (4.x para WordPress). Mapea tags y propiedades CSS a bloques y propiedades nativas de Oxygen (ct_div_block, ct_headline, ct_text_block, ct_link, ct_link_button, ct_image, ct_fancy_icon, ct_code_block, oxy_rich_text). Soporta pseudo-clases y pseudo-elementos como states nativos (hover, focus, active, before, after, disabled, checked, first-child, last-child, nth-child, nth-of-type). Preserva atributos HTML (aria-*, data-*, role, etc.) como custom-attributes. Usa este skill cuando el usuario quiera transformar HTML/CSS en bloques nativos de Oxygen, mencione "JSON de Oxygen", "bloque reusable de Oxygen", "Oxygen Builder", nombres internos de bloques de Oxygen, o pegue HTML/CSS pidiendo convertirlo al formato del constructor. También aplica cuando el usuario quiera recrear un componente HTML usando bloques nativos de Oxygen para preservar editabilidad y comportamiento responsive.
---

# Oxygen JSON v3 (HTML/CSS → JSON)

Transforma un par HTML + CSS en el JSON que se pega en un bloque reusable de Oxygen Builder clásico (versión 4.x para WordPress).

**Versión v3** consolida descubrimientos de las tres fases:
- **Fase 1 y 2** (heredadas de v2): mapeo semántico de listas, fix arquitectónico de `margin: 0` en `ct_div_block`, auto-adiciones inteligentes (icon-size, flex en links icono+texto, flex-direction row por default), diferenciación de `gap` en flex vs grid, expansión correcta de `background` shorthand, `oxy_rich_text` sin `<p>` envolvente cuando hay `useCustomTag`.
- **Fase 3** (nueva en v3): sufijo de selector parametrizable por CLI, `original: []` cuando está vacío (formato correcto de Oxygen), clases referenciadas en HTML aunque no tengan CSS, atributos HTML arbitrarios preservados como `custom-attributes`, y soporte completo de pseudo-clases/elementos como states nativos de Oxygen.

**v3.1** (auditoría contra código fuente de Oxygen, 2026-05-26): fix de `<img>` rota, box-shadow/text-shadow broken-out editables, auto-flex en bloque (no en clases), ampliación de `NATIVE_PROPERTIES` (transitions, filters, grid avanzado, AOS, etc.), `var()` nativo en colores, grid `auto-fit/minmax`, pseudo-elementos `first-letter/first-line/selection`, `:visited`. Ver sección "v3.1" más abajo y `CHANGELOG.md`.

**v3.2** (cobertura extendida, 2026-05-26): `filter` parseado a `filter-amount-*` broken-out (editable), `transform` como array de transform-step objects, `data-aos-*` del HTML mapeado a keys `aos-*` nativas, mapeo completo de tablas (`<table>/<thead>/<tbody>/<tr>/<td>/<th>`), forms (`<form>/<input>/<label>/<select>/<textarea>/<button>/<fieldset>/<legend>`), void elements (`<hr>/<input>/<col>/<br>`) y otros block-level (`<blockquote>/<pre>/<code>/<figcaption>/<summary>`). `style="..."` inline soportado (antes rechazado). Comentarios HTML ya no generan `ct_text_block` ruido.

**v3.3** (bloques nativos avanzados, 2026-05-26): detección automática de `oxy-shape-divider` para SVGs que matcheen el catálogo built-in de Oxygen (30 shapes vía hash md5 del path); `ct_section` nativo via opt-in `is-oxy-section` (habilita `section-width`, `container-padding-*`, `video_background`); `ct_new_columns` nativo via opt-in `is-oxy-columns` (habilita `stack-columns-vertically`, `reverse-column-order`, etc.).

**v3.4** (multimedia + filtro de clases internas, 2026-05-26): `ct_video` auto-detect desde iframe YouTube/Vimeo; `oxy_map` auto-detect desde iframe Google Maps Embed (parsea `q=` y `zoom=`); `oxy_progress_bar` opt-in via `is-oxy-progress-bar` (con `data-percent`); `ct_code_block` con `unwrap:true` opt-in via `is-oxy-unwrap` (preserva markup arbitrario sin wrapper); filtro automático de clases internas de Oxygen (`ct-div-block`, `ct-section-inner-wrap`, `oxy-progress-bar-*`, `ct-fancy-icon`, etc.) que aparecen cuando user pega HTML rendered de un site Oxygen.

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
- **Ruta B — `ct_code_block` con FA 6+**: detecta `<i class="fa-solid fa-XXX">`, `<i class="fa-brands fa-XXX">`, `<i class="fas fa-XXX">` y similares. Lo emite como `ct_code_block` con `original.code-php = "<i class=\"...\"></i>"` y `unwrap: true`. Soporta sintaxis FA 4/5/6.
- **Ruta C — `ct_code_block` con SVG inline**: cualquier SVG inline crudo (con `<path>`, `<ellipse>`, etc.) que no matchee Ruta A. Se emite como `ct_code_block` con el SVG completo en `code-php`, `unwrap: true`. Avisa al usuario.

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

**Auto-flex en links con icono + texto**: cuando se detecta el patrón anterior, el skill añade automáticamente `display: flex`, `flex-direction: row`, `gap: 8` al `options.original` del bloque `ct_link` específico (no a las clases). Esto resuelve que el icono y el texto aparezcan en columna en lugar de fila sin contaminar clases reusables. La inyección solo aplica si NINGUNA clase del link definió `display` en el CSS del user — si lo hizo, se respeta su elección.

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
- **`style="..."` inline soportado** (desde v3.2). Las propiedades se mergean en `options.original` del bloque específico (no en las clases, para no contaminar otros bloques que compartan clase). Inline tiene prioridad sobre lo definido en las clases para ese bloque concreto.
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
| `:visited` | `visited` | Solo aplica a links |
| `:disabled` | `disabled` | |
| `:checked` | `checked` | Inputs tipo checkbox/radio |
| `:first-child` | `first-child` | |
| `:last-child` | `last-child` | |
| `:before` o `::before` | `before` | Ambas sintaxis CSS aceptadas |
| `:after` o `::after` | `after` | Ambas sintaxis CSS aceptadas |
| `::first-letter` | `first-letter` | Pseudo-elemento tipográfico |
| `::first-line` | `first-line` | Pseudo-elemento tipográfico |
| `::selection` | `selection` | Texto seleccionado |
| `:nth-child(N)` | `nth-child(N)` | N puede ser número (2), expresión (2n+1), o keyword (odd/even). Validado empíricamente en frontend de Oxygen. Cuenta TODOS los hijos del padre sin importar tag. |
| `:nth-of-type(N)` | `nth-of-type(N)` | Mismo formato que nth-child. Validado empíricamente en frontend de Oxygen. **Importante**: cuenta solo elementos del MISMO tag. Para que aplique como esperás, los hermanos del elemento deben compartir el mismo tag HTML. |
| `:nth-last-child(N)` | `nth-last-child(N)` | Mismo formato. Validado empíricamente en frontend de Oxygen. Cuenta hijos desde el final. |
| `:nth-last-of-type(N)` | `nth-last-of-type(N)` | Mismo formato. Validado empíricamente en frontend de Oxygen. **Importante**: cuenta solo elementos del MISMO tag, desde el final. |

Para `:before` y `::after`, el valor de `content` se normaliza quitando comillas externas: el CSS `content: "X"` se emite como `"content": "X"` (sin las comillas internas), que es el formato canónico de Oxygen.

**Lo que NO se mapea a state nativo** y va al Code Block:
- `:not(.x)` (argumento es otro selector, no un state)
- `:focus-visible`, `:focus-within` (no validados)
- `::placeholder`, `:read-only`, `:required`, `:valid`, `:invalid` (no validados)
- Cualquier otra pseudo-clase no listada arriba
- Selectores con combinadores (`.foo > .bar`, `.foo .bar`, `.foo + .bar`)
- Selectores con `[atributo]`

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
- **`display: grid` con posicionamiento por `grid-area` o `grid-column: 2 / 4`**: Oxygen Grid usa un modelo distinto (`grid-child-rules` con `column-span` / `row-span`). El skill traduce span simples; posicionamiento absoluto va al `custom-css` o al Code Block.
- **`<ul>` y `<li>`**: mapeo semántico con `useCustomTag`. `<ul>/<ol>` → `ct_div_block` con `useCustomTag: true, tag: ul/ol`. `<li>` con texto plano → `ct_text_block[li]`. `<li>` con HTML inline mixto (incluyendo `<a>`, `<em>`, `<strong>`, `<br>`) → `oxy_rich_text[li]` con contenido inline directo (sin `<p>` envolvente). `<li>` con tags estructurales hijos (div, h1-h6, ul anidado) → `ct_div_block[li]`. Validado contra exports reales de Oxygen.
- **Bug pre-existente en media queries**: en algunos casos un media query puede emitir `display: grid` espurio que no estaba en el CSS original. Bug conocido pendiente.
- **Auto-flex en múltiples clases (resuelto en v3.1)**: el auto-flex ahora va al `options.original` del bloque `ct_link` específico, no a las clases. Las clases compartidas (`btn`, `btn--whatsapp`) no reciben flex y siguen reusables en otros contextos.
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
- **`display: flex; flex-direction: row; gap: 8` en el bloque `ct_link`**: cuando un `<a>` tiene icono + texto, el skill añade estas tres propiedades al `options.original` del bloque específico (no a las clases). Solo aplica si ninguna clase del link definió `display` en el CSS.
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

## v3.1 — auditoría contra código fuente de Oxygen (2026-05-26)

Sesión de polish basada en auditoría del código PHP/Angular de Oxygen. Cambios agrupados por tipo. Detalle completo en `CHANGELOG.md` entrada "2026-05-26".

### Bugs críticos arreglados

5. **`<img>` ahora renderiza inmediatamente**: emite `image_type: "1"` + `src` + `alt` (URL-based). Antes emitía `image_type: "2"` con `attachment_id: 0`, que en el render de Oxygen caía a la rama placeholder leyendo `$options['src']` (vacío) — la imagen no aparecía hasta reasignación manual. El `alt` ya no se descarta.

6. **`box-shadow` y `text-shadow` editables en el panel**: nuevos expansores `_expand_box_shadow` y `_expand_text_shadow` parsean el shorthand CSS a las keys broken-out que Oxygen entiende como nativas (`box-shadow-color`, `-horizontal-offset`, `-vertical-offset`, `-blur`, `-spread`, `-inset`). Antes la sombra se veía pero el panel Effects no la mostraba. Múltiples sombras (separadas por coma) o lengths con unidades distintas a `px` siguen yendo a `custom-css`.

7. **Auto-flex de icono+texto en `<a>` ya no contamina clases compartidas**: la inyección de `display:flex / flex-direction:row / gap:8` va al `options.original` del bloque `ct_link` específico, no a las clases. Si el user definió `display` en alguna clase del link, se respeta (no se inyecta). Implementado como marca interna `__needs_auto_flex__` + post-proceso `apply_auto_flex_to_links()` después de parsear el CSS.

### Cobertura ampliada (menos `custom-css` innecesario)

8. **`NATIVE_PROPERTIES` alineado con `$options_white_list` real de Oxygen**: sumadas como nativas: `transition-*` (con units), `filter` y `filter-amount-*`, `text-shadow-*` (broken-out), `float`, `clear`, `direction`, `list-style-type`, `visibility`, `order`, `-webkit-font-smoothing`, `background-attachment`, `background-clip`, `background-blend-mode`, `mix-blend-mode`, `overlay-color`, `gradient`, grid avanzado (`grid-columns-auto-fit`, `grid-column-min/max-width`, `grid-row-count`, `grid-row-behavior`, `grid-row-min/max-height`, `grid-all-children-rule`, `grid-justify-items`, `grid-align-items`, `grid-match-height-of-tallest-child`), `container-padding-*`, todas las `aos-*`, `button-size`, `button-color`, `button-hover_color`.

9. **`grid-template-columns: repeat(auto-fit, minmax(Xpx, 1fr))` mapeado nativo**: emite `grid-columns-auto-fit: "1"` + `grid-column-min-width: "X"`. Patrón muy común en grids responsivos que antes se perdía a `custom-css`.

10. **`var()` en propiedades de color queda nativo**: para `color`, `background-color`, `border-*-color`, `button-text-color`, `overlay-color`, `box-shadow-color`, `text-shadow-color`, `icon-color`, `icon-background-color`, `fill`, `stroke`, los valores con `var()`/`calc()`/`clamp()`/etc. se emiten directamente. Oxygen los preserva como string opaco en el panel y renderiza tal cual. Mismo trato para `transition-property`. Reduce mucho el `custom-css` en sitios con design tokens.

11. **Pseudo-elementos extra y `:visited`**: agregados `first-letter`, `first-line`, `selection` (set completo según `is_pseudo_element()` de Oxygen) y la pseudo-clase `:visited`. Antes iban a Code Block; ahora se emiten como state nativo.

### Limpieza arquitectónica

12. **`<a>` → `ct_link_button` requiere opt-in explícito**: el mapeo a `ct_link_button` ahora se dispara solo si la clase `is-oxy-button` está presente. Antes cualquier `<a class="...btn...">` o `...button...` o `...boton...` se convertía en `ct_link_button` (que renderiza con estilos de botón nativos de Oxygen, tapando los del user). Todo lo demás cae a `ct_link` (con hijos) o `ct_link_text` (solo texto).

13. **Removido `original.tag` duplicado en classes top-level**: `tag` es opción del bloque, no de la clase. Inyectarlo en las clases forzaba el mismo tag a cualquier otro bloque que compartiera la clase. Ahora `tag` vive solo en `options.original` del bloque correspondiente.

## v3.2 — cobertura extendida (2026-05-26)

Segunda iteración del mismo día. Ataca los pendientes deliberados de v3.1.

### Nuevas capacidades nativas

14. **`filter: <fn>(<arg>)` mapeado broken-out**: `filter: blur(8px)` ahora emite `filter: "blur"` + `filter-amount-blur: "8"` (con `-unit` si difiere del default). Editable desde el panel Effects. Funciones soportadas: `blur`, `brightness`, `contrast`, `grayscale`, `hue-rotate`, `invert`, `saturate`, `sepia`. Múltiples funciones simultáneas, valores ambiguos (ej. `brightness(0.8)` sin unidad) y funciones no soportadas (`drop-shadow`, `matrix`, etc.) caen a `custom-css`.

15. **`transform` como array de transform-step objects**: `transform: translate(10px,20px) rotate(45deg) scale(1.2)` se emite como array de 3 step-objects que Oxygen ensambla en `getTransformCSS`. Funciones soportadas: `translate*`, `translate3d`, `rotate*`, `scale*`, `scale3d`, `skew*`, `perspective`. `matrix`, `matrix3d`, `rotate3d` con args sueltos van a `custom-css`. `transform` agregado a `NATIVE_PROPERTIES`.

16. **`data-aos-*` del HTML → keys `aos-*` nativas**: `<div data-aos="fade-up" data-aos-duration="600">` se emite con `original.aos-type: "fade-up"` y `original.aos-duration: "600"` en lugar de pasarlos como `custom-attributes` inertes. Editables desde el panel "Effects > Animation on Scroll". Mapeo: `data-aos` → `aos-type`, los demás `data-aos-*` → `aos-*` con el mismo sufijo.

### Tags HTML adicionales

17. **Tablas, forms, blockquote, pre, hr, etc. ya no caen a "Tag desconocido"**. Tres categorías:
    - **Pure containers** (`<table>/<thead>/<tbody>/<tfoot>/<tr>/<colgroup>/<form>/<fieldset>/<select>/<blockquote>/<pre>`): `ct_div_block` con `useCustomTag` + tag.
    - **Void elements** (`<input>/<hr>/<col>/<br>`): `ct_div_block` con `useCustomTag`, sin children. Atributos del input viajan como `custom-attributes`.
    - **Trio** (`<td>/<th>/<caption>/<label>/<legend>/<figcaption>/<summary>/<option>/<code>/<textarea>`): mismo trío que `<li>`/`<button>` — estructural → `ct_div_block`, inline mixto → `oxy_rich_text`, texto plano → `ct_text_block`.

### `style="..."` inline soportado

18. **Eliminada la regla de rechazo de `style` inline del contrato**. Las propiedades se parsean con tinycss2 y se mergean en `options.original` del bloque específico (no en las clases — evita contaminar otros bloques que compartan clase). Inline tiene prioridad sobre lo que ya estaba en `original`. Propiedades no nativas se concatenan al `custom-css` existente del bloque. El atributo `style` se excluye de `custom-attributes`.

### Bug pre-existente arreglado

19. **Comentarios HTML (`<!-- ... -->`) generaban `ct_text_block` ruido**: BeautifulSoup expone `Comment` como subclase de `NavigableString`. Fix: importar `Comment` y `continue` cuando aparece como hijo, tanto en `_build_component` como en `_maybe_inject_text_child`.

## v3.3 — bloques nativos avanzados (2026-05-26)

Tercera iteración del día. Suma tres bloques nativos avanzados desbloqueados por una segunda auditoría del código de Oxygen.

### Nuevos bloques nativos

20. **`oxy-shape-divider` con detección automática**: cualquier `<svg viewBox="0 0 1440 320">` cuyo primer `<path d="...">` matchee exactamente el catálogo built-in de Oxygen (30 shapes: Wavy, Angle, Cave, Curvy, Diamond, Ocean, Logs, Towers, Valley, Balance — variantes 1/2/3 de cada uno) se emite como `oxy-shape-divider` nativo con `oxy-shape-divider_svg_shape: "<nombre>"`. Matching por hash md5 del path normalizado: cero falsos positivos. SVGs que no matchean caen a Ruta C (code_block) como antes. Los atributos del `<svg>` original NO se emiten como `custom-attributes`. WARN avisa que debe vivir dentro de un `ct_section`.

21. **`ct_section` nativo via opt-in `<section class="is-oxy-section">`**: habilita las propiedades únicas de section (section-width, container-padding-*, video_background) del panel nativo. Sin la clase, sigue como `ct_div_block` con `tag: section` (default seguro). Oxygen agrega `.ct-section-inner-wrap` automáticamente al renderizar.

22. **`ct_new_columns` nativo via opt-in `<div class="is-oxy-columns">`**: habilita stacking responsive nativo (stack-columns-vertically, reverse-column-order, set-columns-width-50). Reemplaza media queries manuales por una opción editable desde el panel. Default `stack-columns-vertically: tablet`.

### Lo que NO se implementó de la segunda auditoría

- **Stylesheets** (option global, inapropiado para JSON pegable).
- **Omitir defaults Oxygen** (optimización marginal con riesgo si los defaults cambian).
- **`%%ELEMENT_ID%%` en custom-css** (solo funciona en oxy-*, no en ct_* que es lo que mayormente emitimos).
- **`color(N)` / `["global", key]`** (IDs/keys dependen del site destino, no portables).
- **`[oxygen ...]` dynamic shortcodes** (requieren firma HMAC del site).
- **`ct_reusable`** (requiere post `ct_template` pre-creado en DB).
- **Base64-encode `content` de pseudo-states / `normalize_custom_css`**: verificado, solo aplica al save→DB, no al paste flow. El skill ya emite plano correctamente.

## v3.4 — componentes multimedia + filtro de clases internas (2026-05-26)

Cuarta iteración del día. Suma componentes multimedia y limpia el ruido cuando se pega HTML rendered de un site Oxygen.

### Nuevos bloques

23. **`ct_video` auto-detectado desde iframe YouTube/Vimeo**: `<iframe src="https://youtube.com|youtu.be|vimeo.com|player.vimeo.com/...">` se emite como `ct_video` con `src`, `embed_src`, `video-padding-bottom: "56.25%"` (16:9 default), `use-custom: "0"`. Aspect ratio se puede editar desde el panel. iframes que no matchean (formularios, twitter, etc.) caen a `ct_code_block` con HTML literal y WARN.

24. **`oxy_map` auto-detectado desde iframe Google Maps Embed**: `<iframe src="https://www.google.com/maps/embed/v1/place?key=...&q=ADDR&zoom=N">` se emite como `oxy_map` con `map_address` (URL-decoded) y `map_zoom` parseados.

25. **`oxy_progress_bar` opt-in via `is-oxy-progress-bar`**: `<div class="is-oxy-progress-bar" data-percent="75">` → `oxy_progress_bar` con `progress_percent: "75"`. El HTML interno del div se descarta (Oxygen regenera su propia estructura). Sin opt-in, sigue siendo `ct_div_block`.

26. **`ct_code_block` con `unwrap:true` opt-in via `is-oxy-unwrap`**: cualquier tag con esta clase se emite como `ct_code_block` con HTML completo en `code-php` y `unwrap: "true"`. Útil para preservar markup arbitrario sin transformación. Se evalúa antes de cualquier otro detector.

### Filtro de clases internas

27. **Clases internas inyectadas por Oxygen ya no contaminan el output**. Cuando user pega HTML rendered de un site Oxygen, las clases auto-inyectadas (`ct-div-block`, `ct-section-inner-wrap`, `oxy-progress-bar-background`, `ct-fancy-icon`, `oxy-icon-box-content`, prefijos `oxy-pro-menu`, `oxy-pricing-box`, `oxy-nav-menu-hamburger-`, etc.) se filtran del `classes:` array para evitar duplicación. Lista completa en `_OXYGEN_INTERNAL_CLASSES` y `_OXYGEN_INTERNAL_CLASS_PREFIXES` (catalogadas de `oxygen.css`).

28. **Clases marker del skill también filtradas**: `is-oxy-section`, `is-oxy-columns`, `is-oxy-button`, `is-oxy-unwrap`, `is-oxy-progress-bar` se consumen como semáforos y se omiten del `classes:` final para no aparecer como entries vacías en el panel.

### Limitaciones documentadas explícitamente

- **JSON pegable es per-post** (postmeta `ct_builder_json`). Para site-wide imports (clases globales, color palette, stylesheets, page settings) usar Manage > Import en Oxygen — formato distinto con keys `classes`, `custom_selectors`, `style_sets`, `style_folders`, `style_sheets`, `global_settings`, `element_presets`, `global_colors`.
- **Tras pegar el JSON**, regenerar CSS cache desde Settings > Cache > Regenerate (o el endpoint `?regenerate_oxygen_css=true`).
- **WPML auto-traduce** el contenido de `ct_headline`, `ct_text_block`, `ct_paragraph`, `ct_li`, `ct_link_text` sin acción adicional.
- **Componentes NO emitibles** (requieren WP runtime): `oxy_login_form`, `oxy_search_form`, `oxy_comments`, `oxy_comment_form`, `ct_widget`, `ct_sidebar`, `oxy_nav_menu`, `oxy_pro_menu`, `oxy_posts_grid` (Easy Posts), `oxy_dynamic_list`, `ct_toolset_view`, `ct_inner_content`, `ct_reusable`, `ct_shortcode`, `ct_nestable_shortcode`. El user debe crearlos manualmente en el builder.
- **`_conditions`** (display rules): no se auto-emiten (no hay señal visible en HTML).
- **`[oxygen ...]` dynamic shortcodes**: no emitibles desde el skill (requieren firma HMAC del site, generada por el editor al insertarlas).

### Lo que NO se implementó (de la tercera auditoría)

- `oxy_social_icons` (hard-coded a 6 redes, muy específico al estilo Oxygen).
- `oxy_superbox` (2-state hover, uso nicho).
- `oxy_soundcloud` (ultra-nicho).
- `ct_slider`/`ct_slide` (requiere unslider JS y `<script>` inline).
- `oxy_gallery` (requiere `image_ids` de WP media library).
- `oxy_header*` builder, `ct_inner_content` (solo tienen sentido en templates de Oxygen).

## Si el usuario pide algo que está fuera de scope

Sé honesto y específico:
- Si pide soporte para Oxygen 4 nuevo (Breakdance-style): este skill es para Oxygen clásico 4.x, no para el reescrito reciente.
- Si pide convertir JSON de Oxygen → HTML/CSS (dirección inversa): este skill NO hace eso, dile que sería un skill distinto.
- Si pide soporte para sliders, accordions, tabs, repeaters, dynamic data: fuera de scope, sugiere crear esos bloques manualmente y luego envolver con un `ct_div_block`.
