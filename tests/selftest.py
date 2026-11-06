"""Free checks that need no API key. Run from the repo root: python tests/selftest.py

Run this after any change to the cost rules, library facts, or design checks.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from layer_one.tools import cost, generate  # noqa: E402

failures = 0


def expect(label, got, want):
    global failures
    ok = got == want
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'}  {label}: got {got!r}" + ("" if ok else f", want {want!r}"))


# 1. Nick's cost test table (docs/library-constraints.md, Section 7)
for grams, prices in {25: (3, 3, 13), 45: (6, 6, 18), 100: (11, 11, 28), 200: (18, 18, 40)}.items():
    for printer, want in zip(["Ultimaker S5", "Bambu X1C", "Stratasys F270"], prices):
        expect(f"{grams} g on {printer}", cost.library_cost(grams, printer), float(want))

# 2. Rounding at tier edges
expect("30.4 g rounds to Small", cost.library_cost(30.4, "Ultimaker S5"), 3.0)
expect("30.5 g rounds to Medium", cost.library_cost(30.5, "Ultimaker S5"), 6.0)

# 3. Library recommendations (volume mm^3, area mm^2, size mm)
hook = (11030, 4500, [30, 50, 24])
r = cost.library_options(*hook)
expect("hook: cheapest libraries", r["recommended"], ["Bruno", "Gorgas"])
expect("hook: Rodgers range", next((o["price_low"], o["price_high"]) for o in r["options"] if o["library"] == "Rodgers"), (3.0, 13.0))
expect("ivory only at Rodgers", cost.library_options(*hook, color="ivory")["recommended"], ["Rodgers"])
expect("orange skips Rodgers", [o["library"] for o in cost.library_options(*hook, color="orange")["options"]], ["Bruno", "Gorgas"])
expect("gray PLA only at Rodgers", cost.library_options(*hook, color="gray", material="PLA")["recommended"], ["Rodgers"])
expect("gray ABS at Bruno and Gorgas", cost.library_options(*hook, color="gray", material="ABS")["recommended"], ["Bruno", "Gorgas"])
expect("preferred library wins", cost.library_options(*hook, preferred="Rodgers")["recommended"], ["Rodgers"])
expect("ABS at Rodgers is Stratasys only", [p["printer"] for p in cost.library_options(*hook, material="ABS")["options"][2]["printers"]], ["Stratasys F270"])
expect("too big for everything", cost.library_options(1e6, 1e5, [300, 300, 300])["recommended"], [])
expect("250 mm cube: Rodgers only", [o["library"] for o in cost.library_options(1e6, 1e5, [250, 250, 250])["options"]], ["Rodgers"])

# 4. Design checks
skipped = """hole_d = 4.5; // screw hole (assumed)
width = 20; // strap width
cube([width, 10, 5]);
"""
expect("unused measurement caught", generate.unused_variables(skipped), ["hole_d"])
expect("multi-line call args ignored", generate.unused_variables("w = 3;\ncylinder(\n  d = 2,\n  h = w);\n"), [])
dims = generate.dimensions(skipped)
expect("assumed values flagged", [(d["name"], d["assumed"]) for d in dims], [("hole_d", True), ("width", False)])

print(f"\n{'All checks passed.' if not failures else f'{failures} check(s) FAILED.'}")
sys.exit(1 if failures else 0)
