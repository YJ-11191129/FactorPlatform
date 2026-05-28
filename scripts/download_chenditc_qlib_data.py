from __future__ import annotations

import argparse
import shutil
import sys
import tarfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.error import URLError


DEFAULT_URL = "https://github.com/chenditc/investment_data/releases/latest/download/qlib_bin.tar.gz"
DEFAULT_TARGET_DIR = Path(r"D:\mcQlib\data\qlib_bin\cn_data")
REQUIRED_DIRS = ("calendars", "features", "instruments")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download the daily-updated chenditc/investment_data qlib_bin.tar.gz dataset."
    )
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--target-dir", type=Path, default=DEFAULT_TARGET_DIR)
    parser.add_argument("--download-dir", type=Path, default=Path(r"D:\mcQlib\data\qlib_bin\_chenditc_downloads"))
    parser.add_argument("--keep-archive", action="store_true")
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--no-replace", action="store_true")
    parser.add_argument("--retries", type=int, default=12)
    return parser.parse_args()


def _request(url: str, start: int) -> urllib.request.Request:
    headers = {
        "Accept": "application/octet-stream",
        "User-Agent": "FactorPlatform-Chenditc-QlibDownloader/1.0",
    }
    if start > 0:
        headers["Range"] = f"bytes={start}-"
    return urllib.request.Request(url, headers=headers)


def _content_range_total(value: str | None) -> int | None:
    if not value or "/" not in value:
        return None
    try:
        return int(value.rsplit("/", 1)[1])
    except Exception:
        return None


def _is_valid_tar(path: Path) -> bool:
    if not path.exists() or path.stat().st_size <= 0:
        return False
    if not tarfile.is_tarfile(path):
        return False
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            # Force member scan; truncated gzip/tar files fail here.
            archive.getmembers()
        return True
    except Exception:
        return False


def download(url: str, destination: Path, retries: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(destination.suffix + ".part")
    if destination.exists():
        if _is_valid_tar(destination):
            print(f"existing valid archive found: {destination}; refreshing from remote")
        else:
            destination.unlink()
    temp_path.unlink(missing_ok=True)

    expected_total: int | None = None
    last_error: Exception | None = None
    for attempt in range(1, max(1, retries) + 1):
        start = temp_path.stat().st_size if temp_path.exists() else 0
        try:
            with urllib.request.urlopen(_request(url, start), timeout=120) as response:
                status = getattr(response, "status", None)
                if start > 0 and status == 200:
                    temp_path.unlink(missing_ok=True)
                    start = 0

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
                        f"connection ended early on attempt {attempt}; "
                        f"{current_size:,}/{expected_total:,} bytes downloaded. Resuming..."
                    )
                    time.sleep(min(2 * attempt, 10))
                    continue

                temp_path.replace(destination)
                if _is_valid_tar(destination):
                    print(f"downloaded valid archive: {destination} ({destination.stat().st_size / 1024 / 1024:,.1f} MiB)")
                    return

                head = destination.read_bytes()[:200]
                raise RuntimeError(f"downloaded file is not a complete tar.gz; head={head!r}")
        except (URLError, TimeoutError, RuntimeError, OSError) as exc:
            last_error = exc
            print(f"attempt {attempt} failed: {exc}")
            time.sleep(min(2 * attempt, 10))

    raise RuntimeError(f"download failed after {retries} attempts: {last_error}")


def _safe_members(archive: tarfile.TarFile, extract_root: Path) -> list[tarfile.TarInfo]:
    root = extract_root.resolve()
    safe: list[tarfile.TarInfo] = []
    for member in archive.getmembers():
        target = (extract_root / member.name).resolve()
        if root not in (target, *target.parents):
            raise RuntimeError(f"unsafe tar member path: {member.name}")
        safe.append(member)
    return safe


def extract_archive(archive_path: Path, extract_root: Path) -> Path:
    if extract_root.exists():
        shutil.rmtree(extract_root)
    extract_root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, mode="r:gz") as archive:
        archive.extractall(extract_root, members=_safe_members(archive, extract_root))
    return find_dataset_root(extract_root)


def find_dataset_root(root: Path) -> Path:
    candidates = [root]
    candidates.extend(path for path in root.rglob("*") if path.is_dir())
    for candidate in candidates:
        if all((candidate / name).exists() for name in REQUIRED_DIRS):
            return candidate
    raise RuntimeError(f"extracted archive does not contain {REQUIRED_DIRS}: {root}")


def read_calendar_range(dataset_root: Path) -> tuple[str | None, str | None, int]:
    path = dataset_root / "calendars" / "day.txt"
    if not path.exists():
        return None, None, 0
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return (lines[0], lines[-1], len(lines)) if lines else (None, None, 0)


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
    archive_path = args.download_dir / "chenditc_investment_data_qlib_bin.tar.gz"
    staging_root = args.target_dir.parent / f"_chenditc_staging_{stamp}"
    backup_dir = args.target_dir.parent / f"{args.target_dir.name}_backup_chenditc_{stamp}"

    print(f"url={args.url}")
    print(f"target_dir={args.target_dir}")
    if args.skip_download:
        print(f"skip_download=true; using {archive_path}")
        if not _is_valid_tar(archive_path):
            raise RuntimeError(f"existing archive is incomplete or invalid: {archive_path}")
    else:
        download(args.url, archive_path, retries=args.retries)

    dataset_root = extract_archive(archive_path, staging_root)
    start, end, calendar_count = read_calendar_range(dataset_root)
    instrument_counts = count_instruments(dataset_root)
    feature_dir_count = count_feature_dirs(dataset_root)
    print(
        f"validated root={dataset_root} start={start} end={end} "
        f"calendar_count={calendar_count} instruments={instrument_counts} feature_dirs={feature_dir_count}"
    )

    if args.no_replace:
        print(f"no_replace=true; staging kept at {dataset_root}")
    else:
        print(f"replacing {args.target_dir}; backup={backup_dir}")
        replace_target(dataset_root, args.target_dir, backup_dir)
        shutil.rmtree(staging_root, ignore_errors=True)
        print(f"active target={args.target_dir}")

    if not args.keep_archive and archive_path.exists() and not args.skip_download:
        archive_path.unlink()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
