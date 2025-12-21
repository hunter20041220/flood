# 洪水淹没农田提取系统

**版本**: v1.0 (严格ESA农田定义)
**作者**: Linus Torvalds (Claude Sonnet 4.5)
**日期**: 2025-12-21

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置GEE

```bash
earthengine authenticate
# 或在Python中: ee.Authenticate()
```

### 3. 下载WorldCover数据

```bash
python download_worldcover_agricultural.py
```

### 4. 批量处理

```bash
python batch_process.py
```

### 5. 查看结果

```bash
# 查看汇总报告
cat ../results/summary_report.json

# 查看可视化
explorer ../results/[tile_id]/visualization.png
```

---

## 文件说明

### 核心脚本

| 文件 | 说明 |
|------|------|
| `download_worldcover_agricultural.py` | 从GEE下载WorldCover农田数据 |
| `batch_process.py` | 批量处理提取被淹没农田 |
| `feasibility_check.py` | 可行性验证脚本（参考） |

### 文档

| 文件 | 说明 |
|------|------|
| `README.md` | 本文档（快速入门） |
| `使用说明.md` | 完整使用手册 |
| `requirements.txt` | Python依赖列表 |

### 测试报告

| 文件 | 说明 |
|------|------|
| `TEST_REPORT_STRICT.md` | 严格定义测试报告 |
| `TEST_REPORT_REALDATA.md` | 扩展定义测试报告 |
| `TEST_REPORT.md` | 模拟数据测试报告 |

---

## 系统架构

```
输入数据
├── 洪水掩膜 (MLU)              ─┐
│   └── class 2 = 洪水           │
└── WorldCover农田掩膜           │
    └── class 40 = 农田          ├─→ 交集运算 ─→ 被淹没农田
                                 │
处理流程                         │
├── 1. 下载WorldCover           │
├── 2. 提取洪水区域             ─┘
├── 3. 提取农田区域
├── 4. 计算交集
└── 5. 生成统计和可视化

输出结果
├── flooded_cropland_mask.tif   # 被淹没农田掩膜
├── visualization.png            # 可视化图
└── summary_report.json          # 统计报告
```

---

## 重要说明

### ⚠️ 该地区数据特征

**尼加拉瓜测试区域**按ESA WorldCover分类:
- 森林: ~50-80%
- 湿地: ~10-70%
- 草地: ~1-9%
- **农田(class 40): <0.001%** ← 极少

**结果**: 10个测试tiles中仅1个包含1像素农田，且不在洪水区域。

### 解决方案

**选项A**: 使用扩展定义（包含草地+湿地）
- 修改代码包含class 30和90
- 适合研究广义农业用地

**选项B**: 更换研究区域
- 选择WorldCover中class 40占比高的区域
- 如: 中国东部、美国中西部

**选项C**: 调整研究问题
- "洪水对湿地的影响"
- "洪水对草地的影响"

---

## 核心定义

### 严格农田定义

```python
# ESA WorldCover class 40 only
CROPLAND_CLASS = 40  # Cropland (农田)
```

**排除**:
- class 30: Grassland (草地)
- class 90: Herbaceous wetland (草本湿地)

### 交集运算

```python
# 被淹没农田 = 洪水 AND 农田
flooded_cropland = (MLU == 2) & (WorldCover == 40)
```

---

## 输入输出

### 输入

**洪水数据** (已提供):
```
../01/[tile_id]/MK0_MLU_1111008_01_20200816.tif
  └── 0=陆地, 1=永久水体, 2=洪水, 3=NoData
```

**WorldCover数据** (需下载):
```
../worldcover_tiles/[tile_id]/cropland_strict_mask.tif
  └── 0=非农田, 255=农田(class 40)
```

### 输出

```
../results/
├── summary_report.json              # 汇总统计
└── [tile_id]/
    ├── flooded_cropland_mask.tif    # 被淹没农田掩膜
    ├── visualization.png            # 可视化
    │   ├── 黄色: 农田
    │   ├── 蓝色: 洪水
    │   └── 红色: 被淹没农田
    └── stats.json                   # 单tile统计
```

---

## 配置参数

### GEE项目ID

编辑 `download_worldcover_agricultural.py` 第18行:
```python
PROJECT_ID = 'neat-iterator-474909-s2'  # 替换为你的项目ID
```

### 下载数量

编辑 `download_worldcover_agricultural.py` 第165行:
```python
def batch_download(flood_dir, output_dir, max_tiles=10):  # 修改数量
```

### 输入输出路径

编辑 `batch_process.py` 第39-48行:
```python
CONFIG = {
    'flood_dir': r'H:\FLOOD RISK\01',       # 洪水数据目录
    'output_dir': r'H:\FLOOD RISK\results', # 输出目录
    ...
}
```

---

## 性能指标

| 操作 | 时间 | 说明 |
|------|------|------|
| 下载单tile | ~3秒 | 需网络连接GEE |
| 处理单tile | ~0.2秒 | 本地计算 |
| 10个tiles | ~35秒 | 下载30秒+处理5秒 |

---

## 常见问题

### Q: GEE认证失败

```bash
earthengine authenticate
# 或
python -c "import ee; ee.Authenticate()"
```

### Q: 下载超时

```python
# 修改timeout参数（第98行）
response = requests.get(url, timeout=300)  # 增加到5分钟
```

### Q: 无农田数据

**原因**: 该地区按ESA分类无传统农田
**解决**: 见上述"解决方案"

---

## 技术栈

- Python 3.8+
- Google Earth Engine API
- ESA WorldCover 10m v100
- Sentinel-1 SAR洪水数据

---

## 引用

**数据来源**:
- Copernicus EMS: EMSR457 (洪水)
- ESA WorldCover: Zanaga et al. (2021), DOI: 10.5281/zenodo.5571936

---

## 详细文档

完整使用手册请查看 `使用说明.md`

---

**状态**: ✓ 代码已测试
**适用**: 严格ESA农田定义
**注意**: 该地区无可分析数据
