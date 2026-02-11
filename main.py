from __future__ import annotations

import importlib.util
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

if importlib.util.find_spec("pypdf") is not None:
    from pypdf import PdfReader, PdfWriter
    PDF_BACKEND = "pypdf"
elif importlib.util.find_spec("PyPDF2") is not None:
    from PyPDF2 import PdfReader, PdfWriter
    PDF_BACKEND = "PyPDF2"
else:
    PdfReader = None
    PdfWriter = None
    PDF_BACKEND = None


class PdfMergeApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PDF Birleştirme Aracı")
        self.root.geometry("760x520")

        self.mode_var = tk.StringVar(value="signed")

        self.signature_pdf: Path | None = None
        self.report_pdf: Path | None = None
        self.merge_pdfs: list[Path] = []

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

        backend_text = f"PDF altyapısı: {PDF_BACKEND}" if PDF_BACKEND else "PDF altyapısı: Bulunamadı"
        backend_label = ttk.Label(self.root, text=backend_text)
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

        report_btn = ttk.Button(
            self.signed_frame,
            text="Rapor PDF Seç",
            command=self._select_report_pdf,
        )
        report_btn.grid(row=1, column=0, sticky="w", pady=(10, 0))

        self.report_label = ttk.Label(self.signed_frame, text="Henüz seçilmedi")
        self.report_label.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(10, 0))

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
            self.signed_frame.pack(fill="x", padx=16, pady=(12, 0))
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

    def _select_report_pdf(self) -> None:
        path = filedialog.askopenfilename(
            title="Rapor PDF Seç",
            filetypes=[("PDF", "*.pdf")],
        )
        if not path:
            return
        self.report_pdf = Path(path)
        self.report_label.config(text=self.report_pdf.name)

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
            writer.add_page(page)

        for page in report_reader.pages[1:]:
            writer.add_page(page)

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

    def _save_writer(self, writer: PdfWriter) -> None:
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
