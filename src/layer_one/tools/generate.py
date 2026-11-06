"""Swimlane step: "Generate file and preview"

Claude writes parametric OpenSCAD from the design brief; the OpenSCAD CLI renders it
to an STL. If OpenSCAD fails, or Claude defines a measurement it never uses, the
problem goes back to Claude to fix.
"""

import os
import re
import subprocess
from pathlib import Path

DEFAULT_MODEL = "claude-sonnet-5-5"  # override with LAYER_ONE_MODEL in .env
MAX_ATTEMPTS = 3
PROMPT = (Path(__file__).resolve().parents[1] / "prompts" / "openscad.md").read_text()


class GenerationError(Exception):
    pass


def extract_scad(text: str) -> str:
    match = re.search(r"```(?:openscad|scad)?\s*\n(.*?)```", text, re.DOTALL)
    return (match.group(1) if match else text).strip() + "\n"


def _strip_comments(scad: str) -> str:
    code = re.sub(r"/\*.*?\*/", "", scad, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", code)


def _top_level_names(code: str) -> list[str]:
    names, depth, start = [], 0, 0
    for i, ch in enumerate(code):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if depth == 0 and (ch == ";" or ch == "}"):
            m = re.match(r"\s*([A-Za-z_]\w*)\s*=(?!=)", code[start:i + 1])
            if m:
                names.append(m.group(1))
            start = i + 1
    return names


def unused_variables(scad: str) -> list[str]:
    """Top-level variables that are defined but never used, a sign Claude skipped a feature."""
    code = _strip_comments(scad)
    return [n for n in _top_level_names(code) if len(re.findall(rf"\b{n}\b", code)) == 1]


def dimensions(scad: str) -> list[dict]:
    """Each top-level measurement with its comment, flagging the ones Claude assumed."""
    found = []
    for line in scad.splitlines():
        m = re.match(r"\s*([A-Za-z_]\w*)\s*=\s*([^;]+);\s*(?://\s*(.*))?$", line)
        if m:
            note = (m.group(3) or "").strip()
            found.append({
                "name": m.group(1),
                "value": m.group(2).strip(),
                "note": note,
                "assumed": bool(re.search(r"assum|default", note, re.IGNORECASE)),
            })
    return found


def render_stl(scad_path: Path, stl_path: Path) -> tuple[bool, str]:
    if stl_path.exists():
        stl_path.unlink()
    try:
        result = subprocess.run(
            ["openscad", "-o", str(stl_path), str(scad_path)],
            capture_output=True, text=True, timeout=180,
        )
    except FileNotFoundError:
        raise GenerationError("OpenSCAD isn't installed or isn't on PATH.")
    except subprocess.TimeoutExpired:
        return False, "OpenSCAD timed out after 180 seconds; the model is too complex."
    ok = result.returncode == 0 and stl_path.exists() and stl_path.stat().st_size > 0
    return ok, result.stderr.strip()


def ask_claude(client, messages: list) -> str:
    model = os.getenv("LAYER_ONE_MODEL", DEFAULT_MODEL)
    response = client.messages.create(model=model, max_tokens=4000, system=PROMPT, messages=messages)
    return "".join(block.text for block in response.content if block.type == "text")


def generate(client, brief: str, out_dir: Path, log=print) -> Path:
    """Returns the path to a rendered STL, or raises GenerationError."""
    scad_path, stl_path = out_dir / "model.scad", out_dir / "model.stl"
    messages = [{"role": "user", "content": brief}]
    for attempt in range(1, MAX_ATTEMPTS + 1):
        reply = ask_claude(client, messages)
        scad_path.write_text(extract_scad(reply))
        ok, output = render_stl(scad_path, stl_path)
        unused = unused_variables(scad_path.read_text()) if ok else []
        if ok and (not unused or attempt == MAX_ATTEMPTS):
            return stl_path
        if attempt == MAX_ATTEMPTS:
            break
        if ok:
            log(f"  (attempt {attempt}: unused measurements {', '.join(unused)}; asking for a fix)")
            feedback = (f"These variables are defined but never used: {', '.join(unused)}. "
                        "Use each one in the geometry, or remove it if it isn't needed.")
        else:
            log(f"  (attempt {attempt}: OpenSCAD error; asking for a fix)")
            feedback = f"OpenSCAD failed with this output. Fix the program.\n\n{output[-3000:]}"
        messages += [
            {"role": "assistant", "content": reply},
            {"role": "user", "content": feedback},
        ]
    raise GenerationError(f"No valid STL after {MAX_ATTEMPTS} attempts. Last OpenSCAD output: {output[-500:]}")
