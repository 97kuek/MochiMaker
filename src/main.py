# -*- coding: utf-8 -*-
"""
ExamPackMaker_Multi.py
複数PDFを読み込み、並べ替えてから Nアップで用紙にレイアウトし、1つのPDFに出力するツール
- PyQt6 + PyMuPDF
- ベクタ品質のまま show_pdf_page で配置
- 自動段組（最小スライド幅mmベース）
- 白フチ自動トリム（低DPI二値化で非白領域BBox→clip Rect）
- 複数PDFのドラッグ＆ドロップ並べ替え対応
- プレビューのズーム/パン、ページ送り
- 外部からPDFドラッグ＆ドロップ追加
- ページ番号描画（出力ページ右下）とセル内元ページ番号の描画オプション
- 使い方ヘルプダイアログ
"""

import sys, math, os
from dataclasses import dataclass
from typing import Tuple, List, Optional

from PyQt6.QtCore import Qt, QSize, pyqtSignal, QRectF
from PyQt6.QtGui import QPixmap, QAction, QGuiApplication, QDragEnterEvent, QDropEvent, QKeySequence, QTransform, QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QGroupBox, QFormLayout, QMessageBox, QListWidget, QListWidgetItem,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QSlider, QToolButton, QStyle, QLineEdit
)
from PyQt6.QtGui import QPainter

import fitz  # PyMuPDF

# ===== ユーティリティ =====
PT_PER_INCH = 72.0
MM_PER_INCH = 25.4

def mm_to_pt(mm: float) -> float:
    return mm / MM_PER_INCH * PT_PER_INCH

def paper_size_pt(name: str, landscape: bool) -> Tuple[float, float]:
    sizes_mm = {
        "A4": (210.0, 297.0),
        "A3": (297.0, 420.0),
        "Letter": (215.9, 279.4),
    }
    if name not in sizes_mm:
        name = "A4"
    w_mm, h_mm = sizes_mm[name]
    if landscape:
        w_mm, h_mm = h_mm, w_mm
    return (mm_to_pt(w_mm), mm_to_pt(h_mm))

@dataclass
class LayoutParams:
    rows: int
    cols: int
    margin_mm: float
    gap_mm: float
    auto_readable: bool
    min_slide_w_mm: float

@dataclass
class BuildParams:
    paper: str
    landscape: bool
    layout: LayoutParams
    trim_whitespace: bool
    trim_threshold: int  # 0-255
    draw_page_numbers: bool  # 出力ページ右下に 1 / N を描画
    draw_cell_indices: bool  # 各セル内に元ページの通し番号を描画
    cell_index_font_pt: float
    page_number_font_pt: float

# 候補グリッド
CANDIDATE_GRIDS = [
    (1,1),(1,2),(2,1),(2,2),
    (2,3),(3,2),
    (3,3),
    (2,4),(4,2),
    (3,4),(4,3),
    (4,4)
]

def choose_auto_grid(paper_pt: Tuple[float,float], layout: LayoutParams) -> Tuple[int,int]:
    margin_pt = mm_to_pt(layout.margin_mm)
    gap_pt = mm_to_pt(layout.gap_mm)
    page_w, page_h = paper_pt
    usable_w = page_w - 2*margin_pt
    usable_h = page_h - 2*margin_pt
    best = (1,1)
    for r,c in CANDIDATE_GRIDS:
        cell_w = (usable_w - (c-1)*gap_pt)/c
        cell_h = (usable_h - (r-1)*gap_pt)/r
        if cell_w >= mm_to_pt(layout.min_slide_w_mm):
            if r*c > best[0]*best[1]:
                best = (r,c)
            elif r*c == best[0]*best[1]:
                bw = (usable_w - (best[1]-1)*gap_pt)/best[1]
                if cell_w > bw:
                    best = (r,c)
    return best

def nonwhite_bbox_pixmap(pix: fitz.Pixmap, threshold: int=245) -> Optional[fitz.Rect]:
    try:
        if pix.alpha:
            pix = fitz.Pixmap(pix, 0)  # drop alpha
        w, h = pix.width, pix.height
        data = pix.samples
        ncomp = pix.n  # 3
        xmin, ymin, xmax, ymax = w, h, -1, -1
        for y in range(h):
            row_start = y * w * ncomp
            row = data[row_start:row_start + w*ncomp]
            for x in range(w):
                r = row[x*ncomp]; g = row[x*ncomp+1]; b = row[x*ncomp+2]
                if min(r,g,b) < threshold:
                    if x < xmin: xmin = x
                    if y < ymin: ymin = y
                    if x > xmax: xmax = x
                    if y > ymax: ymax = y
        if xmax < 0:
            return None
        return fitz.Rect(xmin, ymin, xmax+1, ymax+1)
    except Exception:
        return None

def estimate_content_clip(src_page: fitz.Page, threshold: int=245) -> fitz.Rect:
    try:
        target_dpi = 72
        zoom = target_dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = src_page.get_pixmap(matrix=mat, alpha=False)
        bbox_px = nonwhite_bbox_pixmap(pix, threshold)
        if not bbox_px:
            return src_page.rect
        inv = fitz.Matrix(1/zoom, 1/zoom)
        rect_pt = inv.transform_rect(fitz.Rect(bbox_px))
        rect_pt = rect_pt + fitz.Rect(-2,-2,2,2)
        return rect_pt & src_page.rect
    except Exception:
        return src_page.rect

def build_nup_from_multiple(
    src_files: List[str],
    params: BuildParams,
    stop_after_pages: Optional[int] = None
) -> fitz.Document:
    """
    src_files の順にページを並べ、Nアップで out に配置して返す。
    stop_after_pages が指定された場合、出力ページをその枚数作成した時点で停止（プレビュー高速化用）。
    """
    out = fitz.open()
    page_w, page_h = paper_size_pt(params.paper, params.landscape)

    # レイアウト
    if params.layout.auto_readable:
        rows, cols = choose_auto_grid((page_w,page_h), params.layout)
    else:
        rows, cols = params.layout.rows, params.layout.cols

    margin = mm_to_pt(params.layout.margin_mm)
    gap = mm_to_pt(params.layout.gap_mm)
    usable_w = page_w - 2*margin
    usable_h = page_h - 2*margin
    cell_w = (usable_w - (cols-1)*gap)/cols
    cell_h = (usable_h - (rows-1)*gap)/rows
    total_slots = rows * cols

    slot_used = 0
    out_page = None

    # 元ページの通し番号（1始まり）
    global_page_index = 0

    def draw_page_number_footer(page: fitz.Page, page_idx1: int, total_pages: int):
        if not params.draw_page_numbers:
            return
        footer_text = f"{page_idx1} / {total_pages}"
        # 右下寄せの小さめボックス
        pad = mm_to_pt(6)
        box_w = mm_to_pt(40)
        box_h = mm_to_pt(10)
        rect = fitz.Rect(page.rect.x1 - box_w - pad, page.rect.y1 - box_h - pad,
                         page.rect.x1 - pad, page.rect.y1 - pad)
        page.insert_textbox(
            rect, footer_text,
            fontsize=params.page_number_font_pt,
            fontname="helv",
            align=2,  # right
            color=(0,0,0)
        )

    # まず総ページ数を数える（フッターに総数を入れるため）
    total_input_pages = 0
    for path in src_files:
        try:
            with fitz.open(path) as d:
                total_input_pages += len(d)
        except:
            pass

    # 合計の出力ページ数は分からないが、stop_after_pages 指定時はその分のフッタ総数は後から更新できない
    # ここではひとまず仮で 0 を入れておき、最後に2パス目で描画してもいいが、効率のために
    # 「出力ページ作成後にフッタを描く」方式にして、ここではページ番号だけ保持して最後にもう一度回す。
    # ただ、PyMuPDFではページ後編集が可能なので最後に総数を書き込む2パス方式を採用する。

    # 出力ページのインデックス（1始まり）を記録
    out_pages_created: List[int] = []  # ダミー、長さが総ページ枚数になる

    # ソース列挙・配置
    for path in src_files:
        try:
            src = fitz.open(path)
        except Exception as e:
            # 読めないファイルはスキップ
            continue
        try:
            for pno in range(len(src)):
                if slot_used == 0:
                    out_page = out.new_page(width=page_w, height=page_h)
                    out_pages_created.append(0)  # プレースホルダ

                r = slot_used // cols
                c = slot_used % cols
                x0 = margin + c*(cell_w + gap)
                y0 = margin + r*(cell_h + gap)
                rect = fitz.Rect(x0, y0, x0+cell_w, y0+cell_h)

                sp = src.load_page(pno)
                clip_rect = sp.rect
                if params.trim_whitespace:
                    clip_rect = estimate_content_clip(sp, params.trim_threshold)

                out_page.show_pdf_page(rect, src, pno, clip=clip_rect, keep_proportion=True)

                # セル内に元ページ通し番号
                global_page_index += 1
                if params.draw_cell_indices:
                    # 右上に小さく
                    idx_text = f"{global_page_index}"
                    pad = mm_to_pt(2.5)
                    box_w = mm_to_pt(10)
                    box_h = mm_to_pt(6)
                    trect = fitz.Rect(rect.x1 - box_w - pad, rect.y0 + pad,
                                      rect.x1 - pad, rect.y0 + pad + box_h)
                    out_page.insert_textbox(
                        trect, idx_text,
                        fontsize=params.cell_index_font_pt,
                        fontname="helv",
                        align=2,  # right
                        color=(0,0,0)
                    )

                slot_used += 1
                if slot_used >= total_slots:
                    slot_used = 0
                    # stop_after_pages ならここで判定
                    if stop_after_pages is not None and len(out) >= stop_after_pages:
                        src.close()
                        # 総ページ数が stop_after_pages のときのフッタ描画（総枚数が確定している）
                        total_out = len(out)
                        for i in range(total_out):
                            page = out.load_page(i)
                            draw_page_number_footer(page, i+1, total_out)
                        return out
        finally:
            src.close()

    # すべて配置完了。総ページ数が確定したのでフッタ描画
    total_out = len(out)
    for i in range(total_out):
        page = out.load_page(i)
        draw_page_number_footer(page, i+1, total_out)

    return out

# ===== プレビュー（ズーム/パン対応） =====
class PreviewView(QGraphicsView):
    zoomChanged = pyqtSignal(float)  # 現在倍率（%）
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self._pix_item: Optional[QGraphicsPixmapItem] = None
        self._scale = 1.0
        self.setRenderHints(
            self.renderHints()
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.Antialiasing
        )

        # スクロールバー表示、ドラッグでパン
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setBackgroundBrush(Qt.GlobalColor.lightGray)

    def setPixmap(self, pix: QPixmap):
        self.scene().clear()
        self._pix_item = QGraphicsPixmapItem(pix)
        self.scene().addItem(self._pix_item)
        self.scene().setSceneRect(QRectF(pix.rect()))
        self.resetZoom()

    def wheelEvent(self, event):
        # Ctrl+ホイールでズーム、通常ホイールはスクロール
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            angle = event.angleDelta().y()
            factor = 1.25 if angle > 0 else 0.8
            self._applyZoom(factor, anchor_pos=event.position())
        else:
            super().wheelEvent(event)

    def _applyZoom(self, factor: float, anchor_pos=None):
        if self._pix_item is None:
            return
        old_scale = self._scale
        self._scale = max(0.05, min(10.0, self._scale * factor))
        factor_to_apply = self._scale / old_scale

        # アンカー位置でズーム
        if anchor_pos is not None:
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        else:
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

        self.scale(factor_to_apply, factor_to_apply)
        self.zoomChanged.emit(self._scale * 100.0)

    def zoomIn(self):
        self._applyZoom(1.25)

    def zoomOut(self):
        self._applyZoom(0.8)

    def resetZoom(self):
        # 1.0 に戻してフィットはしない
        self.setTransform(QTransform())
        self._scale = 1.0
        self.zoomChanged.emit(100.0)

    def fitWidth(self):
        if self._pix_item is None:
            return
        view_w = self.viewport().width()
        pix_w = self._pix_item.pixmap().width()
        if pix_w <= 0:
            return
        target_scale = (view_w - 20) / pix_w
        if target_scale <= 0:
            return
        self.setTransform(QTransform())
        self._scale = target_scale
        self.scale(self._scale, self._scale)
        self.zoomChanged.emit(self._scale * 100.0)

# ===== ファイルリスト（外部D&D受け入れ） =====
class FileListWidget(QListWidget):
    filesDropped = pyqtSignal(list)  # list[str]
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(self.SelectionMode.ExtendedSelection)
        self.setDragDropMode(self.DragDropMode.InternalMove)
        self.setAlternatingRowColors(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for u in urls:
                if u.isLocalFile() and u.toLocalFile().lower().endswith(".pdf"):
                    event.acceptProposedAction()
                    return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            ok = any(u.isLocalFile() and u.toLocalFile().lower().endswith(".pdf") for u in urls)
            if ok:
                event.acceptProposedAction()
                return
        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            paths = []
            for u in event.mimeData().urls():
                if u.isLocalFile() and u.toLocalFile().lower().endswith(".pdf"):
                    paths.append(u.toLocalFile())
            if paths:
                self.filesDropped.emit(paths)
                event.acceptProposedAction()
                return
        super().dropEvent(event)

# ===== GUI =====
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("期末持ち込み資料メーカー（複数PDF対応）")
        self.setMinimumSize(QSize(1200, 780))

        # 状態
        self.preview_doc: Optional[fitz.Document] = None
        self.preview_current_page = 0  # 0-based

        # 複数PDFの管理：ファイルリスト（外部D&D対応）
        self.list_widget = FileListWidget()
        self.list_widget.setMinimumWidth(380)
        self.list_widget.filesDropped.connect(self._append_files)

        add_btn = QPushButton("ファイルを追加")
        add_btn.clicked.connect(self.add_files)
        add_dir_btn = QPushButton("フォルダから追加")
        add_dir_btn.clicked.connect(self.add_from_folder)
        up_btn = QPushButton("上へ")
        up_btn.clicked.connect(self.move_up)
        down_btn = QPushButton("下へ")
        down_btn.clicked.connect(self.move_down)
        del_btn = QPushButton("削除")
        del_btn.clicked.connect(self.remove_selected)
        clear_btn = QPushButton("クリア")
        clear_btn.clicked.connect(self.clear_list)

        # 用紙 / 余白 / 間隔
        self.paper_combo = QComboBox(); self.paper_combo.addItems(["A4","A3","Letter"])
        self.orientation_combo = QComboBox(); self.orientation_combo.addItems(["縦","横"])
        self.margin_spin = QDoubleSpinBox(); self.margin_spin.setRange(0, 50); self.margin_spin.setValue(10.0); self.margin_spin.setSuffix(" mm")
        self.gap_spin = QDoubleSpinBox(); self.gap_spin.setRange(0, 30); self.gap_spin.setValue(4.0); self.gap_spin.setSuffix(" mm")

        # レイアウト
        self.auto_chk = QCheckBox("自動（読みやすさ優先）"); self.auto_chk.setChecked(True)
        self.rows_spin = QSpinBox(); self.rows_spin.setRange(1, 10); self.rows_spin.setValue(2)
        self.cols_spin = QSpinBox(); self.cols_spin.setRange(1, 10); self.cols_spin.setValue(2)
        self.minw_spin = QDoubleSpinBox(); self.minw_spin.setRange(30, 200); self.minw_spin.setValue(90.0); self.minw_spin.setSuffix(" mm")
        self.auto_chk.stateChanged.connect(self.toggle_auto_ui)

        # トリム
        self.trim_chk = QCheckBox("白フチ自動トリムを有効化"); self.trim_chk.setChecked(True)
        self.trim_thr = QSpinBox(); self.trim_thr.setRange(200, 255); self.trim_thr.setValue(245); self.trim_thr.setSuffix("（しきい値）")

        # ページ番号描画
        self.page_num_chk = QCheckBox("出力ページにページ番号を表示（右下）"); self.page_num_chk.setChecked(True)
        self.page_num_font = QDoubleSpinBox(); self.page_num_font.setRange(6.0, 24.0); self.page_num_font.setValue(9.0); self.page_num_font.setSuffix(" pt")

        # セル内元ページ番号
        self.cell_idx_chk = QCheckBox("各セルに元ページ通し番号を表示（右上）"); self.cell_idx_chk.setChecked(False)
        self.cell_idx_font = QDoubleSpinBox(); self.cell_idx_font.setRange(6.0, 18.0); self.cell_idx_font.setValue(7.0); self.cell_idx_font.setSuffix(" pt")

        # プレビューウィジェット（ズーム）
        self.preview_view = PreviewView()
        self.preview_zoom_label = QLabel("100%")
        self.preview_view.zoomChanged.connect(lambda v: self.preview_zoom_label.setText(f"{v:.0f}%"))

        # プレビューツールバー
        self.btn_prev = QToolButton(); self.btn_prev.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowLeft)); self.btn_prev.setToolTip("前のページ")
        self.btn_next = QToolButton(); self.btn_next.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowRight)); self.btn_next.setToolTip("次のページ")
        self.page_indicator = QLineEdit(); self.page_indicator.setFixedWidth(70); self.page_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_indicator.setPlaceholderText("1")
        self.page_indicator.returnPressed.connect(self._jump_to_page_from_indicator)
        self.total_label = QLabel("/ 0")
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_next.clicked.connect(self.next_page)

        self.btn_zoom_out = QToolButton(); self.btn_zoom_out.setText("−"); self.btn_zoom_out.setToolTip("ズームアウト (Ctrl+ホイールでも可)")
        self.btn_zoom_in  = QToolButton(); self.btn_zoom_in.setText("+"); self.btn_zoom_in.setToolTip("ズームイン (Ctrl+ホイールでも可)")
        self.btn_zoom_100 = QToolButton(); self.btn_zoom_100.setText("100%")
        self.btn_fit_w    = QToolButton(); self.btn_fit_w.setText("幅に合わせる")
        self.btn_zoom_out.clicked.connect(self.preview_view.zoomOut)
        self.btn_zoom_in.clicked.connect(self.preview_view.zoomIn)
        self.btn_zoom_100.clicked.connect(self.preview_view.resetZoom)
        self.btn_fit_w.clicked.connect(self.preview_view.fitWidth)

        # プレビュー更新 / 保存
        preview_btn = QPushButton("プレビュー更新"); preview_btn.clicked.connect(self.update_preview)
        save_btn = QPushButton("PDFとして保存"); save_btn.clicked.connect(self.save_pdf)

        # 情報ラベル
        self.info_label = QLabel("PDF未追加")
        self.info_label.setWordWrap(True)

        # 左カラム（ファイル操作）
        list_ops = QHBoxLayout()
        list_ops.addWidget(add_btn); list_ops.addWidget(add_dir_btn)
        list_ops2 = QHBoxLayout()
        list_ops2.addWidget(up_btn); list_ops2.addWidget(down_btn); list_ops2.addWidget(del_btn); list_ops2.addWidget(clear_btn)

        left = QVBoxLayout()
        left.addWidget(QLabel("入力PDFリスト（ドラッグで並べ替え、外部からドロップで追加可）"))
        left.addWidget(self.list_widget, 1)
        left.addLayout(list_ops)
        left.addLayout(list_ops2)
        left.addWidget(self.info_label)

        # 右カラム（設定）
        paper_box = QGroupBox("用紙")
        pf = QFormLayout()
        pf.addRow("サイズ", self.paper_combo)
        pf.addRow("向き", self.orientation_combo)
        pf.addRow("余白", self.margin_spin)
        pf.addRow("スライド間隔", self.gap_spin)
        paper_box.setLayout(pf)

        layout_box = QGroupBox("段組（Nアップ）")
        lf = QFormLayout()
        lf.addRow(self.auto_chk)
        lf.addRow("行（固定時）", self.rows_spin)
        lf.addRow("列（固定時）", self.cols_spin)
        lf.addRow("最小スライド幅（自動時）", self.minw_spin)
        layout_box.setLayout(lf)

        trim_box = QGroupBox("トリム（白フチ削減）")
        tf = QFormLayout()
        tf.addRow(self.trim_chk)
        tf.addRow("明度しきい値", self.trim_thr)
        trim_box.setLayout(tf)

        number_box = QGroupBox("ページ番号表示")
        nf = QFormLayout()
        nf.addRow(self.page_num_chk)
        nf.addRow("ページ番号フォント", self.page_num_font)
        nf.addRow(self.cell_idx_chk)
        nf.addRow("セル番号フォント", self.cell_idx_font)
        number_box.setLayout(nf)

        right_controls = QVBoxLayout()
        right_controls.addWidget(paper_box)
        right_controls.addWidget(layout_box)
        right_controls.addWidget(trim_box)
        right_controls.addWidget(number_box)
        right_controls.addStretch(1)

        # プレビューバー
        pbar = QHBoxLayout()
        pbar.addWidget(self.btn_prev)
        pbar.addWidget(self.page_indicator)
        pbar.addWidget(self.total_label)
        pbar.addWidget(self.btn_next)
        pbar.addStretch(1)
        pbar.addWidget(self.btn_zoom_out)
        pbar.addWidget(self.btn_zoom_in)
        pbar.addWidget(self.btn_zoom_100)
        pbar.addWidget(self.btn_fit_w)
        pbar.addSpacing(8)
        pbar.addWidget(QLabel("拡大率:"))
        pbar.addWidget(self.preview_zoom_label)
        pbar.addStretch(1)
        pbar.addWidget(preview_btn)
        pbar.addWidget(save_btn)

        # メインレイアウト
        main = QHBoxLayout()
        right_side = QVBoxLayout()
        right_side.addLayout(right_controls)
        right_side.addLayout(pbar)
        right_side.addWidget(self.preview_view, 1)

        main.addLayout(left, 0)
        main.addLayout(right_side, 1)

        container = QWidget(); container.setLayout(main)
        self.setCentralWidget(container)

        # メニュー
        self._build_menu()

        self.toggle_auto_ui()
        self.update_info_label()
        self._update_preview_controls_enabled(False)

        # ショートカット
        QAction("Zoom In", self, shortcut=QKeySequence.StandardKey.ZoomIn, triggered=self.preview_view.zoomIn)
        QAction("Zoom Out", self, shortcut=QKeySequence.StandardKey.ZoomOut, triggered=self.preview_view.zoomOut)

    # ===== メニュー =====
    def _build_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("ファイル")
        add_act = QAction("ファイルを追加...", self); add_act.triggered.connect(self.add_files)
        add_dir_act = QAction("フォルダから追加...", self); add_dir_act.triggered.connect(self.add_from_folder)
        save_act = QAction("PDFとして保存", self); save_act.triggered.connect(self.save_pdf)
        file_menu.addAction(add_act); file_menu.addAction(add_dir_act); file_menu.addAction(save_act)

        help_menu = menubar.addMenu("ヘルプ")
        howto_act = QAction("使い方", self); howto_act.triggered.connect(self.show_howto)
        help_menu.addAction(howto_act)

    def show_howto(self):
        text = (
            "<h3>使い方</h3>"
            "<ol>"
            "<li>左のリストにPDFを追加します（<b>外部からドラッグ＆ドロップ</b>でもOK、上下ボタンやドラッグで並べ替え）。</li>"
            "<li>右側で用紙サイズ・向き、段組（自動 or 固定）、余白や間隔、トリム設定を調整します。</li>"
            "<li>必要なら「ページ番号表示」「セル番号表示」をONにします。</li>"
            "<li>「プレビュー更新」を押すと右下に合成結果のプレビューが表示されます。<br>"
            "　<b>Ctrl+マウスホイール</b>や<b>＋/−</b>ボタンでズーム、ドラッグでパン、<b>幅に合わせる</b>で横幅フィット。</li>"
            "<li>ページ送り（左右ボタン、ページ番号入力）で全ページを確認できます。</li>"
            "<li>OKなら「PDFとして保存」を押して出力します。</li>"
            "</ol>"
            "<p>ヒント：<br>"
            "・「自動（読みやすさ優先）」は最小スライド幅（mm）を満たす最大の段組を自動選択します。<br>"
            "・白フチトリムは明るさしきい値で検出（数値を下げると厳しめに、上げると緩めに）。<br>"
            "・セル番号は、元ドキュメント群を合算した通し番号を小さく右上に描きます。</p>"
        )
        QMessageBox.information(self, "使い方", text)

    # ===== ファイルリスト操作 =====
    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "PDFを選択", "", "PDF Files (*.pdf)")
        if not files:
            return
        self._append_files(files)

    def add_from_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "フォルダ選択")
        if not folder:
            return
        pdfs = []
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith(".pdf"):
                pdfs.append(os.path.join(folder, name))
        if not pdfs:
            QMessageBox.information(self, "情報", "選択フォルダにPDFが見つかりませんでした。")
            return
        self._append_files(pdfs)

    def _append_files(self, paths: List[str]):
        # 重複は許容（順番を尊重）。存在しないファイルはスキップ
        added = 0
        for p in paths:
            if not os.path.isfile(p):
                continue
            try:
                doc = fitz.open(p)
                n = len(doc)
                doc.close()
                item = QListWidgetItem(f"{os.path.basename(p)}  ({n}ページ)")
                item.setToolTip(p)
                self.list_widget.addItem(item)
                added += 1
            except Exception as e:
                QMessageBox.warning(self, "読み込み警告", f"{p}\nを開けませんでした: {e}")
        if added > 0:
            self.update_info_label()
            # 新規追加後はプレビュー無効化（設定が変わるため）
            self._clear_preview_state()

    def move_up(self):
        rows = sorted(set([i.row() for i in self.list_widget.selectedIndexes()]))
        if not rows:
            return
        for r in rows:
            if r == 0: continue
            item = self.list_widget.takeItem(r)
            self.list_widget.insertItem(r-1, item)
            item.setSelected(True)
        self.update_info_label()
        self._clear_preview_state()

    def move_down(self):
        rows = sorted(set([i.row() for i in self.list_widget.selectedIndexes()]), reverse=True)
        if not rows:
            return
        for r in rows:
            if r == self.list_widget.count()-1: continue
            item = self.list_widget.takeItem(r)
            self.list_widget.insertItem(r+1, item)
            item.setSelected(True)
        self.update_info_label()
        self._clear_preview_state()

    def remove_selected(self):
        rows = sorted(set([i.row() for i in self.list_widget.selectedIndexes()]), reverse=True)
        for r in rows:
            self.list_widget.takeItem(r)
        self.update_info_label()
        self._clear_preview_state()

    def clear_list(self):
        self.list_widget.clear()
        self.update_info_label()
        self._clear_preview_state()

    def get_file_list(self) -> List[str]:
        paths = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            paths.append(item.toolTip())  # フルパスを保存してある
        return paths

    # ===== 共通UI =====
    def toggle_auto_ui(self):
        auto = self.auto_chk.isChecked()
        self.rows_spin.setEnabled(not auto)
        self.cols_spin.setEnabled(not auto)
        self.minw_spin.setEnabled(auto)


    def gather_params(self) -> Optional[BuildParams]:
        files = self.get_file_list()
        if not files:
            QMessageBox.warning(self, "注意", "まず入力PDFを追加してください。")
            return None
        paper = self.paper_combo.currentText()
        landscape = (self.orientation_combo.currentText() == "横")
        auto = self.auto_chk.isChecked()
        rows = self.rows_spin.value()
        cols = self.cols_spin.value()
        margin = self.margin_spin.value()
        gap = self.gap_spin.value()
        minw = self.minw_spin.value()
        trim = self.trim_chk.isChecked()
        thr = self.trim_thr.value()
        draw_pn = self.page_num_chk.isChecked()
        draw_ci = self.cell_idx_chk.isChecked()
        pn_font = self.page_num_font.value()
        ci_font = self.cell_idx_font.value()

        layout = LayoutParams(
            rows=rows, cols=cols,
            margin_mm=margin, gap_mm=gap,
            auto_readable=auto, min_slide_w_mm=minw
        )
        return BuildParams(
            paper=paper, landscape=landscape,
            layout=layout,
            trim_whitespace=trim, trim_threshold=thr,
            draw_page_numbers=draw_pn,
            draw_cell_indices=draw_ci,
            cell_index_font_pt=ci_font,
            page_number_font_pt=pn_font
        )

    def update_info_label(self):
        files = self.get_file_list()
        if not files:
            self.info_label.setText("PDF未追加")
            return
        # 総ページ数など
        total_pages = 0
        for p in files:
            try:
                d = fitz.open(p); total_pages += len(d); d.close()
            except:
                pass
        self.info_label.setText(f"入力ファイル数: {len(files)}  / 合計ページ: {total_pages}")

    # ===== プレビュー =====
    def _clear_preview_state(self):
        self.preview_doc = None
        self.preview_current_page = 0
        self.preview_view.setPixmap(QPixmap())  # クリア
        self.page_indicator.setText("")
        self.total_label.setText("/ 0")
        self._update_preview_controls_enabled(False)

    def _update_preview_controls_enabled(self, enabled: bool):
        self.btn_prev.setEnabled(enabled)
        self.btn_next.setEnabled(enabled)
        self.page_indicator.setEnabled(enabled)
        self.btn_zoom_in.setEnabled(enabled)
        self.btn_zoom_out.setEnabled(enabled)
        self.btn_zoom_100.setEnabled(enabled)
        self.btn_fit_w.setEnabled(enabled)

    def update_preview(self):
        params = self.gather_params()
        if not params:
            return
        files = self.get_file_list()
        try:
            # 全ページを生成（メモリ節約したい場合は stop_after_pages を使って逐次でもOK）
            self.preview_doc = build_nup_from_multiple(files, params, stop_after_pages=None)
            self.preview_current_page = 0
            self._show_preview_page(0)
            total = len(self.preview_doc)
            self.total_label.setText(f"/ {total}")
            self.page_indicator.setText("1")
            self._update_preview_controls_enabled(total > 0)
        except Exception as e:
            QMessageBox.warning(self, "プレビューエラー", f"プレビュー生成中にエラーが発生しました:\n{e}")

    def _render_page_to_pixmap(self, doc: fitz.Document, index: int, scale: float = 2.0) -> QPixmap:
        page = doc.load_page(index)
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        from PyQt6.QtGui import QImage
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(img)

    def _show_preview_page(self, index: int):
        if self.preview_doc is None:
            return
        index = max(0, min(index, len(self.preview_doc)-1))
        pix = self._render_page_to_pixmap(self.preview_doc, index, scale=2.0)
        self.preview_view.setPixmap(pix)
        self.preview_current_page = index
        self.page_indicator.setText(str(index+1))

    def prev_page(self):
        if self.preview_doc is None:
            return
        if self.preview_current_page > 0:
            self._show_preview_page(self.preview_current_page - 1)

    def next_page(self):
        if self.preview_doc is None:
            return
        if self.preview_current_page < len(self.preview_doc)-1:
            self._show_preview_page(self.preview_current_page + 1)

    def _jump_to_page_from_indicator(self):
        if self.preview_doc is None:
            return
        try:
            n = int(self.page_indicator.text().strip())
            self._show_preview_page(n-1)
        except:
            # 無効入力は無視して現在値に戻す
            self.page_indicator.setText(str(self.preview_current_page+1))

    # ===== 保存 =====
    def save_pdf(self):
        params = self.gather_params()
        if not params:
            return
        files = self.get_file_list()
        try:
            out = build_nup_from_multiple(files, params, stop_after_pages=None)
            # 保存ダイアログ
            folder = QFileDialog.getExistingDirectory(self, "保存先フォルダを選択")
            if not folder:
                return
            base_name = os.path.basename(folder.rstrip("/")) or "output"
            # 複数回保存対策
            for i in range(1000):
                file_name = os.path.join(folder, f"{base_name}_{i+1}.pdf")
                if not os.path.isfile(file_name):
                    break
            else:
                QMessageBox.warning(self, "保存エラー", "ファイルが保存できませんでした。")
                return
            out.save(file_name)
            QMessageBox.information(self, "完了", f"PDFを保存しました:\n{file_name}")
        except Exception as e:
            QMessageBox.warning(self, "保存エラー", f"PDFの保存中にエラーが発生しました:\n{e}")

if __name__ == "__main__":
    # 任意: Qt6 で DPI の丸め方を素直にする
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QGuiApplication
        if hasattr(QGuiApplication, "setHighDpiScaleFactorRoundingPolicy"):
            QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
                Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
            )
    except Exception:
        pass

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

