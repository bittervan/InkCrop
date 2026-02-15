#!/bin/bash
# 批量二值化并输出加框预览图
# 输入: tests/*.jpg
# 输出: outputs/*_binary.jpg, outputs/*_crop_box.jpg

cd "$(dirname "$0")"

echo "=========================================="
echo "批量二值化 + 加框预览"
echo "输入: tests 目录"
echo "输出: outputs 目录"
echo "=========================================="
echo ""

script_dir="$(cd "$(dirname "$0")" && pwd)"
tests_dir="$script_dir/tests"
outputs_dir="$script_dir/outputs"
mkdir -p "$outputs_dir"

total=$(find "$tests_dir" -maxdepth 1 -name "*.jpg" 2>/dev/null | wc -l)

echo "找到 $total 张图片"
echo ""

count=0
for img in "$tests_dir"/*.jpg; do
    if [ -f "$img" ]; then
        count=$((count + 1))
        filename="$(basename "$img")"
        stem="${filename%.*}"
        ext=".${filename##*.}"

        binary_out="$outputs_dir/${stem}_binary${ext}"
        box_out="$outputs_dir/${stem}_crop_box${ext}"

        echo "[$count/$total] 处理: $filename"
        echo "  - 二值图: $(basename "$binary_out")"
        echo "  - 框预览: $(basename "$box_out")"

        python "$script_dir/simple_binary.py" "$img" "$binary_out" "$box_out"

        if [ $? -eq 0 ]; then
            echo "  ✓ 完成"
        else
            echo "  ✗ 失败"
        fi
        echo ""
    fi
done

echo "=========================================="
echo "✓ 批量处理完成！"
echo "共处理了 $count 张图片"
echo "二值图: outputs/*_binary.jpg"
echo "框预览: outputs/*_crop_box.jpg"
echo "=========================================="
