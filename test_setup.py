"""
测试脚本：验证数据加载和模型初始化
"""
import pyjson5 as json
import torch
from dataset.Dataset import Dataset
from utilities.utilities import prepare_loaders
from models.model_utilities import initialize_segmentation_model

def test_data_loading():
    """测试数据加载"""
    print("="*50)
    print("测试数据加载...")
    print("="*50)
    
    # 加载配置
    configs = json.load(open("configs/config.json", "r"))
    model_configs = json.load(open("configs/method/unet/unet.json", "r"))
    configs.update(model_configs)
    
    # 使用 update_config 函数来正确设置所有配置
    from utilities.utilities import update_config
    configs = update_config(configs, None)
    
    # 确保设备正确设置
    print(f"使用设备: {configs['device']}")
    print(f"输入通道数: {configs['num_channels']}")
    
    # 测试加载单个样本
    try:
        dataset = Dataset(mode="train", configs=configs)
        print(f"[OK] 训练集加载成功! 样本数: {len(dataset)}")
        
        # 获取一个样本
        sample = dataset[0]
        print(f"[OK] 样本形状: {sample['data'].shape}")
        print(f"[OK] 标签形状: {sample['label'].shape}")
        
        return True
    except Exception as e:
        print(f"[ERROR] 数据加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_model_initialization():
    """测试模型初始化"""
    print("\n" + "="*50)
    print("测试模型初始化...")
    print("="*50)
    
    # 加载配置
    configs = json.load(open("configs/config.json", "r"))
    model_configs = json.load(open("configs/method/unet/unet.json", "r"))
    configs.update(model_configs)
    
    # 使用 update_config 函数来正确设置所有配置
    from utilities.utilities import update_config
    configs = update_config(configs, None)
    
    try:
        # 初始化模型
        model = initialize_segmentation_model(configs, model_configs)
        print(f"[OK] 模型初始化成功!")
        print(f"[OK] 模型类型: {type(model).__name__}")
        
        # 计算参数量
        total_params = sum(p.numel() for p in model.parameters())
        trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        print(f"[OK] 总参数量: {total_params:,}")
        print(f"[OK] 可训练参数: {trainable_params:,}")
        
        return True
    except Exception as e:
        print(f"[ERROR] 模型初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_dataloader():
    """测试 DataLoader"""
    print("\n" + "="*50)
    print("测试 DataLoader...")
    print("="*50)
    
    # 加载配置
    configs = json.load(open("configs/config.json", "r"))
    model_configs = json.load(open("configs/method/unet/unet.json", "r"))
    configs.update(model_configs)
    
    # 使用 update_config 函数来正确设置所有配置
    from utilities.utilities import update_config
    configs = update_config(configs, None)
    
    # 减小 batch size 和 workers 用于测试
    configs["batch_size"] = 4
    configs["num_workers"] = 2
    
    try:
        train_loader, val_loader, test_loader = prepare_loaders(configs)
        print(f"[OK] DataLoader 创建成功!")
        print(f"[OK] 训练批次数: {len(train_loader)}")
        print(f"[OK] 验证批次数: {len(val_loader)}")
        print(f"[OK] 测试批次数: {len(test_loader)}")
        
        # 测试获取一个批次
        batch = next(iter(train_loader))
        print(f"[OK] 批次数据形状: {batch['data'].shape}")
        print(f"[OK] 批次标签形状: {batch['label'].shape}")
        
        return True
    except Exception as e:
        print(f"[ERROR] DataLoader 创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n[START] 开始环境测试...\n")
    
    results = []
    
    # 运行测试
    results.append(("数据加载", test_data_loading()))
    results.append(("模型初始化", test_model_initialization()))
    results.append(("DataLoader", test_dataloader()))
    
    # 打印总结
    print("\n" + "="*50)
    print("测试总结")
    print("="*50)
    
    for name, result in results:
        status = "[PASS] 通过" if result else "[FAIL] 失败"
        print(f"{name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n[SUCCESS] 所有测试通过! 环境配置成功，可以开始训练!")
    else:
        print("\n[WARNING] 部分测试失败，请检查错误信息。")
