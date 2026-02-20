from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
MAIN_FILE = PROJECT_ROOT / "main.py"
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"
ICON_CANDIDATES = [
    PROJECT_ROOT / "converted_logo_white.ico",
    PROJECT_ROOT / "converted_logo.ico",
]
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
SPEC_FILE = PROJECT_ROOT / "pdf_merge.spec"
FINAL_EXE = PROJECT_ROOT / "pdf_merge.exe"
FINAL_ONEDIR = PROJECT_ROOT / "pdf_merge"


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def ensure_pyinstaller() -> None:
    if shutil.which("pyinstaller"):
        return

    print("PyInstaller bulunamadı, kuruluyor...")
    run([sys.executable, "-m", "pip", "install", "pyinstaller"])


def ensure_runtime_dependencies() -> None:
    if not REQUIREMENTS_FILE.exists():
        return

    print("Runtime bağımlılıkları kontrol ediliyor/kuruluyor...")
    run([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)])


def clean_artifacts() -> None:
    for path in (DIST_DIR, BUILD_DIR, SPEC_FILE, FINAL_EXE, FINAL_ONEDIR):
        if path.is_dir():
            shutil.rmtree(path)
            print(f"Temizlendi: {path}")
        elif path.is_file():
            path.unlink()
            print(f"Silindi: {path}")


def _get_icon_file() -> Path | None:
    for icon_path in ICON_CANDIDATES:
        if icon_path.exists():
            return icon_path
    return None


def build(one_file: bool = True, windowed: bool = True) -> None:
    data_separator = ";" if sys.platform.startswith("win") else ":"
    icon_file = _get_icon_file()
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--name",
        "pdf_merge",
        "--hidden-import",
        "pypdf",
        "--hidden-import",
        "fitz",
        "--add-data",
        f"{REQUIREMENTS_FILE}{data_separator}.",
    ]

    if icon_file is not None:
        cmd.extend(["--icon", str(icon_file)])
        cmd.extend(["--add-data", f"{icon_file}{data_separator}."])

    if one_file:
        cmd.append("--onefile")
    if windowed:
        cmd.append("--windowed")

    cmd.append(str(MAIN_FILE))
    run(cmd)


def move_output(one_file: bool) -> Path:
    if one_file:
        source = DIST_DIR / "pdf_merge.exe"
        if not source.exists():
            raise FileNotFoundError(f"Beklenen exe çıktısı bulunamadı: {source}")

        shutil.move(str(source), str(FINAL_EXE))
        if DIST_DIR.exists() and not any(DIST_DIR.iterdir()):
            DIST_DIR.rmdir()
        return FINAL_EXE

    source_dir = DIST_DIR / "pdf_merge"
    if not source_dir.exists():
        raise FileNotFoundError(f"Beklenen onedir çıktısı bulunamadı: {source_dir}")

    shutil.move(str(source_dir), str(FINAL_ONEDIR))
    if DIST_DIR.exists() and not any(DIST_DIR.iterdir()):
        DIST_DIR.rmdir()
    return FINAL_ONEDIR


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF Merge uygulaması için .exe oluşturur.")
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Build öncesi dist/build/spec ve hedef çıktı dosyalarını silmez.",
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

    icon_file = _get_icon_file()
    if icon_file is None:
        candidate_list = ", ".join(str(path) for path in ICON_CANDIDATES)
        raise FileNotFoundError(f"Uygulama ikonu bulunamadı. Denenen dosyalar: {candidate_list}")

    if args.dry_run:
        print("Dry-run aktif. Aşağıdaki işlemler yapılacaktı:")
        print("- PyInstaller kontrol/kurulum")
        print("- Runtime bağımlılıklarını pip ile kurma (requirements.txt)")
        if not args.no_clean:
            print("- dist/, build/, .spec ve hedef çıktı temizliği")
        print("- PyInstaller ile build")
        print("- Çıktıyı proje kök klasörüne taşıma")
        return

    ensure_pyinstaller()
    ensure_runtime_dependencies()

    if not args.no_clean:
        clean_artifacts()

    one_file = not args.onedir
    build(one_file=one_file, windowed=not args.console)
    output_path = move_output(one_file=one_file)

    print(f"\nBuild tamamlandı. Çıktı: {output_path}")


if __name__ == "__main__":
    main()
