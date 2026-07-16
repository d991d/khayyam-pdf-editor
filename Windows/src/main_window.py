"""
main_window.py — Main application window for Khayyam PDF Editor (Windows).
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional
import fitz

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QFileDialog, QMessageBox, QStatusBar, QToolBar, QSpinBox,
    QFrame, QApplication, QMenu,
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import (
    QAction, QKeySequence, QFont, QColor, QDragEnterEvent, QDropEvent,
    QIcon,
)

from .models import AnnotationTool
from .pdf_viewer import PDFViewerWidget
from .toolbar import AnnotationToolbar
from .sidebar import SidebarWidget
from .dialogs import (
    MergeDialog, SplitDialog, AddTextDialog, StickyNoteDialog,
    TextEditDialog, GoToPageDialog,
)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self._doc: Optional[fitz.Document] = None
        self._doc_path: Optional[str] = None
        self._is_modified: bool = False
        self._search_index: int = 0
        self._search_count: int = 0

        self.setWindowTitle("Khayyam PDF Editor")
        self.setMinimumSize(900, 640)
        self.resize(1200, 820)

        self._build_menu()
        self._build_nav_toolbar()
        self._build_annotation_toolbar()
        self._build_central()
        self._build_status_bar()

        self.setAcceptDrops(True)
        self._show_welcome()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        mb = self.menuBar()
        mb.setFont(QFont("Segoe UI", 9))

        # File
        file_menu = mb.addMenu("&File")
        self._act_open = QAction("&Open PDF…", self,
                                 shortcut=QKeySequence.StandardKey.Open,
                                 triggered=self.open_pdf_dialog)
        self._act_save = QAction("&Save", self,
                                 shortcut=QKeySequence.StandardKey.Save,
                                 triggered=self.save_pdf)
        self._act_save_as = QAction("Save &As…", self,
                                    shortcut=QKeySequence("Ctrl+Shift+S"),
                                    triggered=self.save_pdf_as)
        self._act_merge = QAction("&Merge PDFs…", self, triggered=self.show_merge_dialog)
        self._act_split = QAction("S&plit PDF…", self, triggered=self.show_split_dialog)
        self._act_close = QAction("&Close Document", self, triggered=self.close_document)
        for act in (self._act_open, None, self._act_save, self._act_save_as,
                    None, self._act_merge, self._act_split, None, self._act_close):
            if act:
                file_menu.addAction(act)
            else:
                file_menu.addSeparator()

        # View
        view_menu = mb.addMenu("&View")
        self._act_zoom_in = QAction("Zoom &In", self,
                                    shortcut=QKeySequence.StandardKey.ZoomIn,
                                    triggered=lambda: self._viewer.zoom_in())
        self._act_zoom_out = QAction("Zoom &Out", self,
                                     shortcut=QKeySequence.StandardKey.ZoomOut,
                                     triggered=lambda: self._viewer.zoom_out())
        self._act_zoom_fit = QAction("Fit &Page", self,
                                     shortcut=QKeySequence("Ctrl+0"),
                                     triggered=lambda: self._viewer.zoom_to_fit())
        self._act_zoom_actual = QAction("&Actual Size", self,
                                        shortcut=QKeySequence("Ctrl+1"),
                                        triggered=lambda: self._viewer.zoom_to_actual())
        self._act_toggle_sidebar = QAction("Toggle &Sidebar", self,
                                           shortcut=QKeySequence("Ctrl+["),
                                           triggered=self._toggle_sidebar)
        for act in (self._act_zoom_in, self._act_zoom_out, self._act_zoom_fit,
                    self._act_zoom_actual, None, self._act_toggle_sidebar):
            if act:
                view_menu.addAction(act)
            else:
                view_menu.addSeparator()

        # Tools
        tools_menu = mb.addMenu("&Tools")
        self._act_del_annot = QAction("&Delete Selected Annotation", self,
                                      shortcut=QKeySequence("Delete"),
                                      triggered=lambda: self._viewer.delete_selected_annotation())
        tools_menu.addAction(self._act_del_annot)

        # Help
        help_menu = mb.addMenu("&Help")
        about_act = QAction("&About Khayyam PDF Editor", self, triggered=self._show_about)
        website_act = QAction("Visit &Website", self, triggered=self._open_website)
        help_menu.addAction(about_act)
        help_menu.addAction(website_act)

    def _build_nav_toolbar(self) -> None:
        """Navigation toolbar: Open, Save, page controls, zoom controls."""
        nav_bar = QToolBar("Navigation")
        nav_bar.setMovable(False)
        nav_bar.setIconSize(QSize(16, 16))
        nav_bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        nav_bar.setStyleSheet(
            "QToolBar { background: #f0f0f0; border-bottom: 1px solid #ccc; padding: 4px 6px; }"
            "QToolButton { padding: 4px 10px; border-radius: 4px; font-size: 9pt;"
            "              color: #1a1a1a; background: transparent; }"
            "QToolButton:hover { background: #d8d8d8; }"
            "QToolButton:pressed { background: #c8c8c8; }"
        )

        open_act = QAction("Open", self, triggered=self.open_pdf_dialog)
        open_act.setToolTip("Open a PDF file  (Ctrl+O)")
        save_act = QAction("Save", self, triggered=self.save_pdf)
        save_act.setToolTip("Save  (Ctrl+S)")
        nav_bar.addAction(open_act)
        nav_bar.addAction(save_act)
        nav_bar.addSeparator()

        # Page navigation
        prev_act = QAction("◀ Prev", self, triggered=lambda: self._viewer.go_to_prev())
        prev_act.setToolTip("Previous page  (Ctrl+Left)")
        self._page_spin = QSpinBox()
        self._page_spin.setMinimum(1)
        self._page_spin.setMaximum(1)
        self._page_spin.setFixedWidth(56)
        self._page_spin.setFont(QFont("Segoe UI Mono", 9))
        self._page_spin.setToolTip("Current page")
        self._page_spin.editingFinished.connect(self._on_page_spin_changed)
        self._page_total_lbl = QLabel(" / 0")
        self._page_total_lbl.setFont(QFont("Segoe UI", 9))
        next_act = QAction("Next ▶", self, triggered=lambda: self._viewer.go_to_next())
        next_act.setToolTip("Next page  (Ctrl+Right)")

        nav_bar.addAction(prev_act)
        nav_bar.addWidget(self._page_spin)
        nav_bar.addWidget(self._page_total_lbl)
        nav_bar.addAction(next_act)
        nav_bar.addSeparator()

        # Zoom
        zoom_out_act = QAction("Zoom −", self, triggered=lambda: self._viewer.zoom_out())
        self._zoom_lbl = QLabel("150%")
        self._zoom_lbl.setFont(QFont("Segoe UI Mono", 9))
        self._zoom_lbl.setFixedWidth(48)
        self._zoom_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        zoom_in_act = QAction("Zoom +", self, triggered=lambda: self._viewer.zoom_in())
        fit_act = QAction("Fit", self, triggered=lambda: self._viewer.zoom_to_fit())
        fit_act.setToolTip("Fit page to window  (Ctrl+0)")

        nav_bar.addAction(zoom_out_act)
        nav_bar.addWidget(self._zoom_lbl)
        nav_bar.addAction(zoom_in_act)
        nav_bar.addAction(fit_act)

        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, nav_bar)
        self._nav_toolbar = nav_bar

        # Keyboard shortcuts for page nav
        QAction(self, shortcut=QKeySequence("Ctrl+Left"),
                triggered=lambda: self._viewer.go_to_prev()).setEnabled(True)
        QAction(self, shortcut=QKeySequence("Ctrl+Right"),
                triggered=lambda: self._viewer.go_to_next()).setEnabled(True)
        self.addAction(
            QAction(self, shortcut="Ctrl+Left",
                    triggered=lambda: self._viewer.go_to_prev())
        )
        self.addAction(
            QAction(self, shortcut="Ctrl+Right",
                    triggered=lambda: self._viewer.go_to_next())
        )

    def _build_annotation_toolbar(self) -> None:
        """Annotation toolbar — placed below the nav toolbar."""
        self._anno_bar = AnnotationToolbar()
        self._anno_bar_container = QToolBar("Annotation Tools")
        self._anno_bar_container.setMovable(False)
        self._anno_bar_container.addWidget(self._anno_bar)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._anno_bar_container)

        self._anno_bar.tool_selected.connect(self._on_tool_selected)
        self._anno_bar.markup_apply.connect(self._on_markup_apply)
        self._anno_bar.markup_color_changed.connect(self._on_markup_color_changed)
        self._anno_bar.stroke_color_changed.connect(self._on_stroke_color_changed)
        self._anno_bar.delete_annotation.connect(
            lambda: self._viewer.delete_selected_annotation()
        )

    def _build_central(self) -> None:
        """Build the splitter with sidebar and viewer."""
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        # Sidebar
        self._sidebar = SidebarWidget()
        self._sidebar.page_clicked.connect(self._viewer_go_to_page)
        self._sidebar.search_requested.connect(self._on_search)
        self._sidebar.search_prev.connect(self._on_search_prev)
        self._sidebar.search_next.connect(self._on_search_next)
        self._sidebar.search_cleared.connect(self._on_search_cleared)
        splitter.addWidget(self._sidebar)

        # PDF viewer
        self._viewer = PDFViewerWidget()
        self._viewer.page_changed.connect(self._on_page_changed)
        self._viewer.status_message.connect(self._show_status)
        self._viewer.document_modified.connect(self._on_doc_modified)
        self._viewer.annotation_selected.connect(
            self._anno_bar.show_annotation_selected
        )
        # Wire up callbacks for dialogs
        self._viewer.on_request_typewriter = self._request_typewriter
        self._viewer.on_request_sticky_note = self._request_sticky_note
        self._viewer.on_request_edit_text = self._request_edit_text
        self._viewer.on_request_insert_image = self._request_insert_image
        splitter.addWidget(self._viewer)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([180, 820])

        self._splitter = splitter
        self.setCentralWidget(splitter)

    def _build_status_bar(self) -> None:
        sb = QStatusBar()
        sb.setFont(QFont("Segoe UI", 8))
        self.setStatusBar(sb)
        self._status_lbl = QLabel("")
        sb.addPermanentWidget(self._status_lbl)
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(lambda: self._status_lbl.setText(""))

    # ── welcome screen ────────────────────────────────────────────────────────

    def _show_welcome(self) -> None:
        """Show welcome in status bar and update title."""
        self.setWindowTitle("Khayyam PDF Editor")
        self._page_spin.setValue(1)
        self._page_total_lbl.setText(" / 0")
        self._zoom_lbl.setText("—")

    # ── drag & drop (onto window) ─────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            p = url.toLocalFile()
            if p.lower().endswith(".pdf"):
                self.open_pdf(p)
                break

    # ── document lifecycle ────────────────────────────────────────────────────

    def open_pdf_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF Files (*.pdf);;All Files (*)"
        )
        if path:
            self.open_pdf(path)

    def open_pdf(self, path: str) -> None:
        if not self._confirm_close():
            return
        try:
            doc = fitz.open(path)
        except Exception as e:
            QMessageBox.critical(self, "Open Error", f"Could not open PDF:\n{e}")
            return
        self._doc = doc
        self._doc_path = path
        self._is_modified = False
        self._viewer.load_document(doc, path)
        self._sidebar.load_document(doc)
        self._page_spin.setMaximum(doc.page_count)
        self._page_spin.setValue(1)
        self._page_total_lbl.setText(f" / {doc.page_count}")
        self._update_title()
        self._update_zoom_label()
        self._show_status(f"Opened {Path(path).name}")

    def close_document(self) -> None:
        if not self._confirm_close():
            return
        self._viewer.close_document()
        self._sidebar.clear()
        if self._doc:
            self._doc.close()
            self._doc = None
        self._doc_path = None
        self._is_modified = False
        self._show_welcome()

    def save_pdf(self) -> bool:
        if not self._doc:
            return False
        if self._doc_path:
            return self._do_save(self._doc_path)
        return self.save_pdf_as()

    def save_pdf_as(self) -> bool:
        if not self._doc:
            return False
        name = Path(self._doc_path or "document").stem + ".pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF As", name, "PDF Files (*.pdf)"
        )
        if not path:
            return False
        return self._do_save(path)

    def _do_save(self, path: str) -> bool:
        try:
            source = getattr(self._doc, "name", "")
            if source and Path(source).resolve() == Path(path).resolve():
                self._doc.saveIncr()
            else:
                self._doc.save(path, garbage=3, deflate=True)
            self._doc_path = path
            self._is_modified = False
            self._update_title()
            self._show_status("Saved.")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save:\n{e}")
            return False

    def _confirm_close(self) -> bool:
        if self._is_modified:
            r = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Save before closing?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel,
            )
            if r == QMessageBox.StandardButton.Save:
                return self.save_pdf()
            elif r == QMessageBox.StandardButton.Cancel:
                return False
        return True

    def closeEvent(self, event) -> None:
        if not self._confirm_close():
            event.ignore()
        else:
            event.accept()

    # ── merge / split ─────────────────────────────────────────────────────────

    def show_merge_dialog(self) -> None:
        dlg = MergeDialog(self)
        dlg.exec()

    def show_split_dialog(self) -> None:
        if not self._doc:
            QMessageBox.information(self, "Split", "Open a PDF first.")
            return
        dlg = SplitDialog(self._doc, self)
        dlg.exec()

    # ── page / zoom sync ──────────────────────────────────────────────────────

    def _viewer_go_to_page(self, idx: int) -> None:
        self._viewer.go_to_page(idx)

    def _on_page_changed(self, idx: int) -> None:
        self._page_spin.setValue(idx + 1)
        self._sidebar.set_current_page(idx)
        self._update_zoom_label()

    def _on_page_spin_changed(self) -> None:
        idx = self._page_spin.value() - 1
        self._viewer.go_to_page(idx)

    def _update_zoom_label(self) -> None:
        pct = int(self._viewer.zoom * 100)
        self._zoom_lbl.setText(f"{pct}%")

    def _toggle_sidebar(self) -> None:
        self._sidebar.setVisible(not self._sidebar.isVisible())

    # ── annotations ──────────────────────────────────────────────────────────

    def _on_tool_selected(self, tool: AnnotationTool) -> None:
        self._viewer.set_tool(tool)
        self._show_status(tool.tooltip)

    def _on_markup_apply(self, tool: AnnotationTool) -> None:
        """User clicked a markup button without dragging — show guidance."""
        self._show_status(f"Drag across text on the page to apply {tool.display_name}.")
        self._viewer.set_tool(tool)
        self._anno_bar.set_tool_externally(tool)

    def _on_markup_color_changed(self, tool: AnnotationTool, color: QColor) -> None:
        if tool == AnnotationTool.HIGHLIGHT:
            self._viewer.highlight_color = color
        elif tool == AnnotationTool.UNDERLINE:
            self._viewer.underline_color = color
        elif tool == AnnotationTool.STRIKETHROUGH:
            self._viewer.strikethrough_color = color

    def _on_stroke_color_changed(self, color: QColor) -> None:
        self._viewer.stroke_color = color

    def _request_typewriter(self, pdf_pt) -> None:
        dlg = AddTextDialog(self)
        if dlg.exec():
            self._viewer.add_typewriter_text(
                pdf_pt, dlg.text, dlg.font_size, dlg.color, False, False, dlg.alignment
            )

    def _request_sticky_note(self, pdf_pt) -> None:
        dlg = StickyNoteDialog(self)
        if dlg.exec():
            self._viewer.add_sticky_note(pdf_pt, dlg.text)

    def _request_edit_text(self, block_rect, current_text: str) -> None:
        dlg = TextEditDialog(current_text, self)
        if dlg.exec():
            self._viewer.replace_text_block(block_rect, dlg.text)

    def _request_insert_image(self, pdf_pt) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.tif);;All Files (*)"
        )
        if path:
            self._viewer.insert_image_at(pdf_pt, path)

    # ── search ────────────────────────────────────────────────────────────────

    def _on_search(self, query: str) -> None:
        n = self._viewer.search(query)
        self._search_count = n
        self._search_index = 0
        self._sidebar.set_search_result_count(n)
        if n > 0:
            self._viewer.jump_to_search_result(0)
            self._show_status(f"{n} result{'s' if n != 1 else ''} for \"{query}\"")
        else:
            self._show_status(f"No results for \"{query}\"")

    def _on_search_prev(self) -> None:
        if self._search_count:
            self._search_index = (self._search_index - 1) % self._search_count
            self._viewer.jump_to_search_result(self._search_index)

    def _on_search_next(self) -> None:
        if self._search_count:
            self._search_index = (self._search_index + 1) % self._search_count
            self._viewer.jump_to_search_result(self._search_index)

    def _on_search_cleared(self) -> None:
        self._viewer.search("")
        self._search_count = 0
        self._search_index = 0

    # ── helpers ───────────────────────────────────────────────────────────────

    def _on_doc_modified(self) -> None:
        self._is_modified = True
        self._update_title()
        self._update_zoom_label()

    def _update_title(self) -> None:
        base = Path(self._doc_path).stem if self._doc_path else "Khayyam PDF Editor"
        mod = " •" if self._is_modified else ""
        self.setWindowTitle(f"{base}{mod} — Khayyam PDF Editor")

    def _show_status(self, message: str) -> None:
        self._status_lbl.setText(message)
        self._status_timer.start(4000)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Khayyam PDF Editor",
            "<h2>Khayyam PDF Editor</h2>"
            "<p>Version 1.1 — Windows Edition</p>"
            "<p>A free PDF editor for annotating, editing, merging, and signing documents.<br>"
            "No subscriptions, no cloud uploads, no privacy trade-offs.</p>"
            "<p><b>Built with</b> Python · PyQt6 · PyMuPDF</p>"
            "<p><a href='https://d991d.com/khayyam-pdf-editor/'>d991d.com</a></p>"
            "<hr>"
            "<p><i>Named after Omar Khayyam (1048–1131) — Persian mathematician, "
            "astronomer, and poet.</i></p>",
        )

    def _open_website(self) -> None:
        import webbrowser
        webbrowser.open("https://d991d.com/khayyam-pdf-editor/")
