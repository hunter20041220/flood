"""
下载WorldCover农田数据（严格定义）

严格按照ESA WorldCover定义:
- 40: Cropland (农田) - 仅此一类

注意：该地区(尼加拉瓜)WorldCover中Cropland分类极少
"""

import ee
import requests
import numpy as np
from PIL import Image
from pathlib import Path
import json
import math

PROJECT_ID = 'neat-iterator-474909-s2'

# 严格农田定义：仅ESA Cropland类别
CROPLAND_CLASS = 40  # 仅Cropland


def mercator_to_wgs84(x, y):
    lon = x / 20037508.34 * 180
    lat = math.atan(math.sinh(y / 20037508.34 * math.pi)) * 180 / math.pi
    return lon, lat


def get_tile_bounds_wgs84(tile_dir):
    info_path = tile_dir / 'info.json'
    with open(info_path, 'r') as f:
        info = json.load(f)

    geom = info.get('geom', '')
    import re
    coords = re.findall(r'(-?\d+\.?\d*)\s+(-?\d+\.?\d*)', geom)

    lons, lats = [], []
    for x, y in coords:
        lon, lat = mercator_to_wgs84(float(x), float(y))
        lons.append(lon)
        lats.append(lat)

    bounds = [min(lons), min(lats), max(lons), max(lats)]
    return bounds, info


def download_worldcover_cropland_strict(tile_dir, output_dir):
    """
    下载WorldCover农田数据（严格定义：仅class 40）

    Args:
        tile_dir: tile目录
        output_dir: 输出目录

    Returns:
        cropland_mask: 农田掩膜 (0或1)，仅包含class 40
        class_stats: 各类别统计
    """

    # 初始化GEE
    try:
        ee.Initialize(project=PROJECT_ID)
    except:
        ee.Initialize()

    # 获取tile边界
    bounds, info = get_tile_bounds_wgs84(tile_dir)
    tile_name = tile_dir.name

    print(f'\n处理tile: {tile_name[:20]}...')

    # 创建几何
    buffer = 0.001
    region = ee.Geometry.Rectangle([
        bounds[0] - buffer,
        bounds[1] - buffer,
        bounds[2] + buffer,
        bounds[3] + buffer
    ])

    # 加载WorldCover完整分类
    worldcover = ee.ImageCollection('ESA/WorldCover/v100').first()
    worldcover_clipped = worldcover.select('Map').clip(region).reproject(
        crs='EPSG:3857',
        scale=10
    )

    # 下载完整分类数据
    url = worldcover_clipped.getDownloadURL({
        'region': region,
        'dimensions': '224x224',
        'format': 'GEO_TIFF',
        'crs': 'EPSG:3857'
    })

    response = requests.get(url, timeout=60)

    # 保存完整分类
    full_path = output_dir / tile_name / 'worldcover_full.tif'
    full_path.parent.mkdir(parents=True, exist_ok=True)

    with open(full_path, 'wb') as f:
        f.write(response.content)

    # 读取并分析
    data = np.array(Image.open(full_path))

    # 统计各类别
    unique_vals = np.unique(data)
    class_stats = {}

    class_names = {
        10: 'Tree cover',
        20: 'Shrubland',
        30: 'Grassland',
        40: 'Cropland',  # 仅此类别为农田
        50: 'Built-up',
        60: 'Bare/sparse vegetation',
        70: 'Snow and ice',
        80: 'Permanent water bodies',
        90: 'Herbaceous wetland',
        95: 'Mangroves',
        100: 'Moss and lichen'
    }

    print('  WorldCover分类:')
    for val in unique_vals:
        count = int(np.sum(data == val))
        pct = count / data.size * 100
        name = class_names.get(val, 'Unknown')
        class_stats[int(val)] = {
            'name': name,
            'pixels': count,
            'percentage': float(pct)
        }
        marker = '***' if val == CROPLAND_CLASS else '   '
        print(f'  {marker} {val}: {name} - {count}px ({pct:.1f}%)')

    # 创建农田掩膜（严格：仅class 40）
    cropland_mask = (data == CROPLAND_CLASS).astype(np.uint8)

    total_cropland = int(np.sum(cropland_mask))
    print(f'  严格农田(class 40): {total_cropland}px ({total_cropland/data.size*100:.1f}%)')

    # 保存农田掩膜
    mask_path = output_dir / tile_name / 'cropland_strict_mask.tif'
    Image.fromarray(cropland_mask * 255).save(mask_path)

    # 保存统计
    stats_path = output_dir / tile_name / 'worldcover_stats_strict.json'
    with open(stats_path, 'w') as f:
        json.dump({
            'definition': 'strict',
            'included_class': CROPLAND_CLASS,
            'class_name': 'Cropland only',
            'class_stats': class_stats,
            'total_cropland_pixels': total_cropland
        }, f, indent=2)

    return cropland_mask, class_stats


def batch_download(flood_dir, output_dir, max_tiles=10):
    """批量下载（严格农田定义）"""

    print('=' * 60)
    print('批量下载WorldCover农田数据（严格定义）')
    print('=' * 60)
    print(f'农田定义: class {CROPLAND_CLASS} (Cropland only)')
    print('  排除: 草地(30), 湿地(90)等其他类别')
    print()

    # 获取有洪水的tiles
    tile_dirs = [d for d in flood_dir.iterdir() if d.is_dir()]

    # 筛选有洪水的
    flood_tiles = []
    for tile_dir in tile_dirs[:30]:  # 检查前30个
        mlu_path = tile_dir / 'MK0_MLU_1111008_01_20200816.tif'
        if mlu_path.exists():
            from PIL import Image
            mlu = np.array(Image.open(mlu_path))
            if np.sum(mlu == 2) > 0:
                flood_tiles.append(tile_dir)
                if len(flood_tiles) >= max_tiles:
                    break

    print(f'待下载tiles: {len(flood_tiles)}个（有洪水）\n')

    # 下载
    results = []
    for i, tile_dir in enumerate(flood_tiles, 1):
        print(f'[{i}/{len(flood_tiles)}]', end=' ')
        try:
            mask, stats = download_worldcover_cropland_strict(tile_dir, output_dir)
            results.append({
                'tile': tile_dir.name,
                'status': 'success',
                'cropland_pixels': int(np.sum(mask)),
                'class_stats': stats
            })
        except Exception as e:
            print(f'  错误: {e}')
            results.append({
                'tile': tile_dir.name,
                'status': 'error',
                'error': str(e)
            })

    # 统计
    success = [r for r in results if r['status'] == 'success']
    total_cropland = sum(r.get('cropland_pixels', 0) for r in success)
    tiles_with_cropland = sum(1 for r in success if r.get('cropland_pixels', 0) > 0)

    print(f'\n成功: {len(success)}/{len(results)}')
    print(f'包含农田(class 40)的tiles: {tiles_with_cropland}/{len(success)}')
    print(f'农田总像素: {total_cropland}')

    # 保存报告
    report_path = output_dir / 'download_report_strict.json'
    with open(report_path, 'w') as f:
        json.dump(results, f, indent=2)

    return results


if __name__ == '__main__':

    flood_dir = Path(r'H:\FLOOD RISK\01')
    output_dir = Path(r'H:\FLOOD RISK\worldcover_tiles')

    # 批量下载前10个有洪水的tiles
    try:
        results = batch_download(flood_dir, output_dir, max_tiles=10)
        print(f'\n下载完成！输出目录: {output_dir}')
    except Exception as e:
        print(f'\n失败: {e}')
        import traceback
        traceback.print_exc()
