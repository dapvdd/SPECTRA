"""Stage 2 demo: acquire real GPU Ark values + quarantine demo.

Read-only against the source CSV; writes nothing to any database.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.scripts import source_acquisition as sa


def main() -> None:
    adapter = sa.GpuArkAdapter.from_csv(
        r"C:\Users\user\spectra-local\data\research\batch017\gpuark-gpu-specs.csv"
    )
    rows = adapter.rows_for()
    print(f"[gpuark] rows loaded: {len(rows)}")
    print(f"[gpuark] license: {adapter.license_status} ({adapter.license_name})")

    for field in ("base_clock_mhz", "boost_clock_mhz", "tdp_w"):
        vals = sa.acquire(adapter, field=field)
        non_null = sum(1 for v in vals if v.normalized_value is not None)
        print(
            f"[gpuark] field={field!r}: {len(vals)} acquisitions, "
            f"{non_null} populated, unit={vals[0].unit!r}"
        )

    tdp = sa.acquire(adapter, field="tdp_w")
    sample = next(v for v in tdp if v.normalized_value is not None)
    print(
        f"[gpuark] sample: {sample.hardware_name} -> {sample.normalized_value} "
        f"{sample.unit} | license={sample.license_status} | ref={sample.source_reference}"
    )

    # --- quarantine demo: restricted sources must NOT publish ---
    for name, cls in (("PassMark", sa.PassMarkAdapter), ("TechPowerUp", sa.TechPowerUpAdapter)):
        verdict = sa.SourceLicenseGate().verdict(cls)
        print(
            f"[gate] {name}: license={cls.license_status!r} -> "
            f"allow={verdict.allow} action={verdict.action!r} reason={verdict.reason!r}"
        )


if __name__ == "__main__":
    main()
