import os
import traceback
import threading
from tkinter import filedialog, messagebox, Entry, Label, Button, END, Listbox, SINGLE
from tkinterdnd2 import TkinterDnD, DND_FILES
from fpdf import FPDF
from PIL import Image

class PDFMakerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Image to PDF Converter")
        self.root.geometry("580x420")
        self.image_files = []

        # --- Title input ---
        Label(root, text="PDF Title (English only):").pack(pady=5)
        self.title_entry = Entry(root, width=40)
        self.title_entry.pack(pady=5)

        # --- Instructions ---
        Label(root, text="1. Drag and drop PNG images below, or click 'Select Image Files'\n"
                         "2. Use ↑ ↓ to reorder images\n"
                         "3. Enter a title, then click 'Create PDF'\n"
                         "4. Click 'Reset' to clear everything", fg="gray").pack()

        # --- Image list ---
        self.listbox = Listbox(root, width=60, height=8, selectmode=SINGLE)
        self.listbox.pack(pady=5)
        self.listbox.insert(END, "← Drop PNG images here")

        # --- Buttons ---
        btn_frame = Label(root)
        btn_frame.pack()
        Button(btn_frame, text="↑", command=self.move_up, width=4).grid(row=0, column=0, padx=2)
        Button(btn_frame, text="↓", command=self.move_down, width=4).grid(row=0, column=1, padx=2)
        Button(btn_frame, text="Select Image Files", command=self.select_files).grid(row=0, column=2, padx=10)
        self.create_button = Button(btn_frame, text="Create PDF", command=self.create_pdf_thread)
        self.create_button.grid(row=0, column=3, padx=10)
        Button(btn_frame, text="Reset", command=self.reset_all).grid(row=0, column=4, padx=10)

        # --- Status ---
        self.status_label = Label(root, text="", fg="green")
        self.status_label.pack(pady=5)

        # --- Drag and Drop ---
        self.listbox.drop_target_register(DND_FILES)
        self.listbox.dnd_bind('<<Drop>>', self.drop_files)

    # --- Image File Handling ---
    def select_files(self):
        files = filedialog.askopenfilenames(filetypes=[("PNG Images", "*.png")])
        if files:
            self.image_files = list(files)
            self.update_listbox()

    def drop_files(self, event):
        files = self.root.tk.splitlist(event.data)
        png_files = [f for f in files if f.lower().endswith('.png')]
        if png_files:
            self.image_files = list(png_files)
            self.update_listbox()

    def update_listbox(self):
        self.listbox.delete(0, END)
        for f in self.image_files:
            self.listbox.insert(END, os.path.basename(f))

    def move_up(self):
        idx = self.listbox.curselection()
        if idx and idx[0] > 0:
            i = idx[0]
            self.image_files[i - 1], self.image_files[i] = self.image_files[i], self.image_files[i - 1]
            self.update_listbox()
            self.listbox.selection_set(i - 1)

    def move_down(self):
        idx = self.listbox.curselection()
        if idx and idx[0] < len(self.image_files) - 1:
            i = idx[0]
            self.image_files[i + 1], self.image_files[i] = self.image_files[i], self.image_files[i + 1]
            self.update_listbox()
            self.listbox.selection_set(i + 1)

    # --- Reset function ---
    def reset_all(self):
        self.image_files = []
        self.title_entry.delete(0, END)
        self.listbox.delete(0, END)
        self.listbox.insert(END, "← Drop PNG images here")
        self.status_label.config(text="")

    # --- PDF Creation Thread ---
    def create_pdf_thread(self):
        thread = threading.Thread(target=self.make_pdf)
        thread.start()

    # --- PDF Creation Core ---
    def make_pdf(self):
        if not self.image_files:
            messagebox.showerror("Error", "Please select image files.")
            return
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showerror("Error", "Please enter a title.")
            return
        safe_title = "".join(c for c in title if c not in r'\/:*?"<>|')
        if not safe_title:
            messagebox.showerror("Error", "Title contains invalid characters.")
            return

        output_pdf = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")],
            initialfile=f"{safe_title}.pdf"
        )
        if not output_pdf:
            return

        self.status_label.config(text="Creating PDF...")
        self.create_button.config(state="disabled")
        self.root.update()

        try:
            A4_WIDTH = 297
            A4_HEIGHT = 210
            MARGIN = 10
            TITLE_HEIGHT = 15

            pdf = FPDF(orientation="L", unit="mm", format="A4")
            pdf.set_auto_page_break(False)

            for i in range(0, len(self.image_files), 4):
                pdf.add_page()
                pdf.set_font("Arial", "", 16)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(0, TITLE_HEIGHT, title, align="C", ln=1)

                subset = self.image_files[i:i+4]
                for j, image_path in enumerate(subset):
                    row = j // 2
                    col = j % 2
                    cell_width = (A4_WIDTH - 3 * MARGIN) / 2
                    cell_height = (A4_HEIGHT - TITLE_HEIGHT - 3 * MARGIN) / 2
                    x = MARGIN + col * (cell_width + MARGIN)
                    y = TITLE_HEIGHT + MARGIN + row * (cell_height + MARGIN)

                    img = Image.open(image_path)
                    img_width, img_height = img.size
                    aspect_ratio = img_width / img_height

                    if (cell_width / cell_height) > aspect_ratio:
                        h = cell_height
                        w = h * aspect_ratio
                    else:
                        w = cell_width
                        h = w / aspect_ratio

                    cx = x + (cell_width - w) / 2
                    cy = y + (cell_height - h) / 2

                    pdf.image(image_path, x=cx, y=cy, w=w, h=h)

                pdf.set_font("Arial", "", 12)
                pdf.set_text_color(100, 100, 100)
                page_num = (i // 4) + 1
                pdf.text(x=A4_WIDTH / 2 - 5, y=A4_HEIGHT - 5, txt=f"{page_num}")

            pdf.output(output_pdf)
            messagebox.showinfo("Done", f"PDF created:\n{output_pdf}")
        except Exception as e:
            tb = traceback.format_exc()
            messagebox.showerror("Error", f"Error during PDF creation:\n{e}\n\n{tb}")
        finally:
            self.status_label.config(text="")
            self.create_button.config(state="normal")

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = PDFMakerGUI(root)
    root.mainloop()