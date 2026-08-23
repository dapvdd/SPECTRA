import csv
from pathlib import Path


def read_cpu_csv(file_path: str | Path) -> list[dict[str, str]]:
    path = Path(file_path)

    with path.open(
        mode="r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        return list(reader)