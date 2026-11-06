# Layer One

Layer One is the guide on the library's 3D printing page that takes a plain-words description, searches free model libraries first, falls back to generating an STL with a preview, checks printability, and explains cost, submission, and pickup.

MIS 430 team project, University of Alabama, Fall 2026.

![Future state swimlane](docs/future-state-swimlane.png)

## Team
- Ethan Snyder: Lead Developer
- Aiden Bulloch: Project Manager
- Blake Thomas: Analyst
- Nick Brooks: Product Owner

## How it works
Claude runs the conversation and decides when to call a tool. The tools make the actual decisions, so policy, printer fit, and cost are deterministic and come from `docs/library-constraints.md`, not from the model guessing.

| Swimlane step | Where it lives |
|---|---|
| Request allowed? | `src/layer_one/prompts/layer_one.md` (library rules) |
| Search approved 3D model sites | `src/layer_one/tools/search.py` (Thingiverse API; GrabCAD has no public API) |
| Generate file and preview | `src/layer_one/tools/generate.py` (Claude writes OpenSCAD, rendered to STL) |
| Check size, STL, and printer fit | `src/layer_one/tools/printability.py` (trimesh) |
| Estimate cost, recommend a library | `src/layer_one/tools/cost.py` |

Library facts used by the code are in `src/layer_one/constraints.py`. Update it whenever `docs/library-constraints.md` changes.

Submission, staff review, and printing stay in the library's existing request system.

## Shaping how Layer One behaves
- `src/layer_one/prompts/layer_one.md`: Layer One's instructions (personality, conversation flow, library rules). Plain English, edit freely.
- `src/layer_one/prompts/openscad.md`: rules for the behind-the-scenes call that writes the 3D design.

## Stack
Python, Anthropic API (tool use), FastAPI, OpenSCAD, trimesh. Prototype hosted on a Proxmox homelab.

## Setup
1. Install OpenSCAD (`apt install openscad` on Debian).
2. `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and add your Anthropic API key and Thingiverse App Token (from thingiverse.com/apps/create). Never commit `.env`.

## Run
- `python web.py`: start the web version, then open `http://<server IP>:8000`. Shows the preview and download buttons for each design.
- `python chat.py`: the same conversation in the terminal, handy for quick testing. Each design is saved in `output/`.
- `python tests/selftest.py`: free checks (no API calls) for cost, library picks, and design checks. Run after any change.

## Status
- [x] Library constraints documented
- [x] Generation spike (text → OpenSCAD → STL → preview → checks)
- [x] Terminal chat with design, checks, pricing, and library recommendation
- [x] Web chat page with preview picture and .stl/.scad downloads
- [x] Model search (Thingiverse)
- [ ] Upright preview and spinnable 3D viewer
- [ ] Always-on hosting on the homelab (fixed IP, starts on boot)
