# MochiMaker(試験持ち込み資料作成ソフト)

このアプリは、PNG画像をドラッグ＆ドロップまたは選択して、**A4横向きのPDF**に**1ページあたり4枚（2行×2列）**ずつ自動で配置し、ページ番号とタイトルを付けて出力するPythonアプリケーションです。

---

## 主な機能

- PNG画像をドラッグ＆ドロップまたは選択して一括読み込み
- **A4横向き1ページに4枚ずつ**（2行×2列）画像を自動配置
- ページ番号、任意のPDFタイトルを自動追加
- 画像の順番を**↑ / ↓ボタンで並び替え可能**
- 出力PDFの**保存先とファイル名を指定可能**
- 「Reset」ボタンで画像・タイトル・表示を初期状態にリセット
- **複数のPDFを1つに結合する**マージ機能も搭載

---

## 必要環境

- Python 3.8 以上
- 以下のPythonライブラリが必要です：

```bash
pip install pillow fpdf tkinterdnd2 PyPDF2
```
---

## 操作手順

- PNG画像をドラッグ＆ドロップまたは「Select Image Files」で読み込み
- 必要に応じて**↑ / ↓で順番を並び替え**
- PDFタイトルを入力
- 「Create PDF」をクリックし、保存先を指定
- 「Reset」で初期化

---

##  補足

- 現在対応している画像形式は **PNG** のみです。
- PDF内フォントは Arial（英語のみ）を使用しています。
- 出力PDFは **A4サイズ横向き** に自動レイアウトされます。
