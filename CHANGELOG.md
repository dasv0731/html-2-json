# Changelog — oxygen-json-v3

Registro de cambios incrementales aplicados al skill `oxygen-json-v3` después de su release inicial. Cada entrada documenta qué se cambió, por qué, y cómo se validó. Backups de versiones previas viven en `.backup-YYYYMMDD-HHMMSS/` en la raíz del skill.

---

## 2026-05-27 — v3.11: background-image con gradient -> custom-css (Test-01 sidebar)

Bug en pipeline de Oxygen detectado en `controller.css.js:5437-5439`:

```javascript
if (parameter == 'background-image' || parameter == 'background-size') {
    continue;  // delegate to getBackgroundLayersCSS
}
```

Oxygen skipea `background-image` en su procesamiento normal — lo delega a `getBackgroundLayersCSS`. Ese handler **solo soporta URL como background-image**, no gradients (`linear-gradient`, `radial-gradient`, `conic-gradient`). Resultado: cualquier gradient emitido como `background-image` se pierde visualmente.

### Caso real

`.t01__sidecta::before` con `background-image: linear-gradient(45deg, transparent 45%, #FFD60A 45%, #FFD60A 55%, transparent 55%)` (el cuadrado decorativo amarillo de la card del sidebar) no aparecía.

### Fix

En `convert_properties`, detectar `background-image` con value que contenga `*gradient(`. Redirigir a `custom-css` (concatenado al state correspondiente). Lista de funciones detectadas:

- `linear-gradient`, `repeating-linear-gradient`
- `radial-gradient`, `repeating-radial-gradient`
- `conic-gradient`, `repeating-conic-gradient`

`background-image: url(...)` sigue por el flow nativo de Oxygen.

### Trade-off

El panel Background de Oxygen no mostrará el gradient editable — vive en custom-css.

---

## 2026-05-27 — v3.10: margin: auto en ct_div_block tambien necesita custom-css !important

Continuacion del fix de v3.9. Aunque el JSON ahora emitia `margin-left: "auto"` + `margin-left-unit: "auto"` correctamente, el container con `margin: 0 auto` **seguia sin centrarse en Oxygen**.

### Causa raíz

Oxygen aplica `.ct-div-block { margin: 0 !important; }` con prioridad CSS. Esto afecta a TODOS los ct_div_block, incluyendo cuando el user define `margin: 0 auto` en su clase. El skill ya tenia workaround para margins numericos (redirigir a `custom-css` con `!important`), pero el branch SKIPEABA explicitamente el caso `auto`:

```python
# v3.9 (broken):
if v_clean != "auto":
    custom_css.append(...)  # solo para numericos
```

### Fix v3.10

Extender el workaround a `auto` tambien:

```python
if v_clean == "auto":
    custom_css.append(f"{prop}: auto !important;")
    continue
# resto del fix numerico
```

Ahora `margin: 0 auto` en `.t01__container` emite:
```css
custom-css: "margin-top: 0px !important; margin-bottom: 0px !important; margin-right: auto !important; margin-left: auto !important;"
```

El centrado del container funciona correctamente.

### Trade-off

El panel "Position > Margin" de Oxygen NO mostrara los valores auto editables — viven en custom-css. Para editar margin del container, el user debe ir a "Advanced > Custom CSS". Mismo trade-off que con margins numericos del workaround original.

---

## 2026-05-27 — v3.9: margin/width auto necesita value + unit (Test-01 hero container)

Bug descubierto al ver que `<div class="t01__container">` con `margin: 0 auto` no se centraba en Oxygen — quedaba alineado a la izquierda con un "corte" visible a la derecha.

### Causa raíz

El skill mapeaba `margin-left: auto` a SOLO `margin-left-unit: "auto"` (sin emitir `margin-left` con value). El flow de Oxygen `build_css` (component.class.php:2766-2778) tiene branches:

- **SECTION A** (línea 2766): si la prop tiene default unit definido (margin-left tiene `'px'`), procesa el unit:
  - Si `atts['margin-left-unit'] == 'auto'`, hace `$atts['margin-left'] = 'auto'`. **Pero solo si `atts['margin-left']` ya existía**. Si solo emites `margin-left-unit` sin `margin-left`, esta inyección NO se dispara porque la línea 2766 chequea contra `default_atts[$default_param.'-unit']`, no contra el `param` actual.

Resultado: Oxygen emite `margin-left-unit: auto` al JSON guardado, pero al renderizar el CSS final, **NO sale `margin-left: auto;`** porque falta el value pair.

### Fix

En `_convert_value_with_unit`, cuando el value es `"auto"` para `margin-{top,right,bottom,left}` o `width/height/min-/max-`, emitir AMBOS:

```python
return [(prop, "auto"), (f"{prop}-unit", "auto")]
```

Antes solo emitía `(f"{prop}-unit", "auto")`. El cambio asegura que el CSS final tenga `<prop>: auto;`.

### Validación

`.t01__container` ahora emite `margin-left: auto` + `margin-left-unit: auto` (y mismo para right). Centrado funciona correctamente.

---

## 2026-05-27 — v3.8: auto `align-items: stretch` para ct_div_block (Test-01 hero overflow)

Bug arquitectónico descubierto durante el aislamiento del hero: `<section class="t01__hero">` (hijo de `<div class="t01">`) no ocupaba el 100% del ancho del parent. Causa raíz: Oxygen aplica `display:flex; flex-direction:column; align-items:flex-start` por default a TODOS los ct_div_block. Con `align-items:flex-start`, los hijos no estiran al ancho del parent — se encogen al ancho de su contenido. Eso rompe el block flow natural de HTML donde `<section>`/`<header>`/`<div>` ocupan 100% del padre.

### Fix

En `build_classes_block`, después de convertir props, si:
- `block_type == "ct_div_block"`, y
- el CSS del user NO define `align-items`,

entonces auto-añadir `align-items: stretch`. En clases con `display:inline-block`/`block`/etc. (no flex containers) la regla es inocua (align-items solo afecta flex/grid). En clases con flex explícito, restaura el behavior natural de HTML donde los hijos block-level ocupan 100% del ancho.

### Side effects controlados

- Clases con `align-items` explícito (`flex-start`, `center`, etc.) se respetan tal cual.
- Clases con `flex-direction: row` reciben stretch que afecta height (matchea default flex-row de browser).
- Clases con `display: grid` reciben stretch (default grid también).

### Validación

Re-corrido de Test-01/01-hero:
- `.t01` ahora emite `align-items: stretch` → `<section class="t01__hero">` ocupa 100% width.
- `.t01__hero-main` mantiene `align-items: flex-start` (definido por user).
- `.t01__heroCta-list` agrega `align-items: stretch` → los `<li>` ocupan 100% (matchea `.t01__btn--full`).

---

## 2026-05-26 — v3.7: tags vacios decorativos -> ct_div_block (post-render Test-01 round 2)

Bug descubierto al ver el segundo render de Test-01: spans/lis/buttons HTML vacíos (típicamente decorativos con dimensiones via CSS, ej. `<span class="brand-mark" aria-hidden></span>` como cuadradito de color) se mapeaban a `ct_text_block`. Oxygen renderiza un placeholder/label visible en ct_text_blocks sin `ct_content`, descuadrando todo el layout del decorativo.

### Fix

Nuevo helper `_is_empty_tag(tag)`: True si el tag no tiene ni texto significativo ni hijos Tag. Aplicado al INICIO de los 4 trios (`<span>`/`<em>`/`<strong>`/etc., `<li>`, `<button>`, TRIO_TAGS general): si el tag está vacío, retornar `ct_div_block` con `useCustomTag`. Resto del trío sin cambios.

### Validación

Re-corrido de Test-01:
- `.t01__brand-mark` (header + footer) ahora `ct_div_block` (antes `ct_text_block`).
- `.t01__hero-dot` (separadores meta) ahora `ct_div_block`.
- `.t01__avatar` (article header) ahora `ct_div_block`.

Estos decorativos ya no muestran texto placeholder; preservan dimensiones y background del CSS sin contenido espurio.

---

## 2026-05-26 — v3.6: fixes derivados de Test-01 (Metalectro blog) post-render

Tres bugs descubiertos al pegar el JSON del primer test integral en Oxygen y observar el render real.

### Bug B (crítico): hijos inline con clase aplanados a oxy_rich_text rompen layout flex

Cuando un container (`<a>`, `<div>`) tenía hijos inline como `<span class="t01__brand-mark">` (con dimensiones/background propios), el skill los aplanaba a un único `oxy_rich_text` con `<p>` envolvente. El layout flex del padre quedaba roto porque los spans ya no eran hijos directos del flex container — eran nietos dentro del `<p>`.

Fix en `_maybe_inject_text_child`: nuevo chequeo `has_classed_inline`. Si CUALQUIER hijo inline (que no sea `<a>`) tiene clase propia, retornar `None` para que cada hijo se procese como bloque editable individual (preserva estructura).

### Bug C (crítico): span/strong/em con SVG hijo perdían el SVG

`<span class="t01__callout-icon"><svg>...</svg></span>` se mapeaba a `ct_text_block` con `useCustomTag: span`. Pero `ct_text_block` solo emite `ct_content` y NO acepta hijos. El SVG desaparecía silenciosamente.

Fix en `_resolve_block_type`: extender el patrón "trío" a `span`/`em`/`strong`/`small`/`b`/`u`/`mark`. Si tienen hijos estructurales → `ct_div_block` (preserva SVG/img). Si tienen HTML inline mixto con texto → `oxy_rich_text`. Texto plano → `ct_text_block` (como antes).

### Bug A (cosmético, CSS inválido): content vacío emitido como `content: ;`

Cuando el inner-style block reserializaba un state `::before`/`::after` con `content: ""`, emitía `content: ;` (sin valor, CSS inválido). El browser descartaba toda la regla → pseudo-elemento decorativo invisible.

Fix con dos helpers nuevos: `_format_content_value()` re-envuelve strings vacíos/sin comillas en comillas dobles; `_serialize_decl()` los aplica a `content`. Las funciones (`attr()`, `counter()`, `url()`, `var()`) y keywords (`none`, `inherit`, etc.) se preservan tal cual.

### Validación

Re-corrido de Test-01 verificado:
- `.t01__brand` ahora emite 2 children directos (`ct_text_block` para brand-mark, `oxy_rich_text` para brand-word) en lugar de un único rich_text aplanado.
- `.t01__callout-icon` ahora es `ct_div_block` con un `ct_code_block` hijo conteniendo el SVG.
- `.t01__brand-mark::after` ahora vive en el state `after` del classes top-level (no en inner-style block, que es donde antes emitía CSS inválido).

---

## 2026-05-26 — v3.5: tags HTML faltantes detectados en testing real

Fix derivado del primer test integral (blog Metalectro). El test reveló que `<figure>` y `<time>` caían a "Tag desconocido" → `ct_div_block` sin tag, perdiendo la semántica HTML y rompiendo cualquier CSS que apunte a esas clases esperando que sean `<figure>`/`<time>` reales.

### Tags agregados a PURE_CONTAINER_TAGS

- `<figure>` (contenedor de img + figcaption)
- `<picture>` (contenedor de source + img responsive)
- `<dl>` (definition list, contenedor de dt/dd)

### Tags agregados a TRIO_TAGS

- `<time>` (texto datetime)
- `<address>` (info de contacto)
- `<dt>`, `<dd>` (items de definition list)
- `<cite>`, `<q>`, `<ins>`, `<del>`, `<abbr>` (texto inline semántico)
- `<var>`, `<kbd>`, `<samp>` (texto inline técnico)

Todos siguen el mismo patrón establecido en v3.2: contenedores puros van a `ct_div_block` con `useCustomTag`, tags texto-inline pasan por trío (estructural → div, inline mixto → rich text, plano → text_block), todos con `useCustomTag`.

### Validación

Test-01 (blog Metalectro completo, 403 nodos, 154 clases) ya no emite ningún "Tag no mapeado".

---

## 2026-05-26 — Sesión "v3.4": componentes multimedia + filtro de clases internas (tercera auditoría)

Cuarta iteración del día. Basada en una tercera pasada exhaustiva del código de Oxygen que cubrió componentes especializados (video, slider, social-icons, progress-bar, map, soundcloud, gallery, easy-posts, dynamic-list, login/search/comments forms, widget, toolset-view, header builder, sidebar, code-block, selector, shortcode wrappers, inner-content), pipeline csslink/signature/main-template, admin/toolbar views (incluyendo conditions), CSS dinámico (oxygen.css clases utilitarias internas vs oxygen.variables.css), wpml-config.xml, vendor (unslider/aos/alpinejs).

### Nuevos bloques nativos

**1. `ct_video` auto-detectado desde iframe YouTube/Vimeo**

Cuando el HTML pegado contiene `<iframe src="https://youtube.com|youtu.be|vimeo.com|player.vimeo.com/...">`, se emite como `ct_video` con `src`, `embed_src`, `video-padding-bottom: "56.25%"` (16:9 default), `use-custom: "0"`. Los demás atributos del iframe (frameborder, allowfullscreen, allow) viajan como `custom-attributes`. iframes que no matchean (formularios, twitter, etc.) caen a `ct_code_block` con HTML literal y WARN.

**2. `oxy_map` auto-detectado desde iframe Google Maps Embed**

Cuando el HTML pegado contiene `<iframe src="https://www.google.com/maps/embed/v1/place?key=...&q=ADDR&zoom=N">`, se emite como `oxy_map` con `map_address` (URL-decoded) y `map_zoom` extraídos del query string. Parser usa `urllib.parse` estándar.

**3. `oxy_progress_bar` opt-in via `is-oxy-progress-bar`**

`<div class="is-oxy-progress-bar" data-percent="75">` → `oxy_progress_bar` con `progress_percent: "75"`. El HTML interno del div se descarta (oxy_progress_bar regenera su propia estructura). Sin la clase opt-in, sigue siendo `ct_div_block` normal. La clase opt-in se filtra del classes: array. Decisión: opt-in en lugar de auto-detect porque `.oxy-progress-bar` ya se filtra como clase interna (ver punto 5).

**4. `ct_code_block` con `unwrap:true` opt-in via `is-oxy-unwrap`**

Cualquier tag con la clase `is-oxy-unwrap` se emite como `ct_code_block` con el HTML completo del tag en `code-php` y `unwrap: "true"` (Oxygen NO agrega wrapper externo). Útil para preservar markup arbitrario (scripts, web components, custom widgets) sin transformación. Se evalúa ANTES de cualquier otro detector (ej. svg/iframe) para que la opt-in del user gane sobre auto-detección. La clase opt-in se filtra del classes: array.

### Filtro de clases internas de Oxygen

**5. Lista negra de clases inyectadas por Oxygen al renderizar**

Cuando el user pega HTML rendered de un site Oxygen, aparecen clases como `ct-div-block`, `ct-section-inner-wrap`, `oxy-progress-bar-background`, `ct-fancy-icon`, `oxy-icon-box-content`, etc. Estas las inyecta Oxygen al renderizar el bloque correspondiente y NO deben emitirse en el `classes:` array (causaría duplicación visual y entradas vacías en Manage > Selectors).

Nuevas constantes:
- `_OXYGEN_INTERNAL_CLASSES`: ~45 nombres exactos (ct-*, oxy-* wrappers, headers, footers, video, gallery, tabs, icon-box, etc.).
- `_OXYGEN_INTERNAL_CLASS_PREFIXES`: `oxy-nav-menu-hamburger-`, `oxy-pricing-box`, `oxy-pro-menu`.
- `_SKILL_OPTIN_CLASSES`: `is-oxy-section`, `is-oxy-columns`, `is-oxy-button`, `is-oxy-unwrap`, `is-oxy-progress-bar` (marker classes que el skill consume y filtra del output).

Helper `_filter_user_classes()` se aplica en `_build_component` al setear `options["classes"]`. Las raw classes siguen siendo accesibles para las detecciones (`_resolve_block_type` lee el `tag.get("class")` directo para chequear opt-ins).

### Limitaciones documentadas

Agregadas a SKILL.md (no requieren código):
- JSON pegable es **per-post** (postmeta `ct_builder_json`). Para emitir clases/colors/stylesheets globales site-wide, usar Manage > Import (formato distinto con keys `classes`, `custom_selectors`, `style_sets`, `style_folders`, `style_sheets`, `global_settings`, `element_presets`, `global_colors`).
- Tras pegar el JSON, regenerar el CSS cache desde Settings > Cache > Regenerate.
- WPML auto-traduce el contenido de 5 shortcodes (`ct_headline`, `ct_text_block`, `ct_paragraph`, `ct_li`, `ct_link_text`) sin acción adicional.
- Componentes que requieren WP runtime y NO se emiten: `oxy_login_form`, `oxy_search_form`, `oxy_comments`, `oxy_comment_form`, `ct_widget`, `ct_sidebar`, `oxy_nav_menu`, `oxy_pro_menu`, `oxy_posts_grid` (Easy Posts), `oxy_dynamic_list`, `ct_toolset_view`, `ct_inner_content`, `ct_reusable`, `ct_shortcode`, `ct_nestable_shortcode`. El user debe crearlos manualmente en el builder.
- `_conditions` (display rules) no se auto-emiten (no hay señal visible en HTML).
- `[oxygen ...]` dynamic shortcodes no se emiten (requieren firma HMAC del site).

### Lo que NO se implementó (de la tercera pasada)

- **`oxy_social_icons`**: hard-coded a 6 redes (facebook, instagram, twitter, linkedin, rss, youtube) con SVG inline; muy específico al estilo de Oxygen; user lo crea manualmente más fácil que un detector de iconos sociales.
- **`oxy_superbox`**: 2-state hover con primary/secondary; uso muy nicho.
- **`oxy_soundcloud`**: iframe trivial pero ultra-nicho; user lo crea con ct_video o ct_code_block.
- **`ct_slider/ct_slide`**: requiere unslider JS y configuración inline `<script>`; complejo y poco usado.
- **`oxy_gallery`**: requiere `image_ids` de WP media library, no recreable desde HTML estático.
- **`oxy_header*` builder, `ct_inner_content`**: solo tienen sentido dentro de templates de Oxygen (no en posts normales).
- **AOS auto-detect ya estaba (v3.2)**.

### Validación

Smoke test con: iframe YouTube embed, iframe Vimeo, iframe Google Maps Embed, iframe Twitter (fallback), div opt-in progress-bar con data-percent, div opt-in unwrap con `<script>`, div con clases internas mezcladas (`ct-div-block ct-section-inner-wrap my-card oxy-pricing-box-price`). Resultado: cada caso emite el bloque correcto con las propiedades parseadas; clases internas filtradas correctamente preservando `my-card`. Sintaxis Python validada vía `ast.parse`.

### Archivos modificados

- `transform.py`: +~140 líneas neto.
- `SKILL.md`: agregar sección v3.4 + limitaciones.
- `CHANGELOG.md`: este registro.

---

## 2026-05-26 — Sesión "v3.3": bloques nativos avanzados (segunda auditoría)

Tercera iteración del día. Basada en una segunda pasada del código de Oxygen enfocada en áreas no cubiertas (Elements API oxy-*, reusable parts, stylesheets, %% tokens, sistema de globals, ct_section/new_columns real). Agrega tres bloques nativos avanzados como opt-in, dejando los defaults seguros.

### Nuevos bloques soportados

**1. `oxy-shape-divider` con detección automática**

Cuando el HTML contiene un `<svg viewBox="0 0 1440 320">` cuyo primer `<path>` matchea exactamente el catálogo built-in de Oxygen 4.x (30 shapes: Wavy 1-3, Angle 1-3, Cave 1-3, Curvy 1-3, Diamond 1-3, Ocean 1-3, Logs 1-3, Towers 1-3, Valley 1-3, Balance 1-3), se emite como `oxy-shape-divider` nativo con `oxy-shape-divider_svg_shape: "<nombre>"` (las options de Elements API van prefijadas con el tag).

- Matching por hash md5 del atributo `d` normalizado → cero falsos positivos.
- Hashes precomputados en `_OXY_SHAPE_DIVIDER_HASHES` (1.7KB embebidos en `transform.py`).
- SVGs que no matchean (cualquier path custom o los 3 Sharks que usan otra estructura) caen a Ruta C (code_block) como antes.
- Los atributos del `<svg>` original (xmlns, viewBox, preserveAspectRatio, fill, fill-opacity) NO se emiten como `custom-attributes` — Oxygen renderiza el SVG completo internamente según `svg_shape`.
- WARN dice al user que el shape-divider debe vivir dentro de un `ct_section` para que Oxygen agregue la clase `ct-section-with-shape-divider` automáticamente.
- Selector base agregado: `"oxy-shape-divider": "-shape-divider"` (es `name.slice(3)`, da el guión inicial).
- Tool auxiliar: regenerar hashes corriendo `extract_shape_hashes.py` contra el código fuente de Oxygen.

**2. `ct_section` nativo via opt-in `is-oxy-section`**

Cuando un `<section class="is-oxy-section">` se detecta, se emite como `ct_section` real en lugar del default `ct_div_block` con `tag: section`. Habilita las propiedades nativas únicas de section:
- `section-width: page-width` (centrado a max-width global)
- `container-padding-*` (padding del inner-wrap)
- `video_background`

Decisión de diseño: opt-in explícito (en lugar de heurística por padding/max-width) para evitar sorpresas. Sin la clase, sigue el default seguro de `ct_div_block`.

Oxygen agrega automáticamente el wrapper `.ct-section-inner-wrap` al renderizar (`section.class.php:70`) — el skill no necesita emitir wrap manual.

**3. `ct_new_columns` nativo via opt-in `is-oxy-columns`**

Cuando un `<div class="is-oxy-columns">` con N hijos se detecta, se emite como `ct_new_columns` real. Habilita las opciones de stacking responsive nativas:
- `stack-columns-vertically: tablet` (default) — abajo de qué breakpoint las columnas se apilan.
- `reverse-column-order` — en qué breakpoint invertir.
- `set-columns-width-50` — abajo de qué breakpoint forzar 50%.

Reemplaza CSS responsive manual (`@media (max-width: 992px) { flex-direction: column }`) por una opción nativa editable desde el panel. Default flex: `direction=row`, `wrap=wrap`, `align-items=stretch`, `stack-vertically-below=tablet`.

### Cambios estructurales menores

- `SELECTOR_BASE` y `NICENAME_BASE` extendidos con `oxy-shape-divider`, `ct_new_columns`.
- `_build_component` ahora trata `ct_section` y `ct_new_columns` como contenedores (procesa children recursivamente).

### Lo que NO se implementó (de la segunda pasada) y por qué

- **Stylesheets en lugar de code_block**: son option global (`ct_style_sheets`), no per-post. Inapropiado para JSON pegable que representa un componente único.
- **Omitir defaults Oxygen redundantes** (ej. `display:flex` en ct_div_block ya es default): optimización marginal con riesgo si Oxygen cambia defaults en el futuro.
- **`%%ELEMENT_ID%%` en custom-css**: solo funciona en oxy-* (Elements API), no en ct_*. El skill emite mayormente ct_*, no aplica.
- **`color(N)` / `["global", key]`**: los IDs/keys dependen del site destino, no portables. Emitir literal hex/font es más seguro.
- **`[oxygen ...]` dynamic shortcodes**: requieren firma HMAC del site (`Oxygen_VSB_Signature`), imposibles de generar desde el skill. El user los inserta vía el builder UI que las firma automáticamente.
- **`ct_reusable`**: requiere un post `ct_template` pre-creado en la DB. No emitible desde JSON pegable puro.
- **Base64-encode `content` de pseudo-states / `normalize_custom_css`**: verificado contra código — solo se ejecutan en save→DB y JSON↔shortcode conversion, no en el paste flow. El skill emite plano correctamente.

### Validación

Smoke test con `<section class="hero is-oxy-section"><div class="hero__cols is-oxy-columns"><div class="col col-a">...</div>...<svg viewBox="0 0 1440 320">...<path d="..."></path></svg></section>`. Resultado:
- `ct_section` con clases preservadas.
- `ct_new_columns` con 3 hijos `ct_div_block`.
- `oxy-shape-divider` detectado como `Wavy 1`, options prefijadas, sin custom-attributes ruido.

Caso negativo (SVG no en catálogo): cae a `ct_code_block` con SVG inline como antes.

### Archivos modificados

- `transform.py`: +~150 líneas neto. Catálogo de 30 hashes + detector + branches opt-in.
- `SKILL.md`: actualizar capacidades + agregar opt-ins.
- `CHANGELOG.md`: este registro.

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
