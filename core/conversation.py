import os, json, uuid
from datetime import datetime, timezone

_CONV_DIR = os.path.join(os.getcwd(), "conversations")
os.makedirs(_CONV_DIR, exist_ok=True)


class Conversation:
    """
    Thin wrapper around a JSON file that stores a list of
    {sender, text, timestamp} dictionaries.
    """

    # ---------- lifecycle -------------------------------------------------
    def __init__(self, conv_id: str | None = None):
        self.id   = conv_id or uuid.uuid4().hex
        self._fp  = os.path.join(_CONV_DIR, f"{self.id}.json")
        self._log = self._load()

    # ---------- public helpers -------------------------------------------
    def add(self, sender: str, text: str) -> None:
        self._log.append({
            "sender": sender,
            "text":   text,
            "ts":     datetime.now(timezone.utc).isoformat(timespec="seconds")
        })
        self._save()

    def history(self, n: int | None = None) -> list[dict]:
        """Return complete history or last *n* messages."""
        return self._log if n is None else self._log[-n:]

    # ---------- internal io ----------------------------------------------
    def _load(self) -> list:
        if os.path.exists(self._fp):
            with open(self._fp, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save(self):
        with open(self._fp, "w", encoding="utf-8") as f:
            json.dump(self._log, f, ensure_ascii=False, indent=2)
