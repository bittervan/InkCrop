#!/usr/bin/env python3
from __future__ import annotations

import queue
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import END, LEFT, RIGHT, TOP, BOTH, X, Y, filedialog, messagebox, ttk
import tkinter as tk

from PIL import Image, ImageTk


class InkCropGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("InkCrop GUI")
        self.root.geometry("1200x760")

        self.script_dir = Path(__file__).resolve().parent
        self.worker_queue: queue.Queue = queue.Queue()
        self.running = False
        self.binary_preview_img = None
        self.box_preview_img = None

        self.input_var = tk.StringVar()
        self.output_dir_var = tk.StringVar(value=str(self.script_dir / "outputs"))

        self._build_ui()
        self.root.after(100, self._poll_queue)

    def _build_ui(self):
        frm_top = ttk.Frame(self.root, padding=10)
        frm_top.pack(side=TOP, fill=X)

        ttk.Label(frm_top, text="输入图片:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm_top, textvariable=self.input_var, width=90).grid(
            row=0, column=1, sticky="we", padx=8
        )
        ttk.Button(frm_top, text="选择图片", command=self._choose_input).grid(row=0, column=2)

        ttk.Label(frm_top, text="输出目录:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frm_top, textvariable=self.output_dir_var, width=90).grid(
            row=1, column=1, sticky="we", padx=8, pady=(8, 0)
        )
        ttk.Button(frm_top, text="选择目录", command=self._choose_output_dir).grid(
            row=1, column=2, pady=(8, 0)
        )

        frm_top.columnconfigure(1, weight=1)

        frm_actions = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        frm_actions.pack(side=TOP, fill=X)

        self.run_btn = ttk.Button(frm_actions, text="开始处理", command=self._run)
        self.run_btn.pack(side=LEFT)
        ttk.Button(frm_actions, text="清空日志", command=self._clear_log).pack(side=LEFT, padx=(8, 0))

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(frm_actions, textvariable=self.status_var).pack(side=RIGHT)

        frm_main = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        frm_main.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        frm_left = ttk.Frame(frm_main)
        frm_right = ttk.Frame(frm_main)
        frm_main.add(frm_left, weight=3)
        frm_main.add(frm_right, weight=2)

        ttk.Label(frm_left, text="日志输出").pack(anchor="w")
        self.log_text = tk.Text(frm_left, height=20, wrap="word")
        self.log_text.pack(fill=BOTH, expand=True)

        frm_previews = ttk.Frame(frm_right)
        frm_previews.pack(fill=BOTH, expand=True)

        ttk.Label(frm_previews, text="二值图预览").pack(anchor="w")
        self.binary_preview = ttk.Label(frm_previews)
        self.binary_preview.pack(fill=BOTH, expand=True, pady=(4, 10))

        ttk.Label(frm_previews, text="框选图预览").pack(anchor="w")
        self.box_preview = ttk.Label(frm_previews)
        self.box_preview.pack(fill=BOTH, expand=True, pady=(4, 0))

    def _choose_input(self):
        path = filedialog.askopenfilename(
            title="选择输入图片",
            filetypes=[
                ("Image Files", "*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp"),
                ("All Files", "*.*"),
            ],
        )
        if path:
            self.input_var.set(path)

    def _choose_output_dir(self):
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.output_dir_var.set(path)

    def _clear_log(self):
        self.log_text.delete("1.0", END)

    def _append_log(self, message: str):
        self.log_text.insert(END, message)
        if not message.endswith("\n"):
            self.log_text.insert(END, "\n")
        self.log_text.see(END)

    def _run(self):
        if self.running:
            return

        input_path = Path(self.input_var.get().strip())
        if not input_path.exists():
            messagebox.showerror("错误", "输入图片不存在，请重新选择。")
            return

        output_dir = Path(self.output_dir_var.get().strip() or (self.script_dir / "outputs"))
        output_dir.mkdir(parents=True, exist_ok=True)

        suffix = input_path.suffix if input_path.suffix else ".jpg"
        stem = input_path.stem
        binary_out = output_dir / f"{stem}_binary{suffix}"
        box_out = output_dir / f"{stem}_crop_box{suffix}"
        pdf_out = output_dir / f"{stem}_a4.pdf"

        cmd = [
            sys.executable,
            str(self.script_dir / "simple_binary.py"),
            str(input_path),
            str(binary_out),
            str(box_out),
            str(pdf_out),
        ]

        self.running = True
        self.run_btn.state(["disabled"])
        self.status_var.set("处理中...")
        self._append_log(f"$ {' '.join(cmd)}")

        thread = threading.Thread(
            target=self._worker_run, args=(cmd, binary_out, box_out, pdf_out), daemon=True
        )
        thread.start()

    def _worker_run(self, cmd, binary_out: Path, box_out: Path, pdf_out: Path):
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert process.stdout is not None
            for line in process.stdout:
                self.worker_queue.put(("log", line))
            returncode = process.wait()
            self.worker_queue.put(
                (
                    "done",
                    {
                        "returncode": returncode,
                        "binary_out": binary_out,
                        "box_out": box_out,
                        "pdf_out": pdf_out,
                    },
                )
            )
        except Exception as exc:
            self.worker_queue.put(("error", str(exc)))

    def _load_preview(self, img_path: Path, target_label: ttk.Label, kind: str):
        if not img_path.exists():
            return

        img = Image.open(img_path)
        img.thumbnail((460, 320))
        tk_img = ImageTk.PhotoImage(img)
        target_label.configure(image=tk_img)
        if kind == "binary":
            self.binary_preview_img = tk_img
        else:
            self.box_preview_img = tk_img

    def _poll_queue(self):
        while True:
            try:
                item = self.worker_queue.get_nowait()
            except queue.Empty:
                break

            event_type = item[0]
            if event_type == "log":
                self._append_log(item[1])
            elif event_type == "error":
                self.running = False
                self.run_btn.state(["!disabled"])
                self.status_var.set("失败")
                messagebox.showerror("运行失败", item[1])
            elif event_type == "done":
                self.running = False
                self.run_btn.state(["!disabled"])
                result = item[1]
                if result["returncode"] == 0:
                    self.status_var.set("完成")
                    self._load_preview(result["binary_out"], self.binary_preview, "binary")
                    self._load_preview(result["box_out"], self.box_preview, "box")
                    self._append_log(
                        f"✓ 完成：\n- {result['binary_out']}\n- {result['box_out']}\n- {result['pdf_out']}\n"
                    )
                else:
                    self.status_var.set("失败")
                    self._append_log(f"✗ 处理失败，退出码: {result['returncode']}")
                    messagebox.showerror("处理失败", f"退出码: {result['returncode']}")

        self.root.after(100, self._poll_queue)


def main():
    root = tk.Tk()
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    InkCropGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
