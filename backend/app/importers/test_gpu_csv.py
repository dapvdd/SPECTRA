import csv
import tempfile
import unittest
from pathlib import Path

from backend.app.importers.gpu_csv import REQUIRED_COLUMNS, read_gpu_csv


def _write_bytes(data: bytes) -> Path:
    file = tempfile.NamedTemporaryFile(
        mode="wb",
        suffix=".csv",
        delete=False,
    )
    file.write(data)
    file.close()
    path = Path(file.name)
    return path


def _write_rows(rows: list[dict[str, str]]) -> Path:
    file = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        suffix=".csv",
        delete=False,
    )
    writer = csv.DictWriter(file, fieldnames=list(REQUIRED_COLUMNS))
    writer.writeheader()
    writer.writerows(rows)
    file.close()
    return Path(file.name)


RTX_5090_ROW = {
    "Brand": "NVIDIA",
    "Name": "GeForce RTX 5090",
    "Graphics Card__Release Date": "Jan 30th, 2025",
    "Graphics Processor__Architecture": "Blackwell 2.0",
    "Memory__Memory Size": "32 GB",
    "Memory__Memory Type": "GDDR7",
    "Memory__Bandwidth": "1.79 TB/s",
    "Clock Speeds__GPU Clock": "",
    "Clock Speeds__Boost Clock": "2407 MHz",
    "Board Design__TDP": "575 W",
    "Graphics Card__Bus Interface": "PCIe 5.0 x16",
    "Board Design__Length": "304 mm 12 inches",
}


class GpuCsvTests(unittest.TestCase):
    def setUp(self):
        self.paths = []
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for path in self.paths:
            path.unlink(missing_ok=True)

    def _track(self, path: Path) -> Path:
        self.paths.append(path)
        return path

    def _valid_file(self, rows) -> Path:
        return self._track(_write_rows(rows))

    def test_valid_csv_returns_rows_with_raw_values(self):
        path = self._valid_file([RTX_5090_ROW, {
            **RTX_5090_ROW,
            "Name": "GeForce RTX 5080",
            "Memory__Memory Size": "16 GB",
        }])

        rows = read_gpu_csv(path)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["Brand"], "NVIDIA")
        self.assertEqual(rows[0]["Memory__Memory Size"], "32 GB")
        self.assertEqual(rows[0]["Clock Speeds__GPU Clock"], "")
        self.assertEqual(rows[1]["Name"], "GeForce RTX 5080")

    def test_utf8_bom_is_stripped(self):
        header = ",".join(REQUIRED_COLUMNS)
        data = ("\ufeff" + header + "\n").encode("utf-8")
        path = self._track(_write_bytes(data))

        rows = read_gpu_csv(path)

        self.assertEqual(rows, [])

    def test_header_only_csv_returns_no_rows(self):
        path = self._valid_file([])

        self.assertEqual(read_gpu_csv(path), [])

    def test_empty_file_raises_error(self):
        path = self._track(_write_bytes(b""))

        with self.assertRaises(ValueError) as ctx:
            read_gpu_csv(path)

        self.assertIn("header", str(ctx.exception))

    def test_missing_required_columns_raises_error(self):
        path = self._track(_write_bytes(b"Brand,Name\nNVIDIA,GeForce RTX 5090\n"))

        with self.assertRaises(ValueError) as ctx:
            read_gpu_csv(path)

        message = str(ctx.exception)
        self.assertIn("missing required columns", message)
        self.assertIn("Memory__Memory Size", message)
        self.assertIn("Board Design__TDP", message)

    def test_missing_file_raises_file_not_found(self):
        missing = Path(tempfile.gettempdir()) / "does-not-exist-gpu.csv"

        with self.assertRaises(FileNotFoundError):
            read_gpu_csv(missing)

    def test_non_utf8_file_raises_error(self):
        path = self._track(_write_bytes(b"\xff\xfe\x00not-utf8"))

        with self.assertRaises(ValueError) as ctx:
            read_gpu_csv(path)

        self.assertIn("UTF-8", str(ctx.exception))

    def test_malformed_short_row_is_not_discarded(self):
        header = ",".join(REQUIRED_COLUMNS)
        line = header + "\nNVIDIA,GeForce RTX 5090\n"
        path = self._track(_write_bytes(line.encode("utf-8")))

        rows = read_gpu_csv(path)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Brand"], "NVIDIA")
        self.assertEqual(rows[0]["Name"], "GeForce RTX 5090")
        self.assertIsNone(rows[0]["Board Design__TDP"])

    def test_representative_real_dataset_row_is_read_raw(self):
        path = self._valid_file([{
            **RTX_5090_ROW,
            "Brand": "ATI",
            "Name": "Color Emulation Card",
            "Graphics Card__Release Date": "Aug 4th, 1986",
            "Memory__Memory Size": "32 KB",
            "Memory__Memory Type": "DRAM",
            "Memory__Bandwidth": "20.00 MB/s",
            "Clock Speeds__GPU Clock": "10 MHz",
            "Clock Speeds__Boost Clock": "",
            "Board Design__TDP": "unknown",
            "Graphics Card__Bus Interface": "ISA 8-bit",
            "Board Design__Length": "",
        }])

        rows = read_gpu_csv(path)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Memory__Memory Size"], "32 KB")
        self.assertEqual(rows[0]["Board Design__TDP"], "unknown")
        self.assertEqual(rows[0]["Clock Speeds__Boost Clock"], "")


if __name__ == "__main__":
    unittest.main()