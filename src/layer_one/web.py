"""Layer One web app. Run from the repo root with: python web.py"""

import hashlib
import hmac
import os
import re
import threading
import time
import traceback
import uuid
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
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

# --- Password ---------------------------------------------------------------------
# The password lives only in .env (LAYER_ONE_PASSWORD), never in this public repo.
COOKIE = "layer_one_auth"
OPEN_PATHS = {"/login", "/api/login"}


def _password() -> str:
    return os.getenv("LAYER_ONE_PASSWORD", "")


def _token(password: str) -> str:
    """What the login cookie holds: proof of the password, not the password itself."""
    return hmac.new(password.encode(), b"layer-one-session", hashlib.sha256).hexdigest()


def _signed_in(request: Request) -> bool:
    password = _password()
    if not password:
        return True  # no password set: the site is open
    return hmac.compare_digest(request.cookies.get(COOKIE, ""), _token(password))


if not _password():
    print("[layer-one] WARNING: LAYER_ONE_PASSWORD isn't set in .env, so the site has no password.")


@app.middleware("http")
async def require_password(request: Request, call_next):
    if request.url.path in OPEN_PATHS or _signed_in(request):
        return await call_next(request)
    if request.url.path == "/":
        return RedirectResponse("/login", status_code=303)
    return JSONResponse({"detail": "Please sign in again."}, status_code=401)


class LoginIn(BaseModel):
    password: str


@app.get("/login")
def login_page():
    return FileResponse(STATIC / "login.html")


@app.post("/api/login")
def login(body: LoginIn):
    password = _password()
    if password and not hmac.compare_digest(body.password.encode(), password.encode()):
        time.sleep(1)  # slows down guessing
        raise HTTPException(401, "That password isn't right.")
    response = JSONResponse({"ok": True})
    if password:
        response.set_cookie(COOKIE, _token(password), max_age=30 * 24 * 3600, httponly=True, samesite="lax")
    return response


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


def design_links(design_id: str) -> dict:
    return {"id": design_id, **{kind: f"/files/{design_id}/{kind}" for kind in FILES}}


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
        {"text": b["text"], "designs": [design_links(d) for d in b["designs"]]} for b in bubbles
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
