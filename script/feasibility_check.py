"""
可行性验证：提取被洪水淹没的农田范围

方案设计：
1. 洪水掩膜 (MLU): 值2 = 洪水区域
2. 农田掩膜 (开源数据): 农田类别
3. 操作: 交集 (AND) - 同时满足"是洪水"且"是农田"
4. 输出: 被淹没的农田范围

开源农田数据源（按优先级）:
- ESA WorldCover 10m (2020/2021): 类别40 = Cropland
- Google Dynamic World 10m: 类别4 = Crops
- ESA CCI Land Cover 300m: 类别10-40 = 各种农田类型
"""

import numpy as np
from PIL import Image
import os

def analyze_flood_mask(mlu_path):
    """分析洪水掩膜"""
    mlu = np.array(Image.open(mlu_path))

    flood_mask = (mlu == 2).astype(np.uint8)
    permanent_water = (mlu == 1).astype(np.uint8)
    land = (mlu == 0).astype(np.uint8)
    nodata = (mlu == 3).astype(np.uint8)

    total_pixels = mlu.size
    stats = {
        'land': np.sum(land),
        'permanent_water': np.sum(permanent_water),
        'flood': np.sum(flood_mask),
        'nodata': np.sum(nodata),
        'total': total_pixels
    }

    print(f"洪水掩膜统计 ({os.path.basename(os.path.dirname(mlu_path))})")
    print(f"  陆地 (0):      {stats['land']:6d} ({stats['land']/total_pixels*100:5.2f}%)")
    print(f"  永久水体 (1):  {stats['permanent_water']:6d} ({stats['permanent_water']/total_pixels*100:5.2f}%)")
    print(f"  洪水 (2):      {stats['flood']:6d} ({stats['flood']/total_pixels*100:5.2f}%)")
    print(f"  无数据 (3):    {stats['nodata']:6d} ({stats['nodata']/total_pixels*100:5.2f}%)")

    return flood_mask, stats


def simulate_cropland_mask(shape, flood_mask, scenario='random'):
    """
    模拟农田掩膜（实际应使用ESA WorldCover等数据）

    场景:
    - random: 随机50%陆地为农田
    - realistic: 基于地形模拟（低洼平坦区域更可能是农田）
    """
    if scenario == 'random':
        # 简单随机：50%陆地为农田
        cropland = np.random.rand(*shape) > 0.5

    elif scenario == 'realistic':
        # 更真实：洪水区域周边更可能是农田（河谷平原）
        from scipy import ndimage
        # 洪水区域膨胀10像素，模拟河谷平原
        flood_dilated = ndimage.binary_dilation(flood_mask, iterations=10)
        # 在河谷平原内随机80%为农田，其他区域20%
        cropland = np.where(
            flood_dilated,
            np.random.rand(*shape) > 0.2,
            np.random.rand(*shape) > 0.8
        )

    return cropland.astype(np.uint8)


def extract_flooded_cropland(flood_mask, cropland_mask):
    """提取被淹没农田：交集操作"""
    flooded_cropland = np.logical_and(flood_mask, cropland_mask).astype(np.uint8)

    flood_pixels = np.sum(flood_mask)
    cropland_pixels = np.sum(cropland_mask)
    flooded_cropland_pixels = np.sum(flooded_cropland)

    print("\n交集运算结果:")
    print(f"  洪水总面积:           {flood_pixels:6d} 像素")
    print(f"  农田总面积:           {cropland_pixels:6d} 像素")
    print(f"  被淹没农田面积:       {flooded_cropland_pixels:6d} 像素")

    if flood_pixels > 0:
        print(f"  洪水中农田占比:       {flooded_cropland_pixels/flood_pixels*100:5.2f}%")
    if cropland_pixels > 0:
        print(f"  农田被淹没比例:       {flooded_cropland_pixels/cropland_pixels*100:5.2f}%")

    return flooded_cropland


def visualize_results(flood_mask, cropland_mask, flooded_cropland, output_path):
    """可视化结果"""
    h, w = flood_mask.shape

    # 创建RGB图像
    vis = np.zeros((h, w, 3), dtype=np.uint8)

    # 蓝色: 洪水
    vis[flood_mask == 1] = [0, 100, 255]

    # 黄色: 农田
    vis[cropland_mask == 1] = [255, 255, 0]

    # 红色: 被淹没农田（优先级最高）
    vis[flooded_cropland == 1] = [255, 0, 0]

    Image.fromarray(vis).save(output_path)
    print(f"\n可视化结果已保存: {output_path}")


if __name__ == '__main__':
    # 测试数据路径
    base_path = r'H:\FLOOD RISK\01'

    # 选择一个有洪水的tile
    test_dir = '0186935b5e345eaf8257eaafc3fa3875'
    mlu_path = os.path.join(base_path, test_dir, 'MK0_MLU_1111008_01_20200816.tif')

    if not os.path.exists(mlu_path):
        print(f"错误: 文件不存在 {mlu_path}")
        exit(1)

    print("=" * 60)
    print("可行性验证: 提取被洪水淹没的农田")
    print("=" * 60)

    # 步骤1: 分析洪水掩膜
    flood_mask, stats = analyze_flood_mask(mlu_path)

    if stats['flood'] == 0:
        print("\n警告: 该tile无洪水，选择另一个tile")
        exit(0)

    # 步骤2: 模拟农田掩膜（实际应使用ESA WorldCover）
    print("\n[模拟] 生成农田掩膜 (实际应使用ESA WorldCover 10m数据)")
    print("  使用'realistic'场景: 河谷平原80%为农田")

    try:
        cropland_mask = simulate_cropland_mask(
            flood_mask.shape,
            flood_mask,
            scenario='realistic'
        )
    except ImportError:
        print("  警告: scipy未安装，使用random场景")
        cropland_mask = simulate_cropland_mask(
            flood_mask.shape,
            flood_mask,
            scenario='random'
        )

    cropland_pixels = np.sum(cropland_mask)
    print(f"  农田像素数: {cropland_pixels}")

    # 步骤3: 交集运算
    flooded_cropland = extract_flooded_cropland(flood_mask, cropland_mask)

    # 步骤4: 可视化
    output_path = os.path.join(base_path, test_dir, 'flooded_cropland_visualization.png')
    visualize_results(flood_mask, cropland_mask, flooded_cropland, output_path)

    # 步骤5: 保存结果
    result_path = os.path.join(base_path, test_dir, 'flooded_cropland_mask.tif')
    Image.fromarray(flooded_cropland * 255).save(result_path)
    print(f"结果掩膜已保存: {result_path}")

    print("\n" + "=" * 60)
    print("结论:")
    print("  ✓ 方案技术可行")
    print("  ✓ 正确操作是交集 (AND)，非并集")
    print("  ✓ 需要获取ESA WorldCover 10m农田数据")
    print("  ✓ 需要确保空间配准一致")
    print("=" * 60)
