"""Fail-closed objective binding; no review criteria or stored records change."""
import hashlib
from pathlib import Path

OBJECTIVE_VERSION = "bct-objective-1"
OBJECTIVE_SHA256 = "0b2de0186c92fa0c5466539b42cdf5a4fba164a7c9fb62092e396cb4ebe0cff7"
LOCK_PATH = Path(__file__).resolve().parents[2] / "BCT_OBJECTIVE_LOCK.md"


class ObjectiveBlocked(ValueError):
    pass


def objective_binding(*, lock_path=None):
    try:
        text = Path(lock_path or LOCK_PATH).read_text(encoding="utf-8")
        sentence = text.split("<!-- objective:start -->\n", 1)[1].split("\n<!-- objective:end -->", 1)[0]
        if (hashlib.sha256(sentence.encode("utf-8")).hexdigest() != OBJECTIVE_SHA256
                or f"objective_version: {OBJECTIVE_VERSION}\n" not in text
                or f"objective_sha256: {OBJECTIVE_SHA256}\n" not in text):
            raise ValueError("objective differs")
    except (OSError, IndexError, ValueError) as exc:
        raise ObjectiveBlocked("BLOCKED: OBJECTIVE_LOCK_MISMATCH") from exc
    return {"objective_version": OBJECTIVE_VERSION, "objective_sha256": OBJECTIVE_SHA256}


def require_objective(document):
    expected = objective_binding()
    if not isinstance(document, dict) or any(document.get(k) != v for k, v in expected.items()):
        raise ObjectiveBlocked("BLOCKED: OBJECTIVE_BATCH_MISMATCH")
    return expected


def stamp_export(document):
    expected = objective_binding()
    if any(k in document and document[k] != v for k, v in expected.items()):
        raise ObjectiveBlocked("BLOCKED: OBJECTIVE_BATCH_MISMATCH")
    return {**document, **expected}
