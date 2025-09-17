#!/usr/bin/env python3
"""
Housekeeping: archive backend/backup and remove compiled caches.

Actions (safe by default):
- Create tar.gz archive of backend/backup at backend/_archive/backup_<ts>.tar.gz
- Remove backend/backup contents after archive, leave a README stub
- Remove all __pycache__ folders under backend/

Usage:
  python backend/scripts/cleanup_backups.py
"""
import os
import tarfile
import shutil
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKUP_DIR = ROOT / 'backend' / 'backup'
ARCHIVE_DIR = ROOT / 'backend' / '_archive'


def archive_backup():
    if not BACKUP_DIR.exists():
        print(f"No backup dir: {BACKUP_DIR}")
        return None
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    out = ARCHIVE_DIR / f'backup_{ts}.tar.gz'
    with tarfile.open(out, 'w:gz') as tar:
        tar.add(BACKUP_DIR, arcname='backup')
    print(f"Archived backup -> {out}")
    return out


def clear_backup():
    if not BACKUP_DIR.exists():
        return
    # Remove all contents
    for p in BACKUP_DIR.iterdir():
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        else:
            try:
                p.unlink()
            except Exception:
                pass
    # Leave a README stub
    README = BACKUP_DIR / 'README.md'
    README.write_text(
        """This directory was cleaned by cleanup_backups.py.
Archived content is stored under backend/_archive/ with timestamped tarballs.
""",
        encoding='utf-8'
    )
    print(f"Cleaned: {BACKUP_DIR}")


def remove_pycache():
    backend_root = ROOT / 'backend'
    count = 0
    for dirpath, dirnames, filenames in os.walk(backend_root):
        for d in list(dirnames):
            if d == '__pycache__':
                p = Path(dirpath) / d
                shutil.rmtree(p, ignore_errors=True)
                count += 1
    print(f"Removed __pycache__ dirs: {count}")


def main():
    out = archive_backup()
    clear_backup()
    remove_pycache()


if __name__ == '__main__':
    main()

