"""
pdf_viewer.py — PDF rendering and annotation interaction widget.
Uses PyMuPDF (fitz) for rendering and annotation, QGraphicsView for display.
"""

from __future__ import annotations
from typing import Optional, Callable
import fitz
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsLineItem,
    QGraphicsPathItem, QApplication,
)
from PyQt6.QtCore import Qt, QPointF, QRectF, QLineF, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QPixmap, QImage, QPainter, QPen, QColor, QBrush, QPainterPath,
    QCursor, QTransform,
)
from .models import AnnotationTool


# ── helpers ───────────────────────────────────────────────────────────────────

def _fitz_color(qcolor: QColor) -> tuple:
    """Convert QColor → fitz RGB tuple (0-1 range)."""
    return (qcolor.redF(), qcolor.greenF(), qcolor.blueF())


def _render_page(page: fitz.Page, zoom: float) -> QPixmap:
    """Render a fitz page to QPixmap at the given zoom level."""
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = QImage(bytes(pix.samples), pix.width, pix.height, pix.stride,
                 QImage.Format.Format_RGB888)
    return QPixmap.fromImage(img)


class PDFViewerWidget(QGraphicsView):
    """
    Core PDF display + annotation interaction widget.

    Signals
    -------
    page_changed(int)          — emitted when the current page changes
    status_message(str)        — short status text for the status bar
    document_modified()        — emitted after any annotation change
    annotation_selected(bool)  — True when an annotation is selected
    """

    page_changed = pyqtSignal(int)
    status_message = pyqtSignal(str)
    document_modified = pyqtSignal()
    annotation_selected = pyqtSignal(bool)

    # ── init ──────────────────────────────────────────────────────────────────

    def __init__(self, parent=None):
        super().__init__(parent)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # Document state
        self._doc: Optional[fitz.Document] = None
        self._doc_path: Optional[str] = None
        self._page_idx: int = 0
        self._zoom: float = 1.5

        # Tool state
        self._tool: AnnotationTool = AnnotationTool.SELECT

        # Colors
        self.highlight_color = QColor(255, 255, 0)      # Yellow
        self.underline_color = QColor(0, 0, 255)        # Blue
        self.strikethrough_color = QColor(255, 0, 0)    # Red
        self.stroke_color = QColor(0, 0, 0)             # Black for shapes/ink
        self.stroke_width: float = 2.0
        self.fill_color = QColor(0, 0, 0, 0)            # Transparent
        self.has_fill: bool = False
        self.typewriter_color = QColor(0, 0, 0)
        self.typewriter_font_size: int = 14

        # Search
        self._search_results: list[fitz.Rect] = []
        self._search_page_results: list[fitz.Rect] = []

        # Drawing / interaction state
        self._pressing: bool = False
        self._press_pdf: Optional[fitz.Point] = None      # PDF-space start
        self._press_scene: Optional[QPointF] = None       # Scene-space start
        self._ink_stroke: list[fitz.Point] = []           # Current ink stroke
        self._ink_path_item: Optional[QGraphicsPathItem] = None
        self._temp_item = None                             # Preview shape item
        self._line_start: Optional[fitz.Point] = None     # For line tool (2-click)
        self._line_start_item = None

        # Selection state
        self._sel_start_scene: Optional[QPointF] = None
        self._sel_rect_item: Optional[QGraphicsRectItem] = None
        self._selected_xref: Optional[int] = None

        # Text blocks (edit text tool)
        self._text_blocks: list[fitz.Rect] = []
        self._text_block_items: list[QGraphicsRectItem] = []

        # Page pixmap item
        self._page_item = QGraphicsPixmapItem()
        self._scene.addItem(self._page_item)

        # Callbacks (set by MainWindow)
        self.on_request_typewriter: Optional[Callable[[fitz.Point], None]] = None
        self.on_request_sticky_note: Optional[Callable[[fitz.Point], None]] = None
        self.on_request_edit_text: Optional[Callable[[fitz.Rect, str], None]] = None
        self.on_request_insert_image: Optional[Callable[[fitz.Point], None]] = None

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setBackgroundBrush(QBrush(QColor(64, 64, 64)))
        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        # Enable mouse tracking for cursor updates
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

    # ── public API ────────────────────────────────────────────────────────────

    def load_document(self, doc: fitz.Document, path: str) -> None:
        """Set a new fitz.Document and render page 0."""
        self._doc = doc
        self._doc_path = path
        self._page_idx = 0
        self._selected_xref = None
        self._clear_text_block_overlays()
        self._search_results.clear()
        self._search_page_results.clear()
        self.render_current_page()

    def close_document(self) -> None:
        self._doc = None
        self._doc_path = None
        self._page_item.setPixmap(QPixmap())
        self._scene.setSceneRect(QRectF())
        self._clear_text_block_overlays()

    @property
    def doc(self) -> Optional[fitz.Document]:
        return self._doc

    @property
    def page_index(self) -> int:
        return self._page_idx

    @property
    def total_pages(self) -> int:
        return self._doc.page_count if self._doc else 0

    @property
    def zoom(self) -> float:
        return self._zoom

    def set_tool(self, tool: AnnotationTool) -> None:
        self._tool = tool
        self._cancel_line_start()
        self._clear_text_block_overlays()
        if tool == AnnotationTool.HAND:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        else:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self._update_cursor()
        if tool == AnnotationTool.EDIT_TEXT:
            self._show_text_blocks()

    def go_to_page(self, index: int) -> None:
        if self._doc and 0 <= index < self._doc.page_count:
            self._page_idx = index
            self._selected_xref = None
            self._clear_text_block_overlays()
            self._update_search_page_results()
            self.render_current_page()
            self.page_changed.emit(self._page_idx)

    def go_to_prev(self) -> None:
        self.go_to_page(self._page_idx - 1)

    def go_to_next(self) -> None:
        self.go_to_page(self._page_idx + 1)

    def zoom_in(self) -> None:
        self._zoom = min(self._zoom * 1.25, 8.0)
        self.render_current_page()

    def zoom_out(self) -> None:
        self._zoom = max(self._zoom / 1.25, 0.15)
        self.render_current_page()

    def zoom_to_fit(self) -> None:
        if not self._doc:
            return
        page = self._doc[self._page_idx]
        vw = self.viewport().width() - 24
        self._zoom = max(0.2, vw / page.rect.width)
        self.render_current_page()

    def zoom_to_actual(self) -> None:
        self._zoom = 1.0
        self.render_current_page()

    def render_current_page(self) -> None:
        if not self._doc:
            return
        page = self._doc[self._page_idx]
        pix = _render_page(page, self._zoom)
        self._page_item.setPixmap(pix)
        w, h = pix.width(), pix.height()
        self._scene.setSceneRect(QRectF(0, 0, w, h))
        # Re-draw search highlights
        self._draw_search_highlights()
        # Re-show text blocks if in edit mode
        if self._tool == AnnotationTool.EDIT_TEXT:
            self._show_text_blocks()
        # Remove stale temp items
        self._remove_temp_item()

    def delete_selected_annotation(self) -> bool:
        if not (self._doc and self._selected_xref):
            return False
        page = self._doc[self._page_idx]
        for annot in page.annots():
            if annot.xref == self._selected_xref:
                page.delete_annot(annot)
                self._selected_xref = None
                self.annotation_selected.emit(False)
                self.render_current_page()
                self.document_modified.emit()
                return True
        return False

    # ── public: add annotations programmatically (called from dialogs) ───────

    def add_typewriter_text(
        self, pdf_pt: fitz.Point, text: str,
        font_size: int, color: QColor, bold: bool, italic: bool, align: int
    ) -> None:
        if not (self._doc and text.strip()):
            return
        page = self._doc[self._page_idx]
        # Estimate rect: roughly 6 px per char, fontSize height
        w = max(200, len(text) * font_size * 0.6)
        h = font_size * 1.6
        rect = fitz.Rect(pdf_pt.x, pdf_pt.y - h, pdf_pt.x + w, pdf_pt.y)
        annot = page.add_freetext_annot(
            rect, text,
            fontsize=font_size,
            fontname="helv",
            text_color=_fitz_color(color),
            fill_color=None,
            align=align,
        )
        annot.update()
        self.render_current_page()
        self.document_modified.emit()
        self.status_message.emit("Text added.")

    def add_sticky_note(self, pdf_pt: fitz.Point, text: str) -> None:
        if not self._doc:
            return
        page = self._doc[self._page_idx]
        annot = page.add_text_annot(pdf_pt, text if text else " ")
        annot.set_colors(stroke=(1, 1, 0))
        annot.update()
        self.render_current_page()
        self.document_modified.emit()
        self.status_message.emit("Sticky note added.")

    def replace_text_block(self, block_rect: fitz.Rect, new_text: str) -> None:
        if not (self._doc and new_text.strip()):
            return
        page = self._doc[self._page_idx]
        try:
            page.add_redact_annot(block_rect)
            page.apply_redactions()
            page.add_freetext_annot(
                block_rect, new_text,
                fontsize=11, fontname="helv",
                text_color=(0, 0, 0),
            )
            self.render_current_page()
            self.document_modified.emit()
            self.status_message.emit("Text updated.")
        except Exception as e:
            self.status_message.emit(f"Edit text failed: {e}")

    def insert_image_at(self, pdf_pt: fitz.Point, image_path: str) -> None:
        if not self._doc:
            return
        page = self._doc[self._page_idx]
        pw = page.rect.width
        ph = page.rect.height
        iw = min(200, pw * 0.4)
        ih = min(200, ph * 0.4)
        rect = fitz.Rect(pdf_pt.x - iw / 2, pdf_pt.y - ih / 2,
                         pdf_pt.x + iw / 2, pdf_pt.y + ih / 2)
        rect = rect & page.rect  # clip to page
        try:
            page.insert_image(rect, filename=image_path)
            self.render_current_page()
            self.document_modified.emit()
            self.status_message.emit("Image inserted.")
        except Exception as e:
            self.status_message.emit(f"Image insert failed: {e}")

    # ── search ────────────────────────────────────────────────────────────────

    def search(self, query: str) -> int:
        """Run full-document search. Returns hit count."""
        self._search_results.clear()
        if not (self._doc and query.strip()):
            self._draw_search_highlights()
            return 0
        for pi in range(self._doc.page_count):
            page = self._doc[pi]
            hits = page.search_for(query, quads=False)
            for r in hits:
                self._search_results.append((pi, r))
        self._update_search_page_results()
        self._draw_search_highlights()
        return len(self._search_results)

    def jump_to_search_result(self, idx: int) -> None:
        if not self._search_results:
            return
        idx = idx % len(self._search_results)
        page_idx, rect = self._search_results[idx]
        if page_idx != self._page_idx:
            self.go_to_page(page_idx)
        # Scroll to rect
        sr = QRectF(rect.x0 * self._zoom, rect.y0 * self._zoom,
                    rect.width * self._zoom, rect.height * self._zoom)
        self.ensureVisible(sr, 40, 40)

    def _update_search_page_results(self) -> None:
        self._search_page_results = [
            r for pi, r in self._search_results if pi == self._page_idx
        ]

    def _draw_search_highlights(self) -> None:
        # Remove old search overlays
        for item in self._scene.items():
            if getattr(item, "_is_search_highlight", False):
                self._scene.removeItem(item)
        for rect in self._search_page_results:
            sr = QRectF(rect.x0 * self._zoom, rect.y0 * self._zoom,
                        rect.width * self._zoom, rect.height * self._zoom)
            item = QGraphicsRectItem(sr)
            item.setPen(QPen(QColor(255, 165, 0, 180), 1))
            item.setBrush(QBrush(QColor(255, 200, 0, 60)))
            item._is_search_highlight = True
            self._scene.addItem(item)

    # ── coordinate helpers ────────────────────────────────────────────────────

    def _scene_to_pdf(self, scene_pt: QPointF) -> fitz.Point:
        return fitz.Point(scene_pt.x() / self._zoom, scene_pt.y() / self._zoom)

    def _widget_to_scene(self, widget_pt) -> QPointF:
        return self.mapToScene(widget_pt)

    # ── cursor ────────────────────────────────────────────────────────────────

    def _update_cursor(self) -> None:
        cursors = {
            AnnotationTool.SELECT: Qt.CursorShape.ArrowCursor,
            AnnotationTool.HAND: Qt.CursorShape.OpenHandCursor,
            AnnotationTool.STICKY_NOTE: Qt.CursorShape.CrossCursor,
            AnnotationTool.HIGHLIGHT: Qt.CursorShape.IBeamCursor,
            AnnotationTool.UNDERLINE: Qt.CursorShape.IBeamCursor,
            AnnotationTool.STRIKETHROUGH: Qt.CursorShape.IBeamCursor,
            AnnotationTool.INK: Qt.CursorShape.CrossCursor,
            AnnotationTool.RECTANGLE: Qt.CursorShape.CrossCursor,
            AnnotationTool.OVAL: Qt.CursorShape.CrossCursor,
            AnnotationTool.LINE: Qt.CursorShape.CrossCursor,
            AnnotationTool.TYPEWRITER: Qt.CursorShape.IBeamCursor,
            AnnotationTool.EDIT_TEXT: Qt.CursorShape.PointingHandCursor,
            AnnotationTool.INSERT_IMAGE: Qt.CursorShape.CrossCursor,
        }
        shape = cursors.get(self._tool, Qt.CursorShape.ArrowCursor)
        self.setCursor(QCursor(shape))

    # ── mouse events ─────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        if not self._doc:
            return

        scene_pt = self.mapToScene(event.pos())
        pdf_pt = self._scene_to_pdf(scene_pt)

        self._pressing = True
        self._press_scene = scene_pt
        self._press_pdf = pdf_pt

        tool = self._tool

        if tool == AnnotationTool.HAND:
            super().mousePressEvent(event)
            return

        if tool == AnnotationTool.SELECT:
            self._handle_select_click(scene_pt, pdf_pt)

        elif tool in (AnnotationTool.HIGHLIGHT, AnnotationTool.UNDERLINE,
                      AnnotationTool.STRIKETHROUGH):
            self._sel_start_scene = scene_pt
            # Create selection rect preview
            self._sel_rect_item = QGraphicsRectItem(QRectF(scene_pt, scene_pt))
            pen = QPen(QColor(70, 130, 180, 160), 1, Qt.PenStyle.DashLine)
            self._sel_rect_item.setPen(pen)
            self._sel_rect_item.setBrush(QBrush(QColor(70, 130, 180, 30)))
            self._scene.addItem(self._sel_rect_item)

        elif tool == AnnotationTool.INK:
            self._ink_stroke = [pdf_pt]
            path = QPainterPath()
            path.moveTo(scene_pt)
            self._ink_path_item = QGraphicsPathItem(path)
            pen = QPen(self.stroke_color, self.stroke_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            self._ink_path_item.setPen(pen)
            self._ink_path_item.setBrush(Qt.BrushStyle.NoBrush)
            self._scene.addItem(self._ink_path_item)

        elif tool in (AnnotationTool.RECTANGLE, AnnotationTool.OVAL):
            pass  # handled in move/release

        elif tool == AnnotationTool.LINE:
            pass  # drag-to-draw: start captured in _press_pdf; preview in mouseMoveEvent

        elif tool == AnnotationTool.STICKY_NOTE:
            if self.on_request_sticky_note:
                self.on_request_sticky_note(pdf_pt)

        elif tool == AnnotationTool.TYPEWRITER:
            if self.on_request_typewriter:
                self.on_request_typewriter(pdf_pt)

        elif tool == AnnotationTool.EDIT_TEXT:
            self._handle_edit_text_click(pdf_pt)

        elif tool == AnnotationTool.INSERT_IMAGE:
            if self.on_request_insert_image:
                self.on_request_insert_image(pdf_pt)

    def mouseMoveEvent(self, event) -> None:
        if not self._pressing:
            super().mouseMoveEvent(event)
            return
        if not self._doc:
            return

        scene_pt = self.mapToScene(event.pos())
        pdf_pt = self._scene_to_pdf(scene_pt)
        tool = self._tool

        if tool == AnnotationTool.HAND:
            super().mouseMoveEvent(event)
            return

        if tool in (AnnotationTool.HIGHLIGHT, AnnotationTool.UNDERLINE,
                    AnnotationTool.STRIKETHROUGH):
            if self._sel_rect_item and self._sel_start_scene:
                r = QRectF(self._sel_start_scene, scene_pt).normalized()
                self._sel_rect_item.setRect(r)

        elif tool == AnnotationTool.INK:
            self._ink_stroke.append(pdf_pt)
            if self._ink_path_item:
                path = self._ink_path_item.path()
                path.lineTo(scene_pt)
                self._ink_path_item.setPath(path)

        elif tool in (AnnotationTool.RECTANGLE, AnnotationTool.OVAL):
            if self._press_scene:
                mods = QApplication.keyboardModifiers()
                end_scene = self._constrain_square(self._press_scene, scene_pt, mods)
                r = QRectF(self._press_scene, end_scene).normalized()
                self._remove_temp_item()
                if tool == AnnotationTool.RECTANGLE:
                    item = QGraphicsRectItem(r)
                else:
                    item = QGraphicsEllipseItem(r)
                pen = QPen(self.stroke_color, self.stroke_width)
                item.setPen(pen)
                brush_color = QColor(self.fill_color)
                item.setBrush(QBrush(brush_color if self.has_fill else QColor(0, 0, 0, 0)))
                self._temp_item = item
                self._scene.addItem(item)

        elif tool == AnnotationTool.LINE:
            if self._press_scene:
                mods = QApplication.keyboardModifiers()
                end_scene = self._constrain_45(self._press_scene, scene_pt, mods)
                self._remove_temp_item()
                item = QGraphicsLineItem(QLineF(self._press_scene, end_scene))
                pen = QPen(self.stroke_color, self.stroke_width)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                item.setPen(pen)
                self._temp_item = item
                self._scene.addItem(item)

        elif tool == AnnotationTool.SELECT:
            # Drag to move selected annotation
            if self._selected_xref and self._press_pdf:
                page = self._doc[self._page_idx]
                for annot in page.annots():
                    if annot.xref == self._selected_xref:
                        r = annot.rect
                        dx = pdf_pt.x - self._press_pdf.x
                        dy = pdf_pt.y - self._press_pdf.y
                        new_rect = fitz.Rect(r.x0 + dx, r.y0 + dy,
                                             r.x1 + dx, r.y1 + dy)
                        annot.set_rect(new_rect)
                        annot.update()
                        self._press_pdf = pdf_pt
                        self.render_current_page()
                        self.document_modified.emit()
                        break

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return

        self._pressing = False
        if not self._doc:
            return

        scene_pt = self.mapToScene(event.pos())
        pdf_pt = self._scene_to_pdf(scene_pt)
        tool = self._tool

        if tool == AnnotationTool.HAND:
            super().mouseReleaseEvent(event)
            return

        if tool in (AnnotationTool.HIGHLIGHT, AnnotationTool.UNDERLINE,
                    AnnotationTool.STRIKETHROUGH):
            if self._sel_rect_item:
                self._scene.removeItem(self._sel_rect_item)
                self._sel_rect_item = None
            if self._sel_start_scene and self._press_pdf:
                self._apply_markup(self._press_pdf, pdf_pt, tool)
            self._sel_start_scene = None

        elif tool == AnnotationTool.INK:
            if len(self._ink_stroke) > 1:
                self._finalize_ink()
            elif self._ink_path_item:
                self._scene.removeItem(self._ink_path_item)
            self._ink_path_item = None
            self._ink_stroke.clear()

        elif tool in (AnnotationTool.RECTANGLE, AnnotationTool.OVAL):
            self._remove_temp_item()
            if self._press_pdf and self._press_scene:
                mods = QApplication.keyboardModifiers()
                end_scene = self._constrain_square(self._press_scene, scene_pt, mods)
                end_pdf = self._scene_to_pdf(end_scene)
                r = fitz.Rect(
                    min(self._press_pdf.x, end_pdf.x),
                    min(self._press_pdf.y, end_pdf.y),
                    max(self._press_pdf.x, end_pdf.x),
                    max(self._press_pdf.y, end_pdf.y),
                )
                if r.width > 4 and r.height > 4:
                    self._finalize_shape(r, tool)

        elif tool == AnnotationTool.LINE:
            self._remove_temp_item()
            if self._press_pdf and self._press_scene:
                mods = QApplication.keyboardModifiers()
                end_scene = self._constrain_45(self._press_scene, scene_pt, mods)
                end_pdf = self._scene_to_pdf(end_scene)
                dx = end_pdf.x - self._press_pdf.x
                dy = end_pdf.y - self._press_pdf.y
                if (dx * dx + dy * dy) > 16:  # at least 4px
                    self._finalize_line(self._press_pdf, end_pdf)

        self._press_pdf = None
        self._press_scene = None

    def wheelEvent(self, event) -> None:
        mods = QApplication.keyboardModifiers()
        if mods & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self._selected_xref:
                self.delete_selected_annotation()
                return
        if event.key() == Qt.Key.Key_Escape:
            self._cancel_line_start()
        super().keyPressEvent(event)

    # ── annotation logic ──────────────────────────────────────────────────────

    def _handle_select_click(self, scene_pt: QPointF, pdf_pt: fitz.Point) -> None:
        page = self._doc[self._page_idx]
        hit = None
        # Find annotation under cursor (expand hit area by 4px)
        expand = 4 / self._zoom
        for annot in page.annots():
            r = annot.rect
            expanded = fitz.Rect(r.x0 - expand, r.y0 - expand,
                                 r.x1 + expand, r.y1 + expand)
            if expanded.contains(pdf_pt):
                hit = annot
                break
        if hit:
            self._selected_xref = hit.xref
            self.annotation_selected.emit(True)
            self.status_message.emit(f"Selected annotation — Del to delete")
        else:
            self._selected_xref = None
            self.annotation_selected.emit(False)

    def _apply_markup(self, start: fitz.Point, end: fitz.Point,
                      tool: AnnotationTool) -> None:
        """Find words in the drag rect and apply markup annotation."""
        page = self._doc[self._page_idx]
        rect = fitz.Rect(
            min(start.x, end.x), min(start.y, end.y),
            max(start.x, end.x), max(start.y, end.y),
        )
        if rect.width < 3 or rect.height < 3:
            self.status_message.emit(
                "Drag across text to select, then the annotation is applied."
            )
            return
        # Find words in or near the selection rect (expand vertically to catch lines)
        expanded = fitz.Rect(rect.x0, rect.y0 - 2, rect.x1, rect.y1 + 2)
        words = page.get_text("words", clip=expanded)
        if not words:
            self.status_message.emit("No text found in selection.")
            return
        quads = [fitz.Quad(fitz.Rect(w[:4])) for w in words]

        if tool == AnnotationTool.HIGHLIGHT:
            annot = page.add_highlight_annot(quads)
            c = self.highlight_color
            annot.set_colors(stroke=_fitz_color(c))
            annot.update(opacity=0.5)
        elif tool == AnnotationTool.UNDERLINE:
            annot = page.add_underline_annot(quads)
            annot.set_colors(stroke=_fitz_color(self.underline_color))
            annot.update()
        elif tool == AnnotationTool.STRIKETHROUGH:
            annot = page.add_strikeout_annot(quads)
            annot.set_colors(stroke=_fitz_color(self.strikethrough_color))
            annot.update()

        self.render_current_page()
        self.document_modified.emit()
        self.status_message.emit(f"{tool.display_name} applied.")

    def _finalize_ink(self) -> None:
        if self._ink_path_item:
            self._scene.removeItem(self._ink_path_item)
            self._ink_path_item = None
        page = self._doc[self._page_idx]
        # Convert to list-of-lists for PyMuPDF ink annotation
        stroke = [(p.x, p.y) for p in self._ink_stroke]
        annot = page.add_ink_annot([stroke])
        c = _fitz_color(self.stroke_color)
        annot.set_colors(stroke=c)
        annot.set_border(width=self.stroke_width)
        annot.update()
        self.render_current_page()
        self.document_modified.emit()

    def _finalize_shape(self, rect: fitz.Rect, tool: AnnotationTool) -> None:
        page = self._doc[self._page_idx]
        if tool == AnnotationTool.RECTANGLE:
            annot = page.add_rect_annot(rect)
        else:
            annot = page.add_circle_annot(rect)
        stroke_c = _fitz_color(self.stroke_color)
        fill_c = _fitz_color(self.fill_color) if self.has_fill else None
        annot.set_colors(stroke=stroke_c, fill=fill_c)
        annot.set_border(width=self.stroke_width)
        annot.update()
        self.render_current_page()
        self.document_modified.emit()

    def _finalize_line(self, start_pdf: fitz.Point, end_pdf: fitz.Point) -> None:
        try:
            page = self._doc[self._page_idx]
            annot = page.add_line_annot(start_pdf, end_pdf)
            annot.set_colors(stroke=_fitz_color(self.stroke_color))
            annot.set_border(width=self.stroke_width)
            annot.update()
            self.render_current_page()
            self.document_modified.emit()
            self.status_message.emit("Line added.")
        except Exception as e:
            self.status_message.emit(f"Line error: {e}")

    def _cancel_line_start(self) -> None:
        pass  # no-op: line is now drag-based

    # ── Shift-key constraint helpers ──────────────────────────────────────────

    @staticmethod
    def _constrain_square(start: QPointF, end: QPointF,
                          mods: Qt.KeyboardModifier) -> QPointF:
        """If Shift held, constrain end so the bounding box is a square."""
        if not (mods & Qt.KeyboardModifier.ShiftModifier):
            return end
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        side = min(abs(dx), abs(dy))
        return QPointF(
            start.x() + (side if dx >= 0 else -side),
            start.y() + (side if dy >= 0 else -side),
        )

    @staticmethod
    def _constrain_45(start: QPointF, end: QPointF,
                      mods: Qt.KeyboardModifier) -> QPointF:
        """If Shift held, constrain line to nearest 45-degree angle."""
        if not (mods & Qt.KeyboardModifier.ShiftModifier):
            return end
        import math
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.hypot(dx, dy)
        if length < 1:
            return end
        angle = math.degrees(math.atan2(dy, dx))
        snapped = round(angle / 45) * 45
        rad = math.radians(snapped)
        return QPointF(
            start.x() + length * math.cos(rad),
            start.y() + length * math.sin(rad),
        )

    def _remove_temp_item(self) -> None:
        if self._temp_item:
            self._scene.removeItem(self._temp_item)
            self._temp_item = None

    # ── text block overlay (Edit Text tool) ──────────────────────────────────

    def _show_text_blocks(self) -> None:
        self._clear_text_block_overlays()
        if not self._doc:
            return
        page = self._doc[self._page_idx]
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if b.get("type") != 0:
                continue  # skip image blocks
            r = fitz.Rect(b["bbox"])
            sr = QRectF(r.x0 * self._zoom, r.y0 * self._zoom,
                        r.width * self._zoom, r.height * self._zoom)
            item = QGraphicsRectItem(sr)
            item.setPen(QPen(QColor(0, 100, 200, 120), 1, Qt.PenStyle.DashLine))
            item.setBrush(QBrush(QColor(0, 100, 200, 15)))
            item._text_rect = r
            item._text = " ".join(
                span["text"]
                for line in b.get("lines", [])
                for span in line.get("spans", [])
            )
            self._text_block_items.append(item)
            self._scene.addItem(item)

    def _clear_text_block_overlays(self) -> None:
        for item in self._text_block_items:
            self._scene.removeItem(item)
        self._text_block_items.clear()

    def _handle_edit_text_click(self, pdf_pt: fitz.Point) -> None:
        if not self.on_request_edit_text:
            return
        if not self._text_block_items:
            self.status_message.emit("No editable text found on this page.")
            return
        # Find the smallest block that contains the click (expand by 3pt for easier targeting)
        best_item = None
        best_area = float("inf")
        for item in self._text_block_items:
            r: fitz.Rect = item._text_rect
            expanded = fitz.Rect(r.x0 - 3, r.y0 - 3, r.x1 + 3, r.y1 + 3)
            if (expanded.x0 <= pdf_pt.x <= expanded.x1 and
                    expanded.y0 <= pdf_pt.y <= expanded.y1):
                area = r.width * r.height
                if area < best_area:
                    best_area = area
                    best_item = item
        if best_item:
            self.on_request_edit_text(best_item._text_rect, best_item._text)
        else:
            self.status_message.emit("Click on a blue-outlined text block to edit it.")
