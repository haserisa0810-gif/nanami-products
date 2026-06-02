from __future__ import annotations

import argparse
import csv
import io
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile


DEFAULT_SOURCE_DIR = Path("data/location/source/municipality")
DEFAULT_OUTPUT = Path("data/location/generated/municipality_coords.csv")


@dataclass
class CoordAccumulator:
    lat_sum: float = 0.0
    lon_sum: float = 0.0
    count: int = 0

    def add(self, lat: float, lon: float) -> None:
        self.lat_sum += lat
        self.lon_sum += lon
        self.count += 1

    def merge(self, other: "CoordAccumulator") -> None:
        self.lat_sum += other.lat_sum
        self.lon_sum += other.lon_sum
        self.count += other.count

    def average(self) -> tuple[float, float]:
        return self.lat_sum / self.count, self.lon_sum / self.count


def _csv_name(zip_file: ZipFile) -> str:
    csv_names = [name for name in zip_file.namelist() if name.lower().endswith(".csv")]
    if len(csv_names) != 1:
        raise ValueError(f"ZIP内のCSVが1件ではありません: {zip_file.filename}")
    return csv_names[0]


def _is_current_row(row: dict[str, str]) -> bool:
    return row.get("更新前履歴フラグ", "0") != "1" and row.get("更新後履歴フラグ", "0") != "1"


def _read_zip_rows(zip_path: Path) -> tuple[dict[tuple[str, str], CoordAccumulator], dict[tuple[str, str], CoordAccumulator]]:
    representative: dict[tuple[str, str], CoordAccumulator] = defaultdict(CoordAccumulator)
    all_current: dict[tuple[str, str], CoordAccumulator] = defaultdict(CoordAccumulator)
    with ZipFile(zip_path) as zf:
        with zf.open(_csv_name(zf)) as raw:
            with io.TextIOWrapper(raw, encoding="cp932", newline="") as text:
                reader = csv.DictReader(text)
                for row in reader:
                    if not _is_current_row(row):
                        continue
                    prefecture = (row.get("都道府県名") or "").strip()
                    city = (row.get("市区町村名") or "").strip()
                    if not prefecture or not city:
                        continue
                    try:
                        lat = float(row["緯度"])
                        lon = float(row["経度"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    key = (prefecture, city)
                    all_current[key].add(lat, lon)
                    if row.get("代表フラグ", "0") == "1":
                        representative[key].add(lat, lon)
    return representative, all_current


def generate(source_dir: Path, output_path: Path, *, verbose: bool = False) -> tuple[int, int]:
    zip_paths = sorted(source_dir.glob("*.zip"))
    if not zip_paths:
        raise ValueError(f"ZIPファイルが見つかりません: {source_dir}")

    representative_points: dict[tuple[str, str], CoordAccumulator] = defaultdict(CoordAccumulator)
    all_points: dict[tuple[str, str], CoordAccumulator] = defaultdict(CoordAccumulator)
    for index, zip_path in enumerate(zip_paths, start=1):
        if verbose:
            print(f"reading {index}/{len(zip_paths)} {zip_path.name}", flush=True)
        representative, all_current = _read_zip_rows(zip_path)
        for key, accumulator in representative.items():
            representative_points[key].merge(accumulator)
        for key, accumulator in all_current.items():
            all_points[key].merge(accumulator)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["prefecture", "city", "lat", "lon"])
        for key in sorted(all_points):
            accumulator = representative_points.get(key)
            if not accumulator or accumulator.count == 0:
                accumulator = all_points[key]
            lat, lon = accumulator.average()
            writer.writerow([key[0], key[1], f"{lat:.6f}", f"{lon:.6f}"])

    return len(zip_paths), len(all_points)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate municipality representative coordinates CSV.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    zip_count, row_count = generate(args.source_dir, args.output, verbose=args.verbose)
    print(f"source_zips={zip_count}")
    print(f"municipalities={row_count}")
    print(f"output={args.output}")
    print(f"output_size={args.output.stat().st_size}")


if __name__ == "__main__":
    main()
