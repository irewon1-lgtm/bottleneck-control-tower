"""Manual role assignment; does not verify a Claim's truth."""
from .core import audit
from .models import Candidate, Claim, now

ROLES = frozenset({"DRIVER", "CONSTRAINT", "RELIEF", "OTHER"})


def set_claim_role(session, claim: Claim, role: str) -> None:
    if not isinstance(claim, Claim) or claim.status != "active":
        raise ValueError("active Claim required")
    candidate = session.get(Candidate, claim.candidate_id)
    if candidate is None or candidate.status != "active":
        raise ValueError("active Candidate required")
    if not isinstance(role, str) or role not in ROLES:
        raise ValueError("invalid Claim role")
    if claim.role == role:
        return
    old = claim.role
    claim.role, claim.updated_at = role, now()
    audit(session, "claim.role_changed", "claim", claim.id,
          {"from": old, "to": role})
