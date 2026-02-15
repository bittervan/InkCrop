#!/usr/bin/env python3
from __future__ import annotations

import os
import shlex
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QProcess, QTimer, Qt
from PySide6.QtGui import QPalette, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStyleFactory,
    QVBoxLayout,
    QWidget,
)


class InkCropWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("InkCrop GUI (PySide6)")
        self.resize(1040, 700)

        self.script_dir = Path(__file__).resolve().parent
        self.cache_dir = self._resolve_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.process: QProcess | None = None
        self.current_outputs: dict[str, Path] = {}
        self.running = False
        self.process_started_at: float | None = None
        self.last_output_at: float | None = None
        self.status_tick = 0
        self.next_heartbeat_at = 10
        self.progress_timer = QTimer(self)
        self.progress_timer.setInterval(1000)
        self.progress_timer.timeout.connect(self._on_progress_tick)

        self.input_edit = QLineEdit()
        self.cache_edit = QLineEdit(str(self.cache_dir))
        self.run_button = QPushButton("开始处理")
        self.clear_button = QPushButton("清空日志")
        self.status_label = QLabel("就绪")
        self.progress_bar = QProgressBar()
        self.log_output = QPlainTextEdit()

        self._build_ui()
        self._bind_events()

    def _resolve_cache_dir(self) -> Path:
        xdg_cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        return xdg_cache_home / "inkcrop"

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        input_row = QHBoxLayout()
        input_row.addWidget(QLabel("输入图片:"))
        self.input_edit.setPlaceholderText("选择要处理的图片…")
        input_row.addWidget(self.input_edit, 1)
        browse_input_btn = QPushButton("选择图片")
        browse_input_btn.clicked.connect(self._choose_input)
        input_row.addWidget(browse_input_btn)
        main_layout.addLayout(input_row)

        cache_row = QHBoxLayout()
        cache_row.addWidget(QLabel("缓存目录:"))
        self.cache_edit.setReadOnly(True)
        cache_row.addWidget(self.cache_edit, 1)
        main_layout.addLayout(cache_row)

        action_row = QHBoxLayout()
        action_row.addWidget(self.run_button)
        action_row.addWidget(self.clear_button)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        action_row.addWidget(self.progress_bar, 1)
        action_row.addWidget(self.status_label)
        main_layout.addLayout(action_row)

        main_layout.addWidget(QLabel("日志输出"))
        self.log_output.setReadOnly(True)
        self.log_output.setLineWrapMode(QPlainTextEdit.NoWrap)
        main_layout.addWidget(self.log_output, 1)

    def _bind_events(self):
        self.run_button.clicked.connect(self._run)
        self.clear_button.clicked.connect(self.log_output.clear)

    def _choose_input(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择输入图片",
            "",
            "Image Files (*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp);;All Files (*)",
        )
        if file_path:
            self.input_edit.setText(file_path)

    def _append_log_raw(self, text: str):
        if not text:
            return
        self.log_output.moveCursor(QTextCursor.End)
        self.log_output.insertPlainText(text)
        self.log_output.moveCursor(QTextCursor.End)

    def _append_log_line(self, text: str):
        line = text if text.endswith("\n") else text + "\n"
        self._append_log_raw(line)

    def _set_running(self, running: bool):
        self.running = running
        self.run_button.setEnabled(not running)
        if running:
            now = time.monotonic()
            self.process_started_at = now
            self.last_output_at = now
            self.status_tick = 0
            self.next_heartbeat_at = 10
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setVisible(True)
            self.progress_timer.start()
            self._refresh_running_status()
            return

        self.progress_timer.stop()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.process_started_at = None
        self.last_output_at = None
        self.status_tick = 0
        self.next_heartbeat_at = 10

    def _elapsed_seconds(self) -> int:
        if self.process_started_at is None:
            return 0
        return int(time.monotonic() - self.process_started_at)

    def _refresh_running_status(self):
        if not self.running:
            return
        elapsed = self._elapsed_seconds()
        dot_count = (self.status_tick % 3) + 1
        self.status_label.setText(f"处理中{'.' * dot_count} {elapsed}s")
        self.status_tick += 1

    def _on_progress_tick(self):
        if not self.running:
            return

        elapsed = self._elapsed_seconds()
        self._refresh_running_status()
        if elapsed < self.next_heartbeat_at:
            return

        since_output = 0
        if self.last_output_at is not None:
            since_output = int(time.monotonic() - self.last_output_at)
        self._append_log_line(
            f"[进度] 正在处理，已运行 {elapsed}s（最近输出 {since_output}s 前）"
        )
        while self.next_heartbeat_at <= elapsed:
            self.next_heartbeat_at += 10

    def _run(self):
        if self.running:
            return

        input_path = Path(self.input_edit.text().strip())
        if not input_path.exists():
            QMessageBox.critical(self, "错误", "输入图片不存在，请重新选择。")
            return

        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run_cache_dir = self.cache_dir / f"{input_path.stem}_{run_id}"
        run_cache_dir.mkdir(parents=True, exist_ok=True)

        suffix = input_path.suffix if input_path.suffix else ".jpg"
        stem = input_path.stem
        binary_out = run_cache_dir / f"{stem}_binary{suffix}"
        box_out = run_cache_dir / f"{stem}_crop_box{suffix}"
        pdf_out = run_cache_dir / f"{stem}_a4.pdf"

        self.current_outputs = {
            "cache_dir": run_cache_dir,
            "binary_out": binary_out,
            "box_out": box_out,
            "pdf_out": pdf_out,
        }

        args = [
            str(self.script_dir / "simple_binary.py"),
            str(input_path),
            str(binary_out),
            str(box_out),
            str(pdf_out),
        ]
        command_str = shlex.join([sys.executable, *args])
        self._append_log_line(f"缓存目录: {run_cache_dir}")
        self._append_log_line(f"$ {command_str}")

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._on_process_output)
        self.process.finished.connect(self._on_process_finished)
        self.process.errorOccurred.connect(self._on_process_error)
        self.process.start(sys.executable, args)

        self._set_running(True)

    def _on_process_output(self):
        if self.process is None:
            return
        raw = bytes(self.process.readAllStandardOutput())
        text = raw.decode("utf-8", errors="replace")
        if text:
            self.last_output_at = time.monotonic()
            self._append_log_raw(text)

    def _on_process_error(self, _):
        if self.process is None:
            return
        self.status_label.setText("进程异常")
        self._append_log_line(f"✗ 进程错误: {self.process.errorString()}")

    def _on_process_finished(self, exit_code: int, _):
        self._on_process_output()
        self._set_running(False)
        self.run_button.setEnabled(True)
        self.process = None

        if exit_code != 0:
            self.status_label.setText("失败")
            self._append_log_line(f"✗ 处理失败，退出码: {exit_code}")
            QMessageBox.critical(self, "处理失败", f"退出码: {exit_code}")
            return

        self.status_label.setText("完成")
        pdf_out = self.current_outputs["pdf_out"]

        self._append_log_line(f"✓ 完成：\n- {pdf_out}")
        self._cleanup_cache_intermediates()
        self._export_outputs()

    def _export_outputs(self):
        save_dir_str = QFileDialog.getExistingDirectory(self, "处理完成：选择结果保存目录")
        if not save_dir_str:
            self._append_log_line(
                f"未选择保存目录，结果保留在缓存: {self.current_outputs['cache_dir']}"
            )
            return

        try:
            save_dir = Path(save_dir_str)
            save_dir.mkdir(parents=True, exist_ok=True)
            src_path = self.current_outputs["pdf_out"]
            dst_path = save_dir / src_path.name
            shutil.copy2(src_path, dst_path)
            self._append_log_line("✓ 已导出：\n- " + str(dst_path))
            QMessageBox.information(self, "导出完成", f"已保存到:\n{save_dir}")
        except Exception as exc:
            self._append_log_line(f"✗ 导出失败: {exc}")
            QMessageBox.critical(self, "导出失败", str(exc))

    def _cleanup_cache_intermediates(self):
        for key in ("binary_out", "box_out"):
            path = self.current_outputs.get(key)
            if path is None:
                continue
            try:
                path.unlink(missing_ok=True)
            except Exception as exc:
                self._append_log_line(f"[提示] 清理缓存文件失败: {path} ({exc})")


def _detect_theme_mode(app: QApplication) -> str:
    scheme = app.styleHints().colorScheme()
    if scheme == Qt.ColorScheme.Dark:
        return "dark"
    if scheme == Qt.ColorScheme.Light:
        return "light"
    window_color = app.palette().color(QPalette.Window)
    return "dark" if window_color.lightness() < 128 else "light"


def _theme_stylesheet(mode: str) -> str:
    if mode == "dark":
        return """
        QWidget { font-size: 14px; color: #e5e7eb; }
        QMainWindow, QWidget { background: #0b1220; color: #e5e7eb; }
        QLabel { color: #e5e7eb; }
        QLineEdit, QPlainTextEdit {
            background: #111827;
            color: #f3f4f6;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 6px;
            selection-background-color: #2563eb;
            selection-color: #ffffff;
        }
        QPushButton {
            background: #3b82f6;
            color: #f8fafc;
            border: none;
            border-radius: 8px;
            padding: 8px 14px;
            font-weight: 600;
        }
        QPushButton:hover { background: #2563eb; }
        QPushButton:disabled { background: #475569; color: #cbd5e1; }
        QProgressBar {
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 6px;
            min-height: 12px;
        }
        QProgressBar::chunk {
            background: #3b82f6;
            border-radius: 6px;
        }
        """
    return """
        QWidget { font-size: 14px; color: #1f2937; }
        QMainWindow, QWidget { background: #f5f7fb; color: #1f2937; }
        QLabel { color: #111827; }
        QLineEdit, QPlainTextEdit {
            background: #ffffff;
            color: #111827;
            border: 1px solid #d4d9e2;
            border-radius: 8px;
            padding: 6px;
            selection-background-color: #2563eb;
            selection-color: #ffffff;
        }
        QPushButton {
            background: #2563eb;
            color: #ffffff;
            border: none;
            border-radius: 8px;
            padding: 8px 14px;
            font-weight: 600;
        }
        QPushButton:hover { background: #1d4ed8; }
        QPushButton:disabled { background: #93c5fd; color: #eff6ff; }
        QProgressBar {
            background: #eef2ff;
            border: 1px solid #d4d9e2;
            border-radius: 6px;
            min-height: 12px;
        }
        QProgressBar::chunk {
            background: #2563eb;
            border-radius: 6px;
        }
        """


def apply_app_style(app: QApplication):
    app.setStyle(QStyleFactory.create("Fusion"))
    mode = _detect_theme_mode(app)
    app.setStyleSheet(_theme_stylesheet(mode))


def main():
    app = QApplication(sys.argv)
    apply_app_style(app)
    app.styleHints().colorSchemeChanged.connect(lambda _: apply_app_style(app))
    window = InkCropWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
