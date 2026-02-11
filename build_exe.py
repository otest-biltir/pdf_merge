from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
MAIN_FILE = PROJECT_ROOT / "main.py"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
SPEC_FILE = PROJECT_ROOT / "pdf_merge.spec"


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def ensure_pyinstaller() -> None:
    if shutil.which("pyinstaller"):
        return

    print("PyInstaller bulunamadı, kuruluyor...")
    run([sys.executable, "-m", "pip", "install", "pyinstaller"])


def clean_artifacts() -> None:
    for path in (DIST_DIR, BUILD_DIR, SPEC_FILE):
        if path.is_dir():
            shutil.rmtree(path)
            print(f"Temizlendi: {path}")
        elif path.is_file():
            path.unlink()
            print(f"Silindi: {path}")


def build(one_file: bool = True, windowed: bool = True) -> None:
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--name",
        "pdf_merge",
    ]

    if one_file:
        cmd.append("--onefile")
    if windowed:
        cmd.append("--windowed")

    cmd.append(str(MAIN_FILE))
    run(cmd)


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF Merge uygulaması için .exe oluşturur.")
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Build öncesi dist/build/spec dosyalarını silmez.",
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="GUI yerine konsol penceresi açık olacak şekilde paketler.",
    )
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="Tek exe yerine klasör çıktısı üretir.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Komutları yazdırır, çalıştırmaz.",
    )
    args = parser.parse_args()

    if not MAIN_FILE.exists():
        raise FileNotFoundError(f"Bulunamadı: {MAIN_FILE}")

    if args.dry_run:
        print("Dry-run aktif. Aşağıdaki işlemler yapılacaktı:")
        print("- PyInstaller kontrol/kurulum")
        if not args.no_clean:
            print("- dist/, build/ ve .spec temizliği")
        print("- PyInstaller ile build")
        return

    ensure_pyinstaller()

    if not args.no_clean:
        clean_artifacts()

    build(one_file=not args.onedir, windowed=not args.console)

    if args.onedir:
        output_path = DIST_DIR / "pdf_merge"
    else:
        output_path = DIST_DIR / "pdf_merge.exe"

    print(f"\nBuild tamamlandı. Çıktı: {output_path}")


if __name__ == "__main__":
    main()
