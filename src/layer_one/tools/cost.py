"""Swimlane steps: "Estimate cost" and recommending a library.

The code decides every number here; Claude only puts them into words.
"""

import math

from layer_one.constraints import (
    DENSITY_G_PER_CM3, INFILL, LIBRARIES, PRINTERS, WALL_MM, WEIGHT_MARGIN,
)


def estimate_grams(volume_mm3: float, area_mm2: float, material: str) -> float:
    """Shell plus partial infill. Ignores supports, brims, and purge."""
    shell = min(area_mm2 * WALL_MM, volume_mm3)
    printed = shell + (volume_mm3 - shell) * INFILL
    return printed / 1000 * DENSITY_G_PER_CM3[material]


def library_cost(grams: float, printer: str) -> float:
    p = PRINTERS[printer]
    # Tiers are written in whole grams, so round first. floor(x + 0.5) always rounds .5 up.
    grams = math.floor(grams + 0.5)
    for limit, price in p["tiers"]:
        if grams <= limit:  # 61 g counts as Medium until staff answer Q2
            return round(price + p["plate_fee"], 2)
    return round(grams * p["per_gram"] + p["plate_fee"], 2)


def fits(extents_mm, build_mm) -> bool:
    # Staff can rotate a model, so compare sorted dimensions (doc Section 7).
    return all(m <= b for m, b in zip(sorted(extents_mm), sorted(build_mm)))


def _color_match(wanted: str, available: list[str]) -> bool:
    wanted = wanted.lower().replace("gray", "grey").strip()
    return any(wanted in c or c in wanted for c in available)


def _money(x: float) -> str:
    return f"${x:.0f}" if x == int(x) else f"${x:.2f}"


def price_text(low: float, high: float) -> str:
    """The exact wording Layer One quotes, so it can't soften a range."""
    return _money(low) if low == high else f"{_money(low)} to {_money(high)}"


def printer_note(lib: str, printers: list[dict]) -> str:
    """Which printer would print it at this library, in words a first-timer can follow."""
    if len(printers) > 1:
        names = " and ".join(f"the {p['printer']} ({p['material']})" for p in printers)
        return (f"{lib} has two printers that could print this: {names}. Staff choose which one "
                "runs the job, so the price depends on which they use.")
    p = printers[0]
    note = f"At {lib}, this would print on the {p['printer']} in {p['material']}."
    fee = PRINTERS[p["printer"]]["plate_fee"]
    if fee:
        note += (" That printer costs more per tier than the others and adds a plate fee of "
                 f"${fee:.0f} to every job.")
    return note


def library_options(volume_mm3, area_mm2, extents_mm, material=None, color=None, preferred=None) -> dict:
    """Which libraries can print this, at what estimated price, and which to recommend."""
    options, excluded = [], []
    for lib, info in LIBRARIES.items():
        printers, reasons = [], []
        for name in info["printers"]:
            p = PRINTERS[name]
            if not fits(extents_mm, p["build_mm"]):
                reasons.append(f"too big for the {name}")
                continue
            usable = [m for m in p["materials"] if material in (None, m)]
            if color:
                usable = [m for m in usable if _color_match(color, info["colors"][m])]
            if not usable:
                reasons.append(f"the {name} doesn't offer that material or color")
                continue
            mat = usable[0]
            grams = estimate_grams(volume_mm3, area_mm2, mat)
            printers.append({
                "printer": name,
                "material": mat,
                "est_grams": round(grams, 1),
                "price_low": library_cost(grams * (1 - WEIGHT_MARGIN), name),
                "price_high": library_cost(grams * (1 + WEIGHT_MARGIN), name),
            })
        if printers:
            low = min(p["price_low"] for p in printers)
            high = max(p["price_high"] for p in printers)
            options.append({
                "library": lib,
                "printers": printers,
                "price_low": low,
                "price_high": high,
                "price_text": price_text(low, high),
                "printer_note": printer_note(lib, printers),
                "colors_in_stock": {p["material"]: info["colors"][p["material"]] for p in printers},
                "turnaround": info["turnaround"],
                "contact": info["contact"],
            })
        else:
            excluded.append({"library": lib, "reason": "; ".join(reasons)})

    if not options:
        recommended, reason = [], "No library printer can make this as designed. Route the student to staff."
    elif preferred and any(o["library"] == preferred for o in options):
        recommended, reason = [preferred], "The student's preferred library can print it."
    else:
        best = min((o["price_low"], o["price_high"]) for o in options)
        recommended = [o["library"] for o in options if (o["price_low"], o["price_high"]) == best]
        reason = "Lowest estimated price."
        if preferred:
            reason = f"{preferred} can't print it as requested; these are the lowest-priced options."

    return {"recommended": recommended, "reason": reason, "options": options, "excluded": excluded}
