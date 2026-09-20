"""Repository boundary: only app/repositories may touch the database directly."""
import pathlib
import re

APP = pathlib.Path(__file__).resolve().parent.parent / "app"
# Patterns that indicate raw DB access.
BANNED = [re.compile(r"\bdb\.[a-zA-Z_]+\.(find|insert|update|delete|aggregate|count|distinct)"),
          re.compile(r"AsyncIOMotorClient")]
ALLOWED_DIR = "repositories"


def test_only_repositories_touch_db():
    offenders = []
    for path in APP.rglob("*.py"):
        if ALLOWED_DIR in path.parts:
            continue
        text = path.read_text()
        for pat in BANNED:
            if pat.search(text):
                offenders.append(f"{path}: {pat.pattern}")
    assert not offenders, "Direct DB access outside repositories:\n" + "\n".join(offenders)
