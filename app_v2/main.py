"""Entry point app_v2. Jalankan: `python -m app_v2.main`."""

import os
import logging

from .cache import initialize
from .app_instance import app
from . import layout      # noqa: F401  — register app.layout
from . import callbacks   # noqa: F401  — register semua callback


def main():
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    initialize()
    debug = os.getenv("DASH_DEBUG", "false").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=8050, use_reloader=False)


if __name__ == "__main__":
    main()
