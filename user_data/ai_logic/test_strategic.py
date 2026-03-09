from strategic_db import StrategicDB
import json

def test_db_operations():
    print("🚀 开始测试战略数据库...")
    db = StrategicDB()

    # 1. 模拟写入一个币种的深度分析（包含链上数据）
    mock_profile = {
        "fundamental_summary": "即将进行 v4 版本升级，社区活跃度高。",
        "technical_analysis": "日线形成双底结构，RSI 底背离。",
        "trend_direction": "LONG",
        "support_level": 60000.0,
        "resistance_level": 65000.0,
        "stop_loss_level": 58500.0,
        
        # 🔴 测试新增的链上字段
        "on_chain_analysis": "监测到过去24小时交易所净流出 2000 BTC，巨鲸地址增持显著。",
        "on_chain_data": {
            "exchange_netflow": -2000,
            "large_holders_inflow": 500,
            "mvrv_ratio": 1.2
        },
        
        "confidence_score": 0.85,
        "active_status": 1
    }

    print("💾 正在写入 BTC/USDT 档案...")
    db.update_coin_profile("BTC/USDT", mock_profile)

    # 2. 模拟读取
    print("🔍 正在读取 BTC/USDT 档案...")
    profile = db.get_active_strategy("BTC/USDT")

    if profile:
        print("\n✅ 读取成功！数据如下：")
        print(f"   交易对: {profile['pair']}")
        print(f"   趋势: {profile['trend_direction']}")
        print(f"   链上分析: {profile['on_chain_analysis']}")
        print(f"   链上数据(JSON): {json.dumps(profile['on_chain_data'], indent=2)}")
    else:
        print("❌ 读取失败！")

if __name__ == "__main__":
    test_db_operations()