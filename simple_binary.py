#!/usr/bin/env python3
"""
简单二值化脚本（单图）
输入：一张图片（白纸黑字）
输出：
1) 二值化图（墨迹=白色，背景=黑色）
2) 边界预览图（在原图上画出后续裁切边界）
"""
import sys
from pathlib import Path

import cv2
import numpy as np


def main():
    if len(sys.argv) < 2:
        print("用法: python simple_binary.py <输入图片> [二值图输出] [边界预览图输出]")
        print("示例: python simple_binary.py input.jpg outputs/input_binary.jpg outputs/input_crop_box.jpg")
        sys.exit(1)

    input_path = sys.argv[1]
    input_file = Path(input_path)
    script_dir = Path(__file__).parent
    outputs_dir = script_dir / "outputs"
    outputs_dir.mkdir(exist_ok=True)

    # 二值图输出路径
    if len(sys.argv) >= 3:
        binary_output_path = Path(sys.argv[2])
    else:
        binary_output_path = outputs_dir / f"{input_file.stem}_binary{input_file.suffix}"

    # 边界预览图输出路径
    if len(sys.argv) >= 4:
        boxed_output_path = Path(sys.argv[3])
    else:
        boxed_output_path = outputs_dir / f"{input_file.stem}_crop_box{input_file.suffix}"

    binary_output_path.parent.mkdir(parents=True, exist_ok=True)
    boxed_output_path.parent.mkdir(parents=True, exist_ok=True)

    # 读取图片
    image = cv2.imread(input_path)
    if image is None:
        print(f"错误：无法读取图片: {input_path}")
        sys.exit(1)

    print(f"已加载图片: {image.shape}")

    # 转灰度图
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # 高斯模糊
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Otsu 二值化（自动计算最佳阈值）
    _, binary_inv = cv2.threshold(
        blurred,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    # THRESH_BINARY_INV 的目标是让墨迹尽量变成白色（255）
    # 但对反色输入时可能颠倒，所以后面做一次面积判断纠正

    # 计算两种颜色的面积
    white_area = np.sum(binary_inv == 255)  # 255的像素数
    black_area = np.sum(binary_inv == 0)  # 0的像素数

    print(f"白色像素数: {white_area} ({white_area/(binary_inv.shape[0]*binary_inv.shape[1])*100:.2f}%)")
    print(f"黑色像素数: {black_area} ({black_area/(binary_inv.shape[0]*binary_inv.shape[1])*100:.2f}%)")

    # 目标固定为：白色=墨迹，黑色=背景
    # 墨迹面积通常小于背景面积，因此白色面积较小时视为正确
    if white_area <= black_area:
        binary = binary_inv
        mode = "白色=墨迹（无需反转）"
    else:
        binary = cv2.bitwise_not(binary_inv)
        mode = "白色占比过大，已反转以保持白色=墨迹"

    # 形态学操作清理噪点
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    # 计算墨迹外接矩形（后续裁切边界）
    points = cv2.findNonZero(binary)
    boxed = image.copy()
    bbox = None
    if points is not None:
        x, y, w, h = cv2.boundingRect(points)
        bbox = (x, y, w, h)
        cv2.rectangle(boxed, (x, y), (x + w - 1, y + h - 1), (0, 0, 255), 2)

    # 保存结果
    cv2.imwrite(str(binary_output_path), binary)
    cv2.imwrite(str(boxed_output_path), boxed)

    print(f"\n✓ 已保存二值化图到: {binary_output_path}")
    print(f"✓ 已保存边界预览图到: {boxed_output_path}")
    print(f"  输入图片: {input_path}")
    print(f"  图片大小: {image.shape}")
    print(f"  二值图大小: {binary.shape}")
    if bbox is None:
        print("  裁切边界: 未检测到墨迹（整图为空）")
    else:
        x, y, w, h = bbox
        print(f"  裁切边界: x={x}, y={y}, w={w}, h={h}")
    print(f"\n说明:")
    print(f"  - 白色区域 = 墨迹")
    print(f"  - 黑色区域 = 背景（纸张）")
    print(f"  - 模式: {mode}")
    print(f"  - 使用 Otsu 自动阈值 + 面积判断 + 外接矩形")


if __name__ == "__main__":
    main()
