#!/usr/bin/env python3
"""
简单二值化脚本 - 根据面积判断墨迹和背景
输入：一张图片（白纸黑字）
输出：
1) 二值化图（墨迹区域）
2) 加框预览图（在原图上画出墨迹范围框）
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from skimage.segmentation import clear_border


BORDER_CLEAN_MAX_SIDE = 2400
BORDER_BAND_RATIO = 0.03
BORDER_BAND_MIN = 24

BBOX_DETECT_MAX_SIDE = 2400
BBOX_PADDING = 12
BBOX_EXTRA_PADDING = 8
BBOX_SCALE_SAFETY = 2.0
BBOX_PROJ_RATIO = 0.002


def get_ink_mask(binary):
    white_pixels = int(cv2.countNonZero(binary))
    black_pixels = int(binary.size - white_pixels)
    if white_pixels <= black_pixels:
        return (binary == 255), "white"
    return (binary == 0), "black"


def remove_border_connected_ink(binary):
    ink_mask, ink_color = get_ink_mask(binary)
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

    inside_small = clear_border(ink_small, buffer_size=0)
    border_connected_small = ink_small & (~inside_small)

    border_band_small = max(
        BORDER_BAND_MIN,
        int(round(min(small_h, small_w) * BORDER_BAND_RATIO))
    )
    edge_band_small = np.zeros_like(ink_small, dtype=bool)
    edge_band_small[:border_band_small, :] = True
    edge_band_small[small_h - border_band_small:, :] = True
    edge_band_small[:, :border_band_small] = True
    edge_band_small[:, small_w - border_band_small:] = True

    remove_small = border_connected_small & edge_band_small
    remove_small_u8 = cv2.dilate(
        remove_small.astype(np.uint8) * 255,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
        iterations=1
    )
    remove_small = remove_small_u8 > 0

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

    if ink_color == "white":
        cleaned_binary = np.where(ink_mask_clean, 255, 0).astype(np.uint8)
    else:
        cleaned_binary = np.where(ink_mask_clean, 0, 255).astype(np.uint8)

    return cleaned_binary, removed_pixels, border_band


def smooth_projection(counts):
    k = max(5, int(round(len(counts) * 0.005)))
    if k % 2 == 0:
        k += 1
    return cv2.GaussianBlur(
        counts.astype(np.float32).reshape(1, -1),
        (k, 1),
        0
    ).ravel()


def projection_bounds(counts, high_thresh, low_thresh):
    smooth = smooth_projection(counts)
    idx = np.where(smooth >= high_thresh)[0]
    if idx.size == 0:
        idx = np.where(smooth >= low_thresh)[0]
    if idx.size == 0:
        return None
    return int(idx[0]), int(idx[-1])


def detect_bbox(binary):
    ink_mask, _ = get_ink_mask(binary)
    if np.count_nonzero(ink_mask) == 0:
        return None, {}

    h, w = ink_mask.shape
    long_side = max(h, w)
    if long_side > BBOX_DETECT_MAX_SIDE:
        scale = BBOX_DETECT_MAX_SIDE / float(long_side)
        small_w = max(1, int(round(w * scale)))
        small_h = max(1, int(round(h * scale)))
        ink_small = cv2.resize(
            ink_mask.astype(np.uint8),
            (small_w, small_h),
            interpolation=cv2.INTER_NEAREST
        )
    else:
        scale = 1.0
        small_h, small_w = h, w
        ink_small = ink_mask.astype(np.uint8)

    ink_small = cv2.morphologyEx(
        ink_small * 255,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    ) > 0

    row_counts = np.count_nonzero(ink_small, axis=1)
    col_counts = np.count_nonzero(ink_small, axis=0)

    row_high = max(4, int(round(small_w * BBOX_PROJ_RATIO)))
    col_high = max(4, int(round(small_h * BBOX_PROJ_RATIO)))
    row_low = max(2, int(round(row_high * 0.35)))
    col_low = max(2, int(round(col_high * 0.35)))

    row_run = projection_bounds(row_counts, row_high, row_low)
    col_run = projection_bounds(col_counts, col_high, col_low)

    if row_run is None or col_run is None:
        ys, xs = np.where(ink_small)
        if ys.size == 0:
            return None, {}
        top_s, bottom_s = int(ys.min()), int(ys.max())
        left_s, right_s = int(xs.min()), int(xs.max())
    else:
        top_s, bottom_s = row_run
        left_s, right_s = col_run

    if scale != 1.0:
        left = int(np.floor(left_s / scale))
        top = int(np.floor(top_s / scale))
        right = int(np.ceil((right_s + 1) / scale)) - 1
        bottom = int(np.ceil((bottom_s + 1) / scale)) - 1
    else:
        left, top, right, bottom = left_s, top_s, right_s, bottom_s

    scale_pad = int(np.ceil(BBOX_SCALE_SAFETY / scale)) if scale < 1.0 else 0
    total_pad = BBOX_PADDING + BBOX_EXTRA_PADDING + scale_pad

    left = max(0, left - total_pad)
    top = max(0, top - total_pad)
    right = min(w - 1, right + total_pad)
    bottom = min(h - 1, bottom + total_pad)

    if right <= left or bottom <= top:
        return None, {}

    info = {
        "scale": scale,
        "detect_h": small_h,
        "detect_w": small_w,
        "row_high": row_high,
        "col_high": col_high,
        "total_pad": total_pad,
    }
    return (left, top, right - left + 1, bottom - top + 1), info


def main():
    if len(sys.argv) < 2:
        print("用法: python simple_binary.py <输入图片> [二值图输出] [加框图输出]")
        print("示例: python simple_binary.py input.jpg outputs/input_binary.jpg outputs/input_crop_box.jpg")
        sys.exit(1)

    input_path = sys.argv[1]
    input_file = Path(input_path)
    script_dir = Path(__file__).parent
    outputs_dir = script_dir / "outputs"
    outputs_dir.mkdir(exist_ok=True)

    if len(sys.argv) >= 3:
        binary_output_path = Path(sys.argv[2])
    else:
        binary_output_path = outputs_dir / f"{input_file.stem}_binary{input_file.suffix}"

    if len(sys.argv) >= 4:
        box_output_path = Path(sys.argv[3])
    else:
        box_output_path = outputs_dir / f"{input_file.stem}_crop_box{input_file.suffix}"

    binary_output_path.parent.mkdir(parents=True, exist_ok=True)
    box_output_path.parent.mkdir(parents=True, exist_ok=True)

    image = cv2.imread(input_path)
    if image is None:
        print(f"错误：无法读取图片: {input_path}")
        sys.exit(1)

    print(f"已加载图片: {image.shape}")

    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary_inv = cv2.threshold(
        blurred,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    white_area = int(np.sum(binary_inv == 255))
    black_area = int(np.sum(binary_inv == 0))

    print(f"白色像素数: {white_area} ({white_area/(binary_inv.shape[0]*binary_inv.shape[1])*100:.2f}%)")
    print(f"黑色像素数: {black_area} ({black_area/(binary_inv.shape[0]*binary_inv.shape[1])*100:.2f}%)")

    if white_area > black_area:
        binary = binary_inv
        mode = "白底黑字（无需反转）"
    else:
        binary = cv2.bitwise_not(binary_inv)
        mode = "黑底白字（已反转）"

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    binary, removed_pixels, border_band = remove_border_connected_ink(binary)
    bbox, bbox_info = detect_bbox(binary)

    boxed = image.copy()
    if bbox is not None:
        x, y, w, h = bbox
        cv2.rectangle(boxed, (x, y), (x + w - 1, y + h - 1), (0, 0, 255), 2)

    cv2.imwrite(str(binary_output_path), binary)
    cv2.imwrite(str(box_output_path), boxed)

    print(f"\n✓ 已保存二值化图到: {binary_output_path}")
    print(f"✓ 已保存加框预览图到: {box_output_path}")
    print(f"  输入图片: {input_path}")
    print(f"  图片大小: {image.shape}")
    print(f"  二值图大小: {binary.shape}")

    if bbox is None:
        print("  检测框: 未找到有效墨迹区域")
    else:
        x, y, w, h = bbox
        print(f"  检测框: x={x}, y={y}, w={w}, h={h}")
        print(
            f"  框检测尺寸: {bbox_info['detect_h']}x{bbox_info['detect_w']}, "
            f"scale={bbox_info['scale']:.4f}, pad={bbox_info['total_pad']}"
        )

    print("\n说明:")
    print("  - 白色区域 = 墨迹")
    print("  - 黑色区域 = 背景（纸张）")
    print(f"  - 模式: {mode}")
    print("  - 使用 Otsu 自动阈值 + 面积判断")
    print(f"  - 边缘连通噪声已清除（边缘带宽: {border_band}px），移除像素: {removed_pixels}")


if __name__ == "__main__":
    main()
