"""Entry point PyInstaller bundles into 'Claude Compass.exe'. Launches the GUI.
Kept at the repo root (with ``--paths src`` at build time) so PyInstaller finds
the ``claude_compass`` package."""

from claude_compass.app import main

if __name__ == "__main__":
    raise SystemExit(main())
