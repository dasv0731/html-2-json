#!/usr/bin/env python3
"""
Transformador de HTML+CSS a JSON de Oxygen Builder clasico (4.x para WordPress).

Uso:
    python transform.py --html input.html --css input.css --out output.json

Salida:
    - output.json con el JSON pegable en bloque reusable de Oxygen
    - Avisos por stderr sobre que se mapeo donde

Ver SKILL.md y references/ para el detalle de las reglas.
"""

import argparse
import hashlib
import json
import re
import sys
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

import tinycss2
from bs4 import BeautifulSoup, Comment, NavigableString, Tag


# ============================================================
# CONSTANTES
# ============================================================

# Sufijo del selector. Se asigna en main() desde --selector-suffix o aleatorio.
# Empiricamente es el post_id del template/page donde el bloque vive (ver oxygen-quirks.md).
# Oxygen probablemente reasigna al pegar, asi que un valor unico es suficiente.
SELECTOR_SUFFIX = "0000"  # placeholder, se sobreescribe en main()

# ct_parent del nodo raiz del bloque reusable. Oxygen lo reasigna al pegar.
ROOT_CT_PARENT = 100007

# Tolerancia para mapeo de breakpoints (en px)
BREAKPOINT_TOLERANCE = 1

# Mapeo breakpoint CSS (max-width en px) -> nombre interno Oxygen
BREAKPOINTS = [
    (1120, "page-width"),
    (992, "tablet"),
    (768, "phone-landscape"),
    (480, "phone-portrait"),
]

# Mapeo HTML tag -> tipo de bloque Oxygen
TAG_TO_BLOCK_TYPE = {
    "div": "ct_div_block",
    "section": "ct_div_block",
    "article": "ct_div_block",
    "header": "ct_div_block",
    "footer": "ct_div_block",
    "aside": "ct_div_block",
    "nav": "ct_div_block",
    "main": "ct_div_block",
    "h1": "ct_headline",
    "h2": "ct_headline",
    "h3": "ct_headline",
    "h4": "ct_headline",
    "h5": "ct_headline",
    "h6": "ct_headline",
    "p": "ct_text_block",
    "span": "ct_text_block",
    "em": "ct_text_block",
    "strong": "ct_text_block",
    "small": "ct_text_block",
    "img": "ct_image",
    # <a> y <button> tienen logica especial mas abajo
}

# Tipo Oxygen -> base del selector.
# Formato: name.slice(3) en Angular (controller.tree.js:727).
# Para tags con 'oxy_' o 'oxy-' la slice da '_rich_text' o '-shape-divider'.
SELECTOR_BASE = {
    "ct_div_block": "div_block",
    "ct_headline": "headline",
    "ct_text_block": "text_block",
    "ct_link_button": "link_button",
    "ct_link": "link",
    "ct_link_text": "link_text",
    "ct_image": "image",
    "ct_section": "section",
    "ct_fancy_icon": "fancy_icon",
    "ct_code_block": "code_block",
    "oxy_rich_text": "_rich_text",
    "oxy-shape-divider": "-shape-divider",
    "ct_new_columns": "new_columns",
    "ct_video": "video",
    "oxy_map": "_map",
    "oxy_progress_bar": "_progress_bar",
}

# Tipo Oxygen -> nicename base
NICENAME_BASE = {
    "ct_div_block": "Div",
    "ct_headline": "Heading",
    "ct_text_block": "Text",
    "ct_link_button": "Button",
    "ct_link": "Link Wrapper",
    "ct_link_text": "Text Link",
    "ct_image": "Image",
    "ct_section": "Section",
    "ct_fancy_icon": "Icon",
    "ct_code_block": "Code Block",
    "oxy_rich_text": "Rich Text",
    "oxy-shape-divider": "Shape Divider",
    "ct_new_columns": "Columns",
    "ct_video": "Video",
    "oxy_map": "Map",
    "oxy_progress_bar": "Progress Bar",
}

# Propiedades CSS soportadas nativamente por Oxygen (panel editable).
# Verificado contra $options_white_list en components/component.class.php:224-453
# del codigo de Oxygen Builder 4.x.
NATIVE_PROPERTIES = {
    # Layout
    "display", "float", "clear", "visibility", "position",
    "top", "right", "bottom", "left", "z-index",
    "overflow", "overflow-x", "overflow-y",
    "flex-direction", "flex-wrap", "justify-content", "align-items",
    "align-content", "align-self", "flex-grow", "flex-shrink", "flex-reverse",
    "order",
    "column-gap", "row-gap", "gap", "grid-column-gap", "grid-row-gap",
    # Grid (panel nativo completo)
    "grid-column-count", "grid-columns-auto-fit",
    "grid-column-min-width", "grid-column-max-width",
    "grid-row-count", "grid-row-behavior",
    "grid-row-min-height", "grid-row-max-height",
    "grid-child-rules", "grid-all-children-rule",
    "grid-justify-items", "grid-align-items",
    "grid-match-height-of-tallest-child",
    # Espaciado
    "padding-top", "padding-right", "padding-bottom", "padding-left",
    "margin-top", "margin-right", "margin-bottom", "margin-left",
    "container-padding-top", "container-padding-right",
    "container-padding-bottom", "container-padding-left",
    "width", "height", "min-width", "min-height", "max-width", "max-height",
    # Tipografia
    "font-family", "font-size", "font-weight", "font-style",
    "color", "line-height", "letter-spacing", "direction",
    "text-align", "text-transform", "text-decoration",
    "list-style-type", "-webkit-font-smoothing",
    # Visual / background
    "background-color", "background-image", "background-position",
    "background-repeat", "background-size", "background-attachment",
    "background-clip", "background-blend-mode", "mix-blend-mode",
    "overlay-color", "gradient",
    # Borders (broken-out, los soportados por el panel)
    "border-top-width", "border-right-width", "border-bottom-width", "border-left-width",
    "border-top-style", "border-right-style", "border-bottom-style", "border-left-style",
    "border-top-color", "border-right-color", "border-bottom-color", "border-left-color",
    "border-top-left-radius", "border-top-right-radius",
    "border-bottom-left-radius", "border-bottom-right-radius",
    # Effects
    "opacity",
    # box-shadow y text-shadow se emiten broken-out (no como shorthand).
    # El expansor parsea el CSS shorthand a estas keys para que sean editables.
    "box-shadow-color", "box-shadow-horizontal-offset", "box-shadow-vertical-offset",
    "box-shadow-blur", "box-shadow-spread", "box-shadow-inset",
    "text-shadow-color", "text-shadow-horizontal-offset", "text-shadow-vertical-offset",
    "text-shadow-blur",
    # Transitions
    "transition-duration", "transition-timing-function",
    "transition-delay", "transition-property",
    # Transform: array de transform-step objects (parseado por _expand_transform).
    "transform",
    # Filters
    "filter",
    "filter-amount-blur", "filter-amount-brightness", "filter-amount-contrast",
    "filter-amount-grayscale", "filter-amount-hue-rotate",
    "filter-amount-invert", "filter-amount-saturate", "filter-amount-sepia",
    # Animations on Scroll (AOS) - mapeables desde data-aos-* del HTML
    "aos-type", "aos-duration", "aos-easing", "aos-offset", "aos-delay",
    "aos-anchor", "aos-anchor-placement", "aos-once", "aos-enable",
    # Botones (solo aplica a ct_link_button via excepcion en convert_properties)
    "button-text-color", "button-color", "button-hover_color", "button-size",
    # Imagenes
    "object-fit", "object-position", "aspect-ratio",
    # Iconos (ct_fancy_icon)
    "icon-size", "icon-color", "icon-background-color", "icon-padding",
    # Pseudo-elementos (validado en JSON real de Oxygen para before/after)
    "content",
}

# Propiedades cuya unidad SIEMPRE se emite (incluso px), para evitar ambiguedad
ALWAYS_EMIT_UNIT = {
    "width", "height", "min-width", "min-height", "max-width", "max-height",
}

# Propiedades unitless (no llevan unidad nunca)
UNITLESS_PROPERTIES = {
    "opacity", "z-index", "font-weight", "flex-grow", "flex-shrink",
    "order", "line-height",  # line-height es unitless O con unidad, manejo especial
    # AOS flags y datos no-numericos
    "aos-once", "aos-enable", "aos-anchor", "aos-easing", "aos-type",
    "aos-anchor-placement",
    # Grid counts y rules (numericos pero sin unidad)
    "grid-column-count", "grid-row-count",
    "grid-columns-auto-fit", "grid-match-height-of-tallest-child",
}

# Propiedades de color: aceptan var(), calc() y funciones complejas como valor nativo.
# Oxygen no rompe si el panel recibe un var(--token); lo muestra como string opaco.
# Esto reduce el ruido en custom-css cuando el sitio usa design tokens.
COLOR_PROPERTIES = {
    "color", "background-color",
    "border-top-color", "border-right-color", "border-bottom-color", "border-left-color",
    "button-text-color", "button-color", "button-hover_color",
    "overlay-color",
    "box-shadow-color", "text-shadow-color",
    "icon-color", "icon-background-color",
    "fill", "stroke",
}


# Clases internas que Oxygen inyecta en el HTML al renderizar sus componentes.
# Si el user pega HTML rendered de un site Oxygen, estas clases aparecen pero
# no deben emitirse al `classes:` array ni al CSS - Oxygen las re-inyecta al
# renderizar el bloque correspondiente. Catalogadas de oxygen.css del plugin.
_OXYGEN_INTERNAL_CLASSES = frozenset({
    # Section
    "ct-section-inner-wrap", "ct-section-with-shape-divider",
    # Columns (legacy)
    "ct-columns-inner-wrap", "ct-column",
    # Video
    "ct-video", "oxygen-vsb-responsive-video-wrapper",
    "oxygen-vsb-responsive-video-wrapper-custom",
    # Section video bg
    "oxy-video-container", "oxy-video-background", "oxy-video-overlay",
    # Header builder
    "oxy-header-wrapper", "oxy-header-row", "oxy-header-container",
    "oxy-header-left", "oxy-header-center", "oxy-header-right",
    "oxy-sticky-header-fade-in", "oxy-overlay-header",
    # Nav menu / Pro menu / Site Nav
    "oxy-nav-menu-list", "oxy-menu-toggle",
    # Social icons / soundcloud
    "oxy-social-icons", "oxy-soundcloud",
    # Icon box
    "oxy-icon-box", "oxy-icon-box-icon", "oxy-icon-box-content",
    "oxy-icon-box-text", "oxy-icon-box-heading",
    # Progress bar
    "oxy-progress-bar", "oxy-progress-bar-background",
    "oxy-progress-bar-progress-wrap", "oxy-progress-bar-progress",
    "oxy-progress-bar-overlay-text", "oxy-progress-bar-overlay-percent",
    # Tabs
    "oxy-tabs", "oxy-tabs-wrapper", "oxy-tab", "oxy-tab-content",
    "oxy-tabs-contents-content-hidden", "oxy-tabs-contents",
    # Superbox / Testimonial / Toggle
    "oxy-superbox", "oxy-superbox-wrap", "oxy-superbox-primary",
    "oxy-superbox-secondary", "oxy-testimonial", "oxy-toggle",
    # Gallery
    "oxy-gallery", "oxy-gallery-item", "oxy-gallery-item-sizer",
    "oxy-gallery-item-contents", "oxy-gallery-flex", "oxy-gallery-masonry",
    "oxy-gallery-grid",
    # Rendered ct-* classes (Oxygen las agrega al class= junto a las del user;
    # NO debemos re-emitirlas como clases propias del bloque)
    "ct-div-block", "ct-text-block", "ct-headline", "ct-image",
    "ct-code-block", "ct-fancy-icon", "ct-link", "ct-link-button",
    "ct-link-text", "ct-new-columns", "ct-span",
})

# Prefijos de clases internas (cualquier clase que arranque con esto se omite).
_OXYGEN_INTERNAL_CLASS_PREFIXES = (
    "oxy-nav-menu-hamburger-",
    "oxy-pricing-box",
    "oxy-pro-menu",
)

# Clases marker que el skill usa como opt-in para emitir bloques especificos
# (ct_section, ct_new_columns, ct_link_button, ct_code_block unwrap). Son
# semaforos para el skill, no estilan nada. Filtrarlas del classes: del output.
_SKILL_OPTIN_CLASSES = frozenset({
    "is-oxy-section",
    "is-oxy-columns",
    "is-oxy-button",
    "is-oxy-unwrap",
    "is-oxy-progress-bar",
})


def _filter_user_classes(classes: list) -> list:
    """Filtra del array de clases del user:
      - las que son internas de Oxygen (inyectadas por el render de bloques);
      - las marker is-oxy-* que el skill usa como opt-in (semaforos, no estilan).
    Preserva orden y duplicados de las clases legitimas del user."""
    if not classes:
        return []
    out = []
    for c in classes:
        if not isinstance(c, str):
            continue
        if c in _OXYGEN_INTERNAL_CLASSES:
            continue
        if c in _SKILL_OPTIN_CLASSES:
            continue
        if any(c.startswith(p) for p in _OXYGEN_INTERNAL_CLASS_PREFIXES):
            continue
        out.append(c)
    return out


# ============================================================
# UTILIDADES
# ============================================================

class Warnings:
    """Acumula avisos para mostrar al usuario al final."""
    def __init__(self):
        self.items: List[str] = []

    def add(self, msg: str):
        self.items.append(msg)

    def emit(self, file=sys.stderr):
        if not self.items:
            print("[OK] Sin avisos. Conversion limpia.", file=file)
            return
        print(f"\n[AVISOS] {len(self.items)} cosas a tener en cuenta:\n", file=file)
        for i, msg in enumerate(self.items, 1):
            print(f"  {i}. {msg}", file=file)


WARN = Warnings()


def fail(msg: str):
    """Aborta con un mensaje de error claro."""
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(1)


# ============================================================
# CSS PARSING
# ============================================================

def parse_css(css_text: str) -> Tuple[Dict[str, Dict], Dict[str, Dict[str, Dict]], List[Dict]]:
    """
    Parsea CSS y retorna tres estructuras:
    - default_rules: {clase: {prop: valor, "__states__": {state: {prop: valor}}}}
    - media_rules: {clase: {breakpoint: {prop: valor, "__states__": {state: {prop: valor}}}}}
    - codeblock_rules: lista de reglas que van al Code Block (selectores complejos)

    Los states (`hover`, `focus`, `before`, `nth-child(2)`, etc.) se guardan bajo
    la key especial `__states__` que el constructor del JSON va a leer y emitir
    como keys paralelas a `original` (formato nativo de Oxygen).
    """
    default_rules: Dict[str, Dict] = {}
    # default_state_rules[cls][state_name] = {prop: value}
    default_state_rules: Dict[str, Dict[str, Dict]] = {}
    media_rules: Dict[str, Dict[str, Dict]] = {}
    codeblock_rules: List[Dict] = []

    rules = tinycss2.parse_stylesheet(css_text, skip_whitespace=True, skip_comments=True)

    for rule in rules:
        if rule.type == "error":
            WARN.add(f"Error de parsing CSS: {rule.message}")
            continue

        if rule.type == "qualified-rule":
            # Regla normal (.foo { ... })
            _process_qualified_rule(rule, default_rules, default_state_rules, codeblock_rules, breakpoint=None)

        elif rule.type == "at-rule":
            if rule.lower_at_keyword == "media":
                # @media query
                bp_name = _parse_media_prelude(rule.prelude)
                if bp_name is None:
                    # Media query no reconocida -> al Code Block
                    codeblock_rules.append({
                        "type": "media_raw",
                        "prelude": tinycss2.serialize(rule.prelude),
                        "content": tinycss2.serialize(rule.content),
                    })
                    continue
                # Procesar reglas dentro del @media
                inner_rules = tinycss2.parse_stylesheet(
                    tinycss2.serialize(rule.content),
                    skip_whitespace=True, skip_comments=True
                )
                for inner in inner_rules:
                    if inner.type == "qualified-rule":
                        _process_qualified_rule(inner, default_rules, default_state_rules, codeblock_rules, breakpoint=bp_name, media_rules=media_rules)
            else:
                # @keyframes, @font-face, etc. -> Code Block
                codeblock_rules.append({
                    "type": "at_rule_raw",
                    "raw": tinycss2.serialize([rule]),
                })

    # Mover los states default al formato definitivo:
    # default_rules[cls]["__states__"] = {state_name: {prop: value}}
    # donde state_name puede ser "hover", "focus", "before", "nth-child(2)", etc.
    for cls, state_props in default_state_rules.items():
        if cls not in default_rules:
            default_rules[cls] = {}
        default_rules[cls]["__states__"] = state_props

    return default_rules, media_rules, codeblock_rules


def _parse_media_prelude(prelude) -> Optional[str]:
    """
    Parsea el prelude de un @media. Acepta solo (max-width: Npx).
    Retorna el nombre interno del breakpoint, o None si no se puede mapear.
    """
    text = tinycss2.serialize(prelude).strip()
    # Aceptar variantes: "(max-width: 992px)", "screen and (max-width: 992px)"
    # Rechazar min-width
    if "min-width" in text:
        WARN.add(f"Media query con min-width no soportada: '{text}'. Reescribe el CSS en mobile-last (max-width).")
        return None
    m = re.search(r"max-width\s*:\s*(\d+(?:\.\d+)?)\s*px", text)
    if not m:
        WARN.add(f"Media query no reconocida: '{text}'. Va al Code Block.")
        return None
    value = float(m.group(1))
    for bp_value, bp_name in BREAKPOINTS:
        if abs(value - bp_value) <= BREAKPOINT_TOLERANCE:
            return bp_name
    WARN.add(f"Breakpoint {value}px no coincide con ningun breakpoint conocido (1120/992/768/480). Va al Code Block.")
    return None


def _process_qualified_rule(rule, default_rules, default_state_rules, codeblock_rules, breakpoint=None, media_rules=None):
    """Procesa una regla qualified-rule y la enruta segun el selector."""
    selector_text = tinycss2.serialize(rule.prelude).strip()
    declarations = _parse_declarations(rule.content)

    # Determinar tipo de selector
    selectors = [s.strip() for s in selector_text.split(",")]
    for sel in selectors:
        target = _classify_selector(sel)
        if target is None:
            # Selector complejo -> Code Block
            codeblock_rules.append({
                "type": "rule",
                "selector": sel,
                "declarations": declarations,
                "breakpoint": breakpoint,
            })
            continue
        cls, state = target
        # Para `content` en before/after: quitar comillas externas porque el JSON
        # real de Oxygen las guarda sin comillas (Oxygen las agrega al renderizar).
        if state in ("before", "after") and "content" in declarations:
            declarations = dict(declarations)  # copia para no mutar
            declarations["content"] = _strip_content_quotes(declarations["content"])
        if breakpoint is None:
            # Default
            if state is None:
                if cls not in default_rules:
                    default_rules[cls] = {}
                default_rules[cls].update(declarations)
            else:
                if cls not in default_state_rules:
                    default_state_rules[cls] = {}
                if state not in default_state_rules[cls]:
                    default_state_rules[cls][state] = {}
                default_state_rules[cls][state].update(declarations)
        else:
            # Dentro de un media query
            if cls not in media_rules:
                media_rules[cls] = {}
            if breakpoint not in media_rules[cls]:
                media_rules[cls][breakpoint] = {}
            if state is None:
                media_rules[cls][breakpoint].update(declarations)
            else:
                if "__states__" not in media_rules[cls][breakpoint]:
                    media_rules[cls][breakpoint]["__states__"] = {}
                if state not in media_rules[cls][breakpoint]["__states__"]:
                    media_rules[cls][breakpoint]["__states__"][state] = {}
                media_rules[cls][breakpoint]["__states__"][state].update(declarations)


def _strip_content_quotes(value: str) -> str:
    """
    Quita comillas externas de un valor de `content` CSS para mapear al formato
    que usa Oxygen: `content: "X"` (CSS) -> `"content": "X"` (JSON Oxygen sin
    las comillas internas).
    Si el valor empieza Y termina con la misma comilla (simple o doble), las quita.
    En otro caso (ej. `content: attr(data-x)`, `content: counter(x)`) lo deja igual.
    """
    v = value.strip()
    if len(v) >= 2:
        if (v[0] == '"' and v[-1] == '"') or (v[0] == "'" and v[-1] == "'"):
            return v[1:-1]
    return v



# Lista de pseudo-clases sin argumento que Oxygen acepta como state nativo.
# Validado contra set_options/build_css en component.class.php:2548-2560:
# Oxygen acepta CUALQUIER sibling array de `original` como state y lo emite
# como `#selector:<key>{...}`. La lista de abajo son las que tienen sentido
# semantico estandar y han sido verificadas en el editor.
# Las que NO estan aqui (focus-visible, focus-within, placeholder, read-only,
# required, valid, invalid, etc.) NO se mapean para no producir regresiones
# silenciosas y van a Code Block.
NATIVE_SIMPLE_PSEUDO = {
    "hover", "focus", "active", "visited",
    "disabled", "checked",
    "first-child", "last-child",
}

# Pseudo-elementos que Oxygen acepta. Tanto `:before` como `::before` son
# sintacticamente validas en CSS y refieren al mismo concepto; ambas se
# mapean a la misma key sin los dos puntos.
# Set completo segun is_pseudo_element() en component-init.php:3878.
NATIVE_PSEUDO_ELEMENTS = {
    "before", "after",
    "first-letter", "first-line", "selection",
}

# Pseudo-clases con argumento entre parentesis que Oxygen acepta como state.
# La key Oxygen preserva el argumento literal (ej: "nth-child(2n+1)").
# Validado empiricamente para nth-child; nth-of-type y nth-last-child se
# incluyen por simetria estructural, pero quien las use deberia validarlas.
NATIVE_PARAM_PSEUDO = {
    "nth-child", "nth-of-type",
    "nth-last-child", "nth-last-of-type",
}


def _classify_selector(sel: str) -> Optional[Tuple[str, Optional[str]]]:
    """
    Clasifica un selector CSS. Retorna:
    - (clase, None) si es `.foo` (selector simple, va a `original`)
    - (clase, state_name) si es `.foo:hover`, `.foo::before`, `.foo:nth-child(2)`, etc.
      donde state_name es la key Oxygen ("hover", "before", "nth-child(2)", ...)
    - None si es complejo (combinadores, atributos, pseudos no soportadas) -> Code Block

    Acepta tanto `:before` como `::before` (ambas validas en CSS). Normaliza al
    formato Oxygen sin dos puntos.
    """
    sel = sel.strip()
    # tinycss2 a veces inserta /**/ para separar tokens (ej: nth-child(2n+1) ->
    # nth-child(2n/**/+1)). Limpiar esos comentarios spurios antes de matchear.
    sel = re.sub(r"/\*[^*]*\*+(?:[^/*][^*]*\*+)*/", "", sel).strip()

    # `.foo` (selector simple sin state)
    m = re.match(r"^\.([a-zA-Z_][a-zA-Z0-9_-]*)$", sel)
    if m:
        return (m.group(1), None)

    # `.foo:pseudo` o `.foo::pseudo` sin argumento
    # Permite uno o dos puntos antes del nombre del pseudo.
    m = re.match(r"^\.([a-zA-Z_][a-zA-Z0-9_-]*)::?([a-zA-Z-]+)$", sel)
    if m:
        cls, pseudo = m.group(1), m.group(2)
        if pseudo in NATIVE_SIMPLE_PSEUDO:
            return (cls, pseudo)
        if pseudo in NATIVE_PSEUDO_ELEMENTS:
            return (cls, pseudo)
        # Pseudo no validada -> Code Block
        return None

    # `.foo:nth-child(...)` y similares con argumento
    # El argumento puede ser un numero, expresion algebraica (2n+1) o keyword (odd, even).
    m = re.match(r"^\.([a-zA-Z_][a-zA-Z0-9_-]*):([a-zA-Z-]+)\(([^)]+)\)$", sel)
    if m:
        cls, pseudo, arg = m.group(1), m.group(2), m.group(3).strip()
        if pseudo in NATIVE_PARAM_PSEUDO:
            # Reconstruir la key Oxygen: "nth-child(2)", "nth-child(odd)", etc.
            return (cls, f"{pseudo}({arg})")
        # Pseudo con argumento no soportada (ej: :not(.x)) -> Code Block
        return None

    return None


def _parse_declarations(content_tokens) -> Dict[str, str]:
    """Parsea las declaraciones CSS dentro de un bloque {} y retorna {prop: valor}."""
    decls = OrderedDict()
    parsed = tinycss2.parse_declaration_list(content_tokens, skip_whitespace=True, skip_comments=True)
    for d in parsed:
        if d.type == "declaration":
            name = d.lower_name
            value = tinycss2.serialize(d.value).strip()
            decls[name] = value
        elif d.type == "error":
            WARN.add(f"Error en declaracion CSS: {d.message}")
    return decls


# ============================================================
# EXPANSION DE SHORTHANDS Y NORMALIZACION
# ============================================================

def expand_shorthands(props: Dict[str, str]) -> Dict[str, str]:
    """
    Expande shorthands CSS (padding, margin, border, border-radius, flex, flex-direction).
    Retorna un nuevo dict con shorthands expandidos.
    """
    # Detectar display ANTES de procesar gap, para saber si es flex o grid.
    # En flex/inline-flex, gap se emite directo. En grid, se descompone.
    display_val = props.get("display", "").strip().lower()
    is_grid = display_val == "grid"
    # Si no hay display, asumir flex (mas comun) para que gap quede como gap directo.
    # Si display llega a ser grid pero gap se proceso antes, hay riesgo. Lo aceptamos:
    # quien escribe grid pone display:grid PRIMERO en su CSS por convencion.

    out = OrderedDict()
    for prop, val in props.items():
        # __states__ es metadata interna (dict de states); se preserva al final, no se procesa aqui.
        if prop == "__states__":
            continue
        if prop in ("padding", "margin"):
            out.update(_expand_box(prop, val))
        elif prop == "border":
            out.update(_expand_border_all(val))
        elif prop == "border-radius":
            out.update(_expand_border_radius(val))
        elif prop in ("border-top", "border-right", "border-bottom", "border-left"):
            out.update(_expand_border_side(prop, val))
        elif prop == "flex":
            out.update(_expand_flex(val))
        elif prop == "flex-direction":
            # Manejar row-reverse / column-reverse
            v = val.strip().lower()
            if v == "row-reverse":
                out["flex-direction"] = "row"
                out["flex-reverse"] = "reverse"
            elif v == "column-reverse":
                out["flex-direction"] = "column"
                out["flex-reverse"] = "reverse"
            else:
                out["flex-direction"] = v
        elif prop == "gap":
            # gap puede ser "10px" o "10px 20px" (row col).
            # En flex (default), gap se preserva como gap. En grid, se descompone.
            # Usar _split_top_level para respetar funciones CSS (calc/var/clamp).
            parts = _split_top_level(val)
            if is_grid:
                if len(parts) == 1:
                    out["grid-row-gap"] = parts[0]
                    out["grid-column-gap"] = parts[0]
                elif len(parts) == 2:
                    out["grid-row-gap"] = parts[0]
                    out["grid-column-gap"] = parts[1]
            else:
                # En flex: si gap es uniforme, una sola propiedad. Si es row/col, dos.
                if len(parts) == 1:
                    out["gap"] = parts[0]
                elif len(parts) == 2:
                    # En flex tambien existen row-gap y column-gap separados.
                    out["row-gap"] = parts[0]
                    out["column-gap"] = parts[1]
        elif prop == "box-shadow":
            out.update(_expand_box_shadow(val))
        elif prop == "text-shadow":
            out.update(_expand_text_shadow(val))
        elif prop == "filter":
            out.update(_expand_filter(val))
        elif prop == "transform":
            out.update(_expand_transform(val))
        elif prop == "background":
            # Shorthand. Casos:
            # - color simple (#hex, rgb, rgba, hsl, transparent, palabra) -> background-color
            # - gradient, url, mezcla compleja -> custom-css (no expandir)
            v = val.strip()
            v_low = v.lower()
            is_simple_color = (
                v.startswith("#")
                or v_low.startswith("rgb(")
                or v_low.startswith("rgba(")
                or v_low.startswith("hsl(")
                or v_low.startswith("hsla(")
                or v_low.startswith("oklch(")
                or v_low.startswith("color-mix(")
                or v_low in ("transparent", "currentcolor", "inherit", "initial", "unset")
                or v_low.replace("-", "").isalpha()  # palabras como "red", "lightblue"
            )
            if is_simple_color:
                out["background-color"] = v
            else:
                # Gradient, url, o mezcla: dejar como background y que vaya a custom-css
                out[prop] = val
        else:
            out[prop] = val
    # Preservar __states__ (dict {state_name: {prop: value}})
    if "__states__" in props:
        out["__states__"] = props["__states__"]
    # Si hay display: flex sin flex-direction explicito, default a row
    # (Oxygen no asume row por default, necesita el valor explicito)
    if out.get("display") == "flex" and "flex-direction" not in out:
        out["flex-direction"] = "row"
    return out


def _split_top_level(val: str) -> List[str]:
    """
    Splittea un valor CSS por whitespace de nivel superior, respetando paréntesis
    balanceados. Funciones como calc(), var(), clamp(), rgb() quedan como UN solo token
    aunque contengan espacios o comas internas.

    Ejemplos:
      "10px 20px"                     -> ["10px", "20px"]
      "calc(10px + 1vw)"              -> ["calc(10px + 1vw)"]
      "var(--y) var(--x)"             -> ["var(--y)", "var(--x)"]
      "clamp(10px, 2vw, 20px) 16px"   -> ["clamp(10px, 2vw, 20px)", "16px"]
      "2px solid rgb(255, 0, 0)"      -> ["2px", "solid", "rgb(255, 0, 0)"]
    """
    tokens: List[str] = []
    buf = []
    depth = 0
    for ch in val:
        if ch == "(":
            depth += 1
            buf.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            buf.append(ch)
        elif ch.isspace() and depth == 0:
            if buf:
                tokens.append("".join(buf))
                buf = []
        else:
            buf.append(ch)
    if buf:
        tokens.append("".join(buf))
    return tokens


def _expand_box(prop: str, val: str) -> Dict[str, str]:
    """Expande padding/margin shorthand a top/right/bottom/left.

    Usa _split_top_level para respetar funciones CSS (calc, var, clamp) cuyo
    contenido puede tener espacios y comas internas.
    """
    parts = _split_top_level(val)
    if len(parts) == 1:
        return {f"{prop}-top": parts[0], f"{prop}-right": parts[0],
                f"{prop}-bottom": parts[0], f"{prop}-left": parts[0]}
    elif len(parts) == 2:
        return {f"{prop}-top": parts[0], f"{prop}-bottom": parts[0],
                f"{prop}-right": parts[1], f"{prop}-left": parts[1]}
    elif len(parts) == 3:
        return {f"{prop}-top": parts[0], f"{prop}-right": parts[1],
                f"{prop}-left": parts[1], f"{prop}-bottom": parts[2]}
    elif len(parts) == 4:
        return {f"{prop}-top": parts[0], f"{prop}-right": parts[1],
                f"{prop}-bottom": parts[2], f"{prop}-left": parts[3]}
    return {}


def _expand_border_all(val: str) -> Dict[str, str]:
    """Expande border shorthand a los 4 lados."""
    width, style, color = _parse_border_value(val)
    out = {}
    for side in ("top", "right", "bottom", "left"):
        if width: out[f"border-{side}-width"] = width
        if style: out[f"border-{side}-style"] = style
        if color: out[f"border-{side}-color"] = color
    return out


def _expand_border_side(prop: str, val: str) -> Dict[str, str]:
    """Expande border-{side} shorthand."""
    side = prop.split("-")[1]
    width, style, color = _parse_border_value(val)
    out = {}
    if width: out[f"border-{side}-width"] = width
    if style: out[f"border-{side}-style"] = style
    if color: out[f"border-{side}-color"] = color
    return out


def _parse_border_value(val: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Parsea 'Npx solid color' en (width, style, color).

    Estrategia: clasificar cada token por tipo en este orden:
      1. style: una de las keywords de border-style (solid, dashed, etc.)
      2. width: número (con o sin unidad) o keyword (thin/medium/thick)
      3. color: todo lo demás (hex, rgb()/rgba()/hsl()/hsla()/oklch(), var(),
         currentcolor, transparent, palabras como 'red', 'green', 'blue')

    Usa _split_top_level para que funciones como rgb(255,0,0) o var(--c) queden
    como un solo token.
    """
    parts = _split_top_level(val)
    width = style = color = None
    border_styles = {"none", "solid", "dashed", "dotted", "double", "groove",
                     "ridge", "inset", "outset", "hidden"}
    width_keywords = {"thin", "medium", "thick"}
    for p in parts:
        p_low = p.lower()
        if p_low in border_styles:
            style = p_low
        elif p_low in width_keywords or _is_border_width_numeric(p):
            width = p
        else:
            # Todo lo demás se asume color: hex, funciones de color, currentcolor,
            # transparent, var(--x), o palabras de color (red, green, blue, etc.)
            color = p
    return width, style, color


def _is_border_width_numeric(s: str) -> bool:
    """True si s parece un valor numérico de width: '2px', '0', '0.5em', '1rem', etc.
    Acepta números con o sin unidad. NO acepta funciones (calc, var) — esas se
    tratan como color en _parse_border_value por defecto, lo cual es incorrecto
    pero conservador: hoy no soportamos width via función CSS en shorthand border.
    """
    if not s:
        return False
    # Quitar unidad común para verificar que el prefijo es numérico
    import re as _re
    m = _re.match(r"^-?\d+(\.\d+)?", s)
    if not m:
        return False
    rest = s[m.end():]
    if rest == "":
        return True  # número puro, ej "0"
    return rest.lower() in ("px", "em", "rem", "pt", "%", "vw", "vh", "ex", "ch")


def _strip_px(val: str) -> str:
    """Quita el sufijo 'px' de un valor numerico.
    Oxygen agrega 'px' al renderizar los offset/blur/spread de box-shadow y
    text-shadow, asi que guardamos el numero pelado."""
    val = val.strip()
    if val.lower().endswith("px"):
        return val[:-2]
    return val


def _has_top_level_comma(val: str) -> bool:
    """True si val tiene una coma fuera de cualquier parentesis. Sirve para
    detectar valores multi-sombra de box-shadow/text-shadow sin confundirse con
    las comas de rgb()/rgba()/hsl()/var()."""
    depth = 0
    for ch in val:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            return True
    return False


def _length_in_px_or_zero(val: str) -> bool:
    """True si el valor es '0' puro o un numero seguido de 'px'. Estos son los
    unicos formatos validos para los offsets/blur/spread de Oxygen, que hardcodea
    'px' al renderizar (component.class.php:3335-3338)."""
    s = val.strip().lower()
    if s == "0":
        return True
    return bool(re.match(r"^-?\d+(\.\d+)?px$", s))


def _expand_box_shadow(val: str) -> Dict[str, str]:
    """Expande box-shadow shorthand a las keys broken-out que Oxygen entiende
    como nativas (box-shadow-color/-horizontal-offset/-vertical-offset/-blur/
    -spread/-inset). Asi quedan editables desde el panel Effects.

    Soporta una unica sombra con offsets en px (o '0'). Multiples sombras
    (separadas por coma fuera de parentesis) o unidades no-px caen a
    custom-css completo.

    Formato CSS: [inset] <h> <v> [blur] [spread] <color>
    El `inset` puede aparecer al principio o al final segun la spec; el
    parser acepta ambos.
    """
    if _has_top_level_comma(val):
        return {"__custom_css__box-shadow": val}

    parts = _split_top_level(val)
    if not parts:
        return {}

    out: Dict[str, str] = {}

    # Detectar 'inset' (case-insensitive) y separarlo
    lowered = [p.lower() for p in parts]
    if "inset" in lowered:
        out["box-shadow-inset"] = "inset"
        parts = [p for p, lo in zip(parts, lowered) if lo != "inset"]

    # Clasificar el resto en lengths (numericos) y color (lo demas)
    lengths: List[str] = []
    color: Optional[str] = None
    for p in parts:
        if _length_in_px_or_zero(p):
            lengths.append(p)
        else:
            color = p

    # Si alguna length usa unidad distinta a px (em/rem/etc), Oxygen no la
    # respetaria (hardcodea px al renderizar). Fallback a custom-css.
    rejected_lengths = [p for p in parts if p != color and p.lower() != "inset"
                        and not _length_in_px_or_zero(p)]
    if rejected_lengths:
        return {"__custom_css__box-shadow": val}

    if len(lengths) >= 1:
        out["box-shadow-horizontal-offset"] = _strip_px(lengths[0])
    if len(lengths) >= 2:
        out["box-shadow-vertical-offset"] = _strip_px(lengths[1])
    if len(lengths) >= 3:
        out["box-shadow-blur"] = _strip_px(lengths[2])
    if len(lengths) >= 4:
        out["box-shadow-spread"] = _strip_px(lengths[3])
    if color:
        out["box-shadow-color"] = color

    return out


# Map de funcion CSS de filter -> (key Oxygen sin el "filter-amount-" prefix, unit default).
# La key real en Oxygen es "filter-amount-<nombre>". El valor de la option `filter`
# es el nombre de la funcion (string). Verificado en controller.css.js:5383
# donde Oxygen renderiza con `value += "(" + options["filter-amount-" + value] + ")"`.
_FILTER_FN_INFO = {
    "blur":        ("blur",        "px"),
    "brightness":  ("brightness",  "%"),
    "contrast":    ("contrast",    "%"),
    "grayscale":   ("grayscale",   "%"),
    "hue-rotate":  ("hue-rotate",  "deg"),
    "invert":      ("invert",      "%"),
    "saturate":    ("saturate",    "%"),
    "sepia":       ("sepia",       "%"),
}


def _expand_filter(val: str) -> Dict[str, str]:
    """Expande filter: <fn>(<arg>) a las keys nativas de Oxygen:
      filter: "<fnname>"   (nombre de la funcion, sin parentesis)
      filter-amount-<fnname>: "<numero>"
      filter-amount-<fnname>-unit: "<unit>"   (si difiere del default)

    Oxygen solo soporta UNA funcion de filter por elemento (controller.css.js:5383
    ensambla `value += "(" + options["filter-amount-" + value] + ")"`). Para casos
    de multiples funciones, fallback a custom-css completo.

    Funciones soportadas: blur, brightness, contrast, grayscale, hue-rotate,
    invert, saturate, sepia. Cualquier otra (drop-shadow, opacity como filter)
    va a custom-css.

    Heuristica de unidad: si la funcion tiene default "%" y el valor CSS viene
    SIN unidad (ej. brightness(0.8) = multiplicador 0-1), Oxygen lo renderizaria
    como "0.8%" lo cual seria erroneo. Para evitar regresiones silenciosas, en
    ese caso fallback a custom-css.
    """
    matches = re.findall(r"([a-zA-Z-]+)\(([^)]*)\)", val)
    if not matches:
        return {"__custom_css__filter": val}
    # Solo una funcion soportada nativamente
    if len(matches) != 1:
        return {"__custom_css__filter": val}
    fn_name_raw, fn_arg = matches[0]
    fn_name = fn_name_raw.lower()
    if fn_name not in _FILTER_FN_INFO:
        return {"__custom_css__filter": val}
    canonical, default_unit = _FILTER_FN_INFO[fn_name]
    arg = fn_arg.strip()
    m = re.match(r"^(-?\d+(?:\.\d+)?)([a-zA-Z%]*)$", arg)
    if not m:
        return {"__custom_css__filter": val}
    num = m.group(1)
    unit = m.group(2) or None
    # Si el default es % pero el CSS no trae unidad, podria ser multiplicador.
    # Para no introducir regresiones silenciosas, fallback a custom-css.
    if default_unit == "%" and not unit:
        return {"__custom_css__filter": val}
    out: Dict[str, str] = {
        "filter": canonical,
        f"filter-amount-{canonical}": num,
    }
    if unit and unit != default_unit:
        out[f"filter-amount-{canonical}-unit"] = unit
    return out


_TRANSFORM_FN_RE = re.compile(r"([a-zA-Z0-9]+)\s*\(([^)]*)\)")


def _parse_length_with_unit(s: str, default_unit: str = "px") -> Optional[Tuple[str, str]]:
    """Parsea un valor numerico con unidad opcional. Retorna (num, unit) o None.
    Si no trae unidad, asume default_unit."""
    s = s.strip()
    m = re.match(r"^(-?\d+(?:\.\d+)?)([a-zA-Z%]*)$", s)
    if not m:
        return None
    return m.group(1), (m.group(2) or default_unit)


def _expand_transform(val: str) -> Dict[str, Any]:
    """Parsea transform: <fn>(<args>) ... y emite {transform: [step, ...]} donde
    cada step es un dict con transform-type + campos especificos. Oxygen ensambla
    el CSS final en getTransformCSS (component.class.php:4153).

    Soporta:
      translate(X[, Y]), translateX, translateY, translateZ, translate3d(X, Y, Z)
      rotate(Ndeg), rotateX, rotateY
      scale(X[, Y]), scaleX, scaleY, scaleZ, scale3d(X, Y, Z)
      skew(Xdeg[, Ydeg]), skewX, skewY
      perspective(Xunit)

    Funciones no soportadas (matrix, matrix3d, rotate3d con args sueltos, etc.)
    o parsing fallido -> fallback a custom-css completo via __custom_css__transform.
    """
    matches = _TRANSFORM_FN_RE.findall(val)
    if not matches:
        return {"__custom_css__transform": val}

    steps: List[Dict[str, str]] = []
    fallback = {"__custom_css__transform": val}

    for fn_raw, args_raw in matches:
        fn = fn_raw.strip()
        args = [a.strip() for a in args_raw.split(",") if a.strip()]

        if fn == "translate":
            if len(args) == 1:
                lu = _parse_length_with_unit(args[0])
                if not lu: return fallback
                num, unit = lu
                step = {"transform-type": "translate", "translateX": num}
                if unit != "px": step["translateX-unit"] = unit
                steps.append(step)
            elif len(args) == 2:
                lu1 = _parse_length_with_unit(args[0])
                lu2 = _parse_length_with_unit(args[1])
                if not (lu1 and lu2): return fallback
                step = {
                    "transform-type": "translate",
                    "translateX": lu1[0],
                    "translateY": lu2[0],
                }
                if lu1[1] != "px": step["translateX-unit"] = lu1[1]
                if lu2[1] != "px": step["translateY-unit"] = lu2[1]
                steps.append(step)
            else:
                return fallback

        elif fn == "translateX":
            if len(args) != 1: return fallback
            lu = _parse_length_with_unit(args[0])
            if not lu: return fallback
            step = {"transform-type": "translate", "translateX": lu[0]}
            if lu[1] != "px": step["translateX-unit"] = lu[1]
            steps.append(step)

        elif fn == "translateY":
            if len(args) != 1: return fallback
            lu = _parse_length_with_unit(args[0])
            if not lu: return fallback
            step = {"transform-type": "translate", "translateY": lu[0]}
            if lu[1] != "px": step["translateY-unit"] = lu[1]
            steps.append(step)

        elif fn == "translateZ":
            if len(args) != 1: return fallback
            lu = _parse_length_with_unit(args[0])
            if not lu: return fallback
            step = {"transform-type": "translate", "translateZ": lu[0]}
            if lu[1] != "px": step["translateZ-unit"] = lu[1]
            steps.append(step)

        elif fn == "translate3d":
            if len(args) != 3: return fallback
            parsed = [_parse_length_with_unit(a) for a in args]
            if not all(parsed): return fallback
            step = {
                "transform-type": "translate",
                "translateX": parsed[0][0],
                "translateY": parsed[1][0],
                "translateZ": parsed[2][0],
            }
            for axis, lu in zip(("X", "Y", "Z"), parsed):
                if lu[1] != "px": step[f"translate{axis}-unit"] = lu[1]
            steps.append(step)

        elif fn in ("rotate", "rotateX", "rotateY"):
            if len(args) != 1: return fallback
            # rotate solo acepta deg en Oxygen (hardcoded en getTransformCSS).
            m = re.match(r"^(-?\d+(?:\.\d+)?)(deg)?$", args[0])
            if not m: return fallback
            angle = m.group(1)
            field_map = {"rotate": "rotateAngle", "rotateX": "rotateXAngle", "rotateY": "rotateYAngle"}
            steps.append({"transform-type": fn, field_map[fn]: angle})

        elif fn == "scale":
            # scale(N) o scale(X, Y)
            if len(args) == 1:
                if not _is_number(args[0]): return fallback
                # scale(N) = scale(N, N) en CSS
                steps.append({"transform-type": "scale", "scaleX": args[0], "scaleY": args[0]})
            elif len(args) == 2:
                if not (_is_number(args[0]) and _is_number(args[1])): return fallback
                steps.append({"transform-type": "scale", "scaleX": args[0], "scaleY": args[1]})
            else:
                return fallback

        elif fn == "scaleX":
            if len(args) != 1 or not _is_number(args[0]): return fallback
            steps.append({"transform-type": "scale", "scaleX": args[0]})

        elif fn == "scaleY":
            if len(args) != 1 or not _is_number(args[0]): return fallback
            steps.append({"transform-type": "scale", "scaleY": args[0]})

        elif fn == "scaleZ":
            if len(args) != 1 or not _is_number(args[0]): return fallback
            steps.append({"transform-type": "scale", "scaleZ": args[0]})

        elif fn == "scale3d":
            if len(args) != 3 or not all(_is_number(a) for a in args): return fallback
            steps.append({"transform-type": "scale", "scaleX": args[0], "scaleY": args[1], "scaleZ": args[2]})

        elif fn == "skew":
            if len(args) == 1:
                m = re.match(r"^(-?\d+(?:\.\d+)?)(deg)?$", args[0])
                if not m: return fallback
                steps.append({"transform-type": "skew", "skewX": m.group(1)})
            elif len(args) == 2:
                m1 = re.match(r"^(-?\d+(?:\.\d+)?)(deg)?$", args[0])
                m2 = re.match(r"^(-?\d+(?:\.\d+)?)(deg)?$", args[1])
                if not (m1 and m2): return fallback
                steps.append({"transform-type": "skew", "skewX": m1.group(1), "skewY": m2.group(1)})
            else:
                return fallback

        elif fn == "skewX":
            if len(args) != 1: return fallback
            m = re.match(r"^(-?\d+(?:\.\d+)?)(deg)?$", args[0])
            if not m: return fallback
            steps.append({"transform-type": "skew", "skewX": m.group(1)})

        elif fn == "skewY":
            if len(args) != 1: return fallback
            m = re.match(r"^(-?\d+(?:\.\d+)?)(deg)?$", args[0])
            if not m: return fallback
            steps.append({"transform-type": "skew", "skewY": m.group(1)})

        elif fn == "perspective":
            if len(args) != 1: return fallback
            lu = _parse_length_with_unit(args[0])
            if not lu: return fallback
            step = {"transform-type": "perspective", "perspective": lu[0]}
            if lu[1] != "px": step["perspective-unit"] = lu[1]
            steps.append(step)

        else:
            # matrix, matrix3d, rotate3d con args sueltos, etc.
            return fallback

    if not steps:
        return fallback
    return {"transform": steps}


def _expand_text_shadow(val: str) -> Dict[str, str]:
    """Expande text-shadow shorthand a las keys broken-out de Oxygen.
    Estructura paralela a box-shadow pero sin `inset` ni `spread`.
    Formato CSS: <h> <v> [blur] <color>
    """
    if _has_top_level_comma(val):
        return {"__custom_css__text-shadow": val}

    parts = _split_top_level(val)
    if not parts:
        return {}

    lengths: List[str] = []
    color: Optional[str] = None
    for p in parts:
        if _length_in_px_or_zero(p):
            lengths.append(p)
        else:
            color = p

    rejected = [p for p in parts if p != color and not _length_in_px_or_zero(p)]
    if rejected:
        return {"__custom_css__text-shadow": val}

    out: Dict[str, str] = {}
    if len(lengths) >= 1:
        out["text-shadow-horizontal-offset"] = _strip_px(lengths[0])
    if len(lengths) >= 2:
        out["text-shadow-vertical-offset"] = _strip_px(lengths[1])
    if len(lengths) >= 3:
        out["text-shadow-blur"] = _strip_px(lengths[2])
    if color:
        out["text-shadow-color"] = color

    return out


def _expand_border_radius(val: str) -> Dict[str, str]:
    """Expande border-radius a las 4 esquinas. Maneja la sintaxis con / si aparece (la rechaza al Code Block en realidad).

    Usa _split_top_level para respetar funciones CSS (calc, var, clamp) con espacios internos.
    """
    if "/" in val:
        # Sintaxis elipse: no soportada nativo
        WARN.add(f"border-radius con sintaxis '/' (elipse) no soportada nativamente: '{val}'. Va a custom-css.")
        return {"__custom_css__border-radius": val}
    parts = _split_top_level(val)
    if len(parts) == 1:
        return {"border-top-left-radius": parts[0], "border-top-right-radius": parts[0],
                "border-bottom-left-radius": parts[0], "border-bottom-right-radius": parts[0]}
    elif len(parts) == 2:
        return {"border-top-left-radius": parts[0], "border-bottom-right-radius": parts[0],
                "border-top-right-radius": parts[1], "border-bottom-left-radius": parts[1]}
    elif len(parts) == 3:
        return {"border-top-left-radius": parts[0],
                "border-top-right-radius": parts[1], "border-bottom-left-radius": parts[1],
                "border-bottom-right-radius": parts[2]}
    elif len(parts) == 4:
        return {"border-top-left-radius": parts[0], "border-top-right-radius": parts[1],
                "border-bottom-right-radius": parts[2], "border-bottom-left-radius": parts[3]}
    return {}


def _expand_flex(val: str) -> Dict[str, str]:
    """Expande flex shorthand. flex-basis se descarta."""
    parts = val.split()
    out = {}
    if len(parts) == 1:
        # 'flex: 1' -> grow=1, shrink=1
        if parts[0].isdigit() or _is_number(parts[0]):
            out["flex-grow"] = parts[0]
            out["flex-shrink"] = "1"
        else:
            WARN.add(f"flex shorthand con valor no numerico '{val}' va a custom-css.")
            out["__custom_css__flex"] = val
    elif len(parts) == 2:
        out["flex-grow"] = parts[0]
        out["flex-shrink"] = parts[1]
    elif len(parts) == 3:
        out["flex-grow"] = parts[0]
        out["flex-shrink"] = parts[1]
        # flex-basis (parts[2]) se descarta y avisa
        if parts[2] != "0" and parts[2] != "auto":
            WARN.add(f"flex-basis '{parts[2]}' no soportado nativamente; se manda a custom-css.")
            out["__custom_css__flex-basis"] = parts[2]
    return out


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


# ============================================================
# CONVERSION DE PROPIEDADES A FORMATO OXYGEN
# ============================================================

def convert_properties(props: Dict[str, str], block_type: Optional[str] = None) -> Tuple[Dict[str, str], List[str]]:
    """
    Convierte propiedades CSS al formato Oxygen.
    Retorna (oxygen_props, custom_css_decls) donde custom_css_decls es lista de strings "prop: val;"
    """
    oxygen = OrderedDict()
    custom_css: List[str] = []

    for prop, val in props.items():
        if prop == "__states__":
            continue
        if prop.startswith("__custom_css__"):
            real_prop = prop.replace("__custom_css__", "")
            custom_css.append(f"{real_prop}: {val};")
            continue

        # v3.11: background-image con gradient -> custom-css. Oxygen skipea
        # background-image en su pipeline normal (controller.css.js:5437)
        # porque lo maneja via getBackgroundLayersCSS que solo soporta URL,
        # no gradients (linear/radial/conic). Sin este redirect, gradients
        # quedan invisibles. Tradeoff: panel Background no muestra el gradient
        # editable, pero el render visual funciona.
        if prop == "background-image" and isinstance(val, str):
            v_low = val.strip().lower()
            if any(g in v_low for g in (
                "linear-gradient(", "radial-gradient(", "conic-gradient(",
                "repeating-linear-gradient(", "repeating-radial-gradient(",
                "repeating-conic-gradient(",
            )):
                custom_css.append(f"background-image: {val};")
                continue

        # Caso especial: transform es array de step-objects (no string).
        # Lo emitimos como nativo directo (Oxygen lo lee en getTransformCSS).
        if prop == "transform" and isinstance(val, list):
            oxygen["transform"] = val
            continue

        # Caso especial: grid-template-columns -> propiedades nativas de Oxygen
        # Soporta tres patrones (los demas van a custom-css):
        #   repeat(N, 1fr)              -> grid-column-count: N
        #   1fr 1fr 1fr ...             -> grid-column-count: N
        #   repeat(auto-fit, minmax(Xpx, 1fr))  -> grid-columns-auto-fit + grid-column-min-width
        if prop == "grid-template-columns":
            mapped = _grid_template_to_oxygen(val)
            if mapped is not None:
                for k, v in mapped.items():
                    oxygen[k] = v
                continue
            # No mapea nativo: a custom-css
            custom_css.append(f"{prop}: {val};")
            continue

        # Excepcion para botones: color -> button-text-color
        effective_prop = prop
        if block_type == "ct_link_button" and prop == "color":
            effective_prop = "button-text-color"

        # Workaround margin: Oxygen aplica `.ct-div-block { margin: 0 !important }` con
        # prioridad CSS. Cualquier margin-* en un ct_div_block (numerico O auto)
        # es sobrescrito a 0 a menos que el override use !important.
        # v3.10: extender a `margin-X: auto` que tambien necesita !important para
        # que el centrado de containers (margin: 0 auto) funcione.
        if block_type == "ct_div_block" and prop in {"margin-top", "margin-right", "margin-bottom", "margin-left"}:
            v_clean = val.strip().lower()
            if v_clean == "auto":
                # margin-X: auto via custom-css con !important.
                custom_css.append(f"{prop}: auto !important;")
                continue
            # Numericos: misma idea, asegurar unidad px si no viene.
            num, unit = _split_value_unit(val)
            if num is not None:
                unit_str = unit or "px"
                custom_css.append(f"{prop}: {num}{unit_str} !important;")
            else:
                custom_css.append(f"{prop}: {val} !important;")
            continue

        # Decidir si es nativo o va a custom-css
        if not _is_property_native(effective_prop, val):
            custom_css.append(f"{prop}: {val};")
            continue

        # Decidir si tiene unidad y como
        emit_pairs = _convert_value_with_unit(effective_prop, val)
        for k, v in emit_pairs:
            oxygen[k] = v

    return dict(oxygen), custom_css


def _is_property_native(prop: str, val: str) -> bool:
    """
    Decide si una propiedad+valor pueden ir nativos a Oxygen.

    Regla general: si el valor contiene una funcion CSS (calc/clamp/min/max/var/env)
    el panel numerico de Oxygen no la puede editar, asi que mejor mandarla a
    custom-css. EXCEPCION: propiedades de color y la propiedad `transition-property`
    (que acepta strings arbitrarios) toleran var() y similares como valor nativo;
    Oxygen las trata como string opaco en el panel y las renderiza tal cual.
    """
    if prop not in NATIVE_PROPERTIES:
        return False
    has_fn = any(fn in val for fn in ("calc(", "clamp(", "min(", "max(", "var(", "env("))
    if not has_fn:
        return True
    # Colores con var() / color-mix() / etc.: Oxygen los preserva como string nativo.
    if prop in COLOR_PROPERTIES:
        return True
    # transition-property acepta string arbitrario (incluyendo nombres de var
    # personalizadas si el usuario las usa).
    if prop == "transition-property":
        return True
    return False


def _grid_template_to_oxygen(val: str) -> Optional[Dict[str, str]]:
    """
    Mapea `grid-template-columns` a las keys nativas de Oxygen cuando es posible.
    Retorna un dict de overrides o None si el valor no mapea.

    Patrones reconocidos:
      - repeat(N, 1fr)                    -> {grid-column-count: "N"}
      - "1fr 1fr ... 1fr"                 -> {grid-column-count: "<len>"}
      - repeat(auto-fit, minmax(Xu, 1fr)) -> {grid-columns-auto-fit: "1",
                                              grid-column-min-width: "X",
                                              grid-column-min-width-unit: "u" if u!=px}
      - repeat(auto-fill, ...)            -> mismo que auto-fit
    """
    val = val.strip()

    # repeat(N, 1fr)
    m = re.match(r"^repeat\(\s*(\d+)\s*,\s*1fr\s*\)$", val)
    if m:
        return {"grid-column-count": m.group(1)}

    # "1fr 1fr 1fr"
    parts = val.split()
    if parts and all(p == "1fr" for p in parts):
        return {"grid-column-count": str(len(parts))}

    # repeat(auto-fit|auto-fill, minmax(Xu, ANY))
    # Soporta cualquier unidad valida en X y descarta el segundo argumento de minmax
    # (que tipicamente es 1fr y Oxygen lo asume por default).
    m = re.match(
        r"^repeat\(\s*(auto-fit|auto-fill)\s*,\s*minmax\(\s*(-?\d+(?:\.\d+)?)([a-zA-Z%]*)\s*,\s*[^)]+\)\s*\)$",
        val,
    )
    if m:
        min_num = m.group(2)
        min_unit = m.group(3) or "px"
        out: Dict[str, str] = {
            "grid-columns-auto-fit": "1",
            "grid-column-min-width": min_num,
        }
        if min_unit != "px":
            out["grid-column-min-width-unit"] = min_unit
        return out

    return None


def _convert_value_with_unit(prop: str, val: str) -> List[Tuple[str, str]]:
    """
    Convierte un valor CSS al formato Oxygen (valor + opcional clave -unit).
    Retorna lista de (clave, valor) para emitir.
    """
    val = val.strip()

    # line-height especial
    if prop == "line-height":
        if _is_number(val):
            # unitless
            return [(prop, val)]
        # con unidad
        num, unit = _split_value_unit(val)
        if num is not None and unit:
            if unit == "px":
                return [(prop, num)]
            return [(prop, num), (f"{prop}-unit", unit)]
        return [(prop, val)]

    # Propiedades unitless
    if prop in UNITLESS_PROPERTIES and prop != "line-height":
        return [(prop, val)]

    # Valores keyword (como "auto", "none", "row", "center", "flex-end", etc.)
    if not _looks_numeric(val):
        # Si es "auto" en una prop con unit, emitir AMBOS: value + unit.
        # v3.9: antes solo emitiamos `<prop>-unit: "auto"` sin value, lo que
        # causaba que Oxygen no emitiera la propiedad al CSS final (su flow
        # de build_css concatena value + unit; sin value, queda incompleto).
        # Tanto value como unit deben ser "auto" para que Oxygen genere
        # `<prop>: auto;` al renderizar.
        if val.lower() == "auto" and prop in {"margin-top", "margin-right", "margin-bottom", "margin-left",
                                                "width", "height", "max-width", "max-height", "min-width", "min-height"}:
            return [(prop, "auto"), (f"{prop}-unit", "auto")]
        # Si es un keyword normal, emitir como string
        return [(prop, val)]

    # Valores numericos con o sin unidad
    num, unit = _split_value_unit(val)
    if num is None:
        return [(prop, val)]

    # Decidir si emitir unit
    if prop in ALWAYS_EMIT_UNIT:
        unit_to_emit = unit or "px"
        return [(prop, num), (f"{prop}-unit", unit_to_emit)]

    # Default: emitir unit solo si NO es px
    if unit and unit != "px":
        return [(prop, num), (f"{prop}-unit", unit)]
    return [(prop, num)]


def _looks_numeric(val: str) -> bool:
    """True si el valor empieza con un numero (puede tener unidad)."""
    val = val.strip()
    if not val:
        return False
    # Hex color no es numerico
    if val.startswith("#"):
        return False
    return bool(re.match(r"^-?\d", val))


def _split_value_unit(val: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Separa '15px' -> ('15', 'px'), '1.5em' -> ('1.5', 'em'), '50%' -> ('50', '%').
    Retorna (None, None) si no parsea.
    """
    val = val.strip()
    m = re.match(r"^(-?\d+(?:\.\d+)?)([a-zA-Z%]*)$", val)
    if m:
        num = m.group(1)
        unit = m.group(2) or None
        return num, unit
    return None, None


# ============================================================
# CONSTRUCCION DEL ARBOL DE COMPONENTES
# ============================================================

class IdAllocator:
    def __init__(self, start=2):
        self.next_id = start
    def alloc(self) -> int:
        i = self.next_id
        self.next_id += 1
        return i


def html_to_component_tree(html: str, ids: IdAllocator) -> Dict:
    """
    Parsea HTML y construye el arbol de componentes Oxygen.
    Asume que el HTML tiene exactamente UN nodo raiz visible.
    """
    soup = BeautifulSoup(html, "html.parser")
    # Encontrar el primer Tag (ignorar text nodes / espacios)
    root = None
    for child in soup.children:
        if isinstance(child, Tag):
            root = child
            break
    if root is None:
        fail("HTML no contiene ningun elemento. Verifica el input.")
    # Verificar que solo haya un elemento raiz
    siblings = [c for c in soup.children if isinstance(c, Tag)]
    if len(siblings) > 1:
        WARN.add(f"HTML tiene {len(siblings)} elementos raiz. Se usara el primero. Considera envolverlos en un <div>.")

    return _build_component(root, ids, parent_ct_id=ROOT_CT_PARENT, depth=2)


# Mapeo data-aos-* del HTML -> key Oxygen en options.original.
# El atributo `data-aos` (sin sufijo) mapea a `aos-type`. Los demas son 1-a-1
# quitando el prefijo `data-`. Todos los valores se pasan como string.
_DATA_AOS_KEY_MAP = {
    "data-aos":                  "aos-type",
    "data-aos-duration":         "aos-duration",
    "data-aos-easing":           "aos-easing",
    "data-aos-offset":           "aos-offset",
    "data-aos-delay":            "aos-delay",
    "data-aos-anchor":           "aos-anchor",
    "data-aos-anchor-placement": "aos-anchor-placement",
    "data-aos-once":             "aos-once",
}


def _extract_aos_options(tag: Tag) -> Dict[str, str]:
    """Extrae los atributos data-aos-* del tag y los devuelve como dict con las
    keys nativas de Oxygen (aos-type, aos-duration, etc.). Las keys que devuelva
    deben sumarse a options.original; las correspondientes data-aos-* deben
    excluirse de custom-attributes para evitar duplicacion."""
    if not hasattr(tag, "attrs"):
        return {}
    out: Dict[str, str] = OrderedDict()
    for raw_name, value in tag.attrs.items():
        lookup = raw_name.lower()
        if lookup not in _DATA_AOS_KEY_MAP:
            continue
        if isinstance(value, list):
            value = " ".join(str(v) for v in value)
        elif value is None:
            value = ""
        else:
            value = str(value)
        out[_DATA_AOS_KEY_MAP[lookup]] = value
    return out


def _extract_custom_attributes(tag: Tag) -> List[Dict[str, str]]:
    """
    Extrae atributos HTML del tag que el skill NO maneja explicitamente en otro lado,
    para emitir como original.custom-attributes (array de {name, value}).

    Lista negra (atributos manejados en otro lado y que NO deben pasar como custom-attributes):
      - class, id          : estructurales del HTML
      - href, target       : <a>
      - src, alt, srcset,
        width, height,
        loading             : <img>
      - xlink:href          : <svg><use>
      - data-aos*           : mapeados a las keys aos-* nativas en _extract_aos_options
    Cualquier otro atributo (aria-*, data-* generales, role, tabindex, title, lang,
    dir, name, value, type, for, placeholder, autocomplete, required, disabled,
    hidden, etc.) se preserva.
    """
    HANDLED_ATTRS = {
        "class", "id",
        "href", "target",
        "src", "alt", "srcset", "width", "height", "loading",
        "xlink:href",
        "style",  # consumido por _parse_inline_style y mergeado en original
    }
    out: List[Dict[str, str]] = []
    if not hasattr(tag, "attrs"):
        return out
    for name, value in tag.attrs.items():
        lower_name = name.lower()
        if lower_name in HANDLED_ATTRS:
            continue
        if lower_name in _DATA_AOS_KEY_MAP:
            # Ya consumido como aos-* nativo; no duplicar.
            continue
        # value puede ser str o list (ej. class siempre es list; pero ya excluimos class)
        # Para otros atributos multi-valor (raros), unir con espacio.
        if isinstance(value, list):
            value = " ".join(str(v) for v in value)
        elif value is None:
            value = ""
        else:
            value = str(value)
        out.append({"name": str(name), "value": value})
    return out


def _parse_inline_style(style_value: str) -> Dict[str, str]:
    """Parsea un atributo style="prop: val; prop: val" y devuelve dict de
    propiedades. Usa tinycss2 para tokenizar (respeta funciones CSS con
    parentesis y comas internas como calc(), rgb(), var())."""
    if not style_value or not style_value.strip():
        return {}
    decls = tinycss2.parse_declaration_list(
        style_value, skip_whitespace=True, skip_comments=True
    )
    out: Dict[str, str] = OrderedDict()
    for d in decls:
        if d.type == "declaration":
            out[d.lower_name] = tinycss2.serialize(d.value).strip()
        elif d.type == "error":
            WARN.add(f"Error en style inline: {d.message}")
    return out


def _build_component(tag: Tag, ids: IdAllocator, parent_ct_id: int, depth: int) -> Dict:
    """Construye un dict de componente para un tag HTML."""
    ct_id = ids.alloc()
    block_type, original = _resolve_block_type(tag)

    # Fix 4: extraer atributos HTML que el skill no maneja explicitamente.
    # Lista negra: atributos manejados por _resolve_block_type o por logica posterior.
    # Todo lo demas se preserva en original.custom-attributes como array de {name,value}.
    #
    # Excepción: si el bloque resultante es ct_code_block con code-php que contiene
    # el HTML literal del tag (Rutas B/C de iconos, button funcional), los atributos
    # ya viajan dentro del code-php y NO deben duplicarse en custom-attributes.
    is_codeblock_with_html_literal = (
        block_type == "ct_code_block"
        and isinstance(original, dict)
        and "code-php" in original
    )
    # oxy-shape-divider y oxy_progress_bar renderizan su propia estructura
    # interna; los atributos del HTML original (data-percent, etc.) o ya se
    # consumieron como options o no aplican al render.
    is_oxy_self_rendered = block_type in ("oxy-shape-divider", "oxy_progress_bar")
    if not is_codeblock_with_html_literal and not is_oxy_self_rendered:
        # Mapear data-aos-* del HTML a las keys aos-* nativas de Oxygen.
        # El user las edita desde el panel "Effects > Animation on Scroll".
        aos_opts = _extract_aos_options(tag)
        if aos_opts:
            if not isinstance(original, dict):
                original = OrderedDict()
            original.update(aos_opts)

        # v3.2: parsear style="..." inline y mergear al options.original del
        # bloque (no a las clases - eso contaminaria otros bloques que las usen).
        # El inline tiene prioridad sobre lo que ya estaba en original.
        inline_style = tag.get("style", "") if hasattr(tag, "get") else ""
        if inline_style:
            inline_props = _parse_inline_style(str(inline_style))
            if inline_props:
                expanded = expand_shorthands(inline_props)
                expanded.pop("__states__", None)
                inline_oxygen, inline_css_decls = convert_properties(expanded, block_type)
                if inline_oxygen or inline_css_decls:
                    if not isinstance(original, dict):
                        original = OrderedDict()
                    for k, v in inline_oxygen.items():
                        original[k] = v
                    if inline_css_decls:
                        existing = original.get("custom-css", "")
                        new_css = " ".join(inline_css_decls)
                        original["custom-css"] = (
                            (existing + " " + new_css).strip() if existing else new_css
                        )

        custom_attrs = _extract_custom_attributes(tag)
        if custom_attrs:
            # Asegurar que original es dict para poder agregarle la key
            if not isinstance(original, dict):
                original = OrderedDict()
            original["custom-attributes"] = custom_attrs

    options: Dict[str, Any] = OrderedDict()
    options["ct_id"] = ct_id
    options["ct_parent"] = parent_ct_id
    options["selector"] = f"{SELECTOR_BASE.get(block_type, block_type)}-{ct_id}-{SELECTOR_SUFFIX}"
    options["original"] = original
    options["nicename"] = f"{NICENAME_BASE.get(block_type, block_type)} (#{ct_id})"

    # ct_content para tipos que llevan texto
    if block_type in ("ct_headline", "ct_text_block", "ct_link_button", "ct_link_text"):
        text = _extract_text(tag)
        if text:
            options["ct_content"] = text
    elif block_type == "oxy_rich_text":
        # Serializar el contenido inline (texto + tags inline) como HTML
        # Si el oxy_rich_text usa useCustomTag (tag distinto de <p>), no envolver
        # en <p> porque el useCustomTag ya provee el wrapper externo (<li>, <h2>, etc).
        # Oxygen acepta contenido inline crudo en ese caso.
        wrap_in_p = not (isinstance(original, dict) and original.get("useCustomTag") == "true")
        rich_html = _serialize_inline_to_rich_text(tag, wrap_in_p=wrap_in_p)
        if rich_html:
            options["ct_content"] = rich_html

    # classes
    # v3.4: filtrar clases internas inyectadas por Oxygen (ct-section-inner-wrap,
    # ct-fancy-icon, oxy-progress-bar-*, etc.) que aparecen cuando el user pega
    # HTML rendered de un site Oxygen. Si las dejamos pasan al `classes` array y
    # quedan duplicadas cuando Oxygen las re-inyecta al renderizar el bloque.
    raw_classes = tag.get("class", []) or []
    classes = _filter_user_classes(raw_classes)
    if classes:
        options["classes"] = list(classes)
        options["activeselector"] = classes[-1]
    else:
        options["activeselector"] = False

    component: Dict[str, Any] = OrderedDict()
    component["id"] = ct_id
    component["name"] = block_type
    component["options"] = options
    component["depth"] = depth

    # Hijos: solo para tipos contenedores
    if block_type in ("ct_div_block", "ct_link", "ct_section", "ct_new_columns"):
        children: List[Dict] = []
        # Caso especial: div con SOLO contenido inline (texto plano o texto+tags inline).
        # Inyectar un ct_text_block o oxy_rich_text que capture ese contenido.
        # Esto resuelve <div class="X">texto</div> que antes perdia el texto.
        injected = _maybe_inject_text_child(tag, ids, ct_id, depth + 1)
        if injected is not None:
            children.append(injected)
        else:
            # Procesar hijos: tags estructurales + text nodes sueltos.
            # Esto resuelve <a><svg></svg> Texto</a>: el "Texto" se vuelve un
            # ct_text_block hermano del icono, en vez de perderse.
            # Los Comment (subclase de NavigableString) se ignoran para que
            # <!-- ... --> no genere ct_text_block ruido.
            for child in tag.children:
                if isinstance(child, Comment):
                    continue
                if isinstance(child, Tag):
                    children.append(_build_component(child, ids, parent_ct_id=ct_id, depth=depth + 1))
                elif isinstance(child, NavigableString):
                    text = str(child).strip()
                    if text:
                        children.append(_build_loose_text_child(text, ids, ct_id, depth + 1))
        if children:
            component["children"] = children

        # Auto-anadir flex si el link tiene icono + texto (postura A confirmada por el usuario).
        # Detecta el patron icono+texto y modifica las clases del link para que se alineen.
        if block_type == "ct_link":
            _maybe_add_flex_for_icon_text_link(tag, options, classes)

    return component


def _build_loose_text_child(text: str, ids: "IdAllocator", parent_ct_id: int, depth: int) -> Dict:
    """Construye un ct_text_block sin clase con el texto suelto recibido."""
    ct_id = ids.alloc()
    options: Dict[str, Any] = OrderedDict()
    options["ct_id"] = ct_id
    options["ct_parent"] = parent_ct_id
    options["selector"] = f"text_block-{ct_id}-{SELECTOR_SUFFIX}"
    options["original"] = {}
    options["nicename"] = f"Text (#{ct_id})"
    options["ct_content"] = text
    options["activeselector"] = False
    return OrderedDict([
        ("id", ct_id),
        ("name", "ct_text_block"),
        ("options", options),
        ("depth", depth),
    ])


def _maybe_add_flex_for_icon_text_link(tag: Tag, options: Dict, classes: List[str]) -> None:
    """
    Detecta si el <a> tiene patron icono (svg/i) + texto (text node suelto).
    Si lo hay, marca el bloque con __needs_auto_flex__=True. La resolucion real
    se hace en apply_auto_flex_to_links() despues de parsear el CSS, para poder
    consultar las default_rules de cada clase y decidir si inyectar o no.

    Decision arquitectonica (v3.1): el auto-flex se aplica al options.original
    del BLOQUE (#selector), no a las clases (.clase). Asi:
      - solo este link especifico recibe flex,
      - clases reusables como .btn no quedan contaminadas con flex+row+gap,
      - el user mantiene control total de las clases para otros contextos.
    """
    if not classes and not tag.get("class"):
        # Sin clases tampoco aplicamos: el bloque no es identificable de forma
        # estable y no hay nada que el user pueda editar facilmente.
        return
    has_icon = False
    has_text = False
    for child in tag.children:
        if isinstance(child, Tag):
            cname = child.name.lower()
            if cname == "svg" or cname == "i":
                has_icon = True
        elif isinstance(child, NavigableString):
            if str(child).strip():
                has_text = True
    if has_icon and has_text:
        options["__needs_auto_flex__"] = True


def _maybe_inject_text_child(tag: Tag, ids: "IdAllocator", parent_ct_id: int, depth: int) -> Optional[Dict]:
    """
    Si el tag contiene SOLO texto plano o texto + tags inline (sin block-level ni svg/i),
    retorna un componente hijo (ct_text_block u oxy_rich_text) que capture ese contenido.
    Si el tag tiene hijos no-inline, retorna None para que el flujo normal procese hijos.

    v3.6: si alguno de los hijos inline tiene `class=`, NO aplanar a rich text.
    Esas clases suelen tener CSS de layout (width/height/background/display) que se
    rompe cuando los spans quedan dentro de <p> en lugar de ser hijos directos del
    flex container padre. En ese caso retornamos None para que cada hijo se procese
    como bloque editable independiente.
    """
    # Clasificar hijos
    has_text = False
    has_inline_tag = False
    has_other_tag = False
    has_classed_inline = False  # v3.6
    for child in tag.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            if str(child).strip():
                has_text = True
        elif isinstance(child, Tag):
            child_name = child.name.lower()
            if child_name in _INLINE_TAGS:
                # v3.6: tag inline con class propia -> tratar como bloque editable.
                # No aplica a <a> que ya tiene su propia logica especial (abajo).
                if child_name != "a" and child.get("class"):
                    has_classed_inline = True
                # Excepciones para <a>:
                # - <a> con hijos Tag (estructural, ej. <a><svg>...</svg></a>)
                # - <a> con clase (intencionalmente estilable, ej. <a class="nav__link">)
                if child_name == "a":
                    has_a_children = any(isinstance(gc, Tag) for gc in child.children)
                    has_a_class = bool(child.get("class"))
                    if has_a_children or has_a_class:
                        has_other_tag = True
                    else:
                        has_inline_tag = True
                else:
                    has_inline_tag = True
            else:
                has_other_tag = True
    # Si hay tags no-inline (div, svg, ul, etc), no inyectar.
    if has_other_tag:
        return None
    # v3.6: si hay hijos inline con clases propias, no aplanar a rich text.
    # Cada hijo se vuelve un bloque editable individual (preserva layouts flex).
    if has_classed_inline:
        return None
    # Si no hay texto en absoluto, no hay nada que inyectar.
    if not has_text and not has_inline_tag:
        return None
    # Caso A: solo texto plano -> ct_text_block
    if has_text and not has_inline_tag:
        text = tag.get_text(strip=True)
        if not text:
            return None
        ct_id = ids.alloc()
        options: Dict[str, Any] = OrderedDict()
        options["ct_id"] = ct_id
        options["ct_parent"] = parent_ct_id
        options["selector"] = f"text_block-{ct_id}-{SELECTOR_SUFFIX}"
        options["original"] = {}
        options["nicename"] = f"Text (#{ct_id})"
        options["ct_content"] = text
        options["activeselector"] = False
        return OrderedDict([
            ("id", ct_id),
            ("name", "ct_text_block"),
            ("options", options),
            ("depth", depth),
        ])
    # Caso B: texto + tags inline (o solo tags inline con texto) -> oxy_rich_text
    rich_html = _serialize_inline_to_rich_text(tag)
    if not rich_html:
        return None
    ct_id = ids.alloc()
    options = OrderedDict()
    options["ct_id"] = ct_id
    options["ct_parent"] = parent_ct_id
    options["selector"] = f"_rich_text-{ct_id}-{SELECTOR_SUFFIX}"
    options["original"] = {}
    options["nicename"] = f"Rich Text (#{ct_id})"
    options["ct_content"] = rich_html
    options["activeselector"] = False
    return OrderedDict([
        ("id", ct_id),
        ("name", "oxy_rich_text"),
        ("options", options),
        ("depth", depth),
    ])


def _parse_google_maps_iframe(src: str) -> Dict[str, str]:
    """Parsea el src de un iframe de Google Maps Embed v1 y devuelve los options
    de oxy_map. Formato esperado:
      https://www.google.com/maps/embed/v1/place?key=KEY&q=ADDRESS&zoom=N
    Falla silenciosa: si no hay match, devuelve dict vacio. El user puede llenar
    los campos desde el panel."""
    from urllib.parse import urlparse, parse_qs, unquote_plus
    out: Dict[str, str] = OrderedDict()
    try:
        parsed = urlparse(src)
        qs = parse_qs(parsed.query)
    except Exception:
        return out
    if "q" in qs and qs["q"]:
        out["map_address"] = unquote_plus(qs["q"][0])
    if "zoom" in qs and qs["zoom"]:
        out["map_zoom"] = qs["zoom"][0]
    # height/width del iframe se podrian capturar, pero quedan en custom-attributes
    # via flow normal.
    return out


# ============================================================
# CATALOGO DE SHAPE-DIVIDERS BUILT-IN DE OXYGEN
# ============================================================

# Hashes md5 del atributo `d` del primer <path> de cada shape-divider built-in
# de Oxygen Builder 4.x (extraido de components/classes/shape-divider.class.php).
# Permite detectar SVGs que matcheen exactamente y emitirlos como oxy-shape-divider
# nativo en lugar de SVG inline en code_block. Si el path normalizado matchea,
# se emite el bloque oxy-* y queda editable desde el panel "Shape Divider".
# Tres shapes built-in (Shark 1/2/3) usan estructuras sin <path>, no se detectan
# y caen a Ruta C (code_block con SVG inline) como antes.
_OXY_SHAPE_DIVIDER_HASHES = {
    'a7fb3946f59925015486f749ec01b041': 'Angle 1',
    '2497d26957518b02d8df5227017f2898': 'Angle 2',
    '4cf223f28a49fcac005b0cb250609612': 'Angle 3',
    'f36ff2b01f059ca715d659a5350a7876': 'Balance 1',
    'b05ded68f281ce46042d03752567cd6a': 'Balance 2',
    '119cf2d18cdff4bfacbcd3f04ef9ef90': 'Balance 3',
    '2d5344accb67c3763ff047b8f6fb8864': 'Cave 1',
    '444faddb7c9cf0b9c7e18ec6b9e26ac7': 'Cave 2',
    '758e94c979b695a4f9db4a8f75ed8836': 'Cave 3',
    '183cd44c3221fdd090acd2c8a047607b': 'Curvy 1',
    'd3308d8e0f52137a6d6aa684d4cd20ae': 'Curvy 2',
    'a3608d80d448d86d77ca82030e790c56': 'Curvy 3',
    'bd39130b5aa00848f1f79403df6f18f6': 'Diamond 1',
    'ab8e98d90a9b4404bb5a2887e662ab2b': 'Diamond 2',
    'bc6f0dba0ebe44eeef58ba92da93b504': 'Diamond 3',
    '05041b410642fea3b1c58e2f9f4276d7': 'Logs 1',
    'b96f55caa8cee733cfa5d480faf24a35': 'Logs 2',
    '51d9fd903ff1d3c3d9f041f23fb4348a': 'Logs 3',
    '455689050f51bfe32b4d07c8fa1c4645': 'Ocean 1',
    '0e96637245493c1dcc56c31de8a3b692': 'Ocean 2',
    '4eabdecc94f0478519be10b6d0de5dc5': 'Ocean 3',
    '76de472d233e13278af69c8221581aef': 'Towers 1',
    '041e397d0d2228ed574e1dd099ae868f': 'Towers 2',
    '8c17615b02044c98c63876c215378110': 'Towers 3',
    'a8756cc76d44f032d08b16e2bcc8de48': 'Valley 1',
    '49107d30647e76f7d74150e9f591b06b': 'Valley 2',
    '4f9aa1c466d13643de1459e9057b1cec': 'Valley 3',
    'bc2feb12ee42ca6ded69ae3575292936': 'Wavy 1',
    '797ee925cd3bdc033de1100e5fb5d62a': 'Wavy 2',
    '9cbcfcfc28e02464cb7c6b15a930a3a4': 'Wavy 3',
}


def _detect_shape_divider(svg_tag: Tag) -> Optional[str]:
    """Si el <svg> matchea EXACTAMENTE un shape-divider built-in de Oxygen,
    retorna su nombre canonico (ej. 'Wavy 1'). Retorna None si no matchea.

    Matching:
    - El <svg> debe tener viewBox="0 0 1440 320" (canonical Oxygen).
    - Debe tener al menos un <path d="...">.
    - El primer path normalizado (whitespace collapsed) debe matchear el hash md5
      de algun shape del catalogo built-in.

    Falsos positivos: cero (md5 de path completo). Falsos negativos: posibles si
    el SVG fue re-serializado con cambios sutiles (separadores, decimales). En
    caso de no-match cae a Ruta C (code_block) como antes.
    """
    if svg_tag.name.lower() != "svg":
        return None
    viewbox = svg_tag.get("viewBox") or svg_tag.get("viewbox") or ""
    if str(viewbox).strip() != "0 0 1440 320":
        return None
    path_tag = svg_tag.find("path")
    if path_tag is None:
        return None
    d = path_tag.get("d", "")
    if not d:
        return None
    d_norm = re.sub(r"\s+", " ", str(d)).strip()
    digest = hashlib.md5(d_norm.encode("utf-8")).hexdigest()
    return _OXY_SHAPE_DIVIDER_HASHES.get(digest)


# ============================================================
# DETECCION DE ICONOS (Rutas A, B, C)
# ============================================================

# Patron de clases FontAwesome que disparan Ruta B
_FA_CLASS_PATTERN = re.compile(
    r"^(fa|fas|fab|far|fal|fad|fat|fa-solid|fa-regular|fa-light|fa-thin|fa-duotone|fa-sharp|fa-brands)$"
)


def _detect_fancy_icon_use(tag: Tag) -> Optional[str]:
    """
    Ruta A: detecta <svg><use xlink:href="#XXX"></use></svg>.
    Retorna el icon-id (sin '#') si el patron matchea, None si no.
    """
    if tag.name.lower() != "svg":
        return None
    # Hijos no-whitespace
    children = [c for c in tag.children if isinstance(c, Tag)]
    if len(children) != 1:
        return None
    use = children[0]
    if use.name.lower() != "use":
        return None
    # xlink:href tiene varias formas en BeautifulSoup
    href = use.get("xlink:href") or use.get("href")
    if not href or not isinstance(href, str):
        return None
    if not href.startswith("#"):
        return None
    return href[1:]  # quitar el '#'


def _detect_fa_icon_class(tag: Tag) -> Optional[str]:
    """
    Ruta B: detecta <i class="fa-... fa-..."></i>.
    Retorna las clases originales como string si el tag es FA, None si no.
    """
    if tag.name.lower() != "i":
        return None
    classes = tag.get("class", [])
    if not classes:
        return None
    # Al menos una clase debe matchear el patron FA
    has_fa = any(_FA_CLASS_PATTERN.match(c) for c in classes)
    has_fa_named = any(c.startswith("fa-") and not _FA_CLASS_PATTERN.match(c) for c in classes)
    # Necesita al menos una clase de set (fa, fas, fab, etc o fa-solid, fa-brands, etc)
    # Y tipicamente tambien una clase de nombre (fa-whatsapp, fa-paw, etc)
    if has_fa and has_fa_named:
        return " ".join(classes)
    return None


def _serialize_svg_for_codeblock(svg_tag: Tag) -> str:
    """
    Convierte un <svg> de BeautifulSoup a string HTML preservando atributos y contenido.
    Usado en Ruta C cuando el SVG no es un patron de icono reconocido.
    """
    return str(svg_tag)


# Tags inline que pueden vivir dentro de un oxy_rich_text sin promover a otro bloque
_INLINE_TAGS = {
    "em", "strong", "b", "i", "small", "mark", "u", "s",
    "span", "br", "sub", "sup", "abbr", "cite", "code", "kbd",
    "a",  # los <a> dentro de un texto largo se preservan como inline
}

# Tags block-level que NO deben envolverse en <p> al serializar a rich text
_BLOCK_TAGS = {
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "div", "ul", "ol", "li", "blockquote", "pre",
    "section", "article", "header", "footer", "aside", "nav", "main",
    "table", "thead", "tbody", "tr", "td", "th",
}


def _has_text_content(tag: Tag) -> bool:
    """True si el tag contiene algun text node no-vacio (directo o en descendientes)."""
    text = tag.get_text(strip=True)
    return bool(text)


def _is_empty_tag(tag: Tag) -> bool:
    """True si el tag no tiene ni texto ni hijos Tag (solo whitespace o nada).
    v3.7: tags vacios decorativos deben emitirse como ct_div_block en lugar de
    ct_text_block. Oxygen renderiza un placeholder de texto ("Click to edit"/
    similar) en ct_text_block sin ct_content, lo que descuadra layouts donde
    el tag se usa como decoracion (ej. <span class="brand-mark" aria-hidden>
    como cuadradito de color)."""
    if _has_text_content(tag):
        return False
    if any(isinstance(c, Tag) for c in tag.children):
        return False
    return True


def _has_inline_children_with_text(tag: Tag) -> bool:
    """
    True si el tag tiene hijos Tag inline mezclados con texto, o solo hijos inline con texto.
    Usado para decidir si emitir oxy_rich_text en vez de aplanar.
    """
    has_text_node = False
    has_inline_tag = False
    for child in tag.children:
        if isinstance(child, NavigableString):
            if str(child).strip():
                has_text_node = True
        elif isinstance(child, Tag):
            if child.name.lower() in _INLINE_TAGS:
                has_inline_tag = True
            else:
                # Hay un hijo no-inline (block o desconocido). Este caso NO es rich text simple.
                return False
    # Caso 1: texto + tag inline mezclado.
    # Caso 2: solo tag inline con texto.
    return (has_text_node and has_inline_tag) or (has_inline_tag and _has_text_content(tag))


def _serialize_inline_to_rich_text(tag: Tag, wrap_in_p: bool = True) -> str:
    """
    Toma un tag y serializa su contenido (texto + hijos inline) a HTML para ct_content.
    Si wrap_in_p=True (default) y no hay un block-level adentro, envuelve todo en <p>.
    Si wrap_in_p=False, retorna el contenido inline crudo (usado cuando el bloque
    tiene useCustomTag y el wrapper externo ya es semantico, ej. <li>).
    Si hay block-level (improbable en este flujo), preserva sin wrapper.
    """
    # Recolectar contenido interno como string
    inner = "".join(str(c) for c in tag.children).strip()
    if not inner:
        return ""
    # Detectar si ya hay un block-level adentro
    has_block = False
    for child in tag.children:
        if isinstance(child, Tag) and child.name.lower() in _BLOCK_TAGS:
            has_block = True
            break
    if has_block:
        return inner
    if not wrap_in_p:
        return inner
    return f"<p>{inner}</p>"


def _resolve_block_type(tag: Tag) -> Tuple[str, Any]:
    """
    Determina el tipo de bloque Oxygen para un tag HTML, y construye su `options.original`.
    Retorna (block_type, original).
    """
    name = tag.name.lower()

    # v3.4: opt-in `is-oxy-unwrap` -> ct_code_block con unwrap:true y HTML
    # literal del tag en code-php. Util cuando el user quiere preservar markup
    # arbitrario (scripts, web components, custom widgets) sin que Oxygen agregue
    # un wrapper externo. La clase se filtra del classes: array por _SKILL_OPTIN_CLASSES.
    classes_for_optin = tag.get("class", []) or []
    if any(str(c).lower() == "is-oxy-unwrap" for c in classes_for_optin):
        return ("ct_code_block", {"code-php": str(tag), "unwrap": "true"})

    # Ruta A: <svg><use xlink:href="#XXX"></use></svg> -> ct_fancy_icon
    if name == "svg":
        icon_id = _detect_fancy_icon_use(tag)
        if icon_id is not None:
            return ("ct_fancy_icon", {"icon-id": icon_id})
        # v3.3: detectar shape-divider built-in (Wavy, Angle, Cave, etc.)
        # antes de caer a Ruta C. Si matchea el catalogo, lo emite como
        # oxy-shape-divider nativo (editable desde el panel).
        # Las options de Elements API (oxy-*) van prefijadas con el tag.
        shape_name = _detect_shape_divider(tag)
        if shape_name is not None:
            WARN.add(
                f"SVG detectado como shape-divider built-in '{shape_name}', "
                "emitido como oxy-shape-divider nativo. Debe vivir dentro de un "
                "ct_section para que Oxygen agregue la clase ct-section-with-shape-divider."
            )
            return ("oxy-shape-divider", {
                "oxy-shape-divider_svg_shape": shape_name,
            })
        # Ruta C: SVG inline crudo -> ct_code_block
        svg_str = _serialize_svg_for_codeblock(tag)
        WARN.add(
            "SVG inline emitido como ct_code_block. "
            "Considera reemplazar manualmente por icono nativo en Oxygen para editabilidad."
        )
        return ("ct_code_block", {"code-php": svg_str, "unwrap": "true"})

    # Ruta B: <i class="fa-..."></i> -> ct_code_block con FA
    if name == "i":
        fa_classes = _detect_fa_icon_class(tag)
        if fa_classes is not None:
            return (
                "ct_code_block",
                {"code-php": f'<i class="{fa_classes}"></i>', "unwrap": "true"},
            )

    # <a>: depende del contenido y de las clases
    # v3.1: heuristica button mas conservadora. La version previa convertia
    # cualquier <a class="...btn..."> en ct_link_button, lo que era frecuente y
    # sorprendia al user (ct_link_button no acepta hijos y aplica estilos de
    # boton de Oxygen que tapaban los del user). Ahora ct_link_button solo se
    # emite si la clase contiene el opt-in explicito 'is-oxy-button'. Para todo
    # lo demas, <a> con solo texto -> ct_link_text, <a> con hijos -> ct_link.
    if name == "a":
        classes = tag.get("class", [])
        is_button = any(c.lower() == "is-oxy-button" for c in classes)
        has_tag_children = any(isinstance(c, Tag) for c in tag.children)
        url = tag.get("href", "")
        target = tag.get("target", "")
        if is_button and not has_tag_children:
            return ("ct_link_button", _strip_empty({"url": url, "target": target}))
        if has_tag_children:
            original = _strip_empty({"url": url, "target": target})
            return ("ct_link", original if original else {})
        # Solo texto
        original = _strip_empty({"url": url, "target": target})
        return ("ct_link_text", original if original else {})

    # <button>: trío de mapeos según contenido, paralelo a <li>.
    # Decisión clave (validada empíricamente vía JSONs pegados en Oxygen):
    # un <button> HTML siempre debe renderizar como <button> HTML, no como <a>.
    # Por eso NO se usa ct_link_button (que renderiza <a>). Se usa el mismo
    # mecanismo useCustomTag que ya funciona para <li> y otros tags semánticos.
    #
    # Beneficio: todos los atributos del button (type, onclick, aria-*, data-*,
    # name, value, formaction, etc.) viajan automáticamente como custom-attributes
    # editables desde el panel "Advanced > Custom Attributes" de Oxygen.
    if name == "button":
        # v3.7: button vacio -> ct_div_block (button decorativo o controlado por JS).
        if _is_empty_tag(tag):
            return ("ct_div_block", {"useCustomTag": "true", "tag": "button"})
        inline_tags_for_button = {"em", "strong", "span", "small", "br", "i", "b", "u", "code"}
        # Hijos estructurales: cualquier tag que no sea inline puro
        structural_children = [
            c for c in tag.children
            if hasattr(c, "name") and c.name and c.name not in inline_tags_for_button
        ]
        if structural_children:
            # Caso 3: <button> con hijos estructurales (svg, div, span con bloque, etc.)
            return ("ct_div_block", {"useCustomTag": "true", "tag": "button"})
        # Caso 2: HTML inline mixto (texto + tags inline)
        if _has_inline_children_with_text(tag):
            return ("oxy_rich_text", {"useCustomTag": "true", "tag": "button"})
        # Caso 2b: solo tags inline sin text node suelto
        non_text_children = [c for c in tag.children if hasattr(c, "name") and c.name]
        if non_text_children and all(c.name in inline_tags_for_button for c in non_text_children):
            return ("oxy_rich_text", {"useCustomTag": "true", "tag": "button"})
        # Caso 1: texto plano puro
        return ("ct_text_block", {"useCustomTag": "true", "tag": "button"})

    # <img>: ct_image
    # Emitimos como image_type="1" (URL-based) en vez de image_type="2" (Media Library)
    # porque Oxygen, con image_type=2 + attachment_id=0, intenta renderizar el src
    # de placeholder ('src' vacio) y la imagen no aparece. Con image_type=1 + src + alt
    # la imagen renderiza inmediatamente; el usuario puede reasignar a media library
    # luego desde el panel si quiere.
    if name == "img":
        src = tag.get("src", "")
        alt = tag.get("alt", "")
        original: Dict[str, Any] = OrderedDict()
        original["image_type"] = "1"
        original["src"] = src
        if alt:
            original["alt"] = alt
        # width/height de los atributos HTML se preservan como hint visual de Oxygen.
        # Oxygen igual los usa para calcular aspect ratio si la imagen no carga.
        if tag.get("width"):
            try:
                original["attachment_width"] = int(tag.get("width"))
            except ValueError:
                pass
        if tag.get("height"):
            try:
                original["attachment_height"] = int(tag.get("height"))
            except ValueError:
                pass
        WARN.add(
            f"<img src=\"{src}\"> emitido como image_type=1 (URL). "
            f"Renderiza inmediatamente. Si queres asignar a la media library de WordPress, "
            f"reasignalo desde el panel de Oxygen tras pegar."
        )
        return ("ct_image", original)

    # Tags de tipo div con tag custom
    if name in ("section", "article", "header", "footer", "aside", "nav", "main"):
        # v3.3: <section class="is-oxy-section"> -> ct_section nativo.
        # Habilita section-width, container-padding-*, video_background del
        # panel nativo de Oxygen. Sin la clase opt-in, sigue siendo ct_div_block
        # con tag=section (default seguro). Oxygen envuelve los children en
        # .ct-section-inner-wrap automaticamente al renderizar.
        if name == "section":
            classes = tag.get("class", []) or []
            if any(c.lower() == "is-oxy-section" for c in classes):
                return ("ct_section", {})
        return ("ct_div_block", {"tag": name})

    # h1-h6
    if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        # Si tiene HTML inline mixto (em, span, br, etc) -> oxy_rich_text
        if _has_inline_children_with_text(tag):
            return ("oxy_rich_text", {})
        if name == "h1":
            return ("ct_headline", {})
        return ("ct_headline", {"tag": name})

    # p
    if name == "p":
        # Si tiene HTML inline mixto -> oxy_rich_text
        if _has_inline_children_with_text(tag):
            return ("oxy_rich_text", {})
        return ("ct_text_block", {})

    # span y otros tags inline
    # v3.6: aplicar trio (estructural -> div, inline mixto -> rich text, texto -> text)
    # cuando el span contiene un SVG o img como hijo (caso comun: <span class="icon"><svg/></span>),
    # ct_text_block ignora hijos y el SVG se pierde. ct_div_block los preserva.
    # v3.7: tags vacios decorativos -> ct_div_block (no ct_text_block, que muestra placeholder).
    if name in ("span", "em", "strong", "small", "b", "u", "mark"):
        if _is_empty_tag(tag):
            return ("ct_div_block", {"useCustomTag": "true", "tag": name})
        inline_set_for_span = {"em", "strong", "span", "small", "br", "i", "b", "u", "code", "a", "mark"}
        structural_children = [
            c for c in tag.children
            if hasattr(c, "name") and c.name and c.name not in inline_set_for_span
        ]
        if structural_children:
            return ("ct_div_block", {"useCustomTag": "true", "tag": name})
        if _has_inline_children_with_text(tag):
            return ("oxy_rich_text", {"useCustomTag": "true", "tag": name})
        # Texto plano puro
        return ("ct_text_block", {"useCustomTag": "true", "tag": name})

    # ul / ol -> ct_div_block con useCustomTag
    if name in ("ul", "ol"):
        return ("ct_div_block", {"useCustomTag": "true", "tag": name})

    # li -> tres mapeos segun contenido (validado empiricamente)
    if name == "li":
        # v3.7: li vacio -> ct_div_block (evita placeholder de Oxygen en ct_text_block vacio).
        if _is_empty_tag(tag):
            return ("ct_div_block", {"useCustomTag": "true", "tag": "li"})
        # Caso 1: li con tags estructurales hijos (div, ul, h1, etc) -> ct_div_block[li]
        # Caso 2: li con HTML inline mixto (em, strong, a, br, etc) -> oxy_rich_text[li]
        # Caso 3: li con texto plano puro -> ct_text_block[li]
        # <a> se considera inline porque es semanticamente inline (vive dentro de p, li).
        # Esto permite que <li><a>text</a></li> sea editable como rich text inline.
        inline_tags_for_li = {"em", "strong", "span", "small", "br", "i", "b", "u", "code", "a"}
        structural_children = [
            c for c in tag.children
            if hasattr(c, "name") and c.name and c.name not in inline_tags_for_li
        ]
        if structural_children:
            return ("ct_div_block", {"useCustomTag": "true", "tag": "li"})
        # Caso 2: HTML inline mixto (incluye <a>)
        if _has_inline_children_with_text(tag):
            return ("oxy_rich_text", {"useCustomTag": "true", "tag": "li"})
        # Caso 2b: solo un <a> con texto (no llega al detector porque no hay texto suelto)
        # Detectar manualmente
        non_text_children = [c for c in tag.children if hasattr(c, "name") and c.name]
        if non_text_children and all(c.name in inline_tags_for_li for c in non_text_children):
            return ("oxy_rich_text", {"useCustomTag": "true", "tag": "li"})
        # Caso 3: texto plano
        return ("ct_text_block", {"useCustomTag": "true", "tag": "li"})

    # div (default)
    if name == "div":
        classes = tag.get("class", []) or []
        classes_lower = [str(c).lower() for c in classes]
        # v3.3: <div class="is-oxy-columns"> -> ct_new_columns nativo.
        if "is-oxy-columns" in classes_lower:
            return ("ct_new_columns", {})
        # v3.4: <div class="is-oxy-progress-bar" data-percent="50"> -> oxy_progress_bar.
        # Estructura HTML interna se descarta - Oxygen la regenera. El user
        # configura textos left/right desde el panel.
        if "is-oxy-progress-bar" in classes_lower:
            orig: Dict[str, Any] = OrderedDict()
            percent = tag.get("data-percent", "")
            if percent:
                orig["progress_percent"] = str(percent)
            return ("oxy_progress_bar", orig)
        return ("ct_div_block", {})

    # ============================================================
    # v3.4: <iframe> -> ct_video (YouTube/Vimeo) | oxy_map (Google Maps) | fallback code_block
    # ============================================================
    if name == "iframe":
        src = tag.get("src", "") or ""
        src_lower = src.lower()
        # YouTube/Vimeo -> ct_video
        if any(d in src_lower for d in ("youtube.com", "youtu.be", "vimeo.com", "player.vimeo.com")):
            original: Dict[str, Any] = OrderedDict()
            original["src"] = src
            original["embed_src"] = src
            # Aspect ratio: default 16:9. Si el iframe tiene width/height numericos,
            # podriamos calcularlo, pero seria sobre-ingenieria. 56.25% cubre el caso
            # mas comun y el user puede cambiarlo desde el panel.
            original["video-padding-bottom"] = "56.25%"
            original["use-custom"] = "0"
            return ("ct_video", original)
        # Google Maps -> oxy_map
        if "google.com/maps/embed" in src_lower:
            return ("oxy_map", _parse_google_maps_iframe(src))
        # Otros iframes (formularios embebidos, twitter, etc.) -> code_block con HTML literal.
        # Pierde editabilidad pero conserva render. WARN al user.
        WARN.add(
            f"<iframe src=\"{src[:80]}{'...' if len(src) > 80 else ''}\"> emitido como ct_code_block. "
            "Si es video o mapa, vuelve a pegar usando un patron reconocible "
            "(URL de YouTube/Vimeo o Google Maps embed)."
        )
        return ("ct_code_block", {"code-php": str(tag), "unwrap": "true"})

    # ============================================================
    # v3.2: tags HTML adicionales mapeados con useCustomTag
    # ============================================================

    # Tags estructurales (contenedores puros): siempre ct_div_block.
    # Cubre tablas (sin <td>/<th>/<caption>/<legend>/<figcaption> que usan trio),
    # forms (sin <label>), y otros block-level que aceptan hijos arbitrarios.
    PURE_CONTAINER_TAGS = {
        "table", "thead", "tbody", "tfoot", "tr", "colgroup",
        "form", "fieldset", "select",
        "blockquote", "pre",
        # v3.5: figure es contenedor (lleva img + figcaption), dl es definition list
        "figure", "picture", "dl",
    }
    if name in PURE_CONTAINER_TAGS:
        return ("ct_div_block", {"useCustomTag": "true", "tag": name})

    # Tags VOID (sin contenido). Oxygen igual los emite con useCustomTag pero los
    # hijos quedan vacios. Los atributos del tag (type, name, value, placeholder,
    # required, etc.) viajan como custom-attributes editables.
    VOID_TAGS = {"input", "hr", "col", "br"}
    if name in VOID_TAGS:
        if name == "br":
            # <br> dentro de inline mixto se preserva en el HTML del oxy_rich_text
            # padre. Como nodo independiente es raro pero igual lo soportamos.
            WARN.add(f"<br> como nodo independiente es poco comun; se emite como ct_div_block vacio con tag=br.")
        return ("ct_div_block", {"useCustomTag": "true", "tag": name})

    # Tags con trio (estructural -> div, inline mixto -> rich text, texto -> text):
    # paralelo al manejo de <li> y <button>. Conserva la semantica del tag externo
    # y elige el bloque interno segun el contenido real.
    TRIO_TAGS = {
        "td", "th", "caption",       # tabla: celdas y caption
        "label", "legend",           # forms: labels
        "figcaption", "summary",     # otros: caption/summary
        "option", "code",            # inline texto (option en select, code standalone)
        "textarea",                  # textarea acepta texto pero no HTML inline
        # v3.5: tags inline-texto comunes en blogs/articulos
        "time",                      # <time datetime="..."> con texto plano
        "address",                   # contacto
        "dt", "dd",                  # definition list items
        "cite", "q", "ins", "del", "abbr",  # texto inline semantico
        "var", "kbd", "samp",        # texto inline tecnico
    }
    if name in TRIO_TAGS:
        # v3.7: trio tag vacio -> ct_div_block (evita placeholder de Oxygen).
        if _is_empty_tag(tag):
            return ("ct_div_block", {"useCustomTag": "true", "tag": name})
        inline_set = {"em", "strong", "span", "small", "br", "i", "b", "u", "code", "a"}
        structural_children = [
            c for c in tag.children
            if hasattr(c, "name") and c.name and c.name not in inline_set
        ]
        if structural_children:
            return ("ct_div_block", {"useCustomTag": "true", "tag": name})
        if _has_inline_children_with_text(tag):
            return ("oxy_rich_text", {"useCustomTag": "true", "tag": name})
        non_text_children = [c for c in tag.children if hasattr(c, "name") and c.name]
        if non_text_children and all(c.name in inline_set for c in non_text_children):
            return ("oxy_rich_text", {"useCustomTag": "true", "tag": name})
        return ("ct_text_block", {"useCustomTag": "true", "tag": name})

    # Tag desconocido
    WARN.add(f"Tag <{name}> no mapeado a un tipo de bloque conocido. Tratado como ct_div_block. Verifica el resultado.")
    return ("ct_div_block", {})


def _extract_text(tag: Tag) -> str:
    """Extrae el texto de un tag para ct_content."""
    return tag.get_text(strip=True)


def _strip_empty(d: Dict) -> Dict:
    """Remueve claves con valor vacio o None."""
    return {k: v for k, v in d.items() if v not in (None, "")}


# ============================================================
# CONSTRUCCION DEL BLOQUE classes TOP-LEVEL
# ============================================================

def build_classes_block(default_rules: Dict, media_rules: Dict, used_classes: List[str], class_to_block_type: Dict[str, str], class_to_tag: Optional[Dict[str, str]] = None) -> Dict:
    """
    Construye el objeto top-level `classes` del JSON de Oxygen.
    used_classes: lista de clases que efectivamente se usan en el HTML (evita emitir clases huerfanas).
    class_to_block_type: mapeo clase -> tipo de bloque (para excepciones como button-text-color).
    class_to_tag: mapeo clase -> tag custom (para emitir en original como vimos en el JSON real).
    """
    classes_obj: Dict[str, Any] = OrderedDict()
    class_to_tag = class_to_tag or {}

    # Combinar todas las clases vistas
    all_classes = set(default_rules.keys()) | set(media_rules.keys())
    # Fix 3: incluir TODAS las clases referenciadas en HTML, aunque no tengan CSS.
    # Las que no tienen CSS se emiten con `original: {}` (visto en JSONs reales).
    # Esto preserva la asociacion HTML -> clase declarada que Oxygen necesita.
    relevant = list(used_classes)  # respeta orden de aparicion en HTML
    used_set = set(used_classes)

    # v3.12: incluir BEM modifiers definidos en CSS aunque no aparezcan en el
    # HTML inicial. Casos comunes: .X--open, .X--closed, .X--active, .X--current.
    # El JS los agrega dinamicamente al toggle/hover/click. Sin su CSS asociado
    # en Oxygen, los toggles funcionan en el DOM pero no tienen efecto visual.
    # Solo incluimos el modifier si su clase base esta usada en HTML (evita
    # incluir clases huerfanas reales).
    auto_included: List[str] = []
    for c in all_classes - used_set:
        if "--" in c:
            base = c.split("--", 1)[0]
            if base in used_set:
                relevant.append(c)
                auto_included.append(c)
                continue
        WARN.add(f"Clase '.{c}' definida en CSS pero no usada en HTML. Se omite.")
    if auto_included:
        WARN.add(
            f"BEM modifiers auto-incluidos (probablemente toggled via JS): "
            f"{', '.join('.' + c for c in auto_included)}"
        )
    # Avisar de las usadas en HTML pero sin CSS (estas se emiten igual, pero
    # le decimos al usuario que probablemente quiere agregarles estilos o que
    # vienen del bloque global de Oxygen).
    for c in set(used_classes) - all_classes:
        WARN.add(
            f"Clase '.{c}' usada en HTML pero sin CSS asociado. "
            f"Se emite con original vacio. Si el styling viene de otro lado "
            f"(stylesheet global, code block, JS) esto esta bien."
        )

    for cls in relevant:
        block_type = class_to_block_type.get(cls)
        cls_obj: Dict[str, Any] = OrderedDict()

        # Default
        default_props = expand_shorthands(default_rules.get(cls, {}))
        # __states__ contiene dict {state_name: {prop: value}} para todas las pseudo-clases
        # nativas que mapeamos (hover, focus, before, nth-child(2), etc.)
        states_default = default_props.pop("__states__", None)
        oxygen_props, custom_css_decls = convert_properties(default_props, block_type)
        if custom_css_decls:
            oxygen_props["custom-css"] = " ".join(custom_css_decls)
        # v3.8: auto align-items:stretch para ct_div_block sin align-items definido.
        # Oxygen aplica align-items:flex-start por default a ct_div_block, lo que
        # rompe el block flow del HTML: un <section>/<header>/<div> hijo de otro
        # ct_div_block NO se estira al 100% del ancho del parent — se encoge al
        # ancho de su contenido. align-items:stretch restaura el behavior natural.
        # Aplica solo si:
        #   - El block_type es ct_div_block (no aplica a text_block/headline/etc.)
        #   - El user no definio align-items en el CSS (respeta su intencion).
        # En clases con display:inline-block/block, align-items no afecta (solo
        # tiene efecto en flex/grid containers), por lo que la regla es inocua.
        if block_type == "ct_div_block" and "align-items" not in oxygen_props:
            oxygen_props["align-items"] = "stretch"
        # v3.1: NO inyectamos el `tag` del bloque dentro del original de la clase.
        # `tag` es una opcion del bloque (options.original.tag), no de la clase.
        # Inyectarlo aqui forzaria el mismo tag a cualquier otro bloque que use
        # la misma clase, lo que es incorrecto.
        cls_obj["original"] = oxygen_props if oxygen_props else {}

        # Auto-icon-size para clases aplicadas a ct_fancy_icon.
        # ct_fancy_icon renderiza como <div class="ct-fancy-icon"><svg></svg></div>.
        # width/height de la clase aplican al div wrapper, NO al svg interno.
        # icon-size es la propiedad propia de Oxygen para el tamano del svg.
        # Si la clase tiene width o height, replicamos el valor a icon-size.
        if block_type == "ct_fancy_icon":
            orig = cls_obj["original"]
            if isinstance(orig, dict) and "icon-size" not in orig:
                size_value = orig.get("width") or orig.get("height")
                if size_value is not None:
                    orig["icon-size"] = size_value

        # States nativos (hover, focus, active, before, after, disabled, checked,
        # first-child, last-child, nth-child(N), etc.) emitidos como keys
        # paralelas a `original` en la clase.
        if states_default:
            for state_name, state_props in states_default.items():
                state_expanded = expand_shorthands(state_props)
                state_oxygen, state_css = convert_properties(state_expanded, block_type)
                if state_css:
                    state_oxygen["custom-css"] = " ".join(state_css)
                if state_oxygen:
                    cls_obj[state_name] = state_oxygen

        # Media queries
        media_for_cls = media_rules.get(cls, {})
        if media_for_cls:
            media_obj: Dict[str, Any] = OrderedDict()
            for bp_name, bp_rules in media_for_cls.items():
                bp_obj: Dict[str, Any] = OrderedDict()
                # States dentro del breakpoint (igual estructura: __states__ dict)
                states_bp = bp_rules.pop("__states__", None) if "__states__" in bp_rules else None
                expanded = expand_shorthands(bp_rules)
                bp_oxygen, bp_css = convert_properties(expanded, block_type)
                # Si hay propiedades de grid o flex, asegurar display
                if any(p.startswith("grid-") for p in bp_oxygen) and "display" not in bp_oxygen:
                    if "display" in default_props or "display" in oxygen_props:
                        bp_oxygen["display"] = "grid"
                if any(p in bp_oxygen for p in ("flex-direction", "flex-wrap", "justify-content")) and "display" not in bp_oxygen:
                    if oxygen_props.get("display") == "flex":
                        bp_oxygen["display"] = "flex"
                if bp_css:
                    bp_oxygen["custom-css"] = " ".join(bp_css)
                if bp_oxygen:
                    bp_obj["original"] = bp_oxygen
                # States en breakpoint emitidos al mismo nivel que `original`
                if states_bp:
                    for state_name, state_props in states_bp.items():
                        state_expanded = expand_shorthands(state_props)
                        state_oxygen, state_css = convert_properties(state_expanded, block_type)
                        if state_css:
                            state_oxygen["custom-css"] = " ".join(state_css)
                        if state_oxygen:
                            bp_obj[state_name] = state_oxygen
                if bp_obj:
                    media_obj[bp_name] = bp_obj
            if media_obj:
                cls_obj["media"] = media_obj

        cls_obj["key"] = cls
        classes_obj[cls] = cls_obj

    return classes_obj


# ============================================================
# CODE BLOCK AGREGADO
# ============================================================

def build_code_block(codeblock_rules: List[Dict], ids: IdAllocator, parent_ct_id: int) -> Optional[Dict]:
    """Construye un ct_code_block agregado con todo el CSS no mapeable."""
    if not codeblock_rules:
        return None
    css_parts: List[str] = []
    for rule in codeblock_rules:
        if rule["type"] == "rule":
            sel = rule["selector"]
            decls = "; ".join(f"{k}: {v}" for k, v in rule["declarations"].items())
            wrapped = f"{sel} {{ {decls}; }}"
            if rule.get("breakpoint"):
                # Buscar el max-width correspondiente
                bp_name = rule["breakpoint"]
                bp_value = next((v for v, n in BREAKPOINTS if n == bp_name), None)
                if bp_value:
                    wrapped = f"@media (max-width: {bp_value}px) {{ {wrapped} }}"
            css_parts.append(wrapped)
        elif rule["type"] == "media_raw":
            css_parts.append(f"@media {rule['prelude']} {{ {rule['content']} }}")
        elif rule["type"] == "at_rule_raw":
            css_parts.append(rule["raw"])

    code_css = "\n".join(css_parts)
    ct_id = ids.alloc()
    return {
        "id": ct_id,
        "name": "ct_code_block",
        "options": {
            "ct_id": ct_id,
            "ct_parent": parent_ct_id,
            "selector": f"code_block-{ct_id}-{SELECTOR_SUFFIX}",
            "original": {
                "code-css": code_css,
                "code-js": "",
                "code-php": "",
            },
            "nicename": f"Code Block (#{ct_id})",
            "activeselector": False,
        },
        "depth": 3,
    }


# ============================================================
# RECOLECCION DE CLASES USADAS Y MAPEO A TIPOS
# ============================================================

def collect_used_classes(component: Dict, out: Optional[Dict[str, str]] = None, tags_out: Optional[Dict[str, str]] = None) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Recorre el arbol de componentes y construye dos mapeos:
    - clase -> tipo de bloque (para excepciones como button-text-color)
    - clase -> tag custom (para emitir en classes[<key>].original.tag)
    """
    if out is None:
        out = OrderedDict()
    if tags_out is None:
        tags_out = OrderedDict()
    classes = component.get("options", {}).get("classes", [])
    block_type = component.get("name")
    original = component.get("options", {}).get("original", {})
    custom_tag = None
    if isinstance(original, dict) and "tag" in original:
        custom_tag = original["tag"]
    for c in classes:
        if c not in out:
            out[c] = block_type
        if custom_tag and c not in tags_out:
            tags_out[c] = custom_tag
    for child in component.get("children", []):
        collect_used_classes(child, out, tags_out)
    return out, tags_out


# ============================================================
# MAIN
# ============================================================

# ============================================================
# POST-PROCESO: COLAPSO DE WRAPPER DE ICONOS
# ============================================================

# Propiedades CSS consideradas "inocuas" para colapso conservador
# Si un wrapper de icono tiene SOLO estas, sus clases se transfieren al icono.
# Las propiedades de tama\u00f1o, color y opacidad son las que un icono puede heredar
# sin que cambie su contenedor. Las de display/flex/align se incluyen porque
# en un wrapper con un \u00fanico hijo, su efecto es no-op al desaparecer el wrapper.
_INNOCUOUS_PROPERTIES = {
    # Tama\u00f1o
    "width", "height", "min-width", "min-height", "max-width", "max-height",
    # Visual basico
    "color", "font-size", "opacity",
    # Margenes (posicionales pero no afectan al hijo)
    "margin-top", "margin-right", "margin-bottom", "margin-left",
    # Layout flex (no-op cuando el wrapper desaparece y solo hab\u00eda 1 hijo)
    "display", "flex-direction", "align-items", "justify-content",
    "flex-grow", "flex-shrink",
    # Otros no visuales
    "pointer-events",
}

# Para 'display' solo aceptamos valores que sean inocuos. 'block', 'flex',
# 'inline-flex' son seguros. 'grid', 'inline', 'none' no se consideran inocuos.
_DISPLAY_INNOCUOUS_VALUES = {"block", "flex", "inline-flex", "inline-block"}


def _is_innocuous_wrapper(classes: List[str], default_rules: Dict, media_rules: Dict) -> bool:
    """
    True si todas las clases del wrapper tienen propiedades inocuas
    (tama\u00f1o, color, opacidad, margen, flex/display estructural inofensivo).
    """
    if not classes:
        return False

    def _check_props(rules: Dict[str, str]) -> bool:
        for prop, val in rules.items():
            if prop == "__states__":
                continue
            if prop not in _INNOCUOUS_PROPERTIES:
                return False
            # Caso especial: display solo es inocuo para ciertos valores
            if prop == "display" and val.strip().lower() not in _DISPLAY_INNOCUOUS_VALUES:
                return False
        return True

    for cls in classes:
        # Saltar clases ct-* (son metadata de Oxygen, no estilan)
        if cls.startswith("ct-"):
            continue
        # Revisar reglas default
        rules = default_rules.get(cls, {})
        if not _check_props(rules):
            return False
        # Revisar tambien media queries
        media = media_rules.get(cls, {})
        for bp_rules in media.values():
            if not _check_props(bp_rules):
                return False
    return True


def collapse_icon_wrappers(node: Dict, default_rules: Dict, media_rules: Dict) -> Dict:
    """
    Recorre el arbol y colapsa wrappers de icono cuando es seguro.
    Patron: ct_div_block con un unico hijo ct_fancy_icon o ct_code_block,
    y cuyas clases son inocuas (solo tama\u00f1o/color/opacidad).
    Retorna el nodo (posiblemente reemplazado).
    """
    children = node.get("children", []) or []
    # Procesar hijos primero (recursivo)
    new_children = [collapse_icon_wrappers(c, default_rules, media_rules) for c in children]
    if new_children:
        node["children"] = new_children
    elif "children" in node:
        del node["children"]

    # Solo intentamos colapso si somos un ct_div_block con UN unico hijo Tag
    if node.get("name") != "ct_div_block":
        return node
    if len(new_children) != 1:
        return node

    child = new_children[0]
    if child.get("name") not in ("ct_fancy_icon", "ct_code_block"):
        return node

    wrapper_classes = node.get("options", {}).get("classes", []) or []
    if not _is_innocuous_wrapper(wrapper_classes, default_rules, media_rules):
        return node

    # Hacer el colapso: transferir clases al hijo, conservar id/parent del wrapper
    # para no romper la jerarquia
    child_options = child.get("options", {})
    child_classes = child_options.get("classes", []) or []
    # Combinar clases (wrapper primero, hijo despues, sin duplicar)
    combined = list(wrapper_classes)
    for c in child_classes:
        if c not in combined:
            combined.append(c)
    child_options["classes"] = combined
    if combined:
        child_options["activeselector"] = combined[-1]
    # El hijo hereda el ct_id y ct_parent del wrapper para mantener parentesco
    child_options["ct_id"] = node["options"]["ct_id"]
    child_options["ct_parent"] = node["options"]["ct_parent"]
    child["id"] = node["id"]
    child["depth"] = node["depth"]
    # Reconstruir selector con el id correcto
    base = SELECTOR_BASE.get(child["name"], child["name"])
    child_options["selector"] = f"{base}-{node['options']['ct_id']}-{SELECTOR_SUFFIX}"
    return child


# ============================================================
# POST-PROCESO: ESTILOS DE CLASES INTERNAS DE RICH TEXT
# ============================================================

# Regex para extraer clases de atributos class="..." en HTML embebido
_CLASS_ATTR_RE = re.compile(r'class\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)


def _extract_classes_from_html(html_str: str) -> List[str]:
    """
    Extrae todas las clases que aparecen en atributos class="..." dentro de un string HTML.
    Usado para encontrar clases que viven embebidas en oxy_rich_text.
    """
    classes: List[str] = []
    for match in _CLASS_ATTR_RE.finditer(html_str):
        for c in match.group(1).split():
            if c and c not in classes:
                classes.append(c)
    return classes


def collect_rich_text_inner_classes(node: Dict) -> List[str]:
    """
    Recorre el arbol y devuelve todas las clases que aparecen embebidas
    en el ct_content de cualquier oxy_rich_text. Sin duplicados.
    """
    found: List[str] = []
    name = node.get("name", "")
    if name == "oxy_rich_text":
        opts = node.get("options", {}) or {}
        content = opts.get("ct_content", "")
        if isinstance(content, str) and content:
            for c in _extract_classes_from_html(content):
                if c not in found:
                    found.append(c)
    for child in node.get("children", []) or []:
        for c in collect_rich_text_inner_classes(child):
            if c not in found:
                found.append(c)
    return found


def _format_content_value(val: str) -> str:
    """Devuelve un valor valido de CSS `content`. El skill normaliza el value
    de content quitando comillas externas (formato Oxygen). Cuando reserializamos
    a CSS bruto (inner-style block / code-block), hay que re-envolver en comillas
    para producir CSS valido. Los formatos no-string de content (attr/counter/url/
    var/keywords) se dejan tal cual.
    """
    if val is None:
        return '""'
    v = str(val).strip()
    if v == "":
        return '""'
    if v.startswith('"') or v.startswith("'"):
        return v  # ya tiene comillas
    if v.lower() in ("none", "normal", "open-quote", "close-quote",
                     "no-open-quote", "no-close-quote", "inherit", "initial", "unset"):
        return v
    # Functional values
    if any(v.startswith(fn) for fn in ("attr(", "counter(", "counters(",
                                        "url(", "var(", "linear-gradient(",
                                        "radial-gradient(", "image(")):
        return v
    # Cualquier otra cosa: string literal. Escapar comillas internas.
    return '"' + v.replace('"', '\\"') + '"'


def _serialize_decl(prop: str, val: str) -> str:
    """Serializa una declaracion CSS aplicando fix de content para evitar CSS invalido."""
    if prop == "content":
        return f"{prop}: {_format_content_value(val)};"
    return f"{prop}: {val};"


def _serialize_css_rules(class_name: str, rules: Dict[str, str]) -> str:
    """
    Serializa un diccionario de propiedades CSS a un string ".clase { prop: val; ... }".
    Filtra __states__ porque se serializan aparte como `.clase:state { ... }`.
    """
    decls = []
    for prop, val in rules.items():
        if prop == "__states__":
            continue
        decls.append(_serialize_decl(prop, val))
    if not decls:
        return ""
    return "." + class_name + " { " + " ".join(decls) + " }"


def build_inner_style_block(
    inner_classes: List[str],
    block_used_classes: set,
    default_rules: Dict,
    media_rules: Dict,
    ids: "IdAllocator",
    parent_ct_id: int,
    depth: int,
) -> Optional[Dict]:
    """
    Construye un ct_code_block con un <style> que contiene las reglas CSS de las clases
    que aparecen DENTRO de un oxy_rich_text pero no son clases de bloque.
    Si una clase aparece como bloque y como inner, NO se incluye (precedencia del bloque).
    Si no hay clases inner relevantes, retorna None.
    """
    relevant: List[str] = []
    for cls in inner_classes:
        if cls in block_used_classes:
            continue  # ya emitida como clase de bloque
        if cls not in default_rules and cls not in media_rules:
            continue  # no hay reglas CSS para esta clase
        relevant.append(cls)
    if not relevant:
        return None

    # Construir el contenido CSS
    css_parts: List[str] = []
    for cls in relevant:
        # Default rules
        rules = default_rules.get(cls, {})
        if rules:
            serialized = _serialize_css_rules(cls, rules)
            if serialized:
                css_parts.append(serialized)
            # States: emitir como `.cls:state { ... }` para cada uno
            states = rules.get("__states__", {})
            for state_name, state_props in states.items():
                state_decls = []
                for prop, val in state_props.items():
                    state_decls.append(_serialize_decl(prop, val))
                if state_decls:
                    # Pseudo-elementos (before/after) usan `::`, pseudo-clases usan `:`
                    sep = "::" if state_name in ("before", "after") else ":"
                    css_parts.append(f".{cls}{sep}{state_name} {{ {' '.join(state_decls)} }}")
        # Media queries
        media = media_rules.get(cls, {})
        for bp_name, bp_rules in media.items():
            # Mapear breakpoint name a max-width px (inverso del mapeo BREAKPOINTS)
            bp_px = None
            for px, name in BREAKPOINTS:
                if name == bp_name:
                    bp_px = px
                    break
            if bp_px is None:
                continue
            serialized = _serialize_css_rules(cls, bp_rules)
            if serialized:
                css_parts.append(f"@media (max-width: {bp_px}px) {{ {serialized} }}")

    if not css_parts:
        return None

    css_content = " ".join(css_parts)

    ct_id = ids.alloc()
    options: Dict[str, Any] = OrderedDict()
    options["ct_id"] = ct_id
    options["ct_parent"] = parent_ct_id
    options["selector"] = f"code_block-{ct_id}-{SELECTOR_SUFFIX}"
    options["original"] = OrderedDict([
        ("code-css", css_content),
        ("code-php", ""),
        ("unwrap", "true"),
    ])
    options["nicename"] = f"Code Block (#{ct_id}) - Inner Rich Text Styles"
    options["activeselector"] = False

    return OrderedDict([
        ("id", ct_id),
        ("name", "ct_code_block"),
        ("options", options),
        ("depth", depth),
    ])


def apply_auto_flex_to_links(node: Dict, default_rules: Dict[str, Dict]) -> None:
    """
    Recorre el arbol y, para cada bloque marcado con __needs_auto_flex__,
    inyecta display:flex / flex-direction:row / gap:8 en options.original SI
    ninguna de las clases del bloque ya definio `display` en el CSS del user.

    Si el user ya configuro un display (flex, grid, block, etc.) en una de las
    clases del link, respetamos su intencion y NO inyectamos. Esto evita romper
    layouts donde el user eligio grid u otra opcion para el container.

    Despues de procesar, eliminamos la marca interna __needs_auto_flex__ para
    que no aparezca en el JSON final.
    """
    if not isinstance(node, dict):
        return
    opts = node.get("options", {})
    if opts.get("__needs_auto_flex__"):
        del opts["__needs_auto_flex__"]
        classes = opts.get("classes", []) or []
        user_defined_display = any(
            "display" in (default_rules.get(c, {}) or {})
            for c in classes
        )
        if not user_defined_display:
            original = opts.get("original")
            if not isinstance(original, dict):
                # Esta vacio (puede ser [] tras normalizacion, o no presente).
                # Reemplazar por dict para poder inyectar.
                original = OrderedDict()
                opts["original"] = original
            if "display" not in original:
                original["display"] = "flex"
            if "flex-direction" not in original:
                original["flex-direction"] = "row"
            if "gap" not in original:
                original["gap"] = "8"
    for child in node.get("children", []) or []:
        apply_auto_flex_to_links(child, default_rules)


def _normalize_original_empty_to_array(node: Dict) -> None:
    """
    Recorre el arbol de componentes y reemplaza `options.original = {}` por `[]`.
    Solo aplica a bloques individuales (options.original), no a classes[X].original
    del top-level que usa `{}` consistentemente.
    """
    if not isinstance(node, dict):
        return
    opts = node.get("options")
    if isinstance(opts, dict):
        orig = opts.get("original")
        # Solo transformar si es exactamente un dict vacio
        if isinstance(orig, dict) and len(orig) == 0:
            opts["original"] = []
        # Tambien en options.media.<bp>.original si esta vacio (visto en reales)
        media = opts.get("media")
        if isinstance(media, dict):
            for bp, bp_obj in media.items():
                if isinstance(bp_obj, dict):
                    bp_orig = bp_obj.get("original")
                    if isinstance(bp_orig, dict) and len(bp_orig) == 0:
                        bp_obj["original"] = []
    for child in node.get("children", []) or []:
        _normalize_original_empty_to_array(child)


def main():
    global SELECTOR_SUFFIX
    parser = argparse.ArgumentParser(description="HTML+CSS to Oxygen Builder JSON")
    parser.add_argument("--html", required=True, help="Archivo HTML de entrada")
    parser.add_argument("--css", required=True, help="Archivo CSS de entrada")
    parser.add_argument("--out", required=True, help="Archivo JSON de salida")
    parser.add_argument(
        "--selector-suffix",
        default=None,
        help=(
            "Sufijo numerico para los selectors (ej. '1908'). "
            "Empiricamente es el post_id de la pagina/template donde vive el bloque. "
            "Si no se pasa, se genera uno aleatorio de 4 digitos por ejecucion."
        ),
    )
    args = parser.parse_args()

    # Asignar sufijo: del flag o generar aleatorio de 4 digitos
    if args.selector_suffix is not None:
        SELECTOR_SUFFIX = str(args.selector_suffix)
    else:
        import random
        SELECTOR_SUFFIX = str(random.randint(1000, 9999))
        WARN.add(
            f"No se paso --selector-suffix. Usando aleatorio '{SELECTOR_SUFFIX}'. "
            f"Si el JSON no funciona al pegar, prueba con el post_id de tu pagina destino."
        )

    with open(args.html, "r", encoding="utf-8") as f:
        html = f.read()
    with open(args.css, "r", encoding="utf-8") as f:
        css = f.read()

    # Parsear CSS
    default_rules, media_rules, codeblock_rules = parse_css(css)

    # Construir arbol de componentes
    ids = IdAllocator(start=2)
    component_tree = html_to_component_tree(html, ids)

    # Post-proceso: colapsar wrappers de iconos cuando es seguro
    component_tree = collapse_icon_wrappers(component_tree, default_rules, media_rules)

    # Recolectar clases usadas
    class_to_block_type, class_to_tag = collect_used_classes(component_tree)
    used_classes = list(class_to_block_type.keys())

    # Construir el bloque classes top-level
    classes_block = build_classes_block(default_rules, media_rules, used_classes, class_to_block_type, class_to_tag)

    # Recolectar clases internas de oxy_rich_text y emitir un ct_code_block con sus estilos
    inner_classes = collect_rich_text_inner_classes(component_tree)
    if inner_classes:
        inner_style_block = build_inner_style_block(
            inner_classes,
            set(used_classes),
            default_rules,
            media_rules,
            ids,
            parent_ct_id=component_tree["id"],
            depth=component_tree["depth"] + 1,
        )
        if inner_style_block:
            if "children" not in component_tree:
                component_tree["children"] = []
            component_tree["children"].append(inner_style_block)
            # Quitar avisos de "clase no usada" para clases que ahora viven en el style block
            new_warnings = []
            for w in WARN.items:
                skip = False
                for cls in inner_classes:
                    if cls not in used_classes and f"'.{cls}'" in w:
                        skip = True
                        break
                if not skip:
                    new_warnings.append(w)
            WARN.items = new_warnings

    # Construir Code Block agregado si hay reglas no mapeables
    code_block = build_code_block(codeblock_rules, ids, parent_ct_id=component_tree["id"])
    if code_block:
        if "children" not in component_tree:
            component_tree["children"] = []
        component_tree["children"].append(code_block)
        WARN.add(f"Se agrego un ct_code_block (id={code_block['id']}) con CSS no mapeable. Revisa que el resultado sea el esperado.")

    # v3.1: aplicar auto-flex a los bloques ct_link con icono+texto. Se hace aqui,
    # despues de tener default_rules parseado, para poder decidir si el user ya
    # configuro display y respetarlo. La inyeccion va al options.original del
    # bloque (no a las clases) para no contaminar clases reusables.
    apply_auto_flex_to_links(component_tree, default_rules)

    # Ensamblar JSON final
    output = OrderedDict()
    output["component"] = component_tree
    output["classes"] = classes_block

    # Fix 2: en bloques individuales, options.original vacio ({}) debe ser []
    # (visto en JSONs reales de Oxygen; coherente con serializacion de array PHP vacio).
    # NO aplica a classes[X].original donde el formato es {} consistentemente.
    _normalize_original_empty_to_array(output["component"])

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=None, separators=(",", ":"))

    # Avisos a stderr
    WARN.emit()
    print(f"\n[OK] JSON escrito en {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
