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

# 固定参数（按当前效果锁定）
MIN_COMPONENT_AREA = 120
BBOX_PADDING = 12
BBOX_DETECT_MAX_SIDE = 2200
SCALE_SAFETY_FACTOR = 2.0


def largest_component_mask(mask):
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num_labels <= 1:
        return np.zeros_like(mask), 0

    largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    largest_area = int(stats[largest_label, cv2.CC_STAT_AREA])
    out = np.zeros_like(mask)
    out[labels == largest_label] = 255
    return out, largest_area


def filter_components_by_area(mask, min_area):
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    out = np.zeros_like(mask)
    kept = 0
    for label in range(1, num_labels):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area >= min_area:
            out[labels == label] = 255
            kept += 1
    return out, kept


def remove_border_touching_components(mask):
    num_labels, labels, _, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num_labels <= 1:
        return np.zeros_like(mask), 0

    h, w = mask.shape
    border_labels = set(labels[0, :]) | set(labels[h - 1, :]) | set(labels[:, 0]) | set(labels[:, w - 1])
    border_labels.discard(0)

    out = np.zeros_like(mask)
    kept = 0
    for label in range(1, num_labels):
        if label in border_labels:
            continue
        out[labels == label] = 255
        kept += 1
    return out, kept


def build_bbox_mask(mask, min_area):
    opened = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    )
    no_border, non_border_kept = remove_border_touching_components(opened)
    if non_border_kept > 0:
        base = no_border
        border_mode = "enabled"
    else:
        base = opened
        border_mode = "fallback"

    filtered, kept = filter_components_by_area(base, min_area)
    if kept == 0:
        return base, 0, border_mode
    return filtered, kept, border_mode


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

    min_component_area = MIN_COMPONENT_AREA
    bbox_padding = BBOX_PADDING
    bbox_detect_max_side = BBOX_DETECT_MAX_SIDE

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

    full_h, full_w = gray.shape
    long_side = max(full_h, full_w)
    if long_side > bbox_detect_max_side:
        scale = bbox_detect_max_side / float(long_side)
        detect_w = max(1, int(round(full_w * scale)))
        detect_h = max(1, int(round(full_h * scale)))
        gray_detect = cv2.resize(gray, (detect_w, detect_h), interpolation=cv2.INTER_AREA)
    else:
        scale = 1.0
        detect_h, detect_w = full_h, full_w
        gray_detect = gray

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
    total_pixels = binary_inv.size
    white_area = int(cv2.countNonZero(binary_inv))  # 255像素数
    black_area = int(total_pixels - white_area)  # 0像素数

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

    # 使用降采样图做边界检测以提速
    if scale != 1.0:
        binary_detect = cv2.resize(binary, (detect_w, detect_h), interpolation=cv2.INTER_NEAREST)
    else:
        binary_detect = binary.copy()

    # 估计纸张区域（亮区域的最大连通域），把深色边框排除在外
    paper_blurred = cv2.GaussianBlur(gray_detect, (5, 5), 0)
    _, paper_mask = cv2.threshold(
        paper_blurred,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    paper_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    paper_mask = cv2.morphologyEx(paper_mask, cv2.MORPH_CLOSE, paper_kernel, iterations=2)
    paper_mask = cv2.morphologyEx(paper_mask, cv2.MORPH_OPEN, paper_kernel, iterations=1)
    largest_paper_mask, largest_paper_area = largest_component_mask(paper_mask)
    detect_total_pixels = detect_h * detect_w
    paper_area_ratio = largest_paper_area / float(detect_total_pixels)
    if 0.35 <= paper_area_ratio <= 0.995:
        paper_mask = largest_paper_mask
        paper_mode = f"已启用（最大亮区域，占比 {paper_area_ratio*100:.1f}%）"
    else:
        paper_mask = np.full_like(binary_detect, 255, dtype=np.uint8)
        paper_mode = f"未启用（纸张占比异常 {paper_area_ratio*100:.1f}%）"

    # 边界计算时只在纸张区域内找墨迹
    bbox_mask_detect = cv2.bitwise_and(binary_detect, paper_mask)
    bbox_mask_detect_no_paper = binary_detect

    # 再过滤掉小噪点连通域
    if min_component_area is None:
        min_component_area = max(16, int(total_pixels * 0.000002))
    if scale != 1.0:
        min_component_area_detect = max(1, int(round(min_component_area * scale * scale * 0.25)))
    else:
        min_component_area_detect = min_component_area

    bbox_mask_detect, kept_components, border_filter_mode = build_bbox_mask(
        bbox_mask_detect,
        min_component_area_detect
    )
    bbox_mask_detect_no_paper, kept_components_no_paper, border_filter_mode_no_paper = build_bbox_mask(
        bbox_mask_detect_no_paper,
        min_component_area_detect
    )

    # 避免阈值过高导致空掩码
    if kept_components == 0:
        bbox_mask_detect = cv2.bitwise_and(binary_detect, paper_mask)

    points = cv2.findNonZero(bbox_mask_detect)
    points_no_paper = cv2.findNonZero(bbox_mask_detect_no_paper)
    boxed = image.copy()
    bbox = None
    bbox_source = "paper+noise_filter"
    # 降采样检测后回投到原图时，给一个与 scale 相关的安全边距，避免框压进笔画
    scale_safety_pad = int(np.ceil(SCALE_SAFETY_FACTOR / scale)) if scale < 1.0 else 0

    def calc_bbox_from_points(pts):
        x_s, y_s, w_s, h_s = cv2.boundingRect(pts)
        if scale != 1.0:
            x0 = int(np.floor(x_s / scale))
            y0 = int(np.floor(y_s / scale))
            x1 = int(np.ceil((x_s + w_s) / scale)) - 1
            y1 = int(np.ceil((y_s + h_s) / scale)) - 1
            return x0, y0, x1 - x0 + 1, y1 - y0 + 1
        return x_s, y_s, w_s, h_s

    if points is not None:
        x, y, w, h = calc_bbox_from_points(points)
        bbox_area_ratio = (w * h) / float(full_h * full_w)
        if bbox_area_ratio < 0.01 and points_no_paper is not None:
            # 纸张过滤可能过于激进，自动回退到仅噪点过滤
            x, y, w, h = calc_bbox_from_points(points_no_paper)
            bbox_source = "noise_filter_fallback"

        total_pad = bbox_padding + scale_safety_pad
        x = max(0, x - total_pad)
        y = max(0, y - total_pad)
        x2 = min(binary.shape[1] - 1, x + w - 1 + total_pad)
        y2 = min(binary.shape[0] - 1, y + h - 1 + total_pad)
        w = x2 - x + 1
        h = y2 - y + 1
        bbox = (x, y, w, h)
        cv2.rectangle(boxed, (x, y), (x + w - 1, y + h - 1), (0, 0, 255), 2)
    elif points_no_paper is not None:
        x, y, w, h = calc_bbox_from_points(points_no_paper)
        total_pad = bbox_padding + scale_safety_pad
        x = max(0, x - total_pad)
        y = max(0, y - total_pad)
        x2 = min(binary.shape[1] - 1, x + w - 1 + total_pad)
        y2 = min(binary.shape[0] - 1, y + h - 1 + total_pad)
        w = x2 - x + 1
        h = y2 - y + 1
        bbox = (x, y, w, h)
        bbox_source = "noise_filter_no_paper"
        cv2.rectangle(boxed, (x, y), (x + w - 1, y + h - 1), (0, 0, 255), 2)

    # 保存结果
    cv2.imwrite(str(binary_output_path), binary)
    cv2.imwrite(str(boxed_output_path), boxed)

    print(f"\n✓ 已保存二值化图到: {binary_output_path}")
    print(f"✓ 已保存边界预览图到: {boxed_output_path}")
    print(f"  输入图片: {input_path}")
    print(f"  图片大小: {image.shape}")
    print(f"  二值图大小: {binary.shape}")
    print(f"  边界检测尺寸: {detect_h}x{detect_w} (scale={scale:.4f})")
    print(f"  纸张区域过滤: {paper_mode}")
    print(f"  边缘连通域过滤: {border_filter_mode} (no_paper={border_filter_mode_no_paper})")
    print(f"  边界过滤最小连通域面积: {min_component_area}")
    print(f"  边界过滤最小连通域面积(检测图): {min_component_area_detect}")
    print(f"  缩放回投安全边距: {scale_safety_pad}")
    print(f"  边界留白像素: {bbox_padding}")
    if bbox is None:
        print("  裁切边界: 未检测到墨迹（整图为空）")
    else:
        x, y, w, h = bbox
        print(f"  裁切边界: x={x}, y={y}, w={w}, h={h}")
        print(f"  裁切边界来源: {bbox_source}")
    print(f"\n说明:")
    print(f"  - 白色区域 = 墨迹")
    print(f"  - 黑色区域 = 背景（纸张）")
    print(f"  - 模式: {mode}")
    print(f"  - 使用 Otsu 自动阈值 + 面积判断 + 外接矩形")


if __name__ == "__main__":
    main()
