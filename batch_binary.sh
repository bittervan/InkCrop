#!/bin/bash
# 批量处理 tests 目录中的图片：
# 1) 二值化（墨迹=白，背景=黑）
# 2) 生成裁切边界预览图（在原图上画框）

# 切换到脚本所在目录（项目根目录）
cd "$(dirname "$0")"

echo "=========================================="
echo "批量处理 tests 目录中的图片"
echo "输出到 outputs 目录"
echo "=========================================="
echo ""

# 获取脚本所在目录的绝对路径
script_dir="$(cd "$(dirname "$0")" && pwd)"
tests_dir="$script_dir/tests"
outputs_dir="$script_dir/outputs"
mkdir -p "$outputs_dir"

# 固定参数（与 simple_binary.py 保持一致）
min_component_area="120"
bbox_padding="12"
bbox_detect_max_side="2200"

shopt -s nullglob
images=(
    "$tests_dir"/*.jpg
    "$tests_dir"/*.jpeg
    "$tests_dir"/*.png
    "$tests_dir"/*.JPG
    "$tests_dir"/*.JPEG
    "$tests_dir"/*.PNG
)
total=${#images[@]}

if [ "$total" -eq 0 ]; then
    echo "未找到可处理图片（支持 jpg/jpeg/png）"
    exit 0
fi

echo "找到 $total 张图片"
echo "边界过滤最小连通域面积: $min_component_area"
echo "边界留白像素: $bbox_padding"
echo "边界检测最长边: $bbox_detect_max_side"
echo ""

count=0
success=0
failed=0

for img in "${images[@]}"; do
    count=$((count + 1))
    filename="$(basename "$img")"
    stem="${filename%.*}"
    ext=".${filename##*.}"
    binary_out="$outputs_dir/${stem}_binary${ext}"
    box_out="$outputs_dir/${stem}_crop_box${ext}"

    echo "[$count/$total] 处理: $filename"
    echo "  - 二值图: $(basename "$binary_out")"
    echo "  - 边界图: $(basename "$box_out")"

    if python "$script_dir/simple_binary.py" \
        "$img" \
        "$binary_out" \
        "$box_out"; then
        success=$((success + 1))
        echo "  ✓ 完成"
    else
        failed=$((failed + 1))
        echo "  ✗ 失败"
    fi
    echo ""
done

echo "=========================================="
echo "✓ 批量处理完成！"
echo "总数: $count, 成功: $success, 失败: $failed"
echo "二值化图片: outputs/*_binary.*"
echo "边界预览图: outputs/*_crop_box.*"
echo "=========================================="
