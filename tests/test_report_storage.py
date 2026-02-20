from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from report_storage import (
    ReportFolderResolutionError,
    build_default_signed_filename,
    find_existing_signed_pdfs,
    move_or_copy_merged_pdf,
    normalize_folder_name,
    resolve_report_pdf_folder,
    resolve_versioned_target_path,
    sanitize_test_no_for_filename,
)


class ReportStorageTests(unittest.TestCase):
    def test_normalize_folder_name(self) -> None:
        self.assertEqual(normalize_folder_name("5 Report PDF"), "5reportpdf")
        self.assertEqual(normalize_folder_name("5-ReportPdf"), "5reportpdf")

    def test_sanitize_test_no_for_filename(self) -> None:
        self.assertEqual(sanitize_test_no_for_filename("2026/077"), "2026_077")
        self.assertEqual(build_default_signed_filename("2026/077"), "2026_077_Report_Signed.pdf")

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

    def test_resolve_versioned_target_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir)
            first = target / "2026_077_Report_Signed.pdf"
            second = target / "2026_077_Report_Signed_V2.pdf"
            first.write_bytes(b"one")
            second.write_bytes(b"two")

            out = resolve_versioned_target_path(target, "2026_077_Report_Signed.pdf")
            self.assertEqual(out.name, "2026_077_Report_Signed_V3.pdf")

    def test_find_existing_signed_pdfs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir)
            (target / "2026_077_Report_Signed.pdf").write_bytes(b"a")
            (target / "2026_077_Report_Signed_V2.pdf").write_bytes(b"b")
            (target / "2026_078_Report_Signed.pdf").write_bytes(b"c")

            found = find_existing_signed_pdfs(target, "2026/077")
            self.assertEqual([p.name for p in found], ["2026_077_Report_Signed.pdf", "2026_077_Report_Signed_V2.pdf"])

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
