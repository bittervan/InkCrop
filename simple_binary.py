#!/usr/bin/env python3
"""
简单二值化脚本 - 根据面积判断墨迹和背景
输入：一张图片（白纸黑字）
输出：
1) 二值化图（墨迹区域）
2) 加框预览图（在原图上画出墨迹范围框）
"""
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from skimage.segmentation import clear_border


BORDER_CLEAN_MAX_SIDE = 2400
BORDER_BAND_RATIO = 0.03
BORDER_BAND_MIN = 24

BBOX_DETECT_MAX_SIDE = 2400
BBOX_PADDING_RATIO = 0.03
BBOX_PROJ_RATIO = 0.002
BBOX_MIN_PROJ_COVER_RATIO = 0.85
SPLIT_VALLEY_PERCENTILE = 24
SPLIT_MIN_SPACING = 80
SPLIT_STRONG_VALLEY_RATIO = 0.45
SPLIT_STRONG_VALLEY_MIN = 12
SPLIT_REFINE_RADIUS_RATIO = 0.40
SPLIT_REFINE_RADIUS_MIN = 3

A4_WIDTH = 210.0
A4_HEIGHT = 297.0
A4_RATIO = A4_HEIGHT / A4_WIDTH
PDF_PAGE_MARGIN_MM = 5.0
PDF_PAGE_MARGIN_PT = PDF_PAGE_MARGIN_MM * 72.0 / 25.4
PDF_IMAGE_JPEG_QUALITY = 90


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
        ink_small_raw = cv2.resize(
            ink_mask.astype(np.uint8),
            (small_w, small_h),
            interpolation=cv2.INTER_NEAREST
        )
    else:
        scale = 1.0
        small_h, small_w = h, w
        ink_small_raw = ink_mask.astype(np.uint8)

    ys_raw, xs_raw = np.where(ink_small_raw > 0)
    if ys_raw.size == 0:
        return None, {}
    raw_top_s, raw_bottom_s = int(ys_raw.min()), int(ys_raw.max())
    raw_left_s, raw_right_s = int(xs_raw.min()), int(xs_raw.max())

    ink_small = cv2.morphologyEx(
        ink_small_raw * 255,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    ) > 0

    if np.count_nonzero(ink_small) == 0:
        ink_small = ink_small_raw > 0

    row_counts = np.count_nonzero(ink_small, axis=1)
    col_counts = np.count_nonzero(ink_small, axis=0)

    row_high = max(4, int(round(small_w * BBOX_PROJ_RATIO)))
    col_high = max(4, int(round(small_h * BBOX_PROJ_RATIO)))
    row_low = max(2, int(round(row_high * 0.35)))
    col_low = max(2, int(round(col_high * 0.35)))

    row_run = projection_bounds(row_counts, row_high, row_low)
    col_run = projection_bounds(col_counts, col_high, col_low)

    if row_run is None or col_run is None:
        top_s, bottom_s = raw_top_s, raw_bottom_s
        left_s, right_s = raw_left_s, raw_right_s
    else:
        top_s, bottom_s = row_run
        left_s, right_s = col_run

        raw_box_h_s = raw_bottom_s - raw_top_s + 1
        raw_box_w_s = raw_right_s - raw_left_s + 1
        proj_box_h_s = bottom_s - top_s + 1
        proj_box_w_s = right_s - left_s + 1

        # 投影框过窄时回退到原始外接框，避免误裁边缘字符。
        if proj_box_w_s < int(round(raw_box_w_s * BBOX_MIN_PROJ_COVER_RATIO)):
            left_s, right_s = raw_left_s, raw_right_s
        if proj_box_h_s < int(round(raw_box_h_s * BBOX_MIN_PROJ_COVER_RATIO)):
            top_s, bottom_s = raw_top_s, raw_bottom_s

    if scale != 1.0:
        left = int(np.floor(left_s / scale))
        top = int(np.floor(top_s / scale))
        right = int(np.ceil((right_s + 1) / scale)) - 1
        bottom = int(np.ceil((bottom_s + 1) / scale)) - 1
    else:
        left, top, right, bottom = left_s, top_s, right_s, bottom_s

    raw_box_h = (bottom - top + 1)
    total_pad = max(1, int(round(raw_box_h * BBOX_PADDING_RATIO)))

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
        "raw_top_s": raw_top_s,
        "raw_bottom_s": raw_bottom_s,
        "raw_left_s": raw_left_s,
        "raw_right_s": raw_right_s,
        "raw_box_h": raw_box_h,
        "total_pad": total_pad,
    }
    return (left, top, right - left + 1, bottom - top + 1), info


def detect_split_candidates(ink_roi):
    h, w = ink_roi.shape
    if w <= 0:
        return [], {}

    if w > BBOX_DETECT_MAX_SIDE:
        scale = BBOX_DETECT_MAX_SIDE / float(w)
        small_w = BBOX_DETECT_MAX_SIDE
        small_h = max(1, int(round(h * scale)))
        roi_small = cv2.resize(
            ink_roi.astype(np.uint8),
            (small_w, small_h),
            interpolation=cv2.INTER_NEAREST
        )
    else:
        scale = 1.0
        small_h, small_w = h, w
        roi_small = ink_roi.astype(np.uint8)

    proj = np.count_nonzero(roi_small > 0, axis=0).astype(np.float32)
    smooth = smooth_projection(proj)

    if np.max(smooth) <= 0:
        return [], {
            "split_scale": scale,
            "split_detect_w": small_w,
            "candidate_count": 0,
        }

    valley_thresh = float(np.percentile(smooth, SPLIT_VALLEY_PERCENTILE))
    valley_mask = smooth <= valley_thresh

    valley_u8 = (valley_mask.astype(np.uint8) * 255).reshape(1, -1)
    close_k = max(3, int(round(small_w * 0.003)))
    if close_k % 2 == 0:
        close_k += 1
    valley_u8 = cv2.morphologyEx(
        valley_u8,
        cv2.MORPH_CLOSE,
        np.ones((1, close_k), dtype=np.uint8)
    )
    valley_mask = valley_u8.ravel() > 0

    runs_small = []
    start = None
    for i, flag in enumerate(valley_mask):
        if flag and start is None:
            start = i
        elif (not flag) and start is not None:
            end = i - 1
            runs_small.append(((start + end) // 2, end - start + 1))
            start = None
    if start is not None:
        end = len(valley_mask) - 1
        runs_small.append(((start + end) // 2, end - start + 1))

    edge_margin = max(2, int(round(small_w * 0.01)))
    runs_small = [
        (c, run_w) for c, run_w in runs_small
        if edge_margin < c < (small_w - edge_margin)
    ]

    candidate_widths = {}
    candidate_costs = {}
    if scale != 1.0:
        for c, run_w in runs_small:
            center = int(round(c / scale))
            width = max(1, int(round(run_w / scale)))
            if 0 < center < w:
                candidate_widths[center] = max(candidate_widths.get(center, 0), width)
    else:
        for c, run_w in runs_small:
            center = int(c)
            width = int(run_w)
            if 0 < center < w:
                candidate_widths[center] = max(candidate_widths.get(center, 0), width)

    if not candidate_widths:
        return [], {
            "split_scale": scale,
            "split_detect_w": small_w,
            "candidate_count": 0,
            "candidate_widths": {},
            "candidate_costs": {},
            "dominant_spacing": None,
            "dominant_spacing_conf": 0.0,
            "dominant_phase": None,
            "strong_candidate_count": 0,
        }

    full_proj = np.count_nonzero(ink_roi, axis=0).astype(np.float32)
    refined_widths = {}
    for c, width in candidate_widths.items():
        refine_r = max(SPLIT_REFINE_RADIUS_MIN, int(round(width * SPLIT_REFINE_RADIUS_RATIO)))
        left = max(0, c - refine_r)
        right = min(w, c + refine_r + 1)
        if right <= left:
            continue
        local = full_proj[left:right]
        best_off = int(np.argmin(local))
        refined_c = left + best_off
        refined_cost = float(local[best_off])

        prev_w = refined_widths.get(refined_c, 0)
        refined_widths[refined_c] = max(prev_w, width)
        prev_cost = candidate_costs.get(refined_c)
        if prev_cost is None or refined_cost < prev_cost:
            candidate_costs[refined_c] = refined_cost

    centers = sorted(refined_widths.keys())
    if not centers:
        return [], {
            "split_scale": scale,
            "split_detect_w": small_w,
            "candidate_count": 0,
            "candidate_widths": {},
            "candidate_costs": {},
            "dominant_spacing": None,
            "dominant_spacing_conf": 0.0,
            "dominant_phase": None,
            "strong_candidate_count": 0,
        }

    keep_n = max(SPLIT_STRONG_VALLEY_MIN, int(round(len(centers) * SPLIT_STRONG_VALLEY_RATIO)))
    keep_n = min(len(centers), keep_n)
    strongest = sorted(centers, key=lambda c: candidate_costs.get(c, 1e9))[:keep_n]
    strong_set = set(strongest)

    spacing, spacing_conf = estimate_dominant_spacing(
        centers=centers,
        candidate_widths=refined_widths,
        candidate_costs=candidate_costs,
        strong_centers=strongest,
    )
    phase = estimate_dominant_phase(
        centers=strongest,
        candidate_widths=refined_widths,
        candidate_costs=candidate_costs,
        spacing=spacing,
    )
    return centers, {
        "split_scale": scale,
        "split_detect_w": small_w,
        "candidate_count": len(centers),
        "candidate_widths": refined_widths,
        "candidate_costs": candidate_costs,
        "dominant_spacing": spacing,
        "dominant_spacing_conf": spacing_conf,
        "dominant_phase": phase,
        "strong_candidate_count": len(strong_set),
    }


def estimate_dominant_spacing(centers, candidate_widths, candidate_costs, strong_centers):
    if len(strong_centers) < 3:
        return None, 0.0

    centers_np = np.asarray(sorted(strong_centers), dtype=np.float32)
    diffs = np.diff(centers_np)
    if diffs.size < 2:
        return None, 0.0

    strengths = []
    for c in centers_np:
        cc = int(c)
        width = float(candidate_widths.get(cc, 1.0))
        cost = float(candidate_costs.get(cc, 1.0))
        strengths.append(width / (1.0 + cost))
    widths_np = np.asarray(strengths, dtype=np.float32)

    pair_weights = (widths_np[:-1] + widths_np[1:]) * 0.5
    q1, q3 = np.percentile(diffs, [25, 75])
    iqr = max(1.0, float(q3 - q1))
    low = max(float(SPLIT_MIN_SPACING), float(q1 - 1.5 * iqr))
    high = float(q3 + 1.5 * iqr)
    mask = (diffs >= low) & (diffs <= high)

    diffs_core = diffs[mask]
    weights_core = pair_weights[mask]
    if diffs_core.size < 2:
        return None, 0.0

    median_step = float(np.median(diffs_core))
    bin_size = max(8.0, round(median_step * 0.08))
    bins = np.round(diffs_core / bin_size).astype(np.int32)
    uniq_bins = np.unique(bins)
    if uniq_bins.size == 0:
        return None, 0.0

    best_bin = None
    best_weight = -1.0
    total_weight = float(np.sum(weights_core)) + 1e-6
    for b in uniq_bins:
        w_sum = float(np.sum(weights_core[bins == b]))
        if w_sum > best_weight:
            best_weight = w_sum
            best_bin = b

    if best_bin is None:
        return None, 0.0

    chosen = diffs_core[bins == best_bin]
    spacing = int(round(float(np.median(chosen))))
    if spacing < SPLIT_MIN_SPACING:
        return None, 0.0

    confidence = max(0.0, min(1.0, best_weight / total_weight))
    return spacing, confidence


def estimate_dominant_phase(centers, candidate_widths, candidate_costs, spacing):
    if spacing is None or spacing <= 0 or len(centers) == 0:
        return None

    residues = []
    weights = []
    for c in centers:
        residue = int(c) % int(spacing)
        width = float(candidate_widths.get(int(c), 1.0))
        cost = float(candidate_costs.get(int(c), 1.0))
        residues.append(residue)
        weights.append(width / (1.0 + cost))

    residues = np.asarray(residues, dtype=np.float32)
    weights = np.asarray(weights, dtype=np.float32)
    if residues.size == 0:
        return None

    bin_size = max(6, int(round(spacing * 0.08)))
    bins = np.round(residues / float(bin_size)).astype(np.int32)
    uniq_bins = np.unique(bins)
    if uniq_bins.size == 0:
        return None

    best_bin = None
    best_weight = -1.0
    for b in uniq_bins:
        w_sum = float(np.sum(weights[bins == b]))
        if w_sum > best_weight:
            best_weight = w_sum
            best_bin = b

    chosen = residues[bins == best_bin]
    if chosen.size == 0:
        return None
    return int(round(float(np.median(chosen))))


def choose_split_in_window(
    feasible, end, target_width, candidate_widths, candidate_costs, cost_low, cost_high, spacing, phase
):
    if not feasible:
        return None

    max_score = 1.0
    if candidate_widths:
        max_score = max(float(v) for v in candidate_widths.values())

    best = None
    best_cost = None
    for c in feasible:
        seg_w = end - c
        width_cost = abs(seg_w - target_width)

        phase_cost = 0.0
        if spacing is not None and phase is not None and spacing > 0:
            delta = abs((c - phase) % spacing)
            phase_cost = min(delta, spacing - delta)

        strength = float(candidate_widths.get(c, 1.0)) / max_score
        raw_cost = float(candidate_costs.get(c, cost_high))
        denom = max(1.0, cost_high - cost_low)
        norm_cost = (raw_cost - cost_low) / denom
        norm_cost = max(0.0, min(2.0, norm_cost))

        cost = width_cost + 0.45 * phase_cost + 34.0 * norm_cost - 20.0 * strength

        if best_cost is None or cost < best_cost:
            best = c
            best_cost = cost
    return best


def build_column_boundaries(total_width, max_col_width, split_candidates, split_info=None):
    max_col_width = max(1, min(int(max_col_width), int(total_width)))
    min_col_width = max(80, int(round(max_col_width * 0.60)))
    min_left_width = max(80, int(round(max_col_width * 0.45)))

    candidates = sorted(set(c for c in split_candidates if 0 < c < total_width))
    candidate_widths = {}
    candidate_costs = {}
    dominant_spacing = None
    dominant_spacing_conf = 0.0
    dominant_phase = None
    if split_info:
        candidate_widths = dict(split_info.get("candidate_widths", {}))
        candidate_costs = dict(split_info.get("candidate_costs", {}))
        dominant_spacing = split_info.get("dominant_spacing")
        dominant_spacing_conf = float(split_info.get("dominant_spacing_conf", 0.0))
        dominant_phase = split_info.get("dominant_phase")

    use_spacing = (
        dominant_spacing is not None
        and dominant_spacing > SPLIT_MIN_SPACING
        and dominant_spacing_conf >= 0.18
    )
    phase = None
    target_width = max_col_width
    if use_spacing and candidates:
        phase = dominant_phase
        if phase is None:
            phase = candidates[-1] % dominant_spacing
        lines_per_col = max(1, int(round(max_col_width / float(dominant_spacing))))
        target_width = int(round(lines_per_col * dominant_spacing))
        if target_width > max_col_width and lines_per_col > 1:
            lines_per_col -= 1
            target_width = int(round(lines_per_col * dominant_spacing))
        if target_width < min_col_width and (lines_per_col + 1) * dominant_spacing <= max_col_width:
            lines_per_col += 1
            target_width = int(round(lines_per_col * dominant_spacing))
        target_width = max(min_col_width, min(max_col_width, target_width))

    # 按“从右到左”切分：优先确定右侧整列，余量留在最左侧
    boundaries_desc = [total_width]
    end = total_width
    if candidate_costs:
        arr_cost = np.array(list(candidate_costs.values()), dtype=np.float32)
        cost_low = float(np.percentile(arr_cost, 15))
        cost_high = float(np.percentile(arr_cost, 85))
        if cost_high <= cost_low:
            cost_high = cost_low + 1.0
    else:
        cost_low, cost_high = 0.0, 1.0

    while end > max_col_width:
        low = end - max_col_width
        high = end - min_col_width
        feasible = [c for c in candidates if low <= c <= high]
        feasible_valid = [
            c for c in feasible
            if (c >= min_left_width or c <= max_col_width)
        ]
        if feasible_valid:
            feasible = feasible_valid

        if feasible:
            split = choose_split_in_window(
                feasible=feasible,
                end=end,
                target_width=target_width,
                candidate_widths=candidate_widths,
                candidate_costs=candidate_costs,
                cost_low=cost_low,
                cost_high=cost_high,
                spacing=dominant_spacing if use_spacing else None,
                phase=phase,
            )
            if split is None:
                split = feasible[0]
        else:
            split = low

        if split >= end:
            split = max(0, end - max_col_width)
            if split >= end:
                break

        boundaries_desc.append(split)
        end = split

    if boundaries_desc[-1] != 0:
        boundaries_desc.append(0)

    boundaries = sorted(set(boundaries_desc))
    normalized = [boundaries[0]]
    for b in boundaries[1:]:
        if b > normalized[-1]:
            normalized.append(b)
    if normalized[-1] != total_width:
        normalized.append(total_width)
    return normalized


def save_columns_to_a4_pdf(image, bbox, boundaries, pdf_output_path):
    x, y, w, h = bbox
    page_w, page_h = A4
    usable_w = page_w - 2 * PDF_PAGE_MARGIN_PT
    usable_h = page_h - 2 * PDF_PAGE_MARGIN_PT

    c = canvas.Canvas(str(pdf_output_path), pagesize=A4)
    page_count = 0

    # 先写临时 JPEG 再嵌入 PDF，可显著减少 ReportLab 的编码开销
    with tempfile.TemporaryDirectory(prefix="inkcrop_pdf_") as temp_dir:
        temp_dir_path = Path(temp_dir)

        # 固定按右到左分页输出
        for i in range(len(boundaries) - 2, -1, -1):
            left = boundaries[i]
            right = boundaries[i + 1]
            if right <= left:
                continue

            seg = image[y:y + h, x + left:x + right]
            if seg.size == 0:
                continue

            img_h, img_w = seg.shape[:2]
            if img_w <= 0 or img_h <= 0:
                continue

            temp_img_path = temp_dir_path / f"page_{page_count:04d}.jpg"
            ok = cv2.imwrite(
                str(temp_img_path),
                seg,
                [cv2.IMWRITE_JPEG_QUALITY, PDF_IMAGE_JPEG_QUALITY]
            )
            if not ok:
                continue

            scale = min(usable_w / img_w, usable_h / img_h)
            draw_w = img_w * scale
            draw_h = img_h * scale
            draw_x = (page_w - draw_w) / 2.0
            draw_y = (page_h - draw_h) / 2.0

            c.drawImage(str(temp_img_path), draw_x, draw_y, draw_w, draw_h)
            c.showPage()
            page_count += 1

    c.save()
    return page_count


def main():
    if len(sys.argv) < 2:
        print("用法: python simple_binary.py <输入图片> [二值图输出] [加框图输出] [A4-PDF输出]")
        print("示例: python simple_binary.py input.jpg outputs/input_binary.jpg outputs/input_crop_box.jpg outputs/input_a4.pdf")
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

    if len(sys.argv) >= 5:
        pdf_output_path = Path(sys.argv[4])
    else:
        pdf_output_path = outputs_dir / f"{input_file.stem}_a4.pdf"

    binary_output_path.parent.mkdir(parents=True, exist_ok=True)
    box_output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_output_path.parent.mkdir(parents=True, exist_ok=True)

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

    white_area = int(cv2.countNonZero(binary_inv))
    black_area = int(binary_inv.size - white_area)

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
    boundaries = []
    pages = 0
    max_col_width = 0
    split_info = {}
    col_widths = []
    if bbox is not None:
        x, y, w, h = bbox
        max_col_width = int(round(h / A4_RATIO))
        max_col_width = max(1, min(max_col_width, w))

        ink_mask, _ = get_ink_mask(binary)
        roi_ink = ink_mask[y:y + h, x:x + w]
        split_candidates, split_info = detect_split_candidates(roi_ink)
        boundaries = build_column_boundaries(
            total_width=w,
            max_col_width=max_col_width,
            split_candidates=split_candidates,
            split_info=split_info,
        )
        col_widths = [boundaries[i + 1] - boundaries[i] for i in range(len(boundaries) - 1)]

        for b in boundaries[1:-1]:
            cv2.line(boxed, (x + b, y), (x + b, y + h - 1), (255, 128, 0), 1)

        cv2.rectangle(boxed, (x, y), (x + w - 1, y + h - 1), (0, 0, 255), 2)
        pages = save_columns_to_a4_pdf(image, bbox, boundaries, pdf_output_path)

    cv2.imwrite(str(binary_output_path), binary)
    cv2.imwrite(str(box_output_path), boxed)

    print(f"\n✓ 已保存二值化图到: {binary_output_path}")
    print(f"✓ 已保存加框预览图到: {box_output_path}")
    if bbox is not None:
        print(f"✓ 已保存A4分页PDF到: {pdf_output_path}")
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
            f"scale={bbox_info['scale']:.4f}, pad={bbox_info['total_pad']} (h*3%, raw_h={bbox_info['raw_box_h']})"
        )
        print(
            f"  分页: max_col_width={max_col_width}, split_candidates={split_info.get('candidate_count', 0)}, "
            f"列数={max(0, len(boundaries)-1)}, PDF页数={pages}, 顺序=右到左"
        )
        if split_info.get("dominant_spacing") is not None:
            print(
                "  行距估计: "
                f"spacing={split_info.get('dominant_spacing')}, "
                f"conf={split_info.get('dominant_spacing_conf', 0.0):.2f}"
            )
            print(
                "  强谷值: "
                f"count={split_info.get('strong_candidate_count', 0)}/"
                f"{split_info.get('candidate_count', 0)}"
            )
        if col_widths:
            print(f"  列宽: 最右={col_widths[-1]}, 最左={col_widths[0]}")

    print("\n说明:")
    print("  - 白色区域 = 墨迹")
    print("  - 黑色区域 = 背景（纸张）")
    print(f"  - 模式: {mode}")
    print("  - 使用 Otsu 自动阈值 + 面积判断")
    print(f"  - 边缘连通噪声已清除（边缘带宽: {border_band}px），移除像素: {removed_pixels}")


if __name__ == "__main__":
    main()
