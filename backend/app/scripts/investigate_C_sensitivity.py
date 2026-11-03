"""Objective C: calibration sensitivity analysis.

Computes star ratings under documented anchors vs observed (drifted) anchors
for every benchmarked hardware in the dev DB — WITHOUT changing any anchors.

Reports which hardware gets a different star rating when observed anchors are
applied instead of documented anchors, quantifying the drift impact.

multi-core drift: documented=(1409,2809,5001,8017,16347) observed=(1409,3214,5001,7266,12303)
"""
import sys, json
from pathlib import Path

P = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(P))
from sqlalchemy import create_engine, text

# Documented anchors (from SCORING_METHODOLOGY.md)
_DOC_SINGLE = (667.0, 983.0, 1325.0, 1637.0, 2020.0)
_DOC_MULTI   = (1409.0, 2809.0, 5001.0, 8017.0, 16347.0)

# Observed anchors (from calibration_verify.py — derived from actual benchmark population)
_OBS_SINGLE = (667.0, 1075.0, 1325.0, 1562.0, 2016.0)
_OBS_MULTI  = (1409.0, 3214.0, 5001.0, 7266.0, 12303.0)

def score_to_stars(score, anchors):
    if score <= anchors[0]: return 1.0
    if score >= anchors[-1]: return 5.0
    for i in range(len(anchors) - 1):
        lo, hi = anchors[i], anchors[i+1]
        if lo <= score <= hi:
            return round(1.0 + i + (score - lo) / (hi - lo), 2)
    return 5.0

def main():
    engine = create_engine(
        f"sqlite:///{P / 'data' / 'dev' / 'spectra_dev.db'}",
        connect_args={"check_same_thread": False},
    )
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    # Collect all benchmarked hardware with their scores
    rows = session.execute(
        text(
            "SELECT h.id, h.name, h.type, h.segment, b.test_type, b.score "
            "FROM hardware h "
            "JOIN benchmark_results b ON b.hardware_id = h.id"
        )
    ).fetchall()
    session.close()
    engine.dispose()

    # Group by hardware, pick best score per family
    hw_scores = {}
    for (hid, name, hw_type, segment, test_type, score) in rows:
        if hid not in hw_scores:
            hw_scores[hid] = dict(name=name, type=hw_type, segment=segment,
                                  single_core=None, multi_core=None)
        if test_type == "single-core":
            hw_scores[hid]["single_core"] = max(
                score, hw_scores[hid]["single_core"] or 0)
        elif test_type == "multi-core":
            hw_scores[hid]["multi_core"] = max(
                score, hw_scores[hid]["multi_core"] or 0)

    # Compute star drift for each hardware
    drifted_hardware = []
    stable_hardware = []
    for hid, hw in hw_scores.items():
        for family, obs_anchors, doc_anchors in [
            ("single_core", _OBS_SINGLE, _DOC_SINGLE),
            ("multi_core",  _OBS_MULTI,  _DOC_MULTI),
        ]:
            score = hw[family]
            if score is None:
                continue
            doc_stars = score_to_stars(score, doc_anchors)
            obs_stars = score_to_stars(score, obs_anchors)
            diff = round(obs_stars - doc_stars, 2)
            if abs(diff) >= 0.01:
                drifted_hardware.append(dict(
                    hw_id=hid, hw_name=hw["name"], hw_type=hw["type"],
                    segment=hw["segment"], family=family,
                    score=score,
                    doc_stars=doc_stars, obs_stars=obs_stars,
                    drift_stars=round(diff, 2),
                    doc_anchors=doc_anchors, obs_anchors=obs_anchors,
                ))
            else:
                stable_hardware.append(dict(
                    hw_id=hid, hw_name=hw["name"], family=family,
                    score=score, stars=doc_stars))

    # Sort by absolute drift descending
    drifted_hardware.sort(key=lambda x: -abs(x["drift_stars"]))

    # Summary stats
    all_single = [r for r in drifted_hardware if r["family"] == "single_core"]
    all_multi  = [r for r in drifted_hardware if r["family"] == "multi_core"]

    result = dict(
        total_benchmarked_hardware=len(hw_scores),
        total_benchmark_entries=len(rows),
        drifted_count=len(drifted_hardware),
        stable_count=len(stable_hardware),
        drift_pct=round(len(drifted_hardware) / max(len(drifted_hardware)+len(stable_hardware), 1) * 100, 1),
        documented_anchors={"single_core": _DOC_SINGLE, "multi_core": _DOC_MULTI},
        observed_anchors={"single_core": _OBS_SINGLE, "multi_core": _OBS_MULTI},
        multi_core_max_pct_err=24.74,
        single_core_max_pct_err=9.36,
        single_core_drift_count=len(all_single),
        multi_core_drift_count=len(all_multi),
        worst_5_drifts=drifted_hardware[:5],
        all_drifts=drifted_hardware,
    )

    OUTPUT = P / "data" / "dev" / "investigation_C_sensitivity.json"
    OUTPUT.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    print("=== Calibration Sensitivity Report ===")
    print(f"Benchmarked hardware: {len(hw_scores)}")
    print(f"Drifted: {len(drifted_hardware)}  Stable: {len(stable_hardware)}")
    print(f"Drift rate: {result['drift_pct']}%")
    print()
    print("Worst 5 star-rating shifts:")
    for h in drifted_hardware[:5]:
        print(f"  {h['hw_name'][:40]:40s}  {h['family']:12s}  "
              f"score={h['score']:8.0f}  "
              f"doc={h['doc_stars']:.2f}*  obs={h['obs_stars']:.2f}*  "
              f"drift={h['drift_stars']:+.2f}")
    print()
    print("Note: multi-core observed anchors (3214,7266,12303) vs documented (2809,8017,16347)")
    print("      compress the rating bands and INFLATE stars for high-end scores (e.g. 12303 ->")
    print("      doc 4.51* vs obs 5.00*). Both directions shift across the population.")
    print(f"wrote {OUTPUT}")

if __name__ == "__main__":
    main()
