from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.error import URLError


DEFAULT_BASE_DIR = Path(r"D:\mcQlib\data\qlib_bin")
DEFAULT_REMOTE_BASE = "https://github.com/SunsetWolf/qlib_dataset/releases/download"
REQUIRED_DIRS = ("calendars", "features", "instruments")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download official/community qlib daily bin datasets without requiring the qlib package."
    )
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE_DIR)
    parser.add_argument("--regions", nargs="+", default=["cn", "us"], choices=["cn", "us", "in"])
    parser.add_argument("--version", default="v2", help="Release version folder, for example v2.")
    parser.add_argument("--interval", default="1d", choices=["1d", "1min"])
    parser.add_argument("--remote-base", default=DEFAULT_REMOTE_BASE)
    parser.add_argument("--keep-zip", action="store_true")
    parser.add_argument("--skip-download", action="store_true", help="Reuse an existing zip in downloads dir if present.")
    parser.add_argument("--no-replace", action="store_true", help="Only download/extract staging data; do not replace targets.")
    parser.add_argument("--retries", type=int, default=8)
    return parser.parse_args()


def target_name(region: str) -> str:
    return f"{region.lower()}_data"


def dataset_file_name(region: str, interval: str) -> str:
    return f"qlib_data_{region.lower()}_{interval.lower()}_latest.zip"


def dataset_url(remote_base: str, version: str, region: str, interval: str) -> str:
    return f"{remote_base.rstrip('/')}/{version}/{dataset_file_name(region, interval)}"


def _content_range_total(value: str | None) -> int | None:
    if not value or "/" not in value:
        return None
    try:
        return int(value.rsplit("/", 1)[1])
    except Exception:
        return None


def _is_valid_zip(path: Path) -> bool:
    if not path.exists() or path.stat().st_size <= 0:
        return False
    if not zipfile.is_zipfile(path):
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.testzip() is None
    except Exception:
        return False


def _request(url: str, start: int) -> urllib.request.Request:
    headers = {
        "Accept": "application/octet-stream",
        "User-Agent": "FactorPlatform-QlibDownloader/1.0",
    }
    if start > 0:
        headers["Range"] = f"bytes={start}-"
    return urllib.request.Request(url, headers=headers)


def download(url: str, destination: Path, retries: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(destination.suffix + ".part")
    if destination.exists():
        if _is_valid_zip(destination):
            print(f"  existing valid zip found: {destination}")
            return
        destination.unlink()

    last_error: Exception | None = None
    expected_total: int | None = None
    for attempt in range(1, max(1, retries) + 1):
        start = temp_path.stat().st_size if temp_path.exists() else 0
        try:
            request = _request(url, start)
            with urllib.request.urlopen(request, timeout=120) as response:
                status = getattr(response, "status", None)
                if start > 0 and status == 200:
                    # Server ignored Range; restart cleanly.
                    temp_path.unlink(missing_ok=True)
                    start = 0

                content_type = response.headers.get("Content-Type", "")
                range_total = _content_range_total(response.headers.get("Content-Range"))
                content_length = int(response.headers.get("Content-Length") or 0)
                expected_total = range_total or (start + content_length if content_length else expected_total)
                mode = "ab" if start > 0 else "wb"
                downloaded = start
                started = time.time()
                with temp_path.open(mode) as file_obj:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        file_obj.write(chunk)
                        downloaded += len(chunk)
                        if expected_total:
                            pct = min(downloaded / expected_total * 100, 100.0)
                            elapsed = max(time.time() - started, 1e-6)
                            mbps = max(downloaded - start, 0) / 1024 / 1024 / elapsed
                            print(
                                f"  {destination.name}: {pct:5.1f}% "
                                f"{downloaded / 1024 / 1024:,.1f}/{expected_total / 1024 / 1024:,.1f} MiB "
                                f"@ {mbps:,.1f} MiB/s",
                                end="\r",
                            )
                print()

                current_size = temp_path.stat().st_size
                if expected_total and current_size < expected_total:
                    print(
                        f"  connection ended early on attempt {attempt}; "
                        f"{current_size:,}/{expected_total:,} bytes downloaded. Resuming..."
                    )
                    time.sleep(min(2 * attempt, 10))
                    continue

                temp_path.replace(destination)
                if _is_valid_zip(destination):
                    print(f"  downloaded valid zip: {destination} ({destination.stat().st_size / 1024 / 1024:,.1f} MiB)")
                    return

                head = destination.read_bytes()[:200]
                raise RuntimeError(
                    f"downloaded file is not a complete zip; content_type={content_type!r}; "
                    f"head={head!r}"
                )
        except (URLError, TimeoutError, RuntimeError, OSError) as exc:
            last_error = exc
            print(f"  attempt {attempt} failed: {exc}")
            time.sleep(min(2 * attempt, 10))

    raise RuntimeError(f"download failed after {retries} attempts: {last_error}")


def find_dataset_root(root: Path) -> Path:
    candidates = [root]
    candidates.extend(path for path in root.rglob("*") if path.is_dir())
    for candidate in candidates:
        if all((candidate / name).exists() for name in REQUIRED_DIRS):
            return candidate
    raise RuntimeError(f"extracted archive does not contain {REQUIRED_DIRS}: {root}")


def read_calendar_end(dataset_root: Path) -> str | None:
    path = dataset_root / "calendars" / "day.txt"
    if not path.exists():
        return None
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return lines[-1] if lines else None


def count_instruments(dataset_root: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    ins_dir = dataset_root / "instruments"
    if not ins_dir.exists():
        return out
    for file_path in sorted(ins_dir.glob("*.txt")):
        out[file_path.stem] = sum(1 for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip())
    return out


def count_feature_dirs(dataset_root: Path) -> int:
    features = dataset_root / "features"
    if not features.exists():
        return 0
    return sum(1 for path in features.iterdir() if path.is_dir())


def replace_target(dataset_root: Path, target_dir: Path, backup_dir: Path) -> None:
    if backup_dir.exists():
        raise RuntimeError(f"backup already exists: {backup_dir}")
    if target_dir.exists():
        target_dir.rename(backup_dir)
    try:
        shutil.move(str(dataset_root), str(target_dir))
    except Exception:
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        if backup_dir.exists():
            backup_dir.rename(target_dir)
        raise


def main() -> None:
    args = parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    downloads_dir = args.base_dir / "_official_downloads"
    staging_parent = args.base_dir / f"_official_staging_{stamp}"
    staging_parent.mkdir(parents=True, exist_ok=True)

    print(f"base_dir={args.base_dir}")
    print(f"regions={','.join(args.regions)} version={args.version} interval={args.interval}")

    completed: list[dict[str, object]] = []
    for region in args.regions:
        region = region.lower()
        file_name = dataset_file_name(region, args.interval)
        zip_path = downloads_dir / file_name
        url = dataset_url(args.remote_base, args.version, region, args.interval)
        print(f"\n[{region}] url={url}")

        if args.skip_download and zip_path.exists():
            print(f"[{region}] reuse {zip_path}")
            if not _is_valid_zip(zip_path):
                raise RuntimeError(f"existing zip is incomplete or invalid: {zip_path}")
        else:
            print(f"[{region}] downloading to {zip_path}")
            download(url, zip_path, retries=args.retries)

        extract_dir = staging_parent / region
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)
        print(f"[{region}] extracting...")
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_dir)

        dataset_root = find_dataset_root(extract_dir)
        latest_date = read_calendar_end(dataset_root)
        instrument_counts = count_instruments(dataset_root)
        feature_dir_count = count_feature_dirs(dataset_root)
        print(
            f"[{region}] validated root={dataset_root} latest={latest_date} "
            f"instruments={instrument_counts} feature_dirs={feature_dir_count}"
        )

        target_dir = args.base_dir / target_name(region)
        backup_dir = args.base_dir / f"{target_name(region)}_backup_{stamp}"
        if args.no_replace:
            print(f"[{region}] no_replace=true; staging kept at {dataset_root}")
        else:
            print(f"[{region}] replacing {target_dir}; backup={backup_dir}")
            replace_target(dataset_root, target_dir, backup_dir)
            print(f"[{region}] active target={target_dir}")

        completed.append(
            {
                "region": region,
                "target": str(target_dir),
                "backup": str(backup_dir) if not args.no_replace else None,
                "latest_date": latest_date,
                "instrument_counts": instrument_counts,
                "feature_dir_count": feature_dir_count,
                "zip_path": str(zip_path),
            }
        )

        if not args.keep_zip and zip_path.exists() and not args.skip_download:
            zip_path.unlink()

    if not args.no_replace:
        shutil.rmtree(staging_parent, ignore_errors=True)

    print("\nCompleted:")
    for item in completed:
        print(item)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
