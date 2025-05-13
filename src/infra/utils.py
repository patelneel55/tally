from pathlib import Path


def find_project_root(start: Path = None, markers=("pyproject.toml", ".git")):
    start = start or Path(__file__).resolve()
    for p in [start] + list(start.parents):
        if any((p / marker).exists() for marker in markers):
            return p
    raise FileNotFoundError(f"Could not find project root (markers: {markers})")
