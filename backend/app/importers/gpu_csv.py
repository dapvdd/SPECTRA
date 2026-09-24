import csv
from pathlib import Path

REQUIRED_COLUMNS = (
    "Brand",
    "Name",
    "Graphics Card__Release Date",
    "Graphics Processor__Architecture",
    "Memory__Memory Size",
    "Memory__Memory Type",
    "Memory__Bandwidth",
    "Clock Speeds__GPU Clock",
    "Clock Speeds__Boost Clock",
    "Board Design__TDP",
    "Graphics Card__Bus Interface",
    "Board Design__Length",
)


def read_gpu_csv(file_path: str | Path) -> list[dict[str, str | None]]:
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"GPU CSV not found: {path}")

    try:
        with path.open(
            mode="r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            reader = csv.DictReader(file)

            if reader.fieldnames is None:
                raise ValueError("GPU CSV must contain a header row.")

            missing = [
                column
                for column in REQUIRED_COLUMNS
                if column not in reader.fieldnames
            ]

            if missing:
                raise ValueError(
                    "GPU CSV is missing required columns: "
                    + ", ".join(missing)
                )

            return list(reader)
    except UnicodeDecodeError as error:
        raise ValueError(
            f"GPU CSV is not valid UTF-8 text: {path}"
        ) from error