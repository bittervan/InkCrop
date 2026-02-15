#!/usr/bin/env python3
"""
简单二值化脚本 - 根据面积判断墨迹和背景
输入：一张图片（白纸黑字）
输出：一张二值化图（墨迹=白色，背景=黑色）
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from skimage.segmentation import clear_border

BORDER_CLEAN_MAX_SIDE = 2400
BORDER_BAND_RATIO = 0.03
BORDER_BAND_MIN = 24


def remove_border_connected_ink(binary):
    total_pixels = binary.size
    white_pixels = int(cv2.countNonZero(binary))
    black_pixels = int(total_pixels - white_pixels)

    # 墨迹默认取面积较小的一类像素，兼容白墨迹或黑墨迹两种输出
    ink_is_white = white_pixels <= black_pixels
    ink_mask = (binary == 255) if ink_is_white else (binary == 0)

    # 在降采样图上做边缘连通检测，速度更快
    h, w = ink_mask.shape
    long_side = max(h, w)
    if long_side > BORDER_CLEAN_MAX_SIDE:
        scale = BORDER_CLEAN_MAX_SIDE / float(long_side)
        small_w = max(1, int(round(w * scale)))
        small_h = max(1, int(round(h * scale)))
        ink_small = cv2.resize(
            ink_mask.astype(np.uint8),
            (small_w, small_h),
            interpolation=cv2.INTER_NEAREST
        ).astype(bool)
    else:
        scale = 1.0
        small_h, small_w = h, w
        ink_small = ink_mask

    # 找到与图像边界连通的墨迹像素
    inside_small = clear_border(ink_small, buffer_size=0)
    border_connected_small = ink_small & (~inside_small)

    # 只移除边缘带里的边缘连通墨迹
    border_band_small = max(BORDER_BAND_MIN, int(round(min(small_h, small_w) * BORDER_BAND_RATIO)))
    edge_band_small = np.zeros_like(ink_small, dtype=bool)
    edge_band_small[:border_band_small, :] = True
    edge_band_small[small_h - border_band_small:, :] = True
    edge_band_small[:, :border_band_small] = True
    edge_band_small[:, small_w - border_band_small:] = True

    remove_small = border_connected_small & edge_band_small

    # 轻微膨胀，防止保留边缘脏带的细碎残留
    remove_small_u8 = cv2.dilate(
        remove_small.astype(np.uint8) * 255,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
        iterations=1
    )
    remove_small = remove_small_u8 > 0

    # 回投到原图尺寸再删除
    if scale != 1.0:
        remove_mask = cv2.resize(
            remove_small.astype(np.uint8),
            (w, h),
            interpolation=cv2.INTER_NEAREST
        ).astype(bool)
    else:
        remove_mask = remove_small

    remove_mask &= ink_mask
    ink_mask_clean = ink_mask & (~remove_mask)
    removed_pixels = int(np.count_nonzero(remove_mask))
    border_band = int(round(border_band_small / scale))

    if ink_is_white:
        cleaned_binary = np.where(ink_mask_clean, 255, 0).astype(np.uint8)
    else:
        cleaned_binary = np.where(ink_mask_clean, 0, 255).astype(np.uint8)

    return cleaned_binary, removed_pixels, border_band


def main():
    if len(sys.argv) < 2:
        print("用法: python simple_binary.py <输入图片> [输出图片]")
        print("示例: python simple_binary.py input.jpg output.jpg")
        sys.exit(1)

    input_path = sys.argv[1]

    # 默认输出到 outputs 目录（相对于项目根目录）
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        input_file = Path(input_path)
        # outputs 目录在项目根目录（simple_binary.py 在根目录）
        script_dir = Path(__file__).parent
        outputs_dir = script_dir / "outputs"
        outputs_dir.mkdir(exist_ok=True)
        output_path = outputs_dir / f"{input_file.stem}_binary{input_file.suffix}"

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

    # 此时 binary_inv 中：
    # - 原图的白色区域 = 255（背景）
    # - 原图的黑色区域 = 0（墨迹）
    # THRESH_BINARY_INV 反转后：
    # - 白色区域 = 0（原来的背景）
    # - 黑色区域 = 255（原来的墨迹）

    # 计算两种颜色的面积
    white_area = np.sum(binary_inv == 255)  # 255的像素数
    black_area = np.sum(binary_inv == 0)     # 0的像素数

    print(f"白色像素数: {white_area} ({white_area/(binary_inv.shape[0]*binary_inv.shape[1])*100:.2f}%)")
    print(f"黑色像素数: {black_area} ({black_area/(binary_inv.shape[0]*binary_inv.shape[1])*100:.2f}%)")

    # 判断：面积大的才是背景（纸张），面积小的是墨迹
    # 因为输入都是"白纸黑字"，所以：
    # - 白色面积大 → 白色是背景 → 墨迹是黑色 → 不需要反转
    # - 白色面积小 → 白色是墨迹 → 墨迹是白色 → 需要反转
    if white_area > black_area:
        # 白色面积更大，白色是背景，墨迹是黑色，已经是我们要的
        binary = binary_inv
        mode = "白底黑字（无需反转）"
    else:
        # 白色面积更小，白色是墨迹，需要反转成黑底白字
        binary = cv2.bitwise_not(binary_inv)
        mode = "黑底白字（已反转）"

    # 形态学操作清理噪点
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    # 去掉与边缘连通的深色噪声，同时尽量保留真实笔画
    binary, removed_pixels, border_band = remove_border_connected_ink(binary)

    # 保存二值化图
    cv2.imwrite(str(output_path), binary)

    print(f"\n✓ 已保存二值化图到: {output_path}")
    print(f"  输入图片: {input_path}")
    print(f"  图片大小: {image.shape}")
    print(f"  二值图大小: {binary.shape}")
    print(f"\n说明:")
    print(f"  - 白色区域 = 墨迹")
    print(f"  - 黑色区域 = 背景（纸张）")
    print(f"  - 模式: {mode}")
    print(f"  - 使用 Otsu 自动阈值 + 面积判断")
    print(f"  - 边缘连通噪声已清除（边缘带宽: {border_band}px），移除像素: {removed_pixels}")


if __name__ == "__main__":
    main()
