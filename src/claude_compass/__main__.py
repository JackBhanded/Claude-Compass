"""Enable ``python -m claude_compass ...``.

The SessionStart hook invokes the package this way (with the absolute Python
that installed it) so it works even when the ``compass`` launcher isn't on PATH.
"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
