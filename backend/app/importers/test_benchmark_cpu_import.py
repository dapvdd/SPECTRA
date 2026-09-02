import csv
from pathlib import Path
from collections import Counter

from backend.app.database import SessionLocal
from backend.app.importers.benchmark_cpu_importer import (
    load_existing_cpu_lookup,
)
from backend.app.importers.benchmark_normalizer import (
    normalize_benchmark_cpu_name,
    normalize_benchmark_row,
)


path = Path.home() / "Downloads" / "benchmark-cpus.csv"


with path.open(
    encoding="utf-8",
    newline="",
) as file:
    rows = list(csv.DictReader(file))


print("Loading CPU database...")

with SessionLocal() as session:

    lookup = load_existing_cpu_lookup(session)

    print("CPU loaded:", len(lookup))
    print("Analyzing benchmark dataset...\n")

    existing = 0
    new = 0
    invalid = 0

    new_by_manufacturer = Counter()
    existing_without_spec = 0

    for row in rows:

        data = normalize_benchmark_row(row)

        name = normalize_benchmark_cpu_name(
            data.get("name")
        )

        manufacturer = data.get("manufacturer")

        if not name or not manufacturer:
            invalid += 1
            continue

        key = (
            str(manufacturer).lower(),
            str(name).lower(),
        )

        hardware = lookup.get(key)

        if hardware:

            existing += 1

            if hardware.cpu_specification is None:
                existing_without_spec += 1

        else:

            new += 1

            new_by_manufacturer[
                manufacturer
            ] += 1


print("TOTAL CSV:", len(rows))
print("EXISTING CPU:", existing)
print("NEW CPU:", new)
print("INVALID:", invalid)

print(
    "\nEXISTING WITHOUT SPEC:",
    existing_without_spec,
)

print("\nNEW CPU BY MANUFACTURER:")

for manufacturer, count in (
    new_by_manufacturer.most_common()
):
    print(f"{manufacturer}: {count}")