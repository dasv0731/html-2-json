#!/usr/bin/env python3
"""
Runner de fixtures para oxygen-json-v3.

Estructura esperada:
    tests/fixtures/<caso>/
        input.html
        input.css
        options.json       # {"selector_suffix": "1001"}
        expected.json      # baseline; comparado byte-a-byte vs el output

Uso:
    python tests/run.py                # corre todos los fixtures
    python tests/run.py card-basico    # corre solo uno
    python tests/run.py --update       # regenera todos los expected.json
    python tests/run.py card-basico --update

Exit code:
    0 si todos pasan
    1 si al menos uno falla
"""

import argparse
import difflib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SCRIPT = ROOT / "scripts" / "transform.py"


def list_fixtures():
    return sorted(p.name for p in FIXTURES_DIR.iterdir() if p.is_dir())


def run_fixture(name: str, update: bool) -> bool:
    """Devuelve True si el fixture pasa (o se acaba de regenerar)."""
    fixture = FIXTURES_DIR / name
    html = fixture / "input.html"
    css = fixture / "input.css"
    opts_path = fixture / "options.json"
    expected_path = fixture / "expected.json"

    if not html.exists() or not css.exists():
        print(f"[SKIP] {name}: falta input.html o input.css")
        return False

    opts = json.loads(opts_path.read_text(encoding="utf-8")) if opts_path.exists() else {}
    suffix = opts.get("selector_suffix")

    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "out.json"
        cmd = [
            sys.executable,
            str(SCRIPT),
            "--html", str(html),
            "--css", str(css),
            "--out", str(out_path),
        ]
        if suffix is not None:
            cmd += ["--selector-suffix", str(suffix)]

        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if proc.returncode != 0:
            print(f"[FAIL] {name}: el script termino con codigo {proc.returncode}")
            print(proc.stderr)
            return False

        actual = out_path.read_text(encoding="utf-8")

    if update:
        expected_path.write_text(actual, encoding="utf-8")
        print(f"[UPD]  {name}: expected.json regenerado ({len(actual)} bytes)")
        return True

    if not expected_path.exists():
        print(f"[FAIL] {name}: no existe expected.json. Corre con --update para crearlo.")
        return False

    expected = expected_path.read_text(encoding="utf-8")
    if actual == expected:
        print(f"[OK]   {name}")
        return True

    print(f"[FAIL] {name}: diff vs expected.json")
    # Diff JSON-aware: pretty-print y comparar linea a linea para legibilidad.
    try:
        a_pretty = json.dumps(json.loads(actual), indent=2, ensure_ascii=False).splitlines()
        e_pretty = json.dumps(json.loads(expected), indent=2, ensure_ascii=False).splitlines()
        diff = difflib.unified_diff(e_pretty, a_pretty, fromfile="expected", tofile="actual", lineterm="")
        for line in list(diff)[:80]:
            print("  " + line)
    except json.JSONDecodeError:
        # Fallback: diff crudo
        diff = difflib.unified_diff(
            expected.splitlines(), actual.splitlines(),
            fromfile="expected", tofile="actual", lineterm="",
        )
        for line in list(diff)[:80]:
            print("  " + line)
    return False


def main():
    parser = argparse.ArgumentParser(description="Runner de fixtures oxygen-json-v3")
    parser.add_argument("fixture", nargs="?", help="Nombre de un fixture especifico (opcional)")
    parser.add_argument("--update", action="store_true", help="Regenera expected.json de los fixtures corridos")
    args = parser.parse_args()

    if not SCRIPT.exists():
        print(f"[ERR] no se encontro {SCRIPT}")
        return 2

    if args.fixture:
        targets = [args.fixture]
        if not (FIXTURES_DIR / args.fixture).is_dir():
            print(f"[ERR] fixture '{args.fixture}' no existe en {FIXTURES_DIR}")
            return 2
    else:
        targets = list_fixtures()

    if not targets:
        print("[ERR] no hay fixtures")
        return 2

    results = [run_fixture(name, args.update) for name in targets]
    passed = sum(1 for r in results if r)
    total = len(results)
    print()
    print(f"{passed}/{total} fixtures {'regenerados' if args.update else 'pasaron'}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
