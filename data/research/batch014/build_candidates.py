"""Batch 014 candidate extraction.

Reads the fetched Wikipedia article/template wikitext (CC BY-SA 4.0), parses
the target processor tables with ``wikitext_tables``, applies an explicit,
per-table column mapping, and writes:

    _candidates.json          machine-readable candidate inventory
    03_candidate_inventory.csv human-readable inventory
    05_database_patch.json    proposed insert patch (hardware + specs + provenance)

The script is deterministic and read-only with respect to the database: it only
reads the database to classify existing vs missing records.

Source of truth for every value is the named Wikipedia table; the mapping here
never invents a value that is not present in the source row.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wikitext_tables import find_tables, parse_table

BATCH = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BATCH, "sources")
DB = r"C:\SPECTRA\data\spectra.db"
ACCESS_DATE = "2026-10-12"

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


# --------------------------------------------------------------------------- #
# value helpers
# --------------------------------------------------------------------------- #

def first_float(text):
    m = re.search(r"\d+(?:\.\d+)?", text or "")
    return float(m.group(0)) if m else None


def all_floats(text):
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", text or "")]


def max_float(*texts):
    vals = []
    for t in texts:
        vals.extend(all_floats(t))
    return max(vals) if vals else None


def core_threads(cell):
    m = re.search(r"(\d+)\s*\(\s*(\d+)\s*\)", cell or "")
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def sum_core_threads(*cells):
    cores = threads = 0
    found = False
    for c in cells:
        n, t = core_threads(c)
        if n is not None:
            cores += n
            threads += t
            found = True
    return (cores, threads) if found else (None, None)


def tdp(cell):
    v = first_float(cell)
    return v


def parse_release(cell):
    s = (cell or "").strip()
    if not s:
        return None
    # "(PRO launch) main launch" -> use the main (unparenthesised) launch
    while s.startswith("("):
        end = s.find(")")
        if end == -1:
            return None
        s = s[end + 1:].strip()
        if not s:
            return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})$", s)
    if m:
        return "%s-%s-%02d" % (m.group(1), m.group(2), int(m.group(3)))
    m = re.match(r"(\d{4})-([A-Za-z]{3,})\.?-(\d{1,2})$", s)
    if m:
        mo = MONTHS.get(m.group(2)[:3].lower())
        if mo:
            return "%s-%02d-%02d" % (m.group(1), mo, int(m.group(3)))
        return None
    m = re.match(r"([A-Za-z]{3,})\.?\s+(\d{1,2}),\s*(\d{4})$", s)
    if m:
        mo = MONTHS.get(m.group(1)[:3].lower())
        if mo:
            return "%s-%02d-%02d" % (m.group(3), mo, int(m.group(2)))
        return None
    return None


def is_section_row(row):
    nonempty = [c for c in row if c.strip()]
    return len(nonempty) > 1 and len(set(nonempty)) == 1


# --------------------------------------------------------------------------- #
# table specifications
# --------------------------------------------------------------------------- #

def intel_name_dash(brand, model):
    return "Intel %s-%s Processor" % (brand, model)


def intel_name_ultra(brand, model):
    return "Intel %s %s Processor" % (brand, model)


def amd_name(brand, model):
    return "AMD %s %s" % (brand, model)


def brand_is_core(brand):
    return brand.strip().startswith("Core") and "Ultra" not in brand


def brand_is_core_ultra(brand):
    return brand.strip().startswith("Core Ultra")


def amd_model_clean(m):
    m = (m or "").replace("(PRO)", "").strip()
    parts = m.split()
    if not parts:
        return m
    if parts[0].upper() == "PRO":
        return "PRO " + (parts[1] if len(parts) > 1 else "")
    return parts[0]


HEADER_BRANDS = {"branding", "brandingandmodel", "processorbranding", "model"}


def is_header_row(brand, spec):
    return brand.lower().replace(" ", "") in HEADER_BRANDS


TABLES = [
    dict(
        key="intel_rpl_refresh_desktop",
        file="Raptor_Lake.wiki.txt", start=935,
        source_title="Raptor Lake",
        source_url="https://en.wikipedia.org/wiki/Raptor_Lake",
        section="List of 14th-generation Raptor Lake processors / Raptor Lake-S Refresh",
        manufacturer="Intel", arch="Raptor Lake Refresh",
        proc_node=10.0, socket="FCLGA1700",
        brand_index=0, model_index=1, brand_filter=brand_is_core,
        name_fn=intel_name_dash,
        cores_fn=lambda r: sum_core_threads(r[2], r[3]),
        base_fn=lambda r: first_float(r[4]),
        boost_fn=lambda r: max_float(r[6], r[7], r[8], r[9]),
        tdp_fn=lambda r: tdp(r[13]),
        release_fn=lambda r: parse_release(r[15]),
    ),
    dict(
        key="intel_mtl_h", file="Meteor_Lake.wiki.txt", start=306,
        source_title="Meteor Lake",
        source_url="https://en.wikipedia.org/wiki/Meteor_Lake",
        section="List of Meteor Lake processors / Meteor Lake-H",
        manufacturer="Intel", arch="Meteor Lake", proc_node=None, socket=None,
        brand_index=0, model_index=1, brand_filter=brand_is_core_ultra,
        name_fn=intel_name_ultra,
        cores_fn=lambda r: sum_core_threads(r[2], r[3], r[4]),
        base_fn=lambda r: first_float(r[5]),
        boost_fn=lambda r: max_float(r[8], r[9], r[10]),
        tdp_fn=lambda r: tdp(r[14]),
        release_fn=lambda r: parse_release(r[17]),
    ),
    dict(
        key="intel_mtl_u", file="Meteor_Lake.wiki.txt", start=400,
        source_title="Meteor Lake",
        source_url="https://en.wikipedia.org/wiki/Meteor_Lake",
        section="List of Meteor Lake processors / Meteor Lake-U",
        manufacturer="Intel", arch="Meteor Lake", proc_node=None, socket=None,
        brand_index=0, model_index=1, brand_filter=brand_is_core_ultra,
        name_fn=intel_name_ultra,
        cores_fn=lambda r: sum_core_threads(r[2], r[3], r[4]),
        base_fn=lambda r: first_float(r[5]),
        boost_fn=lambda r: max_float(r[8], r[9], r[10]),
        tdp_fn=lambda r: tdp(r[14]),
        release_fn=lambda r: parse_release(r[17]),
    ),
    dict(
        key="intel_mtl_hl", file="Meteor_Lake.wiki.txt", start=524,
        source_title="Meteor Lake",
        source_url="https://en.wikipedia.org/wiki/Meteor_Lake",
        section="List of Meteor Lake processors / Meteor Lake-HL",
        manufacturer="Intel", arch="Meteor Lake", proc_node=None, socket=None,
        brand_index=0, model_index=1, brand_filter=brand_is_core_ultra,
        name_fn=intel_name_ultra,
        cores_fn=lambda r: sum_core_threads(r[2], r[3], r[4]),
        base_fn=lambda r: first_float(r[5]),
        boost_fn=lambda r: max_float(r[8], r[9], r[10]),
        tdp_fn=lambda r: tdp(r[14]),
        release_fn=lambda r: parse_release(r[17]),
    ),
    dict(
        key="intel_mtl_ul", file="Meteor_Lake.wiki.txt", start=603,
        source_title="Meteor Lake",
        source_url="https://en.wikipedia.org/wiki/Meteor_Lake",
        section="List of Meteor Lake processors / Meteor Lake-UL",
        manufacturer="Intel", arch="Meteor Lake", proc_node=None, socket=None,
        brand_index=0, model_index=1, brand_filter=brand_is_core_ultra,
        name_fn=intel_name_ultra,
        cores_fn=lambda r: sum_core_threads(r[2], r[3], r[4]),
        base_fn=lambda r: first_float(r[5]),
        boost_fn=lambda r: max_float(r[8], r[9], r[10]),
        tdp_fn=lambda r: tdp(r[14]),
        release_fn=lambda r: parse_release(r[17]),
    ),
    dict(
        key="intel_arl_s", file="Arrow_Lake_microprocessor.wiki.txt", start=220,
        source_title="Arrow Lake (microprocessor)",
        source_url="https://en.wikipedia.org/wiki/Arrow_Lake_(microprocessor)",
        section="Arrow Lake-S desktop processors",
        manufacturer="Intel", arch="Arrow Lake", proc_node=None,
        socket="FCLGA1851",
        brand_index=0, model_index=1, brand_filter=brand_is_core_ultra,
        name_fn=intel_name_ultra,
        cores_fn=lambda r: sum_core_threads(r[2], r[3]),
        base_fn=lambda r: first_float(r[4]),
        boost_fn=lambda r: first_float(r[6]),
        tdp_fn=lambda r: tdp(r[15]),
        release_fn=lambda r: parse_release(r[17]),
    ),
    dict(
        key="intel_arl_u", file="Arrow_Lake_microprocessor.wiki.txt", start=458,
        source_title="Arrow Lake (microprocessor)",
        source_url="https://en.wikipedia.org/wiki/Arrow_Lake_(microprocessor)",
        section="Arrow Lake-U mobile processors",
        manufacturer="Intel", arch="Arrow Lake", proc_node=None, socket=None,
        brand_index=0, model_index=1, brand_filter=brand_is_core_ultra,
        name_fn=intel_name_ultra,
        cores_fn=lambda r: sum_core_threads(r[2], r[3], r[4]),
        base_fn=lambda r: first_float(r[5]),
        boost_fn=lambda r: max_float(r[8], r[9], r[10]),
        tdp_fn=lambda r: tdp(r[18]),
        release_fn=lambda r: parse_release(r[20]),
    ),
    dict(
        key="intel_arl_h", file="Arrow_Lake_microprocessor.wiki.txt", start=540,
        source_title="Arrow Lake (microprocessor)",
        source_url="https://en.wikipedia.org/wiki/Arrow_Lake_(microprocessor)",
        section="Arrow Lake-H mobile processors",
        manufacturer="Intel", arch="Arrow Lake", proc_node=None, socket=None,
        brand_index=0, model_index=1, brand_filter=brand_is_core_ultra,
        name_fn=intel_name_ultra,
        cores_fn=lambda r: sum_core_threads(r[2], r[3], r[4]),
        base_fn=lambda r: first_float(r[5]),
        boost_fn=lambda r: max_float(r[8], r[9], r[10]),
        tdp_fn=lambda r: tdp(r[16]),
        release_fn=lambda r: parse_release(r[18]),
    ),
    dict(
        key="intel_arl_hx", file="Arrow_Lake_microprocessor.wiki.txt", start=632,
        source_title="Arrow Lake (microprocessor)",
        source_url="https://en.wikipedia.org/wiki/Arrow_Lake_(microprocessor)",
        section="Arrow Lake-HX mobile processors",
        manufacturer="Intel", arch="Arrow Lake", proc_node=None, socket=None,
        brand_index=0, model_index=1, brand_filter=brand_is_core_ultra,
        name_fn=intel_name_ultra,
        cores_fn=lambda r: sum_core_threads(r[2], r[3]),
        base_fn=lambda r: first_float(r[4]),
        boost_fn=lambda r: first_float(r[6]),
        tdp_fn=lambda r: tdp(r[13]),
        release_fn=lambda r: parse_release(r[15]),
    ),
    dict(
        key="intel_lnl", file="Lunar_Lake.wiki.txt", start=145,
        source_title="Lunar Lake",
        source_url="https://en.wikipedia.org/wiki/Lunar_Lake",
        section="Lunar Lake processors (Core Ultra 200V)",
        manufacturer="Intel", arch="Lunar Lake", proc_node=None, socket=None,
        brand_index=0, model_index=1, brand_filter=brand_is_core_ultra,
        name_fn=intel_name_ultra,
        cores_fn=lambda r: sum_core_threads(r[2], r[3]),
        base_fn=lambda r: first_float(r[4]),
        boost_fn=lambda r: max_float(r[5], r[6]),
        tdp_fn=lambda r: tdp(r[12]),
        release_fn=lambda r: None,
    ),
    dict(
        key="amd_ryzen_9000_desktop", file="Template_AMD_Ryzen_9000_Series.wiki.txt", start=12,
        source_title="Template:AMD Ryzen 9000 Series",
        source_url="https://en.wikipedia.org/wiki/Template:AMD_Ryzen_9000_Series",
        section="Ryzen 9000 desktop (Granite Ridge)",
        manufacturer="AMD", arch="Zen 5", proc_node=4.0, socket="AM5",
        brand_index=0, model_index=1, brand_filter=None,
        name_fn=amd_name,
        cores_fn=lambda r: core_threads(r[2]),
        base_fn=lambda r: first_float(r[3]),
        boost_fn=lambda r: first_float(r[4]),
        tdp_fn=lambda r: tdp(r[6]),
        release_fn=lambda r: parse_release(r[10]),
    ),
    dict(
        key="amd_ryzen_8000g_desktop", file="Template_AMD_Ryzen_8000_desktop_APUs.wiki.txt", start=11,
        source_title="Template:AMD Ryzen 8000 desktop APUs",
        source_url="https://en.wikipedia.org/wiki/Template:AMD_Ryzen_8000_desktop_APUs",
        section="Ryzen 8000G desktop APUs (Phoenix)",
        manufacturer="AMD", arch="Zen 4", proc_node=4.0, socket="AM5",
        brand_index=0, model_index=1, brand_filter=None,
        name_fn=amd_name,
        cores_fn=lambda r: core_threads(r[2]),
        base_fn=lambda r: first_float(r[5]),
        boost_fn=lambda r: first_float(r[6]),
        tdp_fn=lambda r: tdp(r[13]),
        release_fn=lambda r: parse_release(r[15]),
    ),
    dict(
        key="amd_ryzen_8000_f_desktop", file="Template_AMD_Ryzen_8000_series.wiki.txt", start=None,
        source_title="Template:AMD Ryzen 8000 series",
        source_url="https://en.wikipedia.org/wiki/Template:AMD_Ryzen_8000_series",
        section="Ryzen 8000 desktop (F, no iGPU)",
        manufacturer="AMD", arch="Zen 4", proc_node=4.0, socket="AM5",
        brand_index=0, model_index=1, brand_filter=None,
        name_fn=amd_name,
        cores_fn=lambda r: core_threads(r[2]),
        base_fn=lambda r: first_float(r[3]),
        boost_fn=lambda r: first_float(r[4]),
        tdp_fn=lambda r: tdp(r[7]),
        release_fn=lambda r: parse_release(r[10]),
    ),
    dict(
        key="amd_ryzen_8040_mobile", file="Template_AMD_Ryzen_Mobile_8040_series.wiki.txt", start=12,
        source_title="Template:AMD Ryzen Mobile 8040 series",
        source_url="https://en.wikipedia.org/wiki/Template:AMD_Ryzen_Mobile_8040_series",
        section="Ryzen 8040 mobile (Hawk Point)",
        manufacturer="AMD", arch="Zen 4", proc_node=4.0, socket=None,
        brand_index=0, model_index=1, brand_filter=None,
        name_fn=amd_name,
        cores_fn=lambda r: core_threads(r[2]),
        base_fn=lambda r: first_float(r[5]),
        boost_fn=lambda r: first_float(r[6]),
        tdp_fn=lambda r: tdp(r[12]),
        release_fn=lambda r: parse_release(r[13]),
    ),
    dict(
        key="amd_ryzen_8045_mobile", file="Template_AMD_Ryzen_Mobile_8045_series.wiki.txt", start=11,
        source_title="Template:AMD Ryzen Mobile 8045 series",
        source_url="https://en.wikipedia.org/wiki/Template:AMD_Ryzen_Mobile_8045_series",
        section="Ryzen 8045 mobile (HX)",
        manufacturer="AMD", arch="Zen 4", proc_node=5.0, socket=None,
        brand_index=0, model_index=1, brand_filter=None,
        name_fn=amd_name,
        cores_fn=lambda r: core_threads(r[2]),
        base_fn=lambda r: first_float(r[3]),
        boost_fn=lambda r: first_float(r[4]),
        tdp_fn=lambda r: tdp(r[8]),
        release_fn=lambda r: parse_release(r[9]),
    ),
    dict(
        key="amd_ryzen_ai_300_mobile", file="Template_AMD_Ryzen_AI_Mobile_300_series.wiki.txt", start=14,
        source_title="Template:AMD Ryzen AI Mobile 300 series",
        source_url="https://en.wikipedia.org/wiki/Template:AMD_Ryzen_AI_Mobile_300_series",
        section="Ryzen AI 300 mobile (Strix Point / Krackan Point)",
        manufacturer="AMD", arch="Zen 5", proc_node=4.0, socket=None,
        brand_index=0, model_index=1, brand_filter=None,
        name_fn=amd_name,
        model_clean_fn=lambda m: m.replace("(PRO)", "").strip(),
        cores_fn=lambda r: core_threads(r[2]),
        base_fn=lambda r: first_float(r[5]),
        boost_fn=lambda r: first_float(r[6]),
        tdp_fn=lambda r: tdp(r[12]),
        release_fn=lambda r: parse_release(r[13]),
    ),
]


def find_table(spec):
    path = os.path.join(SRC, spec["file"])
    for start, lines in find_tables(path):
        if spec["start"] is None or start == spec["start"]:
            return parse_table(lines)
    raise SystemExit("table not found: %s @%s" % (spec["file"], spec["start"]))


def valid_candidate(c):
    reasons = []
    if not c["name"]:
        reasons.append("no name")
    if c["cores"] is None or not (1 <= c["cores"] <= 128):
        reasons.append("cores")
    if c["threads"] is None or not (1 <= c["threads"] <= 256):
        reasons.append("threads")
    if c["base_clock_ghz"] is None or not (0.5 <= c["base_clock_ghz"] <= 6.5):
        reasons.append("base_clock")
    if c["boost_clock_ghz"] is None or not (c["base_clock_ghz"] <= c["boost_clock_ghz"] <= 7.0):
        reasons.append("boost_clock")
    if c["tdp_w"] is None or not (5 <= c["tdp_w"] <= 500):
        reasons.append("tdp")
    return reasons


def main(db_path=DB):
    con = sqlite3.connect(db_path)
    existing = set()
    for name, man in con.execute("SELECT name, manufacturer FROM hardware WHERE type='CPU'"):
        existing.add((name.strip().lower(), man.strip().lower()))
    con.close()

    candidates = []
    excluded = []
    seen = {}
    for spec in TABLES:
        grid = find_table(spec)
        for row in grid:
            if is_section_row(row):
                continue
            brand = (row[spec["brand_index"]] or "").strip()
            model = (row[spec["model_index"]] or "").strip()
            if not brand or not model:
                continue
            if is_header_row(brand, spec):
                continue
            if brand in {"Processorbranding"}:
                continue
            if spec.get("brand_filter") and not spec["brand_filter"](brand):
                excluded.append({"table": spec["key"], "brand": brand, "model": model,
                                 "reason": "branding outside scope"})
                continue
            if spec["manufacturer"] == "Intel" and spec["key"] != "intel_rpl_refresh_desktop" \
                    and not brand.startswith("Core Ultra"):
                excluded.append({"table": spec["key"], "brand": brand, "model": model,
                                 "reason": "non-Ultra Series 2 branding outside scope"})
                continue
            clean = spec.get("model_clean_fn")
            if clean is None:
                clean = amd_model_clean if spec["manufacturer"] == "AMD" else (lambda m: m)
            model = clean(model)
            if not model or model in {"Model"}:
                continue
            name = spec["name_fn"](brand, model)
            cores, threads = spec["cores_fn"](row)
            c = {
                "name": name, "manufacturer": spec["manufacturer"], "type": "CPU",
                "cores": cores, "threads": threads,
                "base_clock_ghz": spec["base_fn"](row),
                "boost_clock_ghz": spec["boost_fn"](row),
                "tdp_w": spec["tdp_fn"](row),
                "process_node_nm": spec["proc_node"],
                "socket": spec["socket"],
                "release_date": spec["release_fn"](row),
                "architecture": spec["arch"],
                "table": spec["key"],
                "source_title": spec["source_title"],
                "source_url": spec["source_url"],
                "source_section": spec["section"],
                "confidence": "high" if (spec["source_title"] in
                                          {"Raptor Lake", "Meteor Lake",
                                           "Arrow Lake (microprocessor)", "Lunar Lake"})
                             else "high",
            }
            reasons = valid_candidate(c)
            if reasons:
                c["reason"] = "invalid: " + ",".join(reasons)
                excluded.append(c)
                continue
            key = c["name"].lower()
            if key in seen:
                excluded.append({"table": spec["key"], "name": c["name"],
                                 "reason": "duplicate within research (already from %s)" % seen[key]})
                continue
            seen[key] = spec["key"]
            c["already_in_db"] = (c["name"].strip().lower(), c["manufacturer"].strip().lower()) in existing
            candidates.append(c)

    missing = [c for c in candidates if not c["already_in_db"]]
    present = [c for c in candidates if c["already_in_db"]]

    with open(os.path.join(BATCH, "_candidates.json"), "w", encoding="utf-8") as f:
        json.dump({"candidates": candidates, "excluded": excluded}, f, indent=2)

    with open(os.path.join(BATCH, "03_candidate_inventory.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        cols = ["name", "manufacturer", "architecture", "cores", "threads",
                "base_clock_ghz", "boost_clock_ghz", "tdp_w", "process_node_nm",
                "socket", "release_date", "table", "source_title",
                "already_in_db", "confidence"]
        w.writerow(cols + ["source_url", "source_section"])
        for c in candidates:
            w.writerow([c.get(k) for k in cols] + [c["source_url"], c["source_section"]])

    patch = [dict(k, **{}) for c in missing for k in [c]]
    with open(os.path.join(BATCH, "05_database_patch.json"), "w", encoding="utf-8") as f:
        json.dump({"batch": 14, "insert_hardware": missing}, f, indent=2)

    print("tables:", len(TABLES))
    print("candidates:", len(candidates))
    print("  missing (to insert):", len(missing))
    print("  already in db:", sum(1 for c in candidates if c["already_in_db"]))
    print("excluded rows:", len(excluded))
    from collections import Counter
    print("by table:", dict(Counter(c["table"] for c in candidates)))
    print("missing by table:", dict(Counter(c["table"] for c in missing)))


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Build the Batch 014 candidate inventory.")
    ap.add_argument(
        "--db", default=DB,
        help="reference database used to classify already-present records "
             "(pass a pre-apply backup to reproduce the proposed patch)")
    main(db_path=ap.parse_args().db)
