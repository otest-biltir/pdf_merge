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

        self.signature_preview_images: list[tk.PhotoImage] = []
        self.report_preview_images: list[tk.PhotoImage] = []
        self.preview_zoom_var = tk.DoubleVar(value=0.22)
        self._preview_mouse_inside = False

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

        preview_frame = ttk.LabelFrame(self.signed_frame, text="PDF Önizlemeleri", padding=8)
        preview_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        self.signed_frame.columnconfigure(1, weight=1)
        self.signed_frame.rowconfigure(4, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(1, weight=1)

        zoom_row = ttk.Frame(preview_frame)
        zoom_row.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        zoom_row.columnconfigure(1, weight=1)

        ttk.Label(zoom_row, text="Önizleme Ölçeği (Otomatik dengeli)").grid(row=0, column=0, sticky="w")
        zoom_scale = ttk.Scale(
            zoom_row,
            from_=0.12,
            to=0.45,
            orient="horizontal",
            variable=self.preview_zoom_var,
            command=self._on_preview_scale_change,
        )
        zoom_scale.grid(row=0, column=1, sticky="ew", padx=(10, 10))
        self.zoom_value_label = ttk.Label(zoom_row, text="%22")
        self.zoom_value_label.grid(row=0, column=2, sticky="e")

        self.preview_canvas = tk.Canvas(preview_frame, highlightthickness=0)
        preview_scrollbar = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_canvas.yview)
        self.preview_canvas.configure(yscrollcommand=preview_scrollbar.set)

        self.preview_canvas.grid(row=1, column=0, sticky="nsew")
        preview_scrollbar.grid(row=1, column=1, sticky="ns")

        self.preview_content = ttk.Frame(self.preview_canvas)
        self.preview_canvas_window = self.preview_canvas.create_window((0, 0), window=self.preview_content, anchor="nw")
        self.preview_content.bind("<Configure>", self._on_preview_content_configure)
        self.preview_canvas.bind("<Configure>", self._on_preview_canvas_configure)

        self.preview_canvas.bind("<Enter>", self._set_preview_mouse_inside)
        self.preview_canvas.bind("<Leave>", self._set_preview_mouse_outside)
        self.preview_content.bind("<Enter>", self._set_preview_mouse_inside)
        self.preview_content.bind("<Leave>", self._set_preview_mouse_outside)
        self.root.bind_all("<MouseWheel>", self._on_preview_mousewheel, add="+")
        self.root.bind_all("<Button-4>", self._on_preview_mousewheel, add="+")
        self.root.bind_all("<Button-5>", self._on_preview_mousewheel, add="+")

        self.signature_preview_container = ttk.LabelFrame(
            self.preview_content,
            text="İmza PDF - Tüm Sayfalar",
            padding=8,
        )
        self.signature_preview_container.grid(row=0, column=0, sticky="nsew")

        self.report_preview_container = ttk.LabelFrame(
            self.preview_content,
            text="Rapor PDF - 1. Sayfa Hariç Tüm Sayfalar",
            padding=8,
        )
        self.report_preview_container.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        self.preview_content.columnconfigure(0, weight=1)
        self.signature_preview_container.columnconfigure(0, weight=1)
        self.report_preview_container.columnconfigure(0, weight=1)

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

    def _on_preview_content_configure(self, _: tk.Event) -> None:
        self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))

    def _on_preview_canvas_configure(self, event: tk.Event) -> None:
        self.preview_canvas.itemconfigure(self.preview_canvas_window, width=event.width)

    def _set_preview_mouse_inside(self, _: tk.Event) -> None:
        self._preview_mouse_inside = True

    def _set_preview_mouse_outside(self, _: tk.Event) -> None:
        self._preview_mouse_inside = False

    def _on_preview_mousewheel(self, event: tk.Event) -> None:
        if not self._preview_mouse_inside:
            return

        if hasattr(event, "delta") and event.delta:
            self.preview_canvas.yview_scroll(int(-event.delta / 120), "units")
            return

        event_num = getattr(event, "num", None)
        if event_num == 4:
            self.preview_canvas.yview_scroll(-1, "units")
        elif event_num == 5:
            self.preview_canvas.yview_scroll(1, "units")

    def _on_preview_scale_change(self, _: str) -> None:
        zoom_percent = int(self.preview_zoom_var.get() * 100)
        self.zoom_value_label.config(text=f"%{zoom_percent}")
        self._update_signature_preview()
        self._update_report_preview()

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
        self._render_pdf_preview(
            pdf_path=self.signature_pdf,
            rotation=self.signature_rotation,
            container=self.signature_preview_container,
            preview_images_attr="signature_preview_images",
            empty_text="İmza PDF seçildiğinde tüm sayfaların önizlemesi burada görünecek.",
            start_page=0,
        )

    def _update_report_preview(self) -> None:
        self._render_pdf_preview(
            pdf_path=self.report_pdf,
            rotation=self.report_rotation,
            container=self.report_preview_container,
            preview_images_attr="report_preview_images",
            empty_text="Rapor PDF seçildiğinde (1. sayfa hariç) tüm sayfaların önizlemesi burada görünecek.",
            start_page=1,
        )

    def _clear_preview_container(self, container: ttk.LabelFrame) -> None:
        for widget in container.winfo_children():
            widget.destroy()

    def _normalized_preview_zoom(self, page: Any, rotation: int, base_zoom: float) -> float:
        target_page_width = 595.0  # A4 portrait width in points (~8.27in * 72)
        if rotation % 180 == 90:
            source_width = float(page.rect.height)
        else:
            source_width = float(page.rect.width)

        if source_width <= 0:
            return base_zoom

        normalized_zoom = base_zoom * (target_page_width / source_width)
        return max(0.04, min(normalized_zoom, 1.2))

    def _render_pdf_preview(
        self,
        pdf_path: Path | None,
        rotation: int,
        container: ttk.LabelFrame,
        preview_images_attr: str,
        empty_text: str,
        start_page: int,
    ) -> None:
        self._clear_preview_container(container)
        setattr(self, preview_images_attr, [])

        if pdf_path is None:
            ttk.Label(container, text=empty_text, justify="left").grid(row=0, column=0, sticky="w")
            return

        if not PREVIEW_AVAILABLE:
            ttk.Label(
                container,
                text=f"{pdf_path.name}\n\nÖnizleme için: pip install pymupdf",
                justify="left",
            ).grid(row=0, column=0, sticky="w")
            return

        try:
            doc = fitz.open(str(pdf_path))
            total_pages = len(doc)
            if total_pages <= start_page:
                ttk.Label(container, text=f"{pdf_path.name} için önizlenecek sayfa yok.", justify="left").grid(
                    row=0,
                    column=0,
                    sticky="w",
                )
                doc.close()
                return

            images: list[tk.PhotoImage] = []
            base_zoom = float(self.preview_zoom_var.get())

            for page_index in range(start_page, total_pages):
                page = doc[page_index]
                effective_zoom = self._normalized_preview_zoom(page, rotation, base_zoom)
                matrix = fitz.Matrix(effective_zoom, effective_zoom).prerotate(rotation)
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                photo = tk.PhotoImage(data=pix.tobytes("ppm"))
                images.append(photo)

                row_index = (page_index - start_page) * 2
                ttk.Label(container, text=f"Sayfa {page_index + 1}/{total_pages}", font=("Segoe UI", 9, "bold")).grid(
                    row=row_index,
                    column=0,
                    sticky="w",
                    pady=(6 if page_index > start_page else 0, 2),
                )
                ttk.Label(container, image=photo, relief="solid").grid(
                    row=row_index + 1,
                    column=0,
                    sticky="w",
                    pady=(0, 6),
                )

            doc.close()
            setattr(self, preview_images_attr, images)
            self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))
        except Exception as exc:  # pragma: no cover
            ttk.Label(container, text=f"Önizleme yüklenemedi:\n{exc}", justify="left").grid(row=0, column=0, sticky="w")

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

    try:
        root.mainloop()
    except KeyboardInterrupt:
        root.destroy()


if __name__ == "__main__":
    main()
