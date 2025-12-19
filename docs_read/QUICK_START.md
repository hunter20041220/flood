# 🚀 Kuro Siwo 快速入门指南

## 📌 1分钟了解项目

这是一个**NeurIPS 2024**发表的深度学习项目，用于从卫星雷达图像自动检测全球洪水区域。

---

## 🎯 核心概念

### 输入是什么？
**Sentinel-1 SAR卫星图像**（224×224像素）
- 洪水前2周图像
- 洪水前1周图像
- 洪水发生时图像

每张图2个通道：VV极化 + VH极化

### 输出是什么？
**分割掩码**（224×224像素），每个像素属于三类之一：
- **0**: 陆地（无水）
- **1**: 永久水体（湖泊/河流）
- **2**: 洪水区域（新出现的水）

### 数据集怎么组织？
```
KuroSiwo/data/
└── act_130/               # 激活ID（洪水事件编号）
    └── aoi_01/            # 兴趣区ID
        └── grid_00001/    # 图块ID
            ├── MS1_IVV.tif    # 洪水时VV
            ├── MS1_IVH.tif    # 洪水时VH
            ├── SL1_IVV.tif    # 洪水前1周VV
            ├── SL1_IVH.tif    # 洪水前1周VH
            ├── MK0_GND.tif    # 标注（真值）
            └── ...
```

---

## ⚡ 5分钟快速开始

### 步骤1：安装依赖
```bash
pip install -r requirements.txt
```

### 步骤2：下载数据集
```bash
chmod +x download_kuro_siwo.sh
./download_kuro_siwo.sh /path/to/save/data
```

### 步骤3：训练模型
```bash
# 训练最佳模型SNUNet
python main.py --method=snunet --batch_size=32

# 添加地形特征
python main.py --method=snunet --batch_size=32 --dem --slope
```

### 步骤4：测试模型
```bash
python main.py --method=snunet --test --resume_checkpoint=checkpoints/snunet/.../best.pt
```

---

## 📂 文件作用速查

| 文件 | 作用 | 是否必读 |
|------|------|----------|
| [main.py](main.py:1) | 程序入口，所有功能的起点 | ⭐⭐⭐ |
| [dataset/Dataset.py](dataset/Dataset.py:1) | 数据加载器，读取SAR图像 | ⭐⭐⭐ |
| [models/snunet.py](models/snunet.py:1) | 最佳模型实现（F1=0.85） | ⭐⭐⭐ |
| [training/segmentation_trainer.py](training/segmentation_trainer.py:1) | 训练流程 | ⭐⭐ |
| [configs/train/data_config.json](configs/train/data_config.json:1) | 数据集配置（训练/验证/测试划分） | ⭐⭐ |
| [utilities/utilities.py](utilities/utilities.py:1) | 辅助工具函数 | ⭐ |

---

## 🧠 可用模型一览

| 模型名 | 调用方式 | F1分数 | 速度 | 推荐度 |
|--------|----------|--------|------|--------|
| SNUNet | `--method=snunet` | 0.85 | 中 | ⭐⭐⭐⭐⭐ |
| ChangeFormer | `--method=changeformer` | 0.83 | 慢 | ⭐⭐⭐⭐ |
| U-Net | `--method=unet --backbone=resnet18` | 0.81 | 快 | ⭐⭐⭐⭐ |
| DeepLabV3+ | `--method=deeplabv3` | - | 中 | ⭐⭐⭐ |
| FloodViT | `--method=mae` | 0.87 | 慢 | ⭐⭐⭐⭐⭐ |

---

## 🎓 关键参数说明

### main.py命令行参数

```bash
python main.py \
  --method=snunet \           # 模型名称
  --backbone=resnet18 \       # 编码器骨干（仅U-Net/DeepLabV3需要）
  --batch_size=32 \           # 批次大小（根据GPU内存调整）
  --gpu=0 \                   # GPU ID
  --dem \                     # 添加高程数据
  --slope \                   # 添加坡度数据
  --test \                    # 测试模式（不训练）
  --resume_checkpoint=path/to/model.pt  # 恢复训练或测试
```

### configs/train/data_config.json核心字段

```json
{
  "train_acts": [130, 470, 555, ...],  // 训练用的洪水事件ID
  "val_acts": [514, 559, ...],         // 验证用的洪水事件ID
  "test_acts": [321, 561, ...],        // 测试用的洪水事件ID

  "inputs": ["pre_event_1", "pre_event_2", "post_event"],  // 时间点
  "channels": ["vv", "vh"],            // SAR通道

  "data_mean": [0.0953, 0.0264],       // 归一化均值
  "data_std": [0.0427, 0.0215],        // 归一化标准差

  "dem": true,                         // 是否使用高程
  "slope": false                       // 是否使用坡度
}
```

---

## 🔬 研究者常见任务

### 任务1：对比不同模型性能
```bash
# 依次训练多个模型
python main.py --method=snunet --batch_size=32
python main.py --method=changeformer --batch_size=32
python main.py --method=unet --backbone=resnet50 --batch_size=32

# 在WandB中对比结果
```

### 任务2：消融实验（DEM影响）
```bash
# 不使用DEM
python main.py --method=snunet --batch_size=32

# 使用DEM
python main.py --method=snunet --batch_size=32 --dem
```

### 任务3：跨气候带泛化性测试
修改 [configs/train/data_config.json](configs/train/data_config.json:1)：
```json
{
  "train_acts": [只包含热带的激活ID],
  "test_acts": [只包含寒带的激活ID]
}
```

### 任务4：少样本学习
```json
{
  "train_acts": [130, 470],  // 只用2个事件训练
  "test_acts": [...]         // 测试泛化能力
}
```

---

## 🐛 常见问题

### Q1: CUDA out of memory
**解决：** 降低batch_size
```bash
python main.py --method=snunet --batch_size=8
```

### Q2: FileNotFoundError: pickle文件不存在
**解决：** 检查data_config.json中的root_path设置
```json
{
  "root_path": "/正确的/数据集/路径/KuroSiwo/"
}
```

### Q3: 训练很慢
**解决：** 启用混合精度
在 [configs/config.json](configs/config.json:1) 中设置：
```json
{
  "mixed_precision": true
}
```

### Q4: WandB登录失败
**解决：** 禁用WandB
```json
{
  "wandb_activate": false
}
```

---

## 📊 输出文件位置

### 训练过程文件
```
checkpoints/
└── snunet/
    └── RandomEvents_20231215_143022/
        ├── best_segmentation.pt       # 最佳模型权重
        ├── last_segmentation.pt       # 最后一个epoch的权重
        ├── train_log.txt              # 训练日志
        └── config_backup.json         # 配置备份
```

### WandB云端日志
- 网址：https://wandb.ai/your-username/kuro-siwo
- 包含：训练曲线、验证指标、混淆矩阵

---

## 🔗 相关文档

| 文档 | 用途 |
|------|------|
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | 完整文件结构说明 |
| [项目结构详细说明.md](项目结构详细说明.md) | 中文详细教程（798行） |
| [README.md](README.md) | 官方英文说明 |
| 本文件 | 快速入门 |

---

## 📈 典型实验流程

```
1. 数据准备（运行download脚本）
   ↓
2. 配置修改（编辑data_config.json）
   ↓
3. 模型训练（运行main.py）
   ↓
4. 实时监控（WandB界面）
   ↓
5. 模型评估（--test模式）
   ↓
6. 结果分析（查看测试指标）
   ↓
7. 论文撰写（引用NeurIPS 2024论文）
```

---

## 🎯 推荐学习路径

### 初学者（1-2天）
1. 阅读本文档
2. 运行 `python main.py --method=unet --backbone=resnet18 --batch_size=8`
3. 观察训练过程和输出

### 进阶用户（3-5天）
1. 阅读 [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
2. 理解 [dataset/Dataset.py](dataset/Dataset.py:1) 数据加载流程
3. 对比多个模型性能
4. 尝试添加DEM特征

### 研究者（1-2周）
1. 阅读 [项目结构详细说明.md](项目结构详细说明.md)
2. 深入理解 [models/snunet.py](models/snunet.py:1) 架构
3. 修改 [training/segmentation_trainer.py](training/segmentation_trainer.py:1) 添加新指标
4. 实现自定义模型（参考现有模型）
5. 进行消融实验和泛化性测试

---

## 📧 联系与引用

**论文引用：**
```bibtex
@inproceedings{kurosiwo2024,
  title={Kuro Siwo: 33 billion $m^2$ under the water},
  booktitle={NeurIPS},
  year={2024}
}
```

**数据集许可：** CC BY
**代码许可：** MIT License

---

**祝你研究顺利！有问题请查阅详细文档或提Issue。**
