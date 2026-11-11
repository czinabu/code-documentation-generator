"""Remember which files were already documented, keyed by content hash."""

import hashlib
import json
from pathlib import Path

CACHE_FILE = ".docgen-cache.json"
CACHE_VERSION = 1


def content_hash(text: str, *salt: str) -> str:
    """Hash the file text together with anything that changes the output (model, prompt version)."""
    h = hashlib.sha256()
    for part in salt:
        h.update(part.encode("utf-8"))
        h.update(b"\0")
    h.update(text.encode("utf-8"))
    return h.hexdigest()


class DocCache:
    """A JSON file in the output folder mapping each source path to its last hash."""

    def __init__(self, out_dir: Path):
        self.path = Path(out_dir) / CACHE_FILE
        self.entries: dict[str, dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(data, dict) and data.get("version") == CACHE_VERSION:
            self.entries = data.get("files", {}) or {}

    def get(self, rel_path: str) -> str | None:
        entry = self.entries.get(rel_path)
        return entry.get("hash") if entry else None

    def is_fresh(self, rel_path: str, digest: str, doc_path: Path) -> bool:
        """True when the hash matches and the generated page is still on disk."""
        return self.get(rel_path) == digest and Path(doc_path).is_file()

    def set(self, rel_path: str, digest: str, doc: str) -> None:
        self.entries[rel_path] = {"hash": digest, "doc": doc}

    def prune(self, keep) -> None:
        """Drop entries for source files that no longer exist."""
        keep = set(keep)
        self.entries = {k: v for k, v in self.entries.items() if k in keep}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": CACHE_VERSION, "files": dict(sorted(self.entries.items()))}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)
