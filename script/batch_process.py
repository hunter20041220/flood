"""
批量处理脚本: 从所有洪水tile提取被淹没农田

前置条件:
1. 已从GEE下载ESA WorldCover数据到本地
2. 已安装依赖: pip install numpy pillow rasterio scipy tqdm
"""

import numpy as np
from PIL import Image
import os
import json
from pathlib import Path
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

# 可选: 用于地理配准
try:
    import rasterio
    from rasterio.warp import reproject, Resampling
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False
    print("警告: rasterio未安装，将跳过地理配准步骤")

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    tqdm = lambda x, **kwargs: x


# ============================================================
# 配置
# ============================================================

CONFIG = {
    'flood_dir': r'H:\FLOOD RISK\01',
    'worldcover_path': r'H:\FLOOD RISK\worldcover_cropland.tif',  # 从GEE下载的文件
    'output_dir': r'H:\FLOOD RISK\results',
    'mlu_filename': 'MK0_MLU_1111008_01_20200816.tif',
    'flood_class': 2,      # MLU中洪水的值
    'cropland_class': 40,  # WorldCover中农田的值 (如果是完整数据)
    # 如果下载的是二值掩膜(0/255), 设置为255
    'pixel_size_m': 10,    # 像元大小(米)
}


# ============================================================
# 工具函数
# ============================================================

def load_real_worldcover(tile_dir, worldcover_tiles_dir):
    """
    加载真实WorldCover农田数据（严格定义）

    Args:
        tile_dir: tile目录
        worldcover_tiles_dir: WorldCover数据目录

    Returns:
        cropland_mask: 农田掩膜 (0或1)，仅class 40: Cropland
    """
    tile_name = tile_dir.name

    # 优先使用严格定义的农田掩膜
    mask_path_strict = worldcover_tiles_dir / tile_name / 'cropland_strict_mask.tif'

    if mask_path_strict.exists():
        mask_data = np.array(Image.open(mask_path_strict))
        # 转换255 -> 1
        cropland_mask = (mask_data > 0).astype(np.uint8)
        return cropland_mask

    # Fallback: 旧的扩展定义（兼容性）
    mask_path_old = worldcover_tiles_dir / tile_name / 'agricultural_mask.tif'
    if mask_path_old.exists():
        mask_data = np.array(Image.open(mask_path_old))
        cropland_mask = (mask_data > 0).astype(np.uint8)
        return cropland_mask

    return None


def simulate_cropland_mask(shape, flood_mask, scenario='realistic'):
    """
    模拟农田掩膜（实际应使用ESA WorldCover等数据）

    场景:
    - random: 随机50%陆地为农田
    - realistic: 基于地形模拟（低洼平坦区域更可能是农田）
    """
    if scenario == 'random':
        cropland = np.random.rand(*shape) > 0.5
    elif scenario == 'realistic':
        try:
            from scipy import ndimage
            # 洪水区域膨胀10像素，模拟河谷平原
            flood_dilated = ndimage.binary_dilation(flood_mask, iterations=10)
            # 在河谷平原内随机80%为农田，其他区域20%
            cropland = np.where(
                flood_dilated,
                np.random.rand(*shape) > 0.2,
                np.random.rand(*shape) > 0.8
            )
        except ImportError:
            # scipy未安装，使用random模式
            cropland = np.random.rand(*shape) > 0.5
    else:
        cropland = np.random.rand(*shape) > 0.5

    return cropland.astype(np.uint8)


def load_tile_info(tile_dir: Path) -> Dict:
    """加载tile的元数据"""
    info_path = tile_dir / 'info.json'
    if info_path.exists():
        with open(info_path, 'r') as f:
            return json.load(f)
    return {}


def extract_flood_mask(mlu_path: Path) -> Tuple[np.ndarray, Dict]:
    """从MLU提取洪水掩膜"""
    mlu = np.array(Image.open(mlu_path))

    flood_mask = (mlu == CONFIG['flood_class']).astype(np.uint8)

    stats = {
        'land': np.sum(mlu == 0),
        'permanent_water': np.sum(mlu == 1),
        'flood': np.sum(mlu == 2),
        'nodata': np.sum(mlu == 3),
        'total': mlu.size
    }

    return flood_mask, stats


def load_cropland_for_tile(tile_info: Dict, worldcover_path: Path) -> np.ndarray:
    """
    为特定tile加载对应的农田掩膜

    方法:
    1. 如果WorldCover已按tile分割 → 直接加载
    2. 如果是完整区域 → 根据geom裁剪
    3. 简化版 → 模拟数据(仅用于测试)
    """

    if not worldcover_path.exists():
        raise FileNotFoundError(f"WorldCover文件不存在: {worldcover_path}")

    # 简化版: 假设WorldCover已经按tile分割好，文件名对应
    # 实际使用中需要用rasterio根据geom裁剪

    if HAS_RASTERIO:
        # TODO: 实现基于geom的裁剪和重投影
        # with rasterio.open(worldcover_path) as src:
        #     window = from_bounds(*bounds, src.transform)
        #     cropland = src.read(1, window=window)
        pass

    # 临时方案: 加载完整WorldCover并假设已配准
    worldcover = np.array(Image.open(worldcover_path))

    # 如果是完整类别数据，提取农田
    if worldcover.max() > 100:
        # 二值掩膜(0/255)
        cropland_mask = (worldcover > 0).astype(np.uint8)
    else:
        # 分类数据
        cropland_mask = (worldcover == CONFIG['cropland_class']).astype(np.uint8)

    return cropland_mask


def extract_flooded_cropland(flood_mask: np.ndarray,
                             cropland_mask: np.ndarray) -> Tuple[np.ndarray, Dict]:
    """
    交集运算: 提取被淹没的农田

    Returns:
        flooded_cropland: 二值掩膜 (1=被淹没农田)
        stats: 统计信息字典
    """
    # 确保两个掩膜尺寸一致
    if flood_mask.shape != cropland_mask.shape:
        raise ValueError(f"尺寸不匹配: flood={flood_mask.shape}, cropland={cropland_mask.shape}")

    # 交集 (AND)
    flooded_cropland = np.logical_and(flood_mask, cropland_mask).astype(np.uint8)

    # 统计
    flood_pixels = np.sum(flood_mask)
    cropland_pixels = np.sum(cropland_mask)
    flooded_cropland_pixels = np.sum(flooded_cropland)

    pixel_area_m2 = CONFIG['pixel_size_m'] ** 2

    stats = {
        'flood_pixels': int(flood_pixels),
        'cropland_pixels': int(cropland_pixels),
        'flooded_cropland_pixels': int(flooded_cropland_pixels),
        'flood_area_m2': float(flood_pixels * pixel_area_m2),
        'cropland_area_m2': float(cropland_pixels * pixel_area_m2),
        'flooded_cropland_area_m2': float(flooded_cropland_pixels * pixel_area_m2),
        'flood_cropland_ratio': float(flooded_cropland_pixels / flood_pixels) if flood_pixels > 0 else 0,
        'cropland_flooded_ratio': float(flooded_cropland_pixels / cropland_pixels) if cropland_pixels > 0 else 0,
    }

    return flooded_cropland, stats


def create_visualization(flood_mask: np.ndarray,
                        cropland_mask: np.ndarray,
                        flooded_cropland: np.ndarray) -> np.ndarray:
    """创建RGB可视化图"""
    h, w = flood_mask.shape
    vis = np.zeros((h, w, 3), dtype=np.uint8)

    # 背景: 黑色
    # 农田: 黄色
    vis[cropland_mask == 1] = [255, 255, 0]
    # 洪水: 蓝色
    vis[flood_mask == 1] = [50, 150, 255]
    # 被淹没农田: 红色 (优先级最高)
    vis[flooded_cropland == 1] = [255, 50, 50]

    return vis


def process_single_tile(tile_dir: Path,
                       worldcover_path: Path,
                       output_dir: Path) -> Dict:
    """处理单个tile"""

    tile_name = tile_dir.name
    mlu_path = tile_dir / CONFIG['mlu_filename']

    if not mlu_path.exists():
        return {'status': 'skip', 'reason': 'MLU file not found'}

    # 加载元数据
    tile_info = load_tile_info(tile_dir)

    # 提取洪水掩膜
    flood_mask, flood_stats = extract_flood_mask(mlu_path)

    # 如果无洪水，跳过
    if flood_stats['flood'] == 0:
        return {
            'status': 'skip',
            'reason': 'no flood',
            'tile_name': tile_name,
            **flood_stats
        }

    # 加载农业用地掩膜
    try:
        # 优先使用真实WorldCover数据
        worldcover_dir = Path(r'H:\FLOOD RISK\worldcover_tiles')
        cropland_mask = load_real_worldcover(tile_dir, worldcover_dir)

        if cropland_mask is not None:
            data_source = 'WorldCover'
        else:
            # Fallback: 使用模拟数据
            cropland_mask = simulate_cropland_mask(flood_mask.shape, flood_mask, 'realistic')
            data_source = 'simulated'

    except Exception as e:
        return {
            'status': 'error',
            'reason': f'cropland loading failed: {e}',
            'tile_name': tile_name
        }

    # 提取被淹没农田
    flooded_cropland, extraction_stats = extract_flooded_cropland(flood_mask, cropland_mask)

    # 创建输出目录
    tile_output_dir = output_dir / tile_name
    tile_output_dir.mkdir(parents=True, exist_ok=True)

    # 保存结果掩膜
    result_path = tile_output_dir / 'flooded_cropland_mask.tif'
    Image.fromarray(flooded_cropland * 255).save(result_path)

    # 保存可视化
    vis = create_visualization(flood_mask, cropland_mask, flooded_cropland)
    vis_path = tile_output_dir / 'visualization.png'
    Image.fromarray(vis).save(vis_path)

    # 保存统计（转换numpy类型为Python原生类型）
    stats = {
        'status': 'success',
        'tile_name': tile_name,
        'flood_date': tile_info.get('flood_date'),
        'data_source': data_source,  # 'WorldCover' or 'simulated'
    }

    # 合并flood_stats和extraction_stats，转换类型
    for key, value in {**flood_stats, **extraction_stats}.items():
        if isinstance(value, (np.integer, np.int64, np.int32)):
            stats[key] = int(value)
        elif isinstance(value, (np.floating, np.float64, np.float32)):
            stats[key] = float(value)
        else:
            stats[key] = value

    stats_path = tile_output_dir / 'stats.json'
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)

    return stats


def batch_process_all_tiles(flood_dir: Path,
                            worldcover_path: Path,
                            output_dir: Path) -> List[Dict]:
    """批量处理所有tiles"""

    # 获取所有tile目录
    tile_dirs = [d for d in flood_dir.iterdir() if d.is_dir()]

    print(f"找到 {len(tile_dirs)} 个tiles")
    print(f"WorldCover路径: {worldcover_path}")
    print(f"输出目录: {output_dir}")
    print()

    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)

    # 批量处理
    results = []
    iterator = tqdm(tile_dirs, desc="处理tiles") if HAS_TQDM else tile_dirs

    for tile_dir in iterator:
        result = process_single_tile(tile_dir, worldcover_path, output_dir)
        results.append(result)

        if HAS_TQDM and result['status'] == 'success':
            iterator.set_postfix({
                'flooded_cropland': f"{result['flooded_cropland_pixels']}px"
            })

    return results


def generate_summary_report(results: List[Dict], output_path: Path):
    """生成汇总报告"""

    success_results = [r for r in results if r['status'] == 'success']

    total_stats = {
        'total_tiles': int(len(results)),
        'success_tiles': int(len(success_results)),
        'tiles_with_flood': int(len([r for r in success_results if r.get('flood_pixels', 0) > 0])),
        'total_flood_pixels': int(sum(r.get('flood_pixels', 0) for r in success_results)),
        'total_cropland_pixels': int(sum(r.get('cropland_pixels', 0) for r in success_results)),
        'total_flooded_cropland_pixels': int(sum(r.get('flooded_cropland_pixels', 0) for r in success_results)),
    }

    pixel_area_km2 = (CONFIG['pixel_size_m'] ** 2) / 1e6

    total_stats.update({
        'total_flood_area_km2': float(total_stats['total_flood_pixels'] * pixel_area_km2),
        'total_cropland_area_km2': float(total_stats['total_cropland_pixels'] * pixel_area_km2),
        'total_flooded_cropland_area_km2': float(total_stats['total_flooded_cropland_pixels'] * pixel_area_km2),
    })

    # 转换results中所有numpy类型为Python原生类型
    def convert_types(obj):
        if isinstance(obj, dict):
            return {k: convert_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_types(v) for v in obj]
        elif isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        else:
            return obj

    # 保存JSON
    with open(output_path, 'w') as f:
        json.dump({
            'summary': total_stats,
            'per_tile_results': convert_types(results)
        }, f, indent=2)

    # 打印摘要
    print("\n" + "=" * 60)
    print("处理完成！汇总统计:")
    print("=" * 60)
    print(f"总tiles数:           {total_stats['total_tiles']}")
    print(f"成功处理:           {total_stats['success_tiles']}")
    print(f"包含洪水:           {total_stats['tiles_with_flood']}")
    print(f"洪水总面积:         {total_stats['total_flood_area_km2']:.2f} km^2")
    print(f"农田总面积:         {total_stats['total_cropland_area_km2']:.2f} km^2")
    print(f"被淹没农田面积:     {total_stats['total_flooded_cropland_area_km2']:.2f} km^2")

    if total_stats['total_flood_pixels'] > 0:
        ratio = (total_stats['total_flooded_cropland_pixels'] /
                total_stats['total_flood_pixels'] * 100)
        print(f"洪水中农田占比:     {ratio:.2f}%")

    print("=" * 60)
    print(f"详细报告已保存: {output_path}")


# ============================================================
# 主程序
# ============================================================

if __name__ == '__main__':

    flood_dir = Path(CONFIG['flood_dir'])
    worldcover_path = Path(CONFIG['worldcover_path'])
    output_dir = Path(CONFIG['output_dir'])

    print("=" * 60)
    print("批量提取被洪水淹没的农田")
    print("=" * 60)
    print()

    # 检查输入
    if not flood_dir.exists():
        print(f"错误: 洪水数据目录不存在: {flood_dir}")
        exit(1)

    if not worldcover_path.exists():
        print(f"警告: WorldCover文件不存在: {worldcover_path}")
        print("将使用模拟农田数据进行测试")
        print()

    # 批量处理
    results = batch_process_all_tiles(flood_dir, worldcover_path, output_dir)

    # 生成报告
    report_path = output_dir / 'summary_report.json'
    generate_summary_report(results, report_path)

    print("\n所有处理完成！")
