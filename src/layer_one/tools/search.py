"""Swimlane step: "Search approved 3D model sites"

Searches Thingiverse (the only candidate site with a usable API; GrabCAD has none) and
returns models with an STL file and a license that allows printing. Downloads the STL
the student picks.

Needs THINGIVERSE_TOKEN in .env: the App Token from thingiverse.com/apps/create.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

import httpx

API = "https://api.thingiverse.com"
MAX_RESULTS = 5
CANDIDATES = 10                  # hits checked for license and STL files before trimming
MAX_DOWNLOAD_BYTES = 50_000_000  # 50 MB
TRANSPORT = None                 # tests swap in a fake transport


class SearchError(Exception):
    pass


def _client() -> httpx.Client:
    token = os.getenv("THINGIVERSE_TOKEN", "").strip()
    if not token:
        raise SearchError("Model search isn't set up on this server (no THINGIVERSE_TOKEN in .env).")
    return httpx.Client(
        base_url=API, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=20, follow_redirects=True, transport=TRANSPORT,
    )


def _get(client: httpx.Client, path: str, **params):
    try:
        response = client.get(path, params=params or None)
    except httpx.HTTPError:
        raise SearchError("Couldn't reach Thingiverse. Check the server's internet connection.")
    if response.status_code == 401:
        raise SearchError("Thingiverse rejected the token. Check THINGIVERSE_TOKEN in .env.")
    if response.status_code == 404:
        raise SearchError("Thingiverse couldn't find that model.")
    if response.status_code >= 400:
        raise SearchError(f"Thingiverse returned an error ({response.status_code}). Try again shortly.")
    try:
        return response.json()
    except ValueError:
        raise SearchError("Thingiverse sent back something unexpected. Try again shortly.")


def license_status(license_text: str) -> str:
    """ok: free to print. ok_no_changes: print as-is only. staff_review: unclear (doc Section 7)."""
    text = (license_text or "").lower()
    if not any(k in text for k in ("creative commons", "public domain", "gpl", "bsd")):
        return "staff_review"
    if "no derivatives" in text:
        return "ok_no_changes"
    return "ok"


def _image(thing: dict) -> str:
    for size in (thing.get("default_image") or {}).get("sizes", []):
        if size.get("type") == "preview" and size.get("size") == "card":
            return size.get("url", "")
    return thing.get("preview_image") or thing.get("thumbnail") or ""


def _stl_files(files: list) -> list[dict]:
    return [
        {"file_id": f["id"], "name": f.get("name", ""), "size_kb": round(f.get("size", 0) / 1000)}
        for f in files if isinstance(f, dict) and str(f.get("name", "")).lower().endswith(".stl")
    ]


def _summary(thing: dict, files: list) -> dict:
    creator = thing.get("creator") or {}
    return {
        "thing_id": thing["id"],
        "name": thing.get("name", ""),
        "creator": creator.get("name", ""),
        "url": thing.get("public_url") or f"https://www.thingiverse.com/thing:{thing['id']}",
        "image": _image(thing),
        "license": thing.get("license", ""),
        "license_status": license_status(thing.get("license", "")),
        "likes": thing.get("like_count", 0),
        "downloads": thing.get("download_count", 0),
        "stl_files": _stl_files(files),
    }


def _details(client, thing_id) -> dict:
    return _summary(_get(client, f"/things/{thing_id}"), _get(client, f"/things/{thing_id}/files"))


def search_models(query: str) -> dict:
    """Up to MAX_RESULTS printable, clearly licensed models for the query."""
    with _client() as client:
        found = _get(client, f"/search/{quote(query.strip(), safe='')}",
                     type="things", sort="relevant", per_page=CANDIDATES)
        hits = found if isinstance(found, list) else found.get("hits", [])
        ids = [h["id"] for h in hits[:CANDIDATES] if isinstance(h, dict) and "id" in h]
        with ThreadPoolExecutor(max_workers=5) as pool:
            things = list(pool.map(lambda i: _details(client, i), ids))

    printable = [t for t in things if t["stl_files"]]
    usable = [t for t in printable if t["license_status"] != "staff_review"]
    return {
        "query": query,
        "results": usable[:MAX_RESULTS],
        "hidden_unclear_license": len(printable) - len(usable),
        "hidden_no_stl": len(things) - len(printable),
    }


def download(thing_id: int, file_id: int, out_dir: Path) -> tuple[Path, dict]:
    """Saves the chosen STL as out_dir/model.stl. Returns (path, model summary)."""
    with _client() as client:
        model = _details(client, thing_id)
        if model["license_status"] == "staff_review":
            raise SearchError("This model's license is unclear, so library staff need to review it first.")
        if not any(f["file_id"] == file_id for f in model["stl_files"]):
            raise SearchError("That file isn't one of this model's STL files.")
        path = out_dir / "model.stl"
        try:
            with client.stream("GET", f"/files/{file_id}/download") as response:
                if response.status_code >= 400:
                    raise SearchError(f"Thingiverse wouldn't send the file ({response.status_code}).")
                size = 0
                with path.open("wb") as f:
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > MAX_DOWNLOAD_BYTES:
                            raise SearchError("That file is over 50 MB, too large to check here.")
                        f.write(chunk)
        except httpx.HTTPError:
            raise SearchError("The download from Thingiverse failed. Try again.")
    return path, model
