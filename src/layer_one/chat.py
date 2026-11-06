"""Layer One terminal chat. Run from the repo root with: python chat.py"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from layer_one.constraints import OUTPUT_DIR, PRINT_PAGE_URL, REPO_ROOT, REQUEST_FORM_URL
from layer_one.tools import cost, generate, printability

DEFAULT_MODEL = "claude-sonnet-5-5"  # override with LAYER_ONE_MODEL in .env
SYSTEM_PROMPT = (Path(__file__).resolve().parent / "prompts" / "layer_one.md").read_text()
KICKOFF = "[A student just opened Layer One. Greet them.]"

TOOLS = [{
    "name": "design_part",
    "description": (
        "Design a new printable part. Writes the design, renders the .stl and a preview, "
        "checks it, and prices it at each library. Takes up to a minute. Only call this "
        "after the request passes the library rules and you have enough detail."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "brief": {
                "type": "string",
                "description": "Complete design brief: what the part is and what it's for, every "
                               "measurement the student gave (converted to mm), mounting, load, "
                               "environment, and any changes requested to an earlier version.",
            },
            "material": {
                "type": "string", "enum": ["PLA", "ABS"],
                "description": "Only if the student needs a specific material, such as ABS for heat.",
            },
            "color": {"type": "string", "description": "Only if the student asked for a color."},
            "preferred_library": {"type": "string", "enum": ["Bruno", "Gorgas", "Rodgers"]},
        },
        "required": ["brief"],
    },
}]


def design_part(client, brief, material=None, color=None, preferred_library=None) -> dict:
    label = re.sub(r"[^a-z0-9]+", "-", brief.lower())[:40].strip("-")
    out_dir = OUTPUT_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-{label}"
    out_dir.mkdir(parents=True)

    stl_path = generate.generate(client, brief, out_dir)
    scad = (out_dir / "model.scad").read_text()
    mesh, facts = printability.check(stl_path)
    printability.render_preview(mesh, out_dir / "preview.png")

    result = {
        "folder": str(out_dir),
        "files": {
            "stl": str(stl_path),
            "scad": str(out_dir / "model.scad"),
            "preview": str(out_dir / "preview.png"),
            "report": str(out_dir / "report.txt"),
        },
        "checks": facts,
        "dimensions": generate.dimensions(scad),
        "unused_variables": generate.unused_variables(scad),
        "pricing": cost.library_options(
            mesh.volume, mesh.area, facts["size_mm_print_orientation"],
            material=material, color=color, preferred=preferred_library,
        ),
        "pricing_note": "Estimates only. Library staff confirm the final cost when they approve the request.",
        "links": {"request_form": REQUEST_FORM_URL, "print_page": PRINT_PAGE_URL},
    }
    (out_dir / "report.json").write_text(json.dumps(result, indent=2))
    return result


def run_tool(client, name, args) -> tuple[dict, bool]:
    """Returns (result, is_error)."""
    if name != "design_part":
        return {"error": f"Unknown tool {name}"}, True
    print("\n  (designing...)")
    try:
        return design_part(client, **args), False
    except generate.GenerationError as e:
        return {"error": str(e)}, True


def run_turn(client, messages) -> str:
    """Sends the conversation to Claude, runs any tools it asks for, and returns its reply."""
    model = os.getenv("LAYER_ONE_MODEL", DEFAULT_MODEL)
    design_folders = []
    while True:
        response = client.messages.create(
            model=model, max_tokens=2000, system=SYSTEM_PROMPT, tools=TOOLS, messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if response.stop_reason != "tool_use":
            # Save Layer One's plain-English write-up next to the files it describes.
            for folder in design_folders:
                (Path(folder) / "report.txt").write_text(text + "\n")
            return text
        if text:
            print(f"\nLayer One: {text}")
        results = []
        for block in response.content:
            if block.type == "tool_use":
                result, is_error = run_tool(client, block.name, block.input)
                if not is_error:
                    design_folders.append(result["folder"])
                results.append({
                    "type": "tool_result", "tool_use_id": block.id,
                    "content": json.dumps(result), "is_error": is_error,
                })
        messages.append({"role": "user", "content": results})


def main(client=None) -> None:
    load_dotenv(REPO_ROOT / ".env")
    if client is None:
        if not os.getenv("ANTHROPIC_API_KEY"):
            sys.exit("ANTHROPIC_API_KEY isn't set. Add it to .env in the repo root.")
        client = anthropic.Anthropic()

    print("Layer One (type 'quit' to leave)\n")
    messages = [{"role": "user", "content": KICKOFF}]
    while True:
        try:
            reply = run_turn(client, messages)
        except anthropic.APIError as e:
            sys.exit(f"\nCouldn't reach Claude: {e}\nCheck the API key and LAYER_ONE_MODEL in .env.")
        print(f"\nLayer One: {reply}\n")
        user = ""
        while not user:
            try:
                user = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
        if user.lower() in {"quit", "exit"}:
            return
        messages.append({"role": "user", "content": user})


if __name__ == "__main__":
    main()
