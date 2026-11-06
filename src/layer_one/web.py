"""Layer One web app. Run from the repo root with: python web.py"""

import re
import threading
import traceback
import uuid
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from layer_one.chat import GREETING, new_conversation, run_turn
from layer_one.constraints import OUTPUT_DIR, REPO_ROOT

load_dotenv(REPO_ROOT / ".env")

STATIC = Path(__file__).resolve().parent / "static"
DESIGN_ID = re.compile(r"^\d{8}-\d{6}-[a-z0-9-]+$")
FILES = {
    "preview": ("preview.png", None),
    "stl": ("model.stl", "stl"),
    "scad": ("model.scad", "scad"),
}

app = FastAPI(title="Layer One")
app.state.client = None
sessions: dict[str, dict] = {}  # kept in memory; restarting the server clears them


class ChatIn(BaseModel):
    session_id: str
    message: str


def get_client():
    if app.state.client is None:
        try:
            app.state.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from .env
        except anthropic.AnthropicError:
            raise HTTPException(500, "The server has no Anthropic API key. Add it to .env and restart.")
    return app.state.client


def design_links(design: dict) -> dict:
    """URLs for the page. Found models have no .scad, and carry their source for credit."""
    design_id = design["id"]
    links = {"id": design_id, "preview": f"/files/{design_id}/preview", "stl": f"/files/{design_id}/stl"}
    if (OUTPUT_DIR / design_id / "model.scad").is_file():
        links["scad"] = f"/files/{design_id}/scad"
    source = design.get("source")
    if source and _thingiverse_url(source.get("url")):
        links["source"] = {k: str(source.get(k, "")) for k in ("name", "creator", "url", "license", "file")}
    return links


def _thingiverse_url(url) -> bool:
    """Third-party links and images only render if they point at Thingiverse."""
    return isinstance(url, str) and url.startswith(("https://www.thingiverse.com/", "https://cdn.thingiverse.com/"))


def search_cards(results: list) -> list:
    cards = []
    for i, r in enumerate(results, 1):
        if not _thingiverse_url(r.get("url")):
            continue
        cards.append({
            "number": i,
            "name": str(r.get("name", "")),
            "creator": str(r.get("creator", "")),
            "url": r["url"],
            "image": r.get("image") if _thingiverse_url(r.get("image")) else "",
            "license": str(r.get("license", "")),
            "likes": int(r.get("likes") or 0),
        })
    return cards


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.post("/api/start")
def start():
    session_id = uuid.uuid4().hex
    sessions[session_id] = {"messages": new_conversation(), "lock": threading.Lock()}
    return {"session_id": session_id, "greeting": GREETING}


@app.post("/api/chat")
def chat(body: ChatIn):
    session = sessions.get(body.session_id)
    if session is None:
        raise HTTPException(404, "This chat has expired. Refresh the page to start a new one.")
    text = body.message.strip()
    if not text:
        raise HTTPException(400, "Type a message first.")
    if len(text) > 4000:
        raise HTTPException(400, "That message is too long. Keep it under 4,000 characters.")
    if not session["lock"].acquire(blocking=False):
        raise HTTPException(409, "Layer One is still answering your last message.")

    messages = session["messages"]
    checkpoint = len(messages)  # undo point if this turn fails partway
    try:
        messages.append({"role": "user", "content": text})
        bubbles = run_turn(get_client(), messages)
    except anthropic.APIError as e:
        del messages[checkpoint:]
        raise HTTPException(502, f"Couldn't reach Claude ({getattr(e, 'status_code', 'no response')}). "
                                 "Check the API key and model in .env, then try again.")
    except HTTPException:
        del messages[checkpoint:]
        raise
    except Exception:
        del messages[checkpoint:]
        traceback.print_exc()
        raise HTTPException(500, "Something went wrong on the server. Try sending that again.")
    finally:
        session["lock"].release()

    return {"bubbles": [
        {
            "text": b["text"],
            "designs": [design_links(d) for d in b["designs"]],
            "searches": [search_cards(results) for results in b["searches"]],
        }
        for b in bubbles
    ]}


@app.get("/files/{design_id}/{kind}")
def files(design_id: str, kind: str):
    if not DESIGN_ID.match(design_id) or kind not in FILES:
        raise HTTPException(404, "File not found.")
    filename, ext = FILES[kind]
    path = OUTPUT_DIR / design_id / filename
    if not path.is_file():
        raise HTTPException(404, "File not found.")
    if ext is None:
        return FileResponse(path, media_type="image/png")
    name = design_id[16:] or "part"  # drop the timestamp
    return FileResponse(path, media_type="application/octet-stream", filename=f"layer-one-{name}.{ext}")
