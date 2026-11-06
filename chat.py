"""Start the Layer One terminal chat: python chat.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from layer_one.chat import main  # noqa: E402

if __name__ == "__main__":
    main()
