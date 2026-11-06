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
Claude runs the conversation and decides which tool to call. The tools make the actual decisions, so policy, printer fit, and cost are deterministic and come from `docs/library-constraints.md`, not from the model guessing.

| Swimlane step | Tool |
|---|---|
| Request allowed? | `tools/policy.py` |
| Search approved 3D model sites | `tools/search.py` |
| Generate file and preview | `tools/generate.py` (Claude writes OpenSCAD, rendered to STL + PNG) |
| Check size, STL, and printer fit | `tools/printability.py` (trimesh) |
| Estimate cost | `tools/cost.py` |

Submission, staff review, and printing stay in the library's existing request system.

## Stack
Python, Anthropic API (tool use), FastAPI, OpenSCAD, trimesh. Prototype hosted on a Proxmox homelab.

## Setup
1. Install OpenSCAD (`sudo apt install openscad` on Debian/Ubuntu).
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and add your Anthropic API key. Never commit `.env`.

## Status
- [ ] Library constraints documented
- [ ] Generation spike (text → OpenSCAD → STL → preview → checks)
- [ ] Model search spike
- [ ] Claude tool-use loop
- [ ] Web front end
- [ ] Hosted on homelab
