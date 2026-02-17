from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Protocol

from db_helpers import DatabaseLookupError, fetch_test_numbers, get_main_path_for_test, iter_test_sources
from report_storage import (
    ReportFolderResolutionError,
    move_or_copy_merged_pdf,
    resolve_report_pdf_folder,
)


class PdfWriterProtocol(Protocol):
    def add_page(self, page: Any) -> None: ...

    def write(self, stream: Any) -> None: ...


PdfReader: Any = None
PdfWriter: Any = None
PDF_BACKEND: str | None = None


def _get_requirements_path() -> Path | None:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    requirements_path = base_path / "requirements.txt"
    if requirements_path.exists():
        return requirements_path

    project_requirements = Path(__file__).with_name("requirements.txt")
    if project_requirements.exists():
        return project_requirements

    return None


def _install_requirements_if_missing() -> None:
    requirements_path = _get_requirements_path()
    if requirements_path is None:
        return

    dependency_imports = {
        "pypdf": "pypdf",
        "PyMuPDF": "fitz",
        "fitz": "fitz",
        "psycopg2-binary": "psycopg2",
        "psycopg2": "psycopg2",
        "psycopg": "psycopg",
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


PREVIEW_ZOOM_OPTIONS = [100, 110, 125, 150, 175, 200, 250, 300]


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

        self.preview_images: list[tk.PhotoImage] = []
        self.preview_zoom_var = tk.StringVar(value="200")
        self._preview_mouse_inside = False
        self.source_var = tk.StringVar()
        self.test_var = tk.StringVar()
        self.target_filename_var = tk.StringVar()

        self._build_ui()
        self._refresh_mode_frames()

    def _build_ui(self) -> None:
        title = ttk.Label(
            self.root,
            text="PDF Birleştirme Uygulaması",
            font=("Segoe UI", 16, "bold"),
        )
        title.pack(pady=(14, 6))

        backend_parts = [f"PDF altyapısı: {PDF_BACKEND}" if PDF_BACKEND else "PDF altyapısı: Bulunamadı"]
        preview_backend = "aktif" if PREVIEW_AVAILABLE else "kapalı (pip install pymupdf)"
        backend_parts.append(f"Önizleme: {preview_backend}")
        backend_label = ttk.Label(self.root, text=" | ".join(backend_parts))
        backend_label.pack(pady=(0, 8))

        self.main_layout = ttk.Frame(self.root)
        self.main_layout.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.main_layout.columnconfigure(1, weight=1)
        self.main_layout.rowconfigure(0, weight=1)

        self.sidebar = ttk.Frame(self.main_layout, width=270)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)

        self.content_area = ttk.Frame(self.main_layout)
        self.content_area.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self.content_area.columnconfigure(0, weight=1)
        self.content_area.rowconfigure(0, weight=1)

        mode_box = ttk.LabelFrame(self.sidebar, text="Mod Seçimi", padding=8)
        mode_box.pack(fill="x")

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

        ttk.Button(
            self.sidebar,
            text="Birleştir ve Kaydet",
            command=self._merge_and_save,
        ).pack(fill="x", pady=(8, 10))

        self.signed_controls_frame = ttk.LabelFrame(
            self.sidebar,
            text="İmzalı Mod Kontrolleri",
            padding=8,
        )

        ttk.Button(
            self.signed_controls_frame,
            text="İmza Sayfası PDF Seç",
            command=self._select_signature_pdf,
        ).grid(row=0, column=0, sticky="ew")

        self.signature_label = ttk.Label(self.signed_controls_frame, text="Henüz seçilmedi", wraplength=230)
        self.signature_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.signature_rotation_label = ttk.Label(self.signed_controls_frame, text="İmza yönü: 0°")
        self.signature_rotation_label.grid(row=2, column=0, sticky="w", pady=(4, 0))

        sig_rotate_box = ttk.Frame(self.signed_controls_frame)
        sig_rotate_box.grid(row=3, column=0, sticky="ew", pady=(4, 8))
        ttk.Button(sig_rotate_box, text="Sola 90°", command=lambda: self._rotate_signature(-90)).pack(side="left")
        ttk.Button(sig_rotate_box, text="Sağa 90°", command=lambda: self._rotate_signature(90)).pack(side="left", padx=(6, 0))

        ttk.Button(
            self.signed_controls_frame,
            text="Rapor PDF Seç",
            command=self._select_report_pdf,
        ).grid(row=4, column=0, sticky="ew")

        self.report_label = ttk.Label(self.signed_controls_frame, text="Henüz seçilmedi", wraplength=230)
        self.report_label.grid(row=5, column=0, sticky="w", pady=(4, 0))

        self.report_rotation_label = ttk.Label(self.signed_controls_frame, text="Rapor yönü: 0°")
        self.report_rotation_label.grid(row=6, column=0, sticky="w", pady=(4, 0))

        report_rotate_box = ttk.Frame(self.signed_controls_frame)
        report_rotate_box.grid(row=7, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(report_rotate_box, text="Sola 90°", command=lambda: self._rotate_report(-90)).pack(side="left")
        ttk.Button(report_rotate_box, text="Sağa 90°", command=lambda: self._rotate_report(90)).pack(side="left", padx=(6, 0))

        self.signed_controls_frame.columnconfigure(0, weight=1)

        db_frame = ttk.LabelFrame(self.signed_controls_frame, text="Test Hedefi", padding=8)
        db_frame.grid(row=8, column=0, sticky="ew", pady=(10, 0))
        db_frame.columnconfigure(0, weight=1)

        ttk.Label(db_frame, text="Kaynak").grid(row=0, column=0, sticky="w")
        self.source_combo = ttk.Combobox(db_frame, textvariable=self.source_var, state="readonly")
        self.source_combo.grid(row=1, column=0, sticky="ew", pady=(2, 6))
        self.source_combo.bind("<<ComboboxSelected>>", self._on_source_selected)

        ttk.Label(db_frame, text="Test No").grid(row=2, column=0, sticky="w")
        self.test_combo = ttk.Combobox(db_frame, textvariable=self.test_var, state="readonly")
        self.test_combo.grid(row=3, column=0, sticky="ew", pady=(2, 6))
        self.test_combo.bind("<<ComboboxSelected>>", self._on_test_selected)

        ttk.Label(db_frame, text="Kopya Dosya Adı (opsiyonel)").grid(row=4, column=0, sticky="w")
        ttk.Entry(db_frame, textvariable=self.target_filename_var).grid(row=5, column=0, sticky="ew", pady=(2, 0))

        ttk.Button(db_frame, text="Testleri Yenile", command=self._refresh_test_sources).grid(
            row=6, column=0, sticky="ew", pady=(8, 0)
        )

        self._refresh_test_sources()

        self.preview_frame = ttk.LabelFrame(self.content_area, text="PDF Önizlemeleri", padding=8)
        self.preview_frame.grid(row=0, column=0, sticky="nsew")
        self.preview_frame.columnconfigure(0, weight=1)
        self.preview_frame.rowconfigure(1, weight=1)

        zoom_row = ttk.Frame(self.preview_frame)
        zoom_row.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        zoom_row.columnconfigure(1, weight=1)

        ttk.Label(zoom_row, text="Önizleme Ölçeği").grid(row=0, column=0, sticky="w")
        self.zoom_combo = ttk.Combobox(
            zoom_row,
            textvariable=self.preview_zoom_var,
            values=[str(value) for value in PREVIEW_ZOOM_OPTIONS],
            state="readonly",
            width=12,
        )
        self.zoom_combo.grid(row=0, column=1, sticky="w", padx=(10, 10))
        self.zoom_combo.bind("<<ComboboxSelected>>", self._on_preview_scale_change)
        ttk.Label(zoom_row, text="%").grid(row=0, column=2, sticky="w")

        self.preview_canvas = tk.Canvas(self.preview_frame, highlightthickness=0)
        preview_scrollbar = ttk.Scrollbar(self.preview_frame, orient="vertical", command=self.preview_canvas.yview)
        self.preview_canvas.configure(yscrollcommand=preview_scrollbar.set)

        self.preview_canvas.grid(row=1, column=0, sticky="nsew")
        preview_scrollbar.grid(row=1, column=1, sticky="ns")

        self.preview_canvas.bind("<Configure>", self._on_preview_canvas_configure)

        self.preview_canvas.bind("<Enter>", self._set_preview_mouse_inside)
        self.preview_canvas.bind("<Leave>", self._set_preview_mouse_outside)
        self.root.bind_all("<MouseWheel>", self._on_preview_mousewheel, add="+")
        self.root.bind_all("<Button-4>", self._on_preview_mousewheel, add="+")
        self.root.bind_all("<Button-5>", self._on_preview_mousewheel, add="+")

        self.merge_frame = ttk.LabelFrame(
            self.content_area,
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

    def _refresh_mode_frames(self) -> None:
        self.signed_controls_frame.pack_forget()
        self.preview_frame.grid_remove()
        self.merge_frame.grid_remove()

        if self.mode_var.get() == "signed":
            self.signed_controls_frame.pack(fill="x")
            self.preview_frame.grid(row=0, column=0, sticky="nsew")
        else:
            self.merge_frame.grid(row=0, column=0, sticky="nsew")

    def _on_preview_canvas_configure(self, event: tk.Event) -> None:
        bbox = self.preview_canvas.bbox("all")
        if bbox is None:
            self.preview_canvas.configure(scrollregion=(0, 0, event.width, event.height))
            return

        _, _, content_width, content_height = bbox
        self.preview_canvas.configure(
            scrollregion=(0, 0, max(content_width, event.width), max(content_height, event.height))
        )

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

    def _on_preview_scale_change(self, _: tk.Event | str | None = None) -> None:
        self._update_signature_preview()
        self._update_report_preview()

    def _get_preview_zoom(self) -> float:
        try:
            zoom_percent = int(self.preview_zoom_var.get())
        except (TypeError, ValueError):
            zoom_percent = 200
            self.preview_zoom_var.set(str(zoom_percent))

        return max(10, zoom_percent) / 100

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
        self._render_preview_canvas()

    def _update_report_preview(self) -> None:
        self._render_preview_canvas()

    def _normalized_preview_zoom(self, page: Any, rotation: int, base_zoom: float) -> float:
        target_page_width = 595.0  # A4 portrait width in points (~8.27in * 72)
        if rotation % 180 == 90:
            source_width = float(page.rect.height)
        else:
            source_width = float(page.rect.width)

        if source_width <= 0:
            return base_zoom

        normalized_zoom = base_zoom * (target_page_width / source_width)
        return max(0.04, min(normalized_zoom, 3.0))

    def _render_pdf_preview(
        self,
        pdf_path: Path | None,
        rotation: int,
        section_title: str,
        empty_text: str,
        start_page: int,
        start_y: int,
    ) -> int:
        content_x = 12
        current_y = start_y
        section_bottom = start_y

        self.preview_canvas.create_text(
            content_x,
            current_y,
            text=section_title,
            anchor="nw",
            font=("Segoe UI", 10, "bold"),
        )
        current_y += 28

        if pdf_path is None:
            self.preview_canvas.create_text(content_x, current_y, text=empty_text, anchor="nw")
            return current_y + 30

        if not PREVIEW_AVAILABLE:
            self.preview_canvas.create_text(
                content_x,
                current_y,
                text=f"{pdf_path.name}\n\nÖnizleme için: pip install pymupdf",
                anchor="nw",
            )
            return current_y + 30

        try:
            doc = fitz.open(str(pdf_path))
            total_pages = len(doc)
            if total_pages <= start_page:
                self.preview_canvas.create_text(
                    content_x,
                    current_y,
                    text=f"{pdf_path.name} için önizlenecek sayfa yok.",
                    anchor="nw",
                )
                doc.close()
                return current_y + 30

            base_zoom = self._get_preview_zoom()

            for page_index in range(start_page, total_pages):
                page = doc[page_index]
                effective_zoom = self._normalized_preview_zoom(page, rotation, base_zoom)
                matrix = fitz.Matrix(effective_zoom, effective_zoom).prerotate(rotation)
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                photo = tk.PhotoImage(data=pix.tobytes("ppm"))
                self.preview_images.append(photo)

                self.preview_canvas.create_text(
                    content_x,
                    current_y,
                    text=f"Sayfa {page_index + 1}/{total_pages}",
                    anchor="nw",
                    font=("Segoe UI", 9, "bold"),
                )

                current_y += 22
                self.preview_canvas.create_image(content_x, current_y, image=photo, anchor="nw")
                current_y += pix.height + 12
                section_bottom = max(section_bottom, current_y)

            doc.close()
            return section_bottom
        except Exception as exc:  # pragma: no cover
            self.preview_canvas.create_text(
                content_x,
                current_y,
                text=f"Önizleme yüklenemedi:\n{exc}",
                anchor="nw",
                justify="left",
            )
            return current_y + 30

    def _render_preview_canvas(self) -> None:
        self.preview_canvas.delete("all")
        self.preview_images = []

        y = self._render_pdf_preview(
            pdf_path=self.signature_pdf,
            rotation=self.signature_rotation,
            section_title="İmza PDF - Tüm Sayfalar",
            empty_text="İmza PDF seçildiğinde tüm sayfaların önizlemesi burada görünecek.",
            start_page=0,
            start_y=12,
        )

        y += 22
        y = self._render_pdf_preview(
            pdf_path=self.report_pdf,
            rotation=self.report_rotation,
            section_title="Rapor PDF - 1. Sayfa Hariç Tüm Sayfalar",
            empty_text="Rapor PDF seçildiğinde (1. sayfa hariç) tüm sayfaların önizlemesi burada görünecek.",
            start_page=1,
            start_y=y,
        )

        canvas_width = self.preview_canvas.winfo_width()
        canvas_height = self.preview_canvas.winfo_height()
        self.preview_canvas.configure(
            scrollregion=(0, 0, max(canvas_width, 900), max(y + 20, canvas_height))
        )

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

    def _refresh_test_sources(self) -> None:
        try:
            source_names = [table.name for table in iter_test_sources()]
        except Exception as exc:
            messagebox.showerror("Veritabanı Hatası", f"Kaynak listesi alınamadı:\n{exc}")
            return

        self.source_combo["values"] = source_names
        if source_names and not self.source_var.get():
            self.source_var.set(source_names[0])
            self._load_tests_for_source(source_names[0])

    def _on_source_selected(self, _: tk.Event | None = None) -> None:
        source_name = self.source_var.get()
        if source_name:
            self._load_tests_for_source(source_name)

    def _load_tests_for_source(self, source_name: str) -> None:
        try:
            tests = fetch_test_numbers(source_name)
        except Exception as exc:
            self.test_combo["values"] = []
            self.test_var.set("")
            messagebox.showerror("Veritabanı Hatası", f"Test listesi alınamadı:\n{exc}")
            return

        self.test_combo["values"] = tests
        if tests:
            self.test_var.set(tests[0])
            self._on_test_selected()
        else:
            self.test_var.set("")
            self.target_filename_var.set("")

    def _on_test_selected(self, _: tk.Event | None = None) -> None:
        test_no = self.test_var.get().strip()
        if not test_no:
            self.target_filename_var.set("")
            return
        self.target_filename_var.set(f"{test_no}_Signed.pdf")

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

        self._save_writer(writer, signed_mode=True)

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

        self._save_writer(writer, signed_mode=False)

    def _save_writer(self, writer: PdfWriterProtocol, *, signed_mode: bool) -> None:
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

        if signed_mode:
            self._copy_signed_pdf_to_report_folder(Path(save_path))
            return

        messagebox.showinfo("Başarılı", "PDF dosyası başarıyla birleştirildi ve kaydedildi.")

    def _copy_signed_pdf_to_report_folder(self, merged_path: Path) -> None:
        source_name = self.source_var.get().strip()
        test_no = self.test_var.get().strip()
        if not source_name or not test_no:
            messagebox.showwarning(
                "Test seçimi eksik",
                "PDF kaydedildi ancak otomatik kopyalama için kaynak ve test seçimi gerekli.",
            )
            return

        try:
            main_path = get_main_path_for_test(test_no=test_no, source_name=source_name)
            target_dir = resolve_report_pdf_folder(main_path)

            requested_name = self.target_filename_var.get().strip() or f"{test_no}_Signed.pdf"
            copied_path = move_or_copy_merged_pdf(
                merged_pdf_path=merged_path,
                target_dir=target_dir,
                filename=requested_name,
                overwrite=True,
            )
        except DatabaseLookupError as exc:
            messagebox.showerror("Veritabanı Hatası", str(exc))
            return
        except ReportFolderResolutionError as exc:
            messagebox.showerror("Hedef Klasör Hatası", str(exc))
            return
        except Exception as exc:  # pragma: no cover
            messagebox.showerror("Kopyalama Hatası", f"Birleşik PDF kopyalanamadı:\n{exc}")
            return

        messagebox.showinfo(
            "Başarılı",
            "PDF dosyası başarıyla birleştirildi ve kaydedildi.\n"
            f"Otomatik kopya: {copied_path}",
        )


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
