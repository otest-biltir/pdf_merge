from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Protocol


class PdfWriterProtocol(Protocol):
    def add_page(self, page: Any) -> None: ...

    def write(self, stream: Any) -> None: ...


PdfReader: Any = None
PdfWriter: Any = None
PDF_BACKEND: str | None = None


def _install_requirements_if_missing() -> None:
    requirements_path = Path(__file__).with_name("requirements.txt")
    if not requirements_path.exists():
        return

    dependency_imports = {
        "pypdf": "pypdf",
        "PyMuPDF": "fitz",
        "fitz": "fitz",
    }

    missing = False
    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        package_name = line.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].strip()
        import_name = dependency_imports.get(package_name, package_name)
        if importlib.util.find_spec(import_name) is None:
            missing = True
            break

    if not missing:
        return

    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(requirements_path)])
    except Exception as exc:
        print(f"Bağımlılıklar otomatik kurulamadı: {exc}", file=sys.stderr)


_install_requirements_if_missing()

if importlib.util.find_spec("pypdf") is not None:
    pypdf_module = importlib.import_module("pypdf")
    PdfReader = pypdf_module.PdfReader
    PdfWriter = pypdf_module.PdfWriter
    PDF_BACKEND = "pypdf"

PREVIEW_AVAILABLE = False
fitz: Any = None
if importlib.util.find_spec("fitz") is not None:
    fitz = importlib.import_module("fitz")
    PREVIEW_AVAILABLE = True


class PdfMergeApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PDF Birleştirme Aracı")
        self.root.geometry("980x680")

        self.mode_var = tk.StringVar(value="signed")

        self.signature_pdf: Path | None = None
        self.report_pdf: Path | None = None
        self.merge_pdfs: list[Path] = []

        self.signature_rotation = 0
        self.report_rotation = 0

        self.signature_preview_image: tk.PhotoImage | None = None
        self.report_preview_image: tk.PhotoImage | None = None

        self._build_ui()
        self._refresh_mode_frames()

    def _build_ui(self) -> None:
        title = ttk.Label(
            self.root,
            text="PDF Birleştirme Uygulaması",
            font=("Segoe UI", 16, "bold"),
        )
        title.pack(pady=(18, 6))

        subtitle = ttk.Label(
            self.root,
            text=(
                "İki mod desteklenir: İmzalı PDF birleştirme ve standart PDF birleştirme.\n"
                "Not: Sayfalar doğrudan kopyalandığı için çözünürlükte kayıp oluşturulmaz."
            ),
            justify="center",
        )
        subtitle.pack(pady=(0, 16))

        backend_parts = [f"PDF altyapısı: {PDF_BACKEND}" if PDF_BACKEND else "PDF altyapısı: Bulunamadı"]
        preview_backend = "aktif" if PREVIEW_AVAILABLE else "kapalı (pip install pymupdf)"
        backend_parts.append(f"Önizleme: {preview_backend}")
        backend_label = ttk.Label(self.root, text=" | ".join(backend_parts))
        backend_label.pack(pady=(0, 10))

        mode_box = ttk.LabelFrame(self.root, text="Mod Seçimi", padding=12)
        mode_box.pack(fill="x", padx=16)

        ttk.Radiobutton(
            mode_box,
            text="İmzalanmış PDF'leri Birleştir",
            value="signed",
            variable=self.mode_var,
            command=self._refresh_mode_frames,
        ).pack(anchor="w")

        ttk.Radiobutton(
            mode_box,
            text="PDF'leri Birleştir",
            value="merge",
            variable=self.mode_var,
            command=self._refresh_mode_frames,
        ).pack(anchor="w", pady=(6, 0))

        self.signed_frame = ttk.LabelFrame(
            self.root,
            text="Mod 1 - İmzalanmış PDF'leri Birleştir",
            padding=12,
        )

        sig_btn = ttk.Button(
            self.signed_frame,
            text="İmza Sayfası PDF Seç",
            command=self._select_signature_pdf,
        )
        sig_btn.grid(row=0, column=0, sticky="w")

        self.signature_label = ttk.Label(self.signed_frame, text="Henüz seçilmedi")
        self.signature_label.grid(row=0, column=1, sticky="w", padx=(8, 0))

        self.signature_rotation_label = ttk.Label(self.signed_frame, text="İmza yönü: 0°")
        self.signature_rotation_label.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(4, 0))

        sig_rotate_box = ttk.Frame(self.signed_frame)
        sig_rotate_box.grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Button(sig_rotate_box, text="İmza Sola 90°", command=lambda: self._rotate_signature(-90)).pack(side="left")
        ttk.Button(sig_rotate_box, text="İmza Sağa 90°", command=lambda: self._rotate_signature(90)).pack(
            side="left", padx=(8, 0)
        )

        report_btn = ttk.Button(
            self.signed_frame,
            text="Rapor PDF Seç",
            command=self._select_report_pdf,
        )
        report_btn.grid(row=2, column=0, sticky="w", pady=(10, 0))

        self.report_label = ttk.Label(self.signed_frame, text="Henüz seçilmedi")
        self.report_label.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(10, 0))

        self.report_rotation_label = ttk.Label(self.signed_frame, text="Rapor yönü: 0°")
        self.report_rotation_label.grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(4, 0))

        report_rotate_box = ttk.Frame(self.signed_frame)
        report_rotate_box.grid(row=3, column=0, sticky="w", pady=(4, 0))
        ttk.Button(report_rotate_box, text="Rapor Sola 90°", command=lambda: self._rotate_report(-90)).pack(side="left")
        ttk.Button(report_rotate_box, text="Rapor Sağa 90°", command=lambda: self._rotate_report(90)).pack(
            side="left", padx=(8, 0)
        )

        preview_frame = ttk.LabelFrame(self.signed_frame, text="İlk Sayfa Önizlemeleri", padding=8)
        preview_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        self.signed_frame.columnconfigure(1, weight=1)
        self.signed_frame.rowconfigure(4, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.columnconfigure(1, weight=1)

        self.signature_preview_label = ttk.Label(
            preview_frame,
            text="İmza PDF önizlemesi burada görünecek",
            anchor="center",
            justify="center",
            relief="solid",
            padding=8,
        )
        self.signature_preview_label.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        self.report_preview_label = ttk.Label(
            preview_frame,
            text="Rapor PDF önizlemesi burada görünecek",
            anchor="center",
            justify="center",
            relief="solid",
            padding=8,
        )
        self.report_preview_label.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        self.merge_frame = ttk.LabelFrame(
            self.root,
            text="Mod 2 - PDF'leri Birleştir",
            padding=12,
        )

        control_row = ttk.Frame(self.merge_frame)
        control_row.pack(fill="x")

        ttk.Button(
            control_row,
            text="PDF Dosyaları Ekle",
            command=self._add_merge_pdfs,
        ).pack(side="left")

        ttk.Button(
            control_row,
            text="Seçilenleri Temizle",
            command=self._clear_merge_pdfs,
        ).pack(side="left", padx=(10, 0))

        list_frame = ttk.Frame(self.merge_frame)
        list_frame.pack(fill="both", expand=True, pady=(10, 0))

        self.merge_listbox = tk.Listbox(list_frame, height=10)
        self.merge_listbox.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.merge_listbox.yview)
        scroll.pack(side="left", fill="y")
        self.merge_listbox.config(yscrollcommand=scroll.set)

        move_buttons = ttk.Frame(self.merge_frame)
        move_buttons.pack(fill="x", pady=(8, 0))

        ttk.Button(
            move_buttons,
            text="Yukarı Taşı",
            command=lambda: self._move_selected(-1),
        ).pack(side="left")

        ttk.Button(
            move_buttons,
            text="Aşağı Taşı",
            command=lambda: self._move_selected(1),
        ).pack(side="left", padx=(8, 0))

        ttk.Button(
            move_buttons,
            text="Seçileni Kaldır",
            command=self._remove_selected,
        ).pack(side="left", padx=(8, 0))

        action_row = ttk.Frame(self.root)
        action_row.pack(fill="x", padx=16, pady=16)

        ttk.Button(
            action_row,
            text="Birleştir ve Kaydet",
            command=self._merge_and_save,
        ).pack(side="right")

    def _refresh_mode_frames(self) -> None:
        self.signed_frame.pack_forget()
        self.merge_frame.pack_forget()

        if self.mode_var.get() == "signed":
            self.signed_frame.pack(fill="both", expand=True, padx=16, pady=(12, 0))
        else:
            self.merge_frame.pack(fill="both", expand=True, padx=16, pady=(12, 0))

    def _select_signature_pdf(self) -> None:
        path = filedialog.askopenfilename(
            title="İmza Sayfası PDF Seç",
            filetypes=[("PDF", "*.pdf")],
        )
        if not path:
            return
        self.signature_pdf = Path(path)
        self.signature_label.config(text=self.signature_pdf.name)
        self._update_signature_preview()

    def _select_report_pdf(self) -> None:
        path = filedialog.askopenfilename(
            title="Rapor PDF Seç",
            filetypes=[("PDF", "*.pdf")],
        )
        if not path:
            return
        self.report_pdf = Path(path)
        self.report_label.config(text=self.report_pdf.name)
        self._update_report_preview()

    def _rotate_signature(self, step: int) -> None:
        self.signature_rotation = (self.signature_rotation + step) % 360
        self.signature_rotation_label.config(text=f"İmza yönü: {self.signature_rotation}°")
        self._update_signature_preview()

    def _rotate_report(self, step: int) -> None:
        self.report_rotation = (self.report_rotation + step) % 360
        self.report_rotation_label.config(text=f"Rapor yönü: {self.report_rotation}°")
        self._update_report_preview()

    def _update_signature_preview(self) -> None:
        self.signature_preview_image = self._render_preview(self.signature_pdf, self.signature_rotation)
        if self.signature_preview_image is None:
            return
        self.signature_preview_label.config(image=self.signature_preview_image, text="")

    def _update_report_preview(self) -> None:
        self.report_preview_image = self._render_preview(self.report_pdf, self.report_rotation)
        if self.report_preview_image is None:
            return
        self.report_preview_label.config(image=self.report_preview_image, text="")

    def _render_preview(self, pdf_path: Path | None, rotation: int) -> tk.PhotoImage | None:
        if pdf_path is None:
            return None

        if not PREVIEW_AVAILABLE:
            info = f"{pdf_path.name}\n\nÖnizleme için: pip install pymupdf"
            target = self.signature_preview_label if pdf_path == self.signature_pdf else self.report_preview_label
            target.config(text=info, image="")
            return None

        try:
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            mat = fitz.Matrix(0.35, 0.35).prerotate(rotation)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            ppm_data = pix.tobytes("ppm")
            image = tk.PhotoImage(data=ppm_data)
            doc.close()
            return image
        except Exception as exc:  # pragma: no cover
            target = self.signature_preview_label if pdf_path == self.signature_pdf else self.report_preview_label
            target.config(text=f"Önizleme yüklenemedi:\n{exc}", image="")
            return None

    def _add_merge_pdfs(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Birleştirilecek PDF Dosyalarını Seç",
            filetypes=[("PDF", "*.pdf")],
        )
        if not paths:
            return

        for path_str in paths:
            path = Path(path_str)
            self.merge_pdfs.append(path)
            self.merge_listbox.insert(tk.END, path.name)

    def _clear_merge_pdfs(self) -> None:
        self.merge_pdfs.clear()
        self.merge_listbox.delete(0, tk.END)

    def _move_selected(self, direction: int) -> None:
        selection = self.merge_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        new_idx = idx + direction

        if new_idx < 0 or new_idx >= len(self.merge_pdfs):
            return

        self.merge_pdfs[idx], self.merge_pdfs[new_idx] = self.merge_pdfs[new_idx], self.merge_pdfs[idx]

        self._rebuild_listbox()
        self.merge_listbox.selection_set(new_idx)

    def _remove_selected(self) -> None:
        selection = self.merge_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        self.merge_pdfs.pop(idx)
        self._rebuild_listbox()

    def _rebuild_listbox(self) -> None:
        self.merge_listbox.delete(0, tk.END)
        for path in self.merge_pdfs:
            self.merge_listbox.insert(tk.END, path.name)

    def _merge_and_save(self) -> None:
        if not self._validate_pdf_backend():
            return

        if self.mode_var.get() == "signed":
            self._run_signed_mode()
        else:
            self._run_merge_mode()

    def _validate_pdf_backend(self) -> bool:
        if PDF_BACKEND is not None:
            return True

        messagebox.showerror(
            "Eksik bağımlılık",
            "PDF işlemek için gerekli paket bulunamadı.\n\n"
            "Kurulum:\n"
            "- pip install -r requirements.txt\n"
            "veya\n"
            "- pip install pypdf",
        )
        return False

    def _apply_rotation(self, page: Any, rotation: int) -> Any:
        if rotation == 0:
            return page

        if hasattr(page, "rotate"):
            return page.rotate(rotation)

        if rotation > 0 and hasattr(page, "rotate_clockwise"):
            return page.rotate_clockwise(rotation)

        if rotation < 0 and hasattr(page, "rotate_counter_clockwise"):
            return page.rotate_counter_clockwise(abs(rotation))

        return page

    def _run_signed_mode(self) -> None:
        if self.signature_pdf is None or self.report_pdf is None:
            messagebox.showwarning(
                "Eksik seçim",
                "Lütfen hem imza sayfası hem de rapor PDF dosyasını seçin.",
            )
            return

        try:
            signature_reader = PdfReader(str(self.signature_pdf))
            report_reader = PdfReader(str(self.report_pdf))
        except Exception as exc:  # pragma: no cover
            messagebox.showerror("Dosya okuma hatası", f"PDF dosyaları açılamadı:\n{exc}")
            return

        if len(report_reader.pages) < 2:
            messagebox.showwarning(
                "Geçersiz rapor",
                "Rapor PDF en az 2 sayfa olmalı (ilk sayfa silineceği için).",
            )
            return

        writer = PdfWriter()

        for page in signature_reader.pages:
            writer.add_page(self._apply_rotation(page, self.signature_rotation))

        for page in report_reader.pages[1:]:
            writer.add_page(self._apply_rotation(page, self.report_rotation))

        self._save_writer(writer)

    def _run_merge_mode(self) -> None:
        if len(self.merge_pdfs) < 2:
            messagebox.showwarning(
                "Yetersiz dosya",
                "Lütfen birleştirmek için en az 2 PDF seçin.",
            )
            return

        writer = PdfWriter()

        try:
            for pdf_path in self.merge_pdfs:
                reader = PdfReader(str(pdf_path))
                for page in reader.pages:
                    writer.add_page(page)
        except Exception as exc:  # pragma: no cover
            messagebox.showerror("Dosya işleme hatası", f"PDF birleştirme sırasında hata oluştu:\n{exc}")
            return

        self._save_writer(writer)

    def _save_writer(self, writer: PdfWriterProtocol) -> None:
        save_path = filedialog.asksaveasfilename(
            title="Birleşik PDF dosyasını kaydet",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        if not save_path:
            return

        try:
            with open(save_path, "wb") as output_file:
                writer.write(output_file)
        except Exception as exc:  # pragma: no cover
            messagebox.showerror("Kaydetme hatası", f"Dosya kaydedilemedi:\n{exc}")
            return

        messagebox.showinfo("Başarılı", "PDF dosyası başarıyla birleştirildi ve kaydedildi.")


def main() -> None:
    root = tk.Tk()
    style = ttk.Style(root)
    style.theme_use("clam")
    PdfMergeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
