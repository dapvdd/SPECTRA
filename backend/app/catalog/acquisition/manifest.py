"""M3.1 Task 2 — acquisition manifest schema.

A manifest is the human-checked unit of verified catalog data: a list of
``VerifiedSKU`` entries (each carrying per-field ``FieldEvidence``) plus the
candidate ``CandidateRecord`` rows from the Task 1 inventory that the
verified SKUs resolve.

Fail-closed validation (``validate_manifest``) mirrors the M3 evidence-gate
contract:

- a MATCHED VerifiedSKU must carry a non-empty ``mpn``, a non-empty
  ``per_sku_url``, and every populated spec field must have a FieldEvidence
  with ``curator_decision == 'APPROVED'``;
- INVALID / UNRESOLVED entries must carry a non-empty ``notes`` explanation.

All dataclasses roundtrip through plain JSON (``to_dict``/``from_dict``,
``load_manifest``/``save_manifest``) with no exotic types.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Classification vocabulary (plan Task 2 / Task 4-6 contract).
CLASSIFICATIONS = ("MATCHED", "REPLACED", "UNRESOLVED", "INVALID")

# Allowed curator decisions on field evidence. Only APPROVED evidence can
# back a published spec value (fail-closed: PENDING/REJECTED never publish).
CURATOR_DECISIONS = ("APPROVED", "PENDING", "REJECTED")

_APPROVER = "m31-curator"


@dataclass
class FieldEvidence:
    """One spec field's evidence trail (how the value was established)."""

    spec_field: str
    normalized_value: object  # JSON-safe value as it goes into spec
    source_value: str  # value as printed in the cited document
    source_evidence_location: str  # table/heading/row inside the document
    curator_decision: str  # APPROVED | PENDING | REJECTED
    source_url: str
    match_method: str  # from m3_validation._VERIFIED_MATCH_METHODS
    access_date: str  # ISO date the document was consulted

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FieldEvidence":
        known = {
            f: data[f] for f in
            ("spec_field", "normalized_value", "source_value",
             "source_evidence_location", "curator_decision", "source_url",
             "match_method", "access_date")
            if f in data
        }
        return cls(**known)


@dataclass
class CandidateRecord:
    """One candidate row from the Task 1 quarantine inventory."""

    category: str
    name: str
    manufacturer: str
    product_family: str
    canonical_key: str
    index: str = ""  # inventory row index ("001" ...)
    claimed_spec: dict = field(default_factory=dict)
    provenance_urls: dict = field(default_factory=dict)
    identity_status: str = "unconfirmed"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CandidateRecord":
        known = {
            f: data[f] for f in
            ("category", "name", "manufacturer", "product_family",
             "canonical_key", "index", "claimed_spec", "provenance_urls",
             "identity_status")
            if f in data
        }
        return cls(**known)


@dataclass
class VerifiedSKU:
    """A human-verified SKU with per-field evidence and a classification."""

    category: str
    name: str
    manufacturer: str
    product_family: str
    mpn: str
    per_sku_url: str
    source_doc_revision: str  # revision/date of the cited document
    spec: dict = field(default_factory=dict)
    fields: list[FieldEvidence] = field(default_factory=list)
    classification: str = "UNRESOLVED"
    replaced_by: str = ""  # MPN or name of the superseding SKU (REPLACED)
    notes: str = ""
    approved_by: str = _APPROVER
    candidate_index: str = ""  # Task 1 inventory row this entry resolves

    def to_dict(self) -> dict:
        data = asdict(self)
        data["fields"] = [f.to_dict() if isinstance(f, FieldEvidence) else f
                          for f in self.fields]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "VerifiedSKU":
        fields = [
            f if isinstance(f, FieldEvidence) else FieldEvidence.from_dict(f)
            for f in data.get("fields", [])
        ]
        known = {
            f: data[f] for f in
            ("category", "name", "manufacturer", "product_family", "mpn",
             "per_sku_url", "source_doc_revision", "spec", "classification",
             "replaced_by", "notes", "approved_by", "candidate_index")
            if f in data
        }
        return cls(fields=fields, **known)


# ---------------------------------------------------------------------------
# Validation (fail-closed; mirrors the M3 evidence-gate contract)
# ---------------------------------------------------------------------------

def validate_verified_sku(sku: VerifiedSKU) -> list[str]:
    """Return blocker strings for a VerifiedSKU that violates the contract.

    Empty list means the entry is structurally valid. A MATCHED entry
    additionally needs: non-empty mpn, non-empty per_sku_url, and every
    populated spec field covered by APPROVED FieldEvidence.
    """
    blockers: list[str] = []
    if sku.classification not in CLASSIFICATIONS:
        blockers.append(
            f"{sku.name!r}: classification {sku.classification!r} outside "
            f"vocabulary {CLASSIFICATIONS}"
        )
    if sku.classification in ("INVALID", "UNRESOLVED") and not sku.notes.strip():
        blockers.append(
            f"{sku.name!r}: classification {sku.classification} requires "
            "non-empty notes documenting why it was not resolved"
        )
    if sku.classification == "MATCHED":
        if not str(sku.mpn).strip():
            blockers.append(f"{sku.name!r}: MATCHED requires non-empty mpn")
        if not str(sku.per_sku_url).strip():
            blockers.append(
                f"{sku.name!r}: MATCHED requires non-empty per_sku_url"
            )
        evidence_by_field = {e.spec_field: e for e in sku.fields}
        for spec_field, value in sku.spec.items():
            if value is None or value == "":
                continue  # absent/NULL fields stay NULL (no evidence needed)
            evidence = evidence_by_field.get(spec_field)
            if evidence is None:
                blockers.append(
                    f"{sku.name!r}: populated spec field {spec_field!r} has "
                    "no FieldEvidence entry"
                )
            elif evidence.curator_decision != "APPROVED":
                blockers.append(
                    f"{sku.name!r}: spec field {spec_field!r} evidence has "
                    f"curator_decision {evidence.curator_decision!r}; only "
                    "APPROVED evidence may back a published value"
                )
    return blockers


def validate_manifest(manifest: dict) -> list[str]:
    """Validate a whole manifest dict; returns blocker strings (fail-closed)."""
    blockers: list[str] = []
    for i, entry in enumerate(manifest.get("verified_skus", [])):
        sku = (entry if isinstance(entry, VerifiedSKU)
               else VerifiedSKU.from_dict(entry))
        blockers += validate_verified_sku(sku)
    return blockers


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------

MANIFEST_VERSION = 1


def new_manifest(
    verified_skus: list,
    candidates: list | None = None,
    *,
    source: str = "",
) -> dict:
    """Build a manifest dict with the schema-version envelope.

    Accepts VerifiedSKU/CandidateRecord instances or their plain-dict form.
    """
    return {
        "manifest_version": MANIFEST_VERSION,
        "source": source,
        "verified_skus": [
            s.to_dict() if isinstance(s, VerifiedSKU) else s
            for s in verified_skus
        ],
        "candidates": [
            c.to_dict() if isinstance(c, CandidateRecord) else c
            for c in (candidates or [])
        ],
    }


def load_manifest(path: str | Path) -> dict:
    """Load and validate a manifest JSON file (raises on contract breach)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"manifest {path} must be a JSON object")
    blockers = validate_manifest(data)
    if blockers:
        raise ValueError(
            "manifest failed fail-closed validation: " + "; ".join(blockers)
        )
    return data


def save_manifest(
    manifest: dict,
    path: str | Path,
    *,
    validate: bool = True,
) -> None:
    """Write a manifest JSON file (validates first unless ``validate=False``)."""
    if validate:
        blockers = validate_manifest(manifest)
        if blockers:
            raise ValueError(
                "refusing to save invalid manifest: " + "; ".join(blockers)
            )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
