"""Start the Layer One web app: python web.py

Then open http://<this server's IP>:8000 in a browser on the same network.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import uvicorn  # noqa: E402

from layer_one.web import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
