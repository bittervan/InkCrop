#!/bin/bash
# 批量二值化 tests 目录中的图片
# 输出到 outputs 目录

# 切换到脚本所在目录（项目根目录）
cd "$(dirname "$0")"

echo "=========================================="
echo "批量二值化 tests 目录中的图片"
echo "输出到 outputs 目录"
echo "=========================================="
echo ""

# 获取脚本所在目录的绝对路径
script_dir="$(cd "$(dirname "$0")" && pwd)"

# 计算jpg文件数量
tests_dir="$script_dir/tests"
total=$(find "$tests_dir" -maxdepth 1 -name "*.jpg" 2>/dev/null | wc -l)

echo "找到 $total 张图片"
echo ""

# 计数器
count=0

# 依次处理每张图片
for img in "$tests_dir"/*.jpg; do
    if [ -f "$img" ]; then
        count=$((count + 1))
        filename=$(basename "$img")

        echo "[$count/$total] 处理: $filename"

        # 调用 simple_binary.py 处理（它会自动输出到 outputs/ 目录）
        python "$script_dir/simple_binary.py" "$img"

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
echo "二值化图片保存在 outputs/ 目录，文件名格式：原文件名_binary.jpg"
echo "=========================================="
