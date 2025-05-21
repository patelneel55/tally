import asyncio
from pathlib import Path

from tqdm import tqdm


def find_project_root(start: Path = None, markers=("pyproject.toml", ".git")):
    start = start or Path(__file__).resolve()
    for p in [start] + list(start.parents):
        if any((p / marker).exists() for marker in markers):
            return p
    raise FileNotFoundError(f"Could not find project root (markers: {markers})")


def recursive_sort(d):
    if isinstance(d, dict):
        return {k: recursive_sort(d[k]) for k in sorted(d)}
    elif isinstance(d, list):
        return [recursive_sort(i) for i in d]
    else:
        return d


class ProgressTracker:
    def __init__(self, total: int):
        self.total = total
        self.visited = 0
        self.lock = asyncio.Lock()
        self.tqdm_bar = None

    async def step(self):
        async with self.lock:
            self.tqdm_bar.update(1)

    async def __aenter__(self):
        self.tqdm_bar = tqdm(total=self.total, desc="Processing nodes")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.tqdm_bar.close()
