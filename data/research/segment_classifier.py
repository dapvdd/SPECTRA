"""Deterministic hardware segment classifier (Phase B core).

Classifies only where the evidence in the *official product name* is
unambiguous. Every rule is tied to a documented, manufacturer-designated
naming convention — never an inferred guess. Unclassifiable records keep
``segment = None`` (honest unknown).

Rule ordering is load-bearing:
1. Server families first (Xeon / EPYC / Tesla / GRID / A100...) — they are the
   only segment whose full-family token is definitive, and it must win even
   when a model suffix looks mobile (e.g. Xeon W-1370P's trailing P).
   BUT mobile-vs-workstation within a family is decided by explicit words.
2. Explicit mobile words / vendor mobile suffixes.
3. Workstation families.
4. Everything else stays None.

Refused-by-design (kept None):
- bare ``M`` + digits (Quadro M2000 = desktop workstation vs FirePro M2000 =
  mobile vs Tesla M2050 = server) — never classified from M alone.
- Desktop-vs-mobile shared roots (RTX 3060, GTX 1650) without an explicit word.
- Intel HD/UHD "NNN" numbers without a Mobile word.
"""

from __future__ import annotations

import re

SEGMENT_VALUES = ("desktop", "mobile", "server", "workstation", "embedded")

# --------------------------------------------------------------------------
# Server / datacenter families — full-family tokens that are always server.
# --------------------------------------------------------------------------
SERVER_RE = [
    re.compile(r"(^|\W)Tesla\b", re.IGNORECASE),
    re.compile(r"(^|\W)GRID\b", re.IGNORECASE),
    re.compile(r"\b(A100|A800|H100|H800|B100|B200)\b"),
    re.compile(r"(^|\W)A2\b|(^|\W)A30\b|(^|\W)A40\b|\bA16\b"),
    re.compile(r"\b(L4|L40|T4|V100|P100|P40|P4|P10|V100S)\b"),
    re.compile(r"\bInstinct\b"),
    re.compile(r"\bMI\d{3}\b"),
    re.compile(r"\bPG\d{3}\b"),
    re.compile(r"(^|\W)Xeon\b", re.IGNORECASE),
    re.compile(r"(^|\W)EPYC\b", re.IGNORECASE),
    # AMD FirePro S-series (S7000/S9000/S10000...) and FirePro D-series
    # (D300/D500/D700) are GPU-compute / server parts, not workstation.
    # Run BEFORE workstation family check so 'FirePro' itself does not win.
    re.compile(r"\bFirePro S\d+\b", re.IGNORECASE),
    re.compile(r"\bFirePro D\d+\b", re.IGNORECASE),
]


def _match_regexes(name: str, regexes: list[re.Pattern]) -> str | None:
    for rx in regexes:
        if rx.search(name):
            return rx.pattern
    return None


# Explicit mobile words / suffixes
MOBILE_MAXQ = re.compile(r"max-q", re.IGNORECASE)
MOBILE_EXPLICIT = (" Mobile", " Laptop", " Mobility", " Mobile Processor")
MOBILE_WORD = re.compile(r"\b(mobile|laptop)\b", re.IGNORECASE)

MOBILE_AMD_MOBILITY = re.compile(r"\bMobility Radeon\b", re.IGNORECASE)
# Radeon RX 5500M / Radeon HD 7970M (M-suffix mobile).
MOBILE_AMD_RX_M = re.compile(r"\bRadeon (?:RX |HD )?\d{3,4}M\b")
# Radeon R5 M230 / R9 M290X (R-series mobile).
MOBILE_AMD_R_M = re.compile(r"\bRadeon R\d+ M\d{3,4}[A-Z]?\b")
# FirePro M-series is mobile; FirePro W*xxxM carries an explicit M suffix;
# Radeon Pro NNNxM / Vega NNM carry explicit M suffixes.
MOBILE_FIREPRO_M = re.compile(r"\bFirePro M\d{3,4}\b")
MOBILE_FIREPRO_WM = re.compile(r"\bFirePro W\d{3,4}M\b")
MOBILE_RADEONPRO_XM = re.compile(r"\bRadeon Pro \d{3,4}M\b")
MOBILE_RADEONPRO_VEGA_M = re.compile(r"\bRadeon Pro Vega \d+M\b")
MOBILE_NVIDIA_GE_M = re.compile(r"\bGeForce (?:GTX |GT |GTS )?\d{3,4}M\b")
MOBILE_NVIDIA_MX = re.compile(r"\b\d{3,4}MX\b|\bMX\d{2,4}\b")
MOBILE_NVIDIA_NVS_M = re.compile(r"\bNVS \d{3,4}M\b")
MOBILE_NVIDIA_RTX_A = re.compile(r"\bRTX \d{3,4} [AM]a?da?\b")
MOBILE_INTEL_ARC_M = re.compile(r"\bArc(?: Pro)? [A-Z]\d+M\b")

# CPU mobile suffixes. IMPORTANT: run only AFTER server check, so Xeon W-1370P
# / EPYC-class numbers are not caught. Matches the trailing 4-5 digit model
# number plus a mobile suffix letter, with or without a generation digit
# between family and model (Ryzen 9 7945HX / Ryzen 5 5600U / Core i7-13700H /
# Core Ultra 5 125H / Pentium 4417U).
# Bare 'P' is deliberately EXCLUDED: Intel's P suffix is ambiguous
# (desktop Core i5-6402P / i3-6098P vs mobile Core i7-1360P).
CPU_MOBILE_SUFFIX = re.compile(
    r"\b(?:\w+-)?(?:\w+\s+)*\d{4,5}(?:UA|UE|UH|U|HK|HQ|HX|H)\b",
    re.IGNORECASE,
)


def classify(name: str, hardware_type: str, manufacturer: str | None = None) -> dict | None:
    """Deterministic segment. Returns {'segment','rule'} or None (ambiguous)."""
    # 0) Server family always wins (Xeon W-1370P, EPYC, Tesla, GRID, A100...)
    server_match = _match_regexes(name, SERVER_RE)
    if server_match:
        return {"segment": "server", "rule": "server_family"}

    # 1) Explicit mobile words / suffixes
    if MOBILE_MAXQ.search(name):
        return {"segment": "mobile", "rule": "maxq"}
    if any(token in name for token in MOBILE_EXPLICIT) or MOBILE_WORD.search(name):
        return {"segment": "mobile", "rule": "explicit_mobile_word"}

    if hardware_type == "GPU":
        if manufacturer == "NVIDIA":
            if MOBILE_NVIDIA_GE_M.search(name):
                return {"segment": "mobile", "rule": "nvidia_classic_M"}
            if MOBILE_NVIDIA_MX.search(name):
                return {"segment": "mobile", "rule": "nvidia_MX"}
            if MOBILE_NVIDIA_NVS_M.search(name):
                return {"segment": "mobile", "rule": "nvidia_NVS_M"}
            if MOBILE_NVIDIA_RTX_A.search(name):
                return {"segment": "mobile", "rule": "nvidia_RTX_A"}
        elif manufacturer in ("AMD", "ATI"):
            if MOBILE_AMD_MOBILITY.search(name):
                return {"segment": "mobile", "rule": "amd_mobility"}
            if MOBILE_FIREPRO_M.search(name):
                return {"segment": "mobile", "rule": "firepro_M"}
            if MOBILE_FIREPRO_WM.search(name):
                return {"segment": "mobile", "rule": "firepro_WM"}
            if MOBILE_RADEONPRO_XM.search(name):
                return {"segment": "mobile", "rule": "radeonpro_XM"}
            if MOBILE_RADEONPRO_VEGA_M.search(name):
                return {"segment": "mobile", "rule": "radeonpro_vega_M"}
            if MOBILE_AMD_RX_M.search(name):
                return {"segment": "mobile", "rule": "amd_rx_M"}
            if MOBILE_AMD_R_M.search(name):
                return {"segment": "mobile", "rule": "amd_R_M"}
        elif manufacturer == "Intel":
            if MOBILE_INTEL_ARC_M.search(name):
                return {"segment": "mobile", "rule": "intel_arc_M"}

    if hardware_type == "CPU":
        if CPU_MOBILE_SUFFIX.search(name):
            return {"segment": "mobile", "rule": "cpu_mobile_suffix"}

    # 2) Workstation families
    workstation = (
        "quadro", "firepro", "firegl", "radeon pro", "arc pro", "nvs",
        "rtx a", "rtx 2000", "rtx 4000", "rtx 6000", "rtx 8000",
    )
    low = name.lower()
    if any(fam in low for fam in workstation):
        # A CPU record whose name only contains a workstation-family *GPU*
        # (e.g. "Intel Core i7-8706G with Radeon Pro WX Vega M GL") is not a
        # workstation CPU itself — the "Pro" label belongs to its embedded GPU.
        # Only GPU records carry a workstation segment on the family marker.
        if hardware_type != "GPU":
            return None
        return {"segment": "workstation", "rule": "workstation_family"}

    # 3) Nothing conclusive → None (honest unknown)
    return None


def classify_all(records):
    out = []
    for rid, name, htype, manuf in records:
        m = classify(name, htype, manuf)
        out.append((rid, m["segment"] if m else None, m["rule"] if m else None))
    return out


def main() -> None:
    import argparse
    import sqlite3
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default="data/spectra.db")
    args = parser.parse_args()

    con = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT id, name, manufacturer, type FROM hardware ORDER BY id"
        ).fetchall()
    finally:
        con.close()

    records = [(r["id"], r["name"], r["type"], r["manufacturer"]) for r in rows]
    results = classify_all(records)
    by_id = {r[0]: r for r in records}

    from collections import Counter
    counts = Counter(seg for _, seg, _ in results if seg)
    print(f"records: {len(results)}")
    print(f"classified: {sum(counts.values())}  {dict(counts)}")
    print(f"unclassified (NULL): {len(results) - sum(counts.values())}")

    by_rule = Counter(rule for _, _, rule in results if rule)
    print("\nby rule:")
    for rule, n in by_rule.most_common():
        print(f"  {rule}: {n}")

    for seg in ("mobile", "workstation", "server"):
        print(f"\n=== first 15 {seg} ===")
        shown = 0
        for rid, s, rule in results:
            if s == seg:
                r = by_id[rid]
                print(f"  {r[1]} | {r[3]} | {r[2]} [{rule}]")
                shown += 1
                if shown >= 15:
                    break


if __name__ == "__main__":
    main()
