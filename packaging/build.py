#!/usr/bin/env python3
from __future__ import annotations

import argparse
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"
RELEASE_DIR = ROOT_DIR / "release"
APP_NAME = "InkCrop"

COLLECT_ALL_PACKAGES = [
    "PySide6",
    "cv2",
    "numpy",
    "PIL",
    "reportlab",
    "skimage",
]


def run_command(cmd: list[str]) -> None:
    print(f"$ {shlex.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT_DIR, check=True)


def build_pyinstaller(onefile: bool) -> None:
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        "--hidden-import",
        "simple_binary",
    ]
    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    for package_name in COLLECT_ALL_PACKAGES:
        cmd.extend(["--collect-all", package_name])

    cmd.append("inkcrop_gui.py")
    run_command(cmd)


def resolve_dist_artifact(onefile: bool) -> Path:
    system_name = platform.system()
    if onefile:
        if system_name == "Windows":
            return DIST_DIR / f"{APP_NAME}.exe"
        return DIST_DIR / APP_NAME

    if system_name == "Darwin":
        return DIST_DIR / f"{APP_NAME}.app"
    return DIST_DIR / APP_NAME


def archive_artifact(artifact: Path) -> Path:
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    system_name = platform.system().lower()
    machine = platform.machine().lower()
    archive_base = RELEASE_DIR / f"{APP_NAME}-{system_name}-{machine}"

    if artifact.is_dir():
        archive_path = shutil.make_archive(
            str(archive_base),
            "zip",
            root_dir=artifact.parent,
            base_dir=artifact.name,
        )
        return Path(archive_path)

    staged_file = RELEASE_DIR / artifact.name
    shutil.copy2(artifact, staged_file)
    try:
        archive_path = shutil.make_archive(
            str(archive_base),
            "zip",
            root_dir=RELEASE_DIR,
            base_dir=staged_file.name,
        )
        return Path(archive_path)
    finally:
        staged_file.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build standalone InkCrop app with PyInstaller.")
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Build as a single-file executable (default mode).",
    )
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="Build as a directory bundle (faster startup, larger package).",
    )
    parser.add_argument(
        "--skip-clean",
        action="store_true",
        help="Do not remove existing build/dist folders before building.",
    )
    args = parser.parse_args()

    if args.onefile and args.onedir:
        parser.error("--onefile 和 --onedir 不能同时使用")

    onefile = True
    if args.onedir:
        onefile = False
    if args.onefile:
        onefile = True

    if not args.skip_clean:
        shutil.rmtree(BUILD_DIR, ignore_errors=True)
        shutil.rmtree(DIST_DIR, ignore_errors=True)

    build_pyinstaller(onefile=onefile)
    artifact = resolve_dist_artifact(onefile=onefile)
    if not artifact.exists():
        print(f"错误：未找到构建产物 {artifact}")
        return 1

    archive_path = archive_artifact(artifact)
    print(f"\n✓ 构建完成: {artifact}")
    print(f"✓ 分发包: {archive_path}")
    print("提示：请在目标系统上测试双击启动是否正常。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
