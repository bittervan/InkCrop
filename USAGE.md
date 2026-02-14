# inkcrop 使用示例

## 最简单的用法

```bash
# 设置环境变量（只需一次）
export PYTHONPATH=/home/bittervan/Code/inkcrop/src:$PYTHONPATH

# 处理一张图片，输出 PDF（静默模式，无额外输出）
python -m inkcrop.cli your_calligraphy.jpg -o output.pdf
```

## 实际使用场景

### 场景 1：处理单张字帖

```bash
# 基本用法
python -m inkcrop.cli 字帖.jpg -o 字帖_整理.pdf

# 查看详细信息
python -m inkcrop.cli 字帖.jpg -o 字帖_整理.pdf -v
```

### 场景 2：调整布局

```bash
# 每页 5 列 x 12 行（适合较小的字符）
python -m inkcrop.cli 字帖.jpg -o 字帖_整理.pdf --grid-cols 5 --grid-rows 12

# 增大字符边距到 50px
python -m inkcrop.cli 字帖.jpg -o 字帖_整理.pdf --char-margin 50
```

### 场景 3：批量处理

```bash
# 批量处理目录下所有 jpg 文件，输出到 output_dir/
python -m inkcrop.cli *.jpg -o output_dir/

# 查看批量处理结果
python -m inkcrop.cli *.jpg -o output_dir/ -v
```

### 场景 4：高质量输出

```bash
# 600 DPI 高分辨率输出
python -m inkcrop.cli 字帖.jpg -o 字帖_HD.pdf --dpi 600
```

## 输出说明

- **默认模式**：只生成 PDF 文件，无其他输出
- **verbose 模式**（`-v`）：显示处理过程中的详细信息
- **调试模式**（`--debug`，隐藏选项）：生成调试图片

## 文件组织

处理后的文件结构：

```
your_folder/
├── 字帖.jpg          # 原始字帖
└── 字帖_整理.pdf     # 生成的 PDF（可直接打印）
```

批量处理时：

```
your_folder/
├── 字帖1.jpg
├── 字帖2.jpg
├── 字帖3.jpg
└── output_dir/        # 输出目录
    ├── 字帖1.pdf
    ├── 字帖2.pdf
    └── 字帖3.pdf
```

## 常见问题

**Q: 检测不到字符？**
A: 调整 `min_char_size` 参数，或者先在图像处理软件中调整对比度

**Q: 字符被切断了？**
A: 增大 `--char-margin` 参数

**Q: 每页字符太少或太多？**
A: 调整 `--grid-cols` 和 `--grid-rows` 参数

**Q: 输出质量不够？**
A: 使用 `--dpi 600` 提高分辨率
