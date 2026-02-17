from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from report_storage import (
    ReportFolderResolutionError,
    move_or_copy_merged_pdf,
    normalize_folder_name,
    resolve_report_pdf_folder,
)


class ReportStorageTests(unittest.TestCase):
    def test_normalize_folder_name(self) -> None:
        self.assertEqual(normalize_folder_name("5 Report PDF"), "5reportpdf")
        self.assertEqual(normalize_folder_name("5-ReportPdf"), "5reportpdf")

    def test_resolve_returns_special_folder_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            report_files = root / "Report Files"
            report_files.mkdir()
            special = report_files / "5 Report PDF"
            special.mkdir()

            resolved = resolve_report_pdf_folder(str(root))
            self.assertEqual(resolved, special)

    def test_resolve_returns_report_files_when_special_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            report_files = root / "report files"
            report_files.mkdir()

            resolved = resolve_report_pdf_folder(str(root))
            self.assertEqual(resolved, report_files)

    def test_resolve_raises_when_report_files_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(ReportFolderResolutionError):
                resolve_report_pdf_folder(tmp_dir)

    def test_copy_merged_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            merged_pdf = root / "merged.pdf"
            merged_pdf.write_bytes(b"%PDF-1.4 mock")
            target = root / "target"
            target.mkdir()

            out = move_or_copy_merged_pdf(merged_pdf, target, "demo")
            self.assertTrue(out.exists())
            self.assertEqual(out.name, "demo.pdf")
            self.assertEqual(out.read_bytes(), merged_pdf.read_bytes())


if __name__ == "__main__":
    unittest.main()
