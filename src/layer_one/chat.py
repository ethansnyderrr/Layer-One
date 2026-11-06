"""Layer One conversation: the tools Claude can call, and one turn of the chat.

Run the terminal version from the repo root with: python chat.py
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from layer_one.constraints import OUTPUT_DIR, PRINT_PAGE_URL, REPO_ROOT, REQUEST_FORM_URL
from layer_one.tools import cost, generate, printability, search

DEFAULT_MODEL = "claude-sonnet-5-5"  # override with LAYER_ONE_MODEL in .env
SYSTEM_PROMPT = (Path(__file__).resolve().parent / "prompts" / "layer_one.md").read_text()
GREETING = (
    "Hi, I'm Layer One, an AI guide for UA Libraries' 3D printing service. "
    "What are you hoping to print today? Tell me what it is, what it's for, and any "
    "measurements you have. The more detail, the better I can help."
)

PRINT_OPTIONS = {
    "material": {
        "type": "string", "enum": ["PLA", "ABS"],
        "description": "Only if the student needs a specific material, such as ABS for heat.",
    },
    "color": {"type": "string", "description": "Only if the student asked for a color, or asked you to pick one."},
    "preferred_library": {"type": "string", "enum": ["Bruno", "Gorgas", "Rodgers"]},
}

TOOLS = [
    {
        "name": "design_part",
        "description": (
            "Design a new printable part. Writes the design, renders the .stl and a preview, "
            "checks it, and prices it at each library. Takes up to a minute. Only call this "
            "after the request passes the library rules and the student chose to have you design it."
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
                **PRINT_OPTIONS,
            },
            "required": ["brief"],
        },
    },
    {
        "name": "search_models",
        "description": (
            "Search Thingiverse for existing models. Returns up to 5 that have an STL file and a "
            "license that allows printing. The app shows them to the student as cards with pictures. "
            "Only call this after the request passes the library rules and the student chose to search."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "2 to 4 English keywords, like 'backpack wall hook'."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "use_model",
        "description": (
            "Download the STL file the student picked from a search result, then check it, preview it, "
            "and price it at each library, the same way as a designed part."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "thing_id": {"type": "integer", "description": "thing_id from the search result."},
                "file_id": {"type": "integer", "description": "file_id of the STL to print, from stl_files."},
                **PRINT_OPTIONS,
            },
            "required": ["thing_id", "file_id"],
        },
    },
]


def new_conversation() -> list:
    """The greeting is fixed text, so a conversation starts without an API call."""
    return [
        {"role": "user", "content": "[A student just opened Layer One.]"},
        {"role": "assistant", "content": GREETING},
    ]


def _new_output_dir(label: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower())[:40].strip("-") or "part"
    out_dir = OUTPUT_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-{slug}"
    out_dir.mkdir(parents=True)
    return out_dir


def _check_and_price(out_dir, stl_path, material, color, preferred_library) -> dict:
    """Checks, preview, and pricing shared by designed and found models."""
    mesh, facts = printability.check(stl_path)
    printability.render_preview(mesh, out_dir / "preview.png")
    return {
        "design_id": out_dir.name,
        "files_shown_to_student": "The app shows the preview picture and download buttons for the files.",
        "checks": facts,
        "pricing": cost.library_options(
            mesh.volume, mesh.area, facts["size_mm_print_orientation"],
            material=material, color=color, preferred=preferred_library,
        ),
        "pricing_note": "Estimates only. Library staff confirm the final cost when they approve the request.",
        "links": {"request_form": REQUEST_FORM_URL, "print_page": PRINT_PAGE_URL},
    }


def design_part(client, brief, material=None, color=None, preferred_library=None) -> dict:
    out_dir = _new_output_dir(brief)
    stl_path = generate.generate(client, brief, out_dir)
    scad = (out_dir / "model.scad").read_text()
    result = _check_and_price(out_dir, stl_path, material, color, preferred_library)
    result["dimensions"] = generate.dimensions(scad)
    result["unused_variables"] = generate.unused_variables(scad)
    (out_dir / "report.json").write_text(json.dumps(result, indent=2))
    return result


def use_model(client, thing_id, file_id, material=None, color=None, preferred_library=None) -> dict:
    out_dir = _new_output_dir(f"thingiverse-{thing_id}")
    stl_path, model = search.download(thing_id, file_id, out_dir)
    result = _check_and_price(out_dir, stl_path, material, color, preferred_library)
    biggest = max(result["checks"]["size_mm_print_orientation"])
    result["source"] = {k: model[k] for k in ("name", "creator", "url", "license", "license_status")}
    result["source"]["file"] = next(f["name"] for f in model["stl_files"] if f["file_id"] == file_id)
    result["source_note"] = "Paste the source url into the request form's source URL field."
    if biggest < 5 or biggest > 400:
        result["size_warning"] = (f"The largest side is {biggest} mm, which is unusual. The file may "
                                  "have been made in inches or another unit; staff can rescale it.")
    (out_dir / "report.json").write_text(json.dumps(result, indent=2))
    return result


def run_tool(client, name, args, on_status=None) -> tuple[dict, bool]:
    """Returns (result, is_error)."""
    if on_status:
        on_status(name)
    try:
        if name == "design_part":
            return design_part(client, **args), False
        if name == "search_models":
            return search.search_models(args["query"]), False
        if name == "use_model":
            return use_model(client, **args), False
    except (generate.GenerationError, search.SearchError) as e:
        return {"error": str(e)}, True
    return {"error": f"Unknown tool {name}"}, True


def run_turn(client, messages, on_status=None) -> list[dict]:
    """Sends the conversation to Claude and runs any tools it asks for.

    Returns the turn as a list of bubbles:
    {"text": ..., "designs": [{"id", "source"}], "searches": [search results]}.
    """
    model = os.getenv("LAYER_ONE_MODEL", DEFAULT_MODEL)
    bubbles, designs, searches = [], [], []
    while True:
        response = client.messages.create(
            model=model, max_tokens=2000, system=SYSTEM_PROMPT, tools=TOOLS, messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if response.stop_reason != "tool_use":
            bubbles.append({"text": text, "designs": designs, "searches": searches})
            return bubbles
        if text:
            bubbles.append({"text": text, "designs": [], "searches": []})
        results = []
        for block in response.content:
            if block.type == "tool_use":
                result, is_error = run_tool(client, block.name, block.input, on_status)
                if not is_error and "design_id" in result:
                    designs.append({"id": result["design_id"], "source": result.get("source")})
                elif not is_error and block.name == "search_models":
                    searches.append(result["results"])
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

    status = {"design_part": "designing", "search_models": "searching Thingiverse", "use_model": "downloading"}
    print("Layer One terminal (type 'quit' to leave). For the full version, run: python web.py\n")
    print(f"\nLayer One: {GREETING}\n")
    messages = new_conversation()
    while True:
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
        try:
            bubbles = run_turn(client, messages, on_status=lambda n: print(f"\n  ({status.get(n, n)}...)"))
        except anthropic.APIError as e:
            sys.exit(f"\nCouldn't reach Claude: {e}\nCheck the API key and LAYER_ONE_MODEL in .env.")
        for bubble in bubbles:
            print(f"\nLayer One: {bubble['text']}\n")
            for results in bubble["searches"]:
                for i, r in enumerate(results, 1):
                    print(f"  {i}. {r['name']} by {r['creator']} ({r['license']}) {r['url']}")
                print()
            for d in bubble["designs"]:
                print(f"  [files saved in {OUTPUT_DIR / d['id']}]\n")


if __name__ == "__main__":
    main()
