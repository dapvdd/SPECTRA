"""Deterministic external-identifier source mapping (Batch 010).

Batch 009 discovered that every `external_identifiers` row carries
``source_id`` 1 (PassMark) even though the identifier values demonstrably
originate in the Intel ARK and AMD specification exports used for the base CPU
import. This module holds the pure, testable decision logic used to build and
validate the source-correction patch.

The decision contract is the registered *source name* (not a numeric id), so
the logic is portable across databases; callers resolve the name to a row in
their own database. Nothing here reads the database or the source files;
callers supply the evidence sets so the logic can be unit-tested
deterministically.
"""

from __future__ import annotations

# Registered source names (created in batch 009; see data/research/batch009
# provenance_reconciliation.json for the artifact hashes).
INTEL_CSV_SOURCE_NAME = "Intel ARK (intel-cpus.csv snapshot)"
AMD_CSV_SOURCE_NAME = "AMD product specifications (amd-cpus.csv snapshot)"

INTEL_IDENTIFIER_TYPES = frozenset({"intel_cpu_id"})
AMD_IDENTIFIER_TYPES = frozenset(
    {"product_id_tray", "product_id_boxed", "product_id_mpk"}
)


def expected_source_name(identifier_type: str) -> str | None:
    """Return the registered source name an identifier type maps to."""
    if identifier_type in INTEL_IDENTIFIER_TYPES:
        return INTEL_CSV_SOURCE_NAME
    if identifier_type in AMD_IDENTIFIER_TYPES:
        return AMD_CSV_SOURCE_NAME
    return None


def decide_reassignment(
    identifier_type: str,
    external_id: str,
    intel_cpu_ids: set[str],
    amd_product_ids: dict[str, set[str]],
) -> tuple[str | None, dict]:
    """Decide the target source name for one identifier.

    Returns ``(source_name, evidence)``. ``source_name`` is non-None only when
    the identifier type maps to a known source AND the external id value is
    present in the expected artifact column set; otherwise the identifier must
    not be reassigned and the evidence dict explains why.

    This implements the rule "do not infer source identity from a numeric
    source id alone": reassignment requires value-level evidence in the source
    artifact.
    """
    target = expected_source_name(identifier_type)
    evidence = {
        "identifier_type": identifier_type,
        "expected_source_name": target,
    }

    if target is None:
        evidence["reason"] = "unknown identifier type"
        return None, evidence

    if identifier_type == "intel_cpu_id":
        evidence["present_in_intel_cpuid"] = external_id in intel_cpu_ids
        if external_id in intel_cpu_ids:
            return target, evidence
        evidence["reason"] = "external_id not present in intel-cpus.csv CpuId"
        return None, evidence

    bucket = {
        "product_id_tray": "product_id_tray",
        "product_id_boxed": "product_id_boxed",
        "product_id_mpk": "product_id_mpk",
    }[identifier_type]
    source_set = amd_product_ids.get(bucket, set())
    evidence[f"present_in_amd_{bucket}"] = external_id in source_set
    if external_id in source_set:
        return target, evidence
    evidence["reason"] = f"external_id not present in amd-cpus.csv {bucket}"
    return None, evidence