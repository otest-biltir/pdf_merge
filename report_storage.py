from __future__ import annotations

import re
import shutil
from pathlib import Path


class ReportFolderResolutionError(RuntimeError):
    """Raised when report target folder cannot be resolved."""


def normalize_folder_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", name).lower()


def resolve_report_pdf_folder(main_path: str) -> Path:
    root = Path(main_path)
    if not root.exists() or not root.is_dir():
        raise ReportFolderResolutionError(f"main_path geçersiz veya bulunamadı: {main_path}")

    report_files_dir: Path | None = None
    for child in root.iterdir():
        if child.is_dir() and child.name.casefold() == "report files":
            report_files_dir = child
            break

    if report_files_dir is None:
        raise ReportFolderResolutionError(
            f"'{main_path}' altında 'report files' klasörü bulunamadı."
        )

    for child in report_files_dir.iterdir():
        if child.is_dir() and normalize_folder_name(child.name) == "5reportpdf":
            return child

    return report_files_dir


def move_or_copy_merged_pdf(
    merged_pdf_path: Path,
    target_dir: Path,
    filename: str,
    overwrite: bool = True,
) -> Path:
    if not merged_pdf_path.exists() or not merged_pdf_path.is_file():
        raise FileNotFoundError(f"Birleştirilmiş PDF bulunamadı: {merged_pdf_path}")

    if not target_dir.exists() or not target_dir.is_dir():
        raise ReportFolderResolutionError(f"Hedef klasör bulunamadı: {target_dir}")

    safe_name = filename.strip() if filename and filename.strip() else merged_pdf_path.name
    if not safe_name.lower().endswith(".pdf"):
        safe_name = f"{safe_name}.pdf"

    target_path = target_dir / safe_name

    if target_path.exists() and not overwrite:
        raise FileExistsError(f"Hedef dosya zaten var: {target_path}")

    temp_target = target_path.with_suffix(target_path.suffix + ".tmp")
    shutil.copy2(merged_pdf_path, temp_target)
    temp_target.replace(target_path)
    return target_path
