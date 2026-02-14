#!/bin/bash
# 批量二值化脚本
# 依次处理 tests 目录里的图片

# 切换到脚本所在目录
cd "$(dirname "$0")"

echo "=========================================="
echo "批量二值化 tests 目录中的图片"
echo "=========================================="
echo ""

# 计数器
count=0
total=$(ls tests/*.jpg 2>/dev/null | wc -l)

# 依次处理每张图片
for img in tests/*.jpg; do
    if [ -f "$img" ]; then
        count=$((count + 1))
        filename=$(basename "$img")

        echo "[$count/$total] 处理: $filename"

        # 运行二值化脚本
        python simple_binary.py "$img"

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
echo "二值化图片保存在 tests/ 目录，文件名格式: 原文件名_binary.jpg"
echo "=========================================="
