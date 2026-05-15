# oxygen-json-v3

Skill de Claude que convierte HTML + CSS a JSON pegable en bloques reusables de Oxygen Builder clásico (4.x para WordPress).

Mapea tags HTML y propiedades CSS a bloques y propiedades nativas de Oxygen (`ct_div_block`, `ct_headline`, `ct_text_block`, `ct_link`, `ct_link_button`, `ct_image`, `ct_fancy_icon`, `ct_code_block`, `oxy_rich_text`). Soporta pseudo-clases y pseudo-elementos como states nativos. Preserva atributos HTML (`aria-*`, `data-*`, `role`, etc.) como `custom-attributes`.

## Estructura del repo

```
.
├── SKILL.md                       # Punto de entrada del skill (frontmatter + flujo)
├── CHANGELOG.md                   # Registro de cambios incrementales
├── scripts/
│   └── transform.py               # Script Python determinista que hace la conversión
└── references/
    ├── block-types.md             # Tabla HTML tag → tipo de bloque Oxygen
    ├── property-mappings.md       # Mapeo CSS → propiedades Oxygen, expansión de shorthands
    └── oxygen-quirks.md           # Anomalías y comportamientos no obvios de Oxygen
```

## Uso como skill de Claude

Clonar este repo dentro de la carpeta de skills de Claude (típicamente `/mnt/skills/user/` o equivalente). Claude lee `SKILL.md` para activar el skill cuando detecta una consulta relevante (HTML/CSS a JSON de Oxygen).

## Uso directo del script

```bash
python3 scripts/transform.py \
  --html input.html \
  --css input.css \
  --out output.json \
  --selector-suffix 1908
```

- `--html`, `--css`: paths a los archivos de entrada.
- `--out`: path donde escribir el JSON resultante.
- `--selector-suffix`: número que va al final de los selectores Oxygen (`div_block-2-1908`). Si no se pasa, se genera aleatorio. Oxygen lo reasigna al pegar.

Salida en stderr: avisos sobre qué se mapeó nativamente, qué se mandó a `custom-css`, qué se mandó al Code Block, qué clases vacías se preservaron.

## Contrato de input

Ver `SKILL.md` sección "Contrato de input" para reglas estrictas sobre HTML y CSS válidos.

Resumen:
- Una clase por elemento en `class`. Múltiples clases separadas por espacio están bien.
- Sin `style="..."` inline.
- Una regla por clase en CSS. Selectores con combinadores van al Code Block automáticamente.
- Media queries con `max-width` se mapean a breakpoints de Oxygen; `min-width` va al Code Block.

## Versión

`v3` consolida tres fases de descubrimiento documentadas en `SKILL.md`. Para cambios post-release, ver `CHANGELOG.md`.
