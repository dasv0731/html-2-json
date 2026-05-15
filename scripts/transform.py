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
import json
import re
import sys
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

import tinycss2
from bs4 import BeautifulSoup, NavigableString, Tag


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

# Tipo Oxygen -> base del selector
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
}

# Propiedades CSS soportadas nativamente por Oxygen
NATIVE_PROPERTIES = {
    # Layout
    "display", "flex-direction", "flex-wrap", "justify-content", "align-items",
    "align-content", "align-self", "flex-grow", "flex-shrink", "flex-reverse",
    "column-gap", "row-gap", "gap", "grid-column-gap", "grid-row-gap",
    "grid-column-count", "grid-child-rules",
    "position", "top", "right", "bottom", "left", "z-index",
    "overflow", "overflow-x", "overflow-y",
    # Espaciado
    "padding-top", "padding-right", "padding-bottom", "padding-left",
    "margin-top", "margin-right", "margin-bottom", "margin-left",
    "width", "height", "min-width", "min-height", "max-width", "max-height",
    # Tipografia
    "font-family", "font-size", "font-weight", "font-style",
    "color", "line-height", "letter-spacing",
    "text-align", "text-transform", "text-decoration",
    # Visual
    "background-color", "background-image", "background-position",
    "background-repeat", "background-size",
    "border-top-width", "border-right-width", "border-bottom-width", "border-left-width",
    "border-top-style", "border-right-style", "border-bottom-style", "border-left-style",
    "border-top-color", "border-right-color", "border-bottom-color", "border-left-color",
    "border-top-left-radius", "border-top-right-radius",
    "border-bottom-left-radius", "border-bottom-right-radius",
    "opacity", "box-shadow",
    # Botones (excepcion)
    "button-text-color",
    # Imagenes
    "object-fit", "object-position",
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
}


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
                # Extraer grid-column/grid-row span N como metadata especial
                # para que el post-process construya grid-child-rules en el container.
                declarations = _extract_grid_span_metadata(declarations)
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


def _extract_grid_span_metadata(declarations: Dict[str, str]) -> Dict[str, str]:
    """
    Si una regla CSS de clase tiene `grid-column: span N` o `grid-row: span N`,
    extraerlas a metadata especial (__grid_span_column__, __grid_span_row__) y
    quitarlas del dict de declaraciones normales. El post-process apply_grid_child_rules
    las usa para construir el array `grid-child-rules` en el container grid.

    Solo aplica al formato `span N` (donde N es entero >= 1). Otras formas
    (`grid-column: 2/4`, `grid-area: foo`) no se tocan y caen a custom-css por el
    flujo normal.
    """
    out = dict(declarations)
    span_re = re.compile(r"^\s*span\s+(\d+)\s*$")
    if "grid-column" in out:
        m = span_re.match(out["grid-column"])
        if m:
            out["__grid_span_column__"] = m.group(1)
            del out["grid-column"]
    if "grid-row" in out:
        m = span_re.match(out["grid-row"])
        if m:
            out["__grid_span_row__"] = m.group(1)
            del out["grid-row"]
    return out


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
# Validado empiricamente pegando JSONs en Oxygen y viendo que se renderizan.
# Las que NO estan aqui (focus-visible, focus-within, placeholder, read-only,
# etc.) NO han sido validadas y van a Code Block para no producir regresiones
# silenciosas.
NATIVE_SIMPLE_PSEUDO = {
    "hover", "focus", "active",
    "disabled", "checked",
    "first-child", "last-child",
}

# Pseudo-elementos que Oxygen acepta. Tanto `:before` como `::before` son
# sintacticamente validas en CSS y refieren al mismo concepto; ambas se
# mapean a la misma key sin los dos puntos.
NATIVE_PSEUDO_ELEMENTS = {
    "before", "after",
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
        # __grid_span_* es metadata para grid-child-rules; el post-process la consume,
        # no debe llegar al output normal.
        if prop in ("__grid_span_column__", "__grid_span_row__"):
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
        # Metadata interna de spans (consumida por apply_grid_child_rules en otra fase).
        if prop in ("__grid_span_column__", "__grid_span_row__"):
            continue
        if prop.startswith("__custom_css__"):
            real_prop = prop.replace("__custom_css__", "")
            custom_css.append(f"{real_prop}: {val};")
            continue

        # Caso especial: grid-child-rules es un array de objetos, no un string.
        # Emitirlo tal cual; _is_property_native asume valores string.
        if prop == "grid-child-rules" and isinstance(val, list):
            oxygen[prop] = val
            continue

        # Caso especial: grid-template-columns -> grid-column-count si es repeat(N, 1fr) o N veces 1fr
        if prop == "grid-template-columns":
            count = _grid_template_to_count(val)
            if count is not None:
                oxygen["grid-column-count"] = str(count)
                continue
            # No mapea nativo: a custom-css
            custom_css.append(f"{prop}: {val};")
            continue

        # Excepcion para botones: color -> button-text-color
        effective_prop = prop
        if block_type == "ct_link_button" and prop == "color":
            effective_prop = "button-text-color"

        # Workaround margin: Oxygen aplica `.ct-div-block { margin: 0 }` con prioridad CSS.
        # Cualquier margin-* numerico en un ct_div_block es sobrescrito a 0.
        # Solucion: redirigir a custom-css con !important para que sobreviva.
        # NOTA: solo numericos. Si es "auto", sigue la logica de margin-X-unit: auto.
        if block_type == "ct_div_block" and prop in {"margin-top", "margin-right", "margin-bottom", "margin-left"}:
            v_clean = val.strip().lower()
            if v_clean != "auto":
                # Emitir a custom-css con !important
                # Asegurar que tiene unidad: si es solo numero, asumir px
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
    Retorna False si el valor contiene calc(), clamp(), var(), etc.
    """
    if prop not in NATIVE_PROPERTIES:
        return False
    # Valores con funciones complejas: van a custom-css
    if any(fn in val for fn in ("calc(", "clamp(", "min(", "max(", "var(", "env(")):
        return False
    return True


def _grid_template_to_count(val: str) -> Optional[int]:
    """
    Si grid-template-columns es 'repeat(N, 1fr)' o '1fr 1fr ... 1fr',
    retorna N. Si no, retorna None (no mapea nativo).
    """
    val = val.strip()
    # repeat(N, 1fr)
    m = re.match(r"^repeat\(\s*(\d+)\s*,\s*1fr\s*\)$", val)
    if m:
        return int(m.group(1))
    # "1fr 1fr 1fr"
    parts = val.split()
    if all(p == "1fr" for p in parts) and len(parts) >= 1:
        return len(parts)
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
        # Si es "auto", manejarlo como unit
        if val.lower() == "auto" and prop in {"margin-top", "margin-right", "margin-bottom", "margin-left",
                                                "width", "height", "max-width", "max-height", "min-width", "min-height"}:
            return [(f"{prop}-unit", "auto")]
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
    # Limpiar estado entre ejecuciones
    _AUTOFLEX_CLASSES_NEEDED.clear()

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
    Cualquier otro atributo (aria-*, data-*, role, tabindex, title, lang, dir, name,
    value, type, for, placeholder, autocomplete, required, disabled, hidden, etc.)
    se preserva.
    """
    HANDLED_ATTRS = {
        "class", "id",
        "href", "target",
        "src", "alt", "srcset", "width", "height", "loading",
        "xlink:href",
    }
    out: List[Dict[str, str]] = []
    if not hasattr(tag, "attrs"):
        return out
    for name, value in tag.attrs.items():
        if name.lower() in HANDLED_ATTRS:
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
    if not is_codeblock_with_html_literal:
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
    classes = tag.get("class", [])
    # Si el bloque es ct_code_block con HTML literal que ya contiene las clases
    # (Ruta B de iconos FA), filtrar las clases FA del bloque. Ya viajan dentro
    # del code-php y emitirlas tambien como classes del bloque ensucia la tabla
    # global de selectores de Oxygen con .fa-solid, .fa-envelope, etc. (clases
    # de framework, no de usuario, que el usuario no quiere estilizar).
    if is_codeblock_with_html_literal and classes:
        classes = [c for c in classes if not _FA_CLASS_PATTERN.match(c) and not c.startswith("fa-")]
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
    if block_type in ("ct_div_block", "ct_link"):
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
            for child in tag.children:
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


# Clases CSS que se acumularan globalmente para auto-anadir flex.
# Llave: nombre de clase. Valor: True si ya se proceso (para no dupliticar).
_AUTOFLEX_CLASSES_NEEDED: Dict[str, bool] = {}


def _maybe_add_flex_for_icon_text_link(tag: Tag, options: Dict, classes: List[str]) -> None:
    """
    Detecta si el <a> tiene patron icono (svg/i) + texto (text node suelto o multiples hijos).
    Si si, marca la(s) clase(s) del link para auto-anadir display: flex; flex-direction: row; gap: 8;
    """
    if not classes:
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
    if not (has_icon and has_text):
        return
    # Marcar SOLO la ultima clase del link. Convencion BEM: modifier al final
    # (ej. "btn btn--whatsapp" -> .btn--whatsapp es la modifier que aplica al
    # contexto especifico icono+texto, .btn es la base reutilizable que no debe
    # recibir flex inyectado porque puede usarse en otros <a> sin icono).
    target = classes[-1]
    _AUTOFLEX_CLASSES_NEEDED[target] = True
    if len(classes) > 1:
        WARN.add(
            f"<a> con icono+texto tiene multiples clases ({' '.join(classes)}). "
            f"Auto-flex aplicado solo a la ultima ('.{target}'). "
            f"Si la clase modifier no es esa, reordena las clases o ajusta a mano."
        )


def _maybe_inject_text_child(tag: Tag, ids: "IdAllocator", parent_ct_id: int, depth: int) -> Optional[Dict]:
    """
    Si el tag contiene SOLO texto plano o texto + tags inline (sin block-level ni svg/i),
    retorna un componente hijo (ct_text_block u oxy_rich_text) que capture ese contenido.
    Si el tag tiene hijos no-inline, retorna None para que el flujo normal procese hijos.
    """
    # Clasificar hijos
    has_text = False
    has_inline_tag = False
    has_other_tag = False
    for child in tag.children:
        if isinstance(child, NavigableString):
            if str(child).strip():
                has_text = True
        elif isinstance(child, Tag):
            child_name = child.name.lower()
            if child_name in _INLINE_TAGS:
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

    # Ruta A: <svg><use xlink:href="#XXX"></use></svg> -> ct_fancy_icon
    if name == "svg":
        icon_id = _detect_fancy_icon_use(tag)
        if icon_id is not None:
            return ("ct_fancy_icon", {"icon-id": icon_id})
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
    if name == "a":
        classes = tag.get("class", [])
        text_lower = " ".join(classes).lower()
        # Heuristica: si tiene clase con "boton", "btn", "button" -> link_button
        is_button = any(re.search(r"\b(boton|button|btn)\b", c.lower()) for c in classes)
        # Si tiene hijos Tag (no solo texto) -> link wrapper
        has_tag_children = any(isinstance(c, Tag) for c in tag.children)
        if is_button and not has_tag_children:
            url = tag.get("href", "")
            target = tag.get("target", "")
            return ("ct_link_button", _strip_empty({"url": url, "target": target}))
        if has_tag_children:
            url = tag.get("href", "")
            target = tag.get("target", "")
            original = _strip_empty({"url": url, "target": target})
            return ("ct_link", original if original else {})
        # Solo texto
        url = tag.get("href", "")
        target = tag.get("target", "")
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
        # Caso 1: texto plano puro (o vacío)
        return ("ct_text_block", {"useCustomTag": "true", "tag": "button"})

    # <img>: ct_image
    if name == "img":
        src = tag.get("src", "")
        original: Dict[str, Any] = OrderedDict()
        original["image_type"] = "2"
        original["attachment_size"] = "full"
        original["attachment_id"] = 0
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
        original["attachment_url"] = src
        if tag.get("alt"):
            WARN.add(f"<img alt=\"{tag.get('alt')}\"> no se transfiere al JSON; reasigna manualmente tras pegar.")
        WARN.add(f"<img src=\"{src}\"> emitido con attachment_id=0. Reasigna la imagen al media library de WordPress tras pegar.")
        return ("ct_image", original)

    # Tags de tipo div con tag custom
    if name in ("section", "article", "header", "footer", "aside", "nav", "main", "blockquote"):
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
    if name in ("span", "em", "strong", "small"):
        return ("ct_text_block", {"useCustomTag": "true", "tag": name})

    # ul / ol -> ct_div_block con useCustomTag
    if name in ("ul", "ol"):
        return ("ct_div_block", {"useCustomTag": "true", "tag": name})

    # li -> tres mapeos segun contenido (validado empiricamente)
    if name == "li":
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
        return ("ct_div_block", {})

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
    # Avisar de las definidas en CSS pero no usadas (estas SI se siguen omitiendo,
    # porque son huerfanas reales en el CSS del usuario)
    for c in all_classes - set(used_classes):
        WARN.add(f"Clase '.{c}' definida en CSS pero no usada en HTML. Se omite.")
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
        custom_tag = class_to_tag.get(cls)
        cls_obj: Dict[str, Any] = OrderedDict()

        # Default
        default_props = expand_shorthands(default_rules.get(cls, {}))
        # __states__ contiene dict {state_name: {prop: value}} para todas las pseudo-clases
        # nativas que mapeamos (hover, focus, before, nth-child(2), etc.)
        states_default = default_props.pop("__states__", None)
        oxygen_props, custom_css_decls = convert_properties(default_props, block_type)
        if custom_css_decls:
            oxygen_props["custom-css"] = " ".join(custom_css_decls)
        # Si la clase pertenece a un bloque con tag custom, emitir el tag en original
        # tambien (visto en JSON real de Oxygen)
        if custom_tag:
            new_original = OrderedDict()
            new_original["tag"] = custom_tag
            new_original.update(oxygen_props)
            oxygen_props = new_original
        cls_obj["original"] = oxygen_props if oxygen_props else {}

        # Auto-flex para clases de <a> con icono+texto (postura A confirmada).
        # Solo se anade si el usuario no escribio esas propiedades en su CSS.
        if _AUTOFLEX_CLASSES_NEEDED.get(cls):
            orig = cls_obj["original"]
            if not isinstance(orig, dict):
                orig = OrderedDict()
                cls_obj["original"] = orig
            if "display" not in orig:
                orig["display"] = "flex"
            if "flex-direction" not in orig and orig.get("display") == "flex":
                orig["flex-direction"] = "row"
            if "gap" not in orig:
                orig["gap"] = "8"

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
                # Si hay propiedades de flex en el breakpoint, asegurar display: flex
                # para que el panel UI de Oxygen muestre los controles flex en ese breakpoint.
                # Para grid NO hacemos lo paralelo: el display: grid de top-level se hereda
                # en cascada CSS y emitirlo en cada breakpoint genera ruido al editar.
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


def _serialize_css_rules(class_name: str, rules: Dict[str, str]) -> str:
    """
    Serializa un diccionario de propiedades CSS a un string ".clase { prop: val; ... }".
    Filtra __states__ porque se serializan aparte como `.clase:state { ... }`.
    """
    decls = []
    for prop, val in rules.items():
        if prop == "__states__":
            continue
        decls.append(f"{prop}: {val};")
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
                    state_decls.append(f"{prop}: {val};")
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


def apply_grid_child_rules(node: Dict, default_rules: Dict) -> None:
    """
    Post-process: para cada container con `display: grid` en alguna de sus clases,
    construye el array `grid-child-rules` mirando los hijos en orden.

    Formato canonico de Oxygen (validado empiricamente contra JSONs reales):
      [
        {"child-index": 0, "column-span": "",  "row-span": ""},      # hijo default 1x1
        {"child-index": 1, "column-span": "3", "row-span": "2"},     # hijo 3 cols x 2 rows
        ...
      ]
    Una entrada por cada hijo (NO truncar al ultimo no-default).

    Los spans se detectan via metadata __grid_span_column__ / __grid_span_row__
    que `_extract_grid_span_metadata` deposita en default_rules al parsear CSS
    de la forma `grid-column: span N` o `grid-row: span N`.

    El array se inyecta en `default_rules[container_class]["grid-child-rules"]`
    para que `build_classes_block` lo emita en su lugar natural.
    """
    if not isinstance(node, dict):
        return

    children = node.get("children") or []
    if children and node.get("name") == "ct_div_block":
        opts = node.get("options", {})
        container_classes = opts.get("classes") or []
        # Encontrar la primera clase del container que sea display: grid
        grid_class = None
        for cls in container_classes:
            rule = default_rules.get(cls, {})
            if isinstance(rule, dict) and rule.get("display", "").strip().lower() == "grid":
                grid_class = cls
                break
        if grid_class is not None:
            rules_array = []
            for i, child in enumerate(children):
                child_classes = child.get("options", {}).get("classes") or []
                col_span = ""
                row_span = ""
                # Mergear spans desde todas las clases del hijo (modifier puede vivir
                # en una clase distinta a la base).
                for ccls in child_classes:
                    child_rule = default_rules.get(ccls, {})
                    if isinstance(child_rule, dict):
                        if "__grid_span_column__" in child_rule and not col_span:
                            col_span = child_rule["__grid_span_column__"]
                        if "__grid_span_row__" in child_rule and not row_span:
                            row_span = child_rule["__grid_span_row__"]
                rules_array.append({
                    "child-index": i,
                    "column-span": col_span,
                    "row-span": row_span,
                })
            # Solo inyectar si al menos un hijo tiene span no-default (evita ruido
            # en grids puros 1x1 que no necesitan grid-child-rules).
            if any(r["column-span"] or r["row-span"] for r in rules_array):
                default_rules[grid_class]["grid-child-rules"] = rules_array

    for child in children:
        apply_grid_child_rules(child, default_rules)


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

    # Post-proceso: construir grid-child-rules para containers display:grid cuyos
    # hijos tienen grid-column/grid-row span N (detectado y guardado como metadata
    # durante el parseo del CSS).
    apply_grid_child_rules(component_tree, default_rules)

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
