# inkcrop

将中国书法字帖切割成适合 A4 纸打印的 PDF 页面（支持竖向书法）。

## 功能特点

- **自动检测单个字符**区域（不是 OCR）
- **自动聚合成竖列**（从右到左，从上到下）
- **智能计算页面边界**：根据 A4 比例，自动计算每页应包含的内容
- **保持完整页面**：每页都是完整的字帖内容，不会被截断
- 生成适合打印的 PDF 文件
- 支持批量处理

## 工作原理

inkcrop **不做文字识别（OCR）**，而是：

1. **字符检测**：使用 OpenCV 检测所有墨迹区域
2. **列聚类**：将相近的字符聚合成竖列
3. **页面计算**：
   - 根据 A4 纸比例（√2:1）计算最佳页面大小
   - 确保每页包含完整的字符列
   - 向下取整，避免截断
4. **裁剪提取**：从原图裁剪出完整页面
5. **生成 PDF**：每页作为一页 PDF

## 安装

```bash
# 安装依赖
pip install -r requirements.txt
```

### 依赖

- OpenCV (opencv-python) - 图像处理
- NumPy - 数组操作
- Pillow - 图像格式处理
- fpdf - PDF 生成

## 使用方法

### 快速开始

```bash
# 使用便捷脚本（推荐）
./inkcrop.py your_calligraphy.jpg -o output.pdf

# 显示详细信息
./inkcrop.py your_calligraphy.jpg -o output.pdf -v

# 保存调试图片
./inkcrop.py your_calligraphy.jpg -o output.pdf --debug
```

### 命令行参数

```bash
# 基本用法
./inkcrop.py input.jpg -o output.pdf

# 显示处理信息
./inkcrop.py input.jpg -o output.pdf -v

# 自定义每页最少/最多字符数
./inkcrop.py input.jpg -o output.pdf --min-chars-per-page 5 --max-chars-per-page 50

# 批量处理多个图片
./inkcrop.py *.jpg -o output_dir/

# 高分辨率输出
./inkcrop.py input.jpg -o output.pdf --dpi 600
```

### 参数说明

- `inputs`: 输入图片路径（必需）
- `-o, --output`: 输出 PDF 路径或目录（必需）
- `--dpi`: 输出 DPI（默认 300）
- `--min-chars-per-page`: 每页最少字符数（默认 2）
- `--max-chars-per-page`: 每页最多字符数（默认 100）
- `-v, --verbose`: 显示详细处理信息

### 作为 Python 库使用

```python
from inkcrop.processor import CalligraphyProcessor
from inkcrop.detector import VerticalColumnDetector

# 创建检测器
detector = VerticalColumnDetector(
    column_merge_threshold=100,  # 同列字符的最大水平距离
)

# 创建处理器
processor = CalligraphyProcessor(
    detector=detector,
    dpi=300,
    min_chars_per_page=2,
    max_chars_per_page=100,
)

# 处理图片
result = processor.process(
    "input.jpg",
    "output.pdf",
)

print(f"检测到 {result['num_characters']} 个字符")
print(f"生成 {result['num_columns']} 列")
print(f"输出 {result['num_pages']} 页")
```

## 适用场景

- 竖向书法字帖扫描件裁剪
- 诗词作品整理
- 拓片数字化
- 任何需要从扫描件中提取完整字帖页面的场景

## 算法详解

### 1. 字符检测
- 使用 Otsu 自动阈值二值化
- 形态学操作去除噪声
- 轮廓检测找到所有字符区域

### 2. 列聚类
- 按字符 X 坐标分组（竖列）
- 使用水平距离阈值判断是否同列
- 每列内部按 Y 坐标排序（从上到下）
- 列之间按 X 坐标排序（从右到左）

### 3. 页面计算
- A4 纸比例：高/宽 = 297/210 ≈ √2
- 遍历可能的列组合
- 选择最接近 A4 比例的组合
- 向下取整字符数量

### 4. 裁剪提取
- 根据计算出的边界裁剪
- 每页保持原始分辨率
- 不缩放，不变形

## 测试

```bash
# 运行示例
python example_vertical.py

# 查看测试输出
./inkcrop.py tests/元\ 赵孟頫\ 归去来辞行书纸本26x239湖州博物馆.jpg -o test.pdf --debug -v
```

## 注意事项

1. 这个工具**不识别文字内容**，只是检测墨迹区域
2. 适用于有清晰墨迹的书法作品
3. 如果背景复杂，可能需要调整检测参数
4. 默认参数适用于大多数标准字帖扫描件

## 许可证

MIT License
