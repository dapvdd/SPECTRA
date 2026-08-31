import csv
from pathlib import Path
from collections import Counter

from backend.app.importers.benchmark_matcher import (
    find_matching_cpu,
    load_cpu_lookup,
)
from backend.app.importers.benchmark_normalizer import (
    detect_manufacturer,
    normalize_benchmark_cpu_name,
)


path = Path.home() / "Downloads" / "benchmark-cpus.csv"

with path.open(encoding="utf-8") as file:
    rows = list(csv.DictReader(file))


print("Loading CPU database...")

lookup = load_cpu_lookup()

print("CPU loaded:", len(lookup))
print("Matching benchmark CPUs...\n")


matched = 0
unmatched = []


for row in rows:
    name = normalize_benchmark_cpu_name(
        row.get("CpuName")
    )

    manufacturer = detect_manufacturer(name)

    hardware = find_matching_cpu(
        name,
        manufacturer,
        lookup,
    )

    if hardware:
        matched += 1
    else:
        unmatched.append(
            (
                manufacturer,
                name,
            )
        )


print("TOTAL:", len(rows))
print("MATCHED:", matched)
print("UNMATCHED:", len(unmatched))


manufacturer_counts = Counter(
    manufacturer
    for manufacturer, _ in unmatched
)

print("\nUNMATCHED BY MANUFACTURER:")

for manufacturer, count in manufacturer_counts.most_common():
    print(f"{manufacturer}: {count}")


print("\nINTEL UNMATCHED SAMPLES:")

intel_samples = [
    name
    for manufacturer, name in unmatched
    if manufacturer == "Intel"
]

for name in intel_samples[:30]:
    print(name)