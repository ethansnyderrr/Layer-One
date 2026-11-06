"""Generation spike: plain-words description -> OpenSCAD -> STL -> preview -> checks -> cost.

Throwaway code to prove the "Generate file and preview" and "Check size, STL,
and printer fit" boxes work before building them for real in src/.

Usage (run from the repo root):
    python spikes/generate_spike.py "a wall hook for a 20 mm strap that sticks out 25 mm"
    python spikes/generate_spike.py --scad path/to/model.scad   # skip Claude, test the pipeline only
    python spikes/generate_spike.py --selftest                  # check cost logic against the doc's test table

Needs: OpenSCAD on PATH, `pip install -r requirements.txt`, and ANTHROPIC_API_KEY in .env
(only for the Claude path). Printer, fee, and tier numbers come from docs/library-constraints.md.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: the homelab LXC has no display
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from dotenv import load_dotenv
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "output"
MODEL = os.getenv("LAYER_ONE_MODEL", "claude-sonnet-5-5")
MAX_ATTEMPTS = 3  # Claude gets the OpenSCAD error back and retries this many times total

# --- Library constraints (docs/library-constraints.md, Sections 1 and 3) -------------
PRINTERS = {
    "Ultimaker S5": {
        "libraries": ["Bruno", "Gorgas"],
        "build_mm": (330, 240, 300),
        "material": "PLA",  # also prints ABS; PLA assumed as the default for estimates
        "tiers": [(30, 3.00), (61, 6.00), (120, 11.00)],
        "per_gram": 0.09,
        "plate_fee": 0.00,
    },
    "Bambu X1C": {
        "libraries": ["Rodgers"],
        "build_mm": (256, 256, 256),
        "material": "PLA",
        "tiers": [(30, 3.00), (61, 6.00), (120, 11.00)],
        "per_gram": 0.09,
        "plate_fee": 0.00,  # Q1 open: may be $8
    },
    "Stratasys F270": {
        "libraries": ["Rodgers"],
        "build_mm": (305, 254, 305),
        "material": "ABS",
        "tiers": [(30, 5.00), (61, 10.00), (120, 20.00)],
        "per_gram": 0.16,
        "plate_fee": 8.00,
    },
}

# --- Weight estimate assumptions (placeholders until staff answer Q4) ----------------
DENSITY_G_PER_CM3 = {"PLA": 1.24, "ABS": 1.04}  # typical filament densities
WALL_MM = 1.2   # roughly 3 perimeters at a 0.4 mm nozzle
INFILL = 0.20   # 20% infill

SYSTEM_PROMPT = """You write OpenSCAD programs for parts that will be 3D printed at a university library.

Rules:
- Respond with exactly one ```openscad code block and nothing else.
- Units are millimeters.
- Put every dimension in a named variable at the top, each with a short comment.
- If the description leaves out a measurement, choose a sensible default and say so in that variable's comment.
- The result must be one connected solid that sits flat on z = 0.
- Prefer shapes that print without supports. Keep walls at least 2 mm thick.
- Use only built-in OpenSCAD features: no import(), include, use, or external libraries.
- Set $fn = 64 for curved surfaces."""


# --- Step 1: Claude writes OpenSCAD -------------------------------------------------
def extract_scad(text: str) -> str:
    match = re.search(r"```(?:openscad|scad)?\s*\n(.*?)```", text, re.DOTALL)
    return (match.group(1) if match else text).strip() + "\n"


def ask_claude(messages: list) -> str:
    import anthropic  # imported here so --scad and --selftest work without the SDK configured

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    response = client.messages.create(
        model=MODEL, max_tokens=4000, system=SYSTEM_PROMPT, messages=messages
    )
    return "".join(block.text for block in response.content if block.type == "text")


# --- Step 2: OpenSCAD renders the STL -----------------------------------------------
def render_stl(scad_path: Path, stl_path: Path) -> tuple[bool, str]:
    if stl_path.exists():
        stl_path.unlink()
    try:
        result = subprocess.run(
            ["openscad", "-o", str(stl_path), str(scad_path)],
            capture_output=True, text=True, timeout=180,
        )
    except FileNotFoundError:
        sys.exit("OpenSCAD isn't installed or isn't on PATH.")
    except subprocess.TimeoutExpired:
        return False, "OpenSCAD timed out after 180 seconds; the model is too complex."
    ok = result.returncode == 0 and stl_path.exists() and stl_path.stat().st_size > 0
    return ok, result.stderr.strip()


def generate(description: str, out_dir: Path) -> Path:
    scad_path, stl_path = out_dir / "model.scad", out_dir / "model.stl"
    messages = [{"role": "user", "content": description}]
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"Asking Claude for OpenSCAD (attempt {attempt}/{MAX_ATTEMPTS})...")
        reply = ask_claude(messages)
        scad_path.write_text(extract_scad(reply))
        ok, log = render_stl(scad_path, stl_path)
        if ok:
            return stl_path
        print("OpenSCAD failed; sending the error back to Claude.")
        messages += [
            {"role": "assistant", "content": reply},
            {"role": "user", "content": f"OpenSCAD failed with this output. Fix the program.\n\n{log[-3000:]}"},
        ]
    sys.exit(f"No valid STL after {MAX_ATTEMPTS} attempts. Last OpenSCAD output:\n{log}")


# --- Step 3: preview image (matplotlib, since OpenSCAD's PNG export needs a display) --
def render_preview(mesh: trimesh.Trimesh, png_path: Path) -> None:
    # matplotlib draws faces back to front by their center, so long thin triangles
    # overlap wrongly. Splitting them into smaller ones fixes most of that.
    vertices, faces = trimesh.remesh.subdivide_to_size(
        mesh.vertices, mesh.faces, max_edge=max(mesh.extents) / 30, max_iter=8
    )
    view = trimesh.Trimesh(vertices, faces, process=False)

    light = np.array([0.4, -0.6, 0.7])
    light /= np.linalg.norm(light)
    shade = np.clip(view.face_normals @ light, 0.0, 1.0)
    base = np.array([0.62, 0.11, 0.20])  # crimson
    rgb = np.outer(0.45 + 0.55 * shade, base)
    colors = np.column_stack([rgb, np.ones(len(rgb))])

    fig = plt.figure(figsize=(6, 6), dpi=150)
    ax = fig.add_subplot(projection="3d")
    ax.add_collection3d(Poly3DCollection(view.triangles, facecolors=colors, linewidths=0))
    lo, hi = mesh.bounds
    ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
    ax.set_box_aspect(np.maximum(mesh.extents, 1e-6))
    ax.view_init(elev=25, azim=-60)
    ax.set_xlabel("X (mm)"); ax.set_ylabel("Y (mm)"); ax.set_zlabel("Z (mm)")
    fig.savefig(png_path, bbox_inches="tight")
    plt.close(fig)


# --- Step 4: trimesh checks ---------------------------------------------------------
def fits(extents_mm, build_mm) -> bool:
    # Staff can rotate a model, so compare sorted dimensions (doc Section 7).
    return all(m <= b for m, b in zip(sorted(extents_mm), sorted(build_mm)))


def estimate_grams(mesh: trimesh.Trimesh, material: str) -> tuple[float, float]:
    """Returns (estimate, solid upper bound). Ignores supports, brims, and purge."""
    density = DENSITY_G_PER_CM3[material]
    volume = mesh.volume  # mm^3
    shell = min(mesh.area * WALL_MM, volume)
    printed = shell + (volume - shell) * INFILL
    return printed / 1000 * density, volume / 1000 * density


# --- Step 5: cost (doc Sections 3 and 7) --------------------------------------------
def library_cost(grams: float, printer: str) -> float:
    p = PRINTERS[printer]
    for limit, price in p["tiers"]:
        if grams <= limit:  # 61 g counts as Medium until staff answer Q2
            return round(price + p["plate_fee"], 2)
    return round(grams * p["per_gram"] + p["plate_fee"], 2)


def check(stl_path: Path) -> dict:
    mesh = trimesh.load(stl_path, force="mesh")
    extents = [round(float(x), 1) for x in mesh.extents]
    report = {
        "watertight": bool(mesh.is_watertight),
        "faces_point_consistently": bool(mesh.is_winding_consistent),
        "separate_pieces": int(mesh.body_count),
        "size_mm": extents,
        "volume_cm3": round(mesh.volume / 1000, 2),
        "printers": {},
    }
    for name, p in PRINTERS.items():
        est, solid = estimate_grams(mesh, p["material"])
        report["printers"][name] = {
            "libraries": p["libraries"],
            "material": p["material"],
            "fits_printer": fits(extents, p["build_mm"]),
            "est_grams": round(est, 1),
            "solid_grams_upper_bound": round(solid, 1),
            "est_cost": library_cost(est, name),
        }
    render_preview(mesh, stl_path.with_name("preview.png"))
    return report


def selftest() -> None:
    # Test table from docs/library-constraints.md Section 7 (Bambu assumes no plate fee).
    expected = {
        25: (3.00, 3.00, 13.00),
        45: (6.00, 6.00, 18.00),
        100: (11.00, 11.00, 28.00),
        200: (18.00, 18.00, 40.00),
    }
    names = ["Ultimaker S5", "Bambu X1C", "Stratasys F270"]
    failures = 0
    for grams, costs in expected.items():
        for name, want in zip(names, costs):
            got = library_cost(grams, name)
            status = "ok" if got == want else "FAIL"
            failures += status == "FAIL"
            print(f"{status:4}  {grams:>3} g  {name:<15} want ${want:.2f}  got ${got:.2f}")
    sys.exit(1 if failures else 0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("description", nargs="?", help="what the student needs, in plain words")
    parser.add_argument("--scad", type=Path, help="render this .scad file instead of asking Claude")
    parser.add_argument("--selftest", action="store_true", help="check cost logic against the doc")
    args = parser.parse_args()

    if args.selftest:
        selftest()
    if not args.description and not args.scad:
        parser.error("give a description or --scad")

    load_dotenv(REPO_ROOT / ".env")
    label = args.scad.stem if args.scad else re.sub(r"[^a-z0-9]+", "-", args.description.lower())[:40].strip("-")
    out_dir = OUTPUT_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-{label}"
    out_dir.mkdir(parents=True)

    if args.scad:
        stl_path = out_dir / "model.stl"
        (out_dir / "model.scad").write_text(args.scad.read_text())
        ok, log = render_stl(out_dir / "model.scad", stl_path)
        if not ok:
            sys.exit(f"OpenSCAD failed:\n{log}")
    else:
        if not os.getenv("ANTHROPIC_API_KEY"):
            sys.exit("ANTHROPIC_API_KEY isn't set. Add it to .env in the repo root.")
        stl_path = generate(args.description, out_dir)

    report = check(stl_path)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"\nFiles in {out_dir}: model.scad, model.stl, preview.png, report.json")


if __name__ == "__main__":
    main()
