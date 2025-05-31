import os
import sys
import traceback
import datetime
import time

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt

from fpdf import FPDF
from PIL import Image

# 用紙サイズの定義（mm単位、横向き）
PAPER_SIZES = {
    "A4": (297, 210),
    "B4": (364, 257),
    "A3": (420, 297),
    "B5": (250, 176),
    "A5": (210, 148),
}


class ImageListWidget(QtWidgets.QListWidget):
    """
    QListWidget を継承し、外部からのファイルドラッグ＆ドロップを受け取るためのクラス。
    ファイルがドロップされると、files_dropped シグナルが発行される。
    """
    files_dropped = QtCore.pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.setDropIndicatorShown(True)

    def dragEnterEvent(self, event):
        # 外部からの URL（ファイルパス）を受け入れる
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        # 外部からのファイルドロップを検知
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            files = [url.toLocalFile() for url in urls]
            image_exts = ('.png', '.jpg', '.jpeg', '.bmp')
            image_files = [f for f in files if f.lower().endswith(image_exts)]
            if image_files:
                # ドロップされた画像ファイルのリストをシグナルで通知
                self.files_dropped.emit(image_files)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class PDFMakerGUI(QtWidgets.QMainWindow):
    """
    メインのウィンドウクラス。PyQt5 を使って Tkinter 版と同等の機能を実装している。
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image to PDF Converter")
        self.setGeometry(100, 100, 1200, 900)

        self.image_files = []  # 現在選択されている画像ファイルパスのリスト

        # --- ウィジェットの配置 ---
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QVBoxLayout(central_widget)

        # PDF タイトル入力欄
        title_layout = QtWidgets.QHBoxLayout()
        title_label = QtWidgets.QLabel("PDF Title (English only):")
        self.title_edit = QtWidgets.QLineEdit()
        title_layout.addWidget(title_label)
        title_layout.addWidget(self.title_edit)
        main_layout.addLayout(title_layout)

        # 用紙サイズ選択
        size_layout = QtWidgets.QHBoxLayout()
        size_label = QtWidgets.QLabel("Paper Size:")
        self.paper_size_combo = QtWidgets.QComboBox()
        self.paper_size_combo.addItems(PAPER_SIZES.keys())
        size_layout.addWidget(size_label)
        size_layout.addWidget(self.paper_size_combo)
        size_layout.addStretch()
        main_layout.addLayout(size_layout)

        # 操作手順のラベル
        instructions = QtWidgets.QLabel(
            "1. Drag and drop images below, or click 'Select Image Files'\n"
            "2. Use ↑ ↓ or drag to reorder images\n"
            "3. Enter a title, select paper size, then click 'Create PDF'\n"
            "4. Click 'Reset' to clear everything"
        )
        instructions.setStyleSheet("color: gray;")
        main_layout.addWidget(instructions)

        # メイン部分：リストとサムネイルを左右に配置
        frame_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(frame_layout)

        # 左側レイアウト：画像リスト、ボタン、ステータス
        left_layout = QtWidgets.QVBoxLayout()
        frame_layout.addLayout(left_layout, 2)

        # ImageListWidget を使ってドラッグ＆ドロップ対応の QListWidget を作成
        self.list_widget = ImageListWidget()
        self.list_widget.addItem("← Drop images here")
        # 外部ドロップ時のシグナル接続
        self.list_widget.files_dropped.connect(self.drop_files)
        # 選択アイテム変更時にサムネイルを更新
        self.list_widget.itemSelectionChanged.connect(self.show_thumbnail)
        left_layout.addWidget(self.list_widget)

        # ボタン群
        btn_layout = QtWidgets.QHBoxLayout()
        self.up_button = QtWidgets.QPushButton("↑")
        self.down_button = QtWidgets.QPushButton("↓")
        self.select_button = QtWidgets.QPushButton("Select Image Files")
        self.create_button = QtWidgets.QPushButton("Create PDF")
        self.reset_button = QtWidgets.QPushButton("Reset")
        btn_layout.addWidget(self.up_button)
        btn_layout.addWidget(self.down_button)
        btn_layout.addWidget(self.select_button)
        btn_layout.addWidget(self.create_button)
        btn_layout.addWidget(self.reset_button)
        left_layout.addLayout(btn_layout)

        # ステータス表示用ラベル
        self.status_label = QtWidgets.QLabel("")
        left_layout.addWidget(self.status_label)

        # 右側レイアウト：サムネイル表示用 QLabel
        self.thumb_label = QtWidgets.QLabel("サムネイル")
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setFrameStyle(QtWidgets.QFrame.StyledPanel | QtWidgets.QFrame.Sunken)
        frame_layout.addWidget(self.thumb_label, 3)

        # ボタンのクリックイベントをそれぞれのメソッドに接続
        self.select_button.clicked.connect(self.select_files)
        self.up_button.clicked.connect(self.move_up)
        self.down_button.clicked.connect(self.move_down)
        self.reset_button.clicked.connect(self.reset_all)
        self.create_button.clicked.connect(self.make_pdf)

    def select_files(self):
        """
        『Select Image Files』ボタンが押されたとき。
        QFileDialog を使って複数画像ファイルを選択し、image_files に格納、リストを更新する。
        """
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Select Image Files",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        if files:
            self.image_files = files
            self.update_list_widget()

    def drop_files(self, files):
        """
        リストに外部から画像ファイルがドロップされたときに呼ばれるメソッド。
        受け取ったファイルリストで image_files を置き換え、リストを更新する。
        """
        self.image_files = files
        self.update_list_widget()

    def update_list_widget(self):
        """
        QListWidget の内容を、現在の image_files リストに合わせて更新する。
        アイテムのテキストはファイル名、データにフルパスを保管する。
        """
        self.list_widget.clear()
        for f in self.image_files:
            item = QtWidgets.QListWidgetItem(os.path.basename(f))
            item.setData(Qt.UserRole, f)
            self.list_widget.addItem(item)
        # サムネイルもリセット
        self.thumb_label.setPixmap(QtGui.QPixmap())
        self.thumb_label.setText("サムネイル")

    def move_up(self):
        """
        選択中のアイテムを 1 つ上に移動する。
        image_files リスト内でも同じ位置を入れ替え、リストを再表示する。
        """
        row = self.list_widget.currentRow()
        if row > 0:
            self.image_files[row - 1], self.image_files[row] = self.image_files[row], self.image_files[row - 1]
            self.update_list_widget()
            self.list_widget.setCurrentRow(row - 1)
            self.show_thumbnail()

    def move_down(self):
        """
        選択中のアイテムを 1 つ下に移動する。
        image_files リスト内でも同じ位置を入れ替え、リストを再表示する。
        """
        row = self.list_widget.currentRow()
        if 0 <= row < len(self.image_files) - 1:
            self.image_files[row + 1], self.image_files[row] = self.image_files[row], self.image_files[row + 1]
            self.update_list_widget()
            self.list_widget.setCurrentRow(row + 1)
            self.show_thumbnail()

    def show_thumbnail(self):
        """
        QListWidget で選択されたアイテムに対応する画像を、thumb_label にサムネイル表示する。
        """
        items = self.list_widget.selectedItems()
        if not items:
            self.thumb_label.setPixmap(QtGui.QPixmap())
            self.thumb_label.setText("サムネイル")
            return

        item = items[0]
        img_path = item.data(Qt.UserRole)
        if not img_path:
            return

        try:
            pixmap = QtGui.QPixmap(img_path)
            if pixmap.isNull():
                raise Exception("Could not load image")
            # 最大 1000×800 の領域に収まるようにアスペクト比を保って縮小
            scaled = pixmap.scaled(1000, 800, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.thumb_label.setPixmap(scaled)
            self.thumb_label.setText("")
        except Exception as img_err:
            print("Thumbnail display error:", img_err)
            traceback.print_exc()
            self.thumb_label.setPixmap(QtGui.QPixmap())
            self.thumb_label.setText("画像を表示できません")

    def reset_all(self):
        """
        『Reset』ボタンが押されたとき。
        すべての入力とリスト、ステータス、サムネイルを初期状態に戻す。
        """
        self.image_files = []
        self.title_edit.clear()
        self.list_widget.clear()
        self.list_widget.addItem("← Drop images here")
        self.status_label.setText("")
        self.thumb_label.setPixmap(QtGui.QPixmap())
        self.thumb_label.setText("サムネイル")

    def make_pdf(self):
        """
        『Create PDF』ボタンが押されたとき。
        画像リストとタイトル、用紙サイズをもとに FPDF で PDF を生成する。
        エラー発生時にはデスクトップにログを残し、メッセージボックスで通知する。
        """
        # 画像が選択されていない場合はエラー
        if not self.image_files:
            QtWidgets.QMessageBox.critical(self, "Error", "Please select image files.")
            return

        title = self.title_edit.text().strip()
        if not title:
            QtWidgets.QMessageBox.critical(self, "Error", "Please enter a title.")
            return

        # ファイル名にできない文字を除去
        safe_title = "".join(c for c in title if c not in r'\/:*?"<>|')
        if not safe_title:
            QtWidgets.QMessageBox.critical(self, "Error", "Title contains invalid characters.")
            return

        # 保存先をユーザーに選ばせる
        options = QtWidgets.QFileDialog.Options()
        output_pdf, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save PDF",
            f"{safe_title}.pdf",
            "PDF Files (*.pdf)",
            options=options
        )
        if not output_pdf:
            return

        self.status_label.setText("Creating PDF...")
        self.create_button.setEnabled(False)
        QtWidgets.QApplication.processEvents()

        try:
            paper_name = self.paper_size_combo.currentText()
            if paper_name not in PAPER_SIZES:
                QtWidgets.QMessageBox.critical(self, "Error", "Invalid paper size.")
                return

            PAGE_WIDTH, PAGE_HEIGHT = PAPER_SIZES[paper_name]
            MARGIN = 10
            TITLE_HEIGHT = 15

            pdf = FPDF(orientation="L", unit="mm", format=paper_name)
            pdf.set_auto_page_break(False)

            # 4 画像ずつ 1 ページにレイアウト
            for page_start in range(0, len(self.image_files), 4):
                pdf.add_page()
                pdf.set_font("helvetica", "", 16)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(0, TITLE_HEIGHT, title, align="C", ln=1)

                grid_cols = 2
                grid_rows = 2
                cell_width = (PAGE_WIDTH - (grid_cols + 1) * MARGIN) / grid_cols
                cell_height = (PAGE_HEIGHT - TITLE_HEIGHT - (grid_rows + 1) * MARGIN) / grid_rows

                for idx_in_page, image_idx in enumerate(range(page_start, min(page_start + 4, len(self.image_files)))):
                    row = idx_in_page // 2
                    col = idx_in_page % 2
                    x = MARGIN + col * (cell_width + MARGIN)
                    y = TITLE_HEIGHT + MARGIN + row * (cell_height + MARGIN)

                    img_path = os.path.abspath(self.image_files[image_idx])
                    img = Image.open(img_path)
                    img_width, img_height = img.size
                    aspect_ratio = img_width / img_height

                    # セルに最大限収まるサイズを計算
                    if (cell_width / cell_height) > aspect_ratio:
                        h = cell_height
                        w = h * aspect_ratio
                    else:
                        w = cell_width
                        h = w / aspect_ratio

                    cx = x + (cell_width - w) / 2
                    cy = y + (cell_height - h) / 2

                    pdf.image(img_path, x=cx, y=cy, w=w, h=h)

                pdf.set_font("helvetica", "", 12)
                pdf.set_text_color(100, 100, 100)
                page_num = (page_start // 4) + 1
                pdf.text(x=PAGE_WIDTH / 2 - 5, y=PAGE_HEIGHT - 5, txt=f"{page_num}")

            pdf.output(output_pdf)
            QtWidgets.QMessageBox.information(self, "Done", f"PDF created:\n{output_pdf}")

        except Exception as e:
            # エラー情報をコンソールに表示
            print("Error during PDF creation:", e)
            traceback.print_exc()

            # デスクトップ上にログフォルダを作成し、詳細を保存
            desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
            log_dir = os.path.join(desktop_dir, "ImageToPDF_logs")
            os.makedirs(log_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            log_path = os.path.join(log_dir, f"error_{timestamp}.log")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())

            QtWidgets.QMessageBox.critical(self, "Error", f"PDF creation failed.\nLog saved at:\n{log_path}")

        finally:
            self.status_label.setText("")
            self.create_button.setEnabled(True)


def load_pixmap(path):
    """
    指定パスから QPixmap をロードする。存在しないか読み込めなかった場合は None を返す。
    """
    if os.path.exists(path):
        pixmap = QtGui.QPixmap(path)
        if not pixmap.isNull():
            return pixmap
    return None


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    try:
        # PyInstaller でバンドルされた場合の画像読み込み用パスを取得
        base_dir = getattr(sys, "_MEIPASS", os.path.dirname(__file__))

        # スプラッシュスクリーンを作成
        splash_img_path = os.path.join(base_dir, "mochimaker.png")
        pixmap = load_pixmap(splash_img_path)
        if pixmap:
            splash = QtWidgets.QSplashScreen(pixmap)
        else:
            splash = QtWidgets.QSplashScreen(QtGui.QPixmap())
            splash.showMessage("MochiMaker", Qt.AlignCenter | Qt.AlignBottom, Qt.white)
        splash.show()
        QtWidgets.qApp.processEvents()
        time.sleep(1.5)
        splash.close()

        # メインウィンドウを生成・表示
        window = PDFMakerGUI()

        # アプリケーションアイコンの設定
        icon = load_pixmap(os.path.join(base_dir, "mochimaker.png"))
        if icon:
            window.setWindowIcon(QtGui.QIcon(icon))
        else:
            ico_path = os.path.join(base_dir, "mochimaker_icon.ico")
            if os.path.exists(ico_path):
                window.setWindowIcon(QtGui.QIcon(ico_path))

        window.show()
        sys.exit(app.exec_())

    except Exception:
        # 起動時に致命的なエラーが出た場合は fatal_error.log に書き出す
        print("Fatal error at startup:")
        traceback.print_exc()
        with open("fatal_error.log", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        sys.exit(1)
