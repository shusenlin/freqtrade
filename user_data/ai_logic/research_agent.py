import time
import json
import logging
import random  # 仅用于模拟链上数据
from datetime import datetime
from pycoingecko import CoinGeckoAPI
from strategic_db import StrategicDB
from llm_agent import QuantLLM  # 确保文件名和你实际的一致

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Researcher")

class ResearchAgent:
    def __init__(self):
        self.cg = CoinGeckoAPI()
        self.db = StrategicDB()
        self.llm = QuantLLM()
        self.top_n = 20  # 每次分析市值前 20 的币

    def fetch_market_data(self):
        """
        1. 获取市场硬数据 (Price, Volume, Market Cap, 24h Change)
        """
        logger.info("正在从 CoinGecko 获取 Top 币种数据...")
        try:
            # 获取市值前 N 的币种，包含价格变动数据
            coins = self.cg.get_coins_markets(
                vs_currency='usd',
                order='market_cap_desc',
                per_page=self.top_n,
                page=1,
                sparkline=False,
                price_change_percentage='24h'
            )
            
            # 简单清洗数据，过滤掉稳定币
            stablecoins = ['usdt', 'usdc', 'dai', 'fdusd']
            clean_coins = [
                c for c in coins 
                if c['symbol'].lower() not in stablecoins
            ]
            return clean_coins
        except Exception as e:
            logger.error(f"获取市场数据失败: {e}")
            return []

    def fetch_on_chain_data(self, symbol):
        """
        2. 获取链上资金流向数据 (On-Chain Data)
        TODO: 这里目前是模拟数据。未来你可以接入 Glassnode 或 CryptoQuant API。
        """
        # 模拟逻辑：随机生成一些“大户动向”
        netflow = random.randint(-5000, 5000)
        whale_txs = random.randint(0, 50)
        
        analysis_text = ""
        if netflow < -2000:
            analysis_text = "交易所大量流出，巨鲸疑似囤货。"
        elif netflow > 2000:
            analysis_text = "交易所大量流入，潜在抛压增加。"
        else:
            analysis_text = "链上资金流动平稳。"

        return {
            "exchange_netflow": netflow,  # 交易所净流量 (BTC/ETH 单位)
            "large_tx_count": whale_txs,  # 大额转账笔数
            "summary": analysis_text
        }

    def analyze_market_regime(self, market_data):
        """
        3. 让 LLM 分析宏观市场情绪 (Market Regime)
        """
        # 计算整体涨跌幅
        avg_change = sum([c['price_change_percentage_24h'] for c in market_data]) / len(market_data)
        top_gainer = max(market_data, key=lambda x: x['price_change_percentage_24h'])
        
        prompt_data = {
            "average_24h_change": f"{avg_change:.2f}%",
            "top_gainer": f"{top_gainer['name']} (+{top_gainer['price_change_percentage_24h']:.2f}%)",
            "btc_price": next((c['current_price'] for c in market_data if c['symbol'] == 'btc'), 0),
        }

        # 构造 Prompt
        system_prompt = "你是一名加密货币宏观分析师。请根据以下数据判断当前市场情绪。"
        user_prompt = f"""
        市场概况: {json.dumps(prompt_data, ensure_ascii=False)}
        
        请输出 JSON 格式:
        {{
            "macro_summary": "一句话市场总结",
            "fear_greed_index": 0-100的整数(模拟恐慌贪婪指数),
            "bullish_score": 0-100的评分,
            "trending_narratives": ["热点板块1", "热点板块2"]
        }}
        """
        
        logger.info("🤖 正在让 AI 分析宏观情绪...")
        # 这里我们复用 QuantLLM，但稍微改一下调用方式（如果你的 analyze_market 是定死的，可能需要增加一个通用 chat 方法，或者我们这里简单点直接用）
        # 为了方便，我们这里假设 llm_agent.py 里有一个通用的 chat 或者我们临时修改一下 prompt 逻辑
        # ⚠️ 注意：为了演示，这里我们直接调用 LLM。如果你的 QuantLLM 类只支持 analyze_market，你可能需要去修改一下 llm_agent.py 增加一个通用方法。
        # 暂时用 analyze_market 里的逻辑 trick 一下，或者你自己去 llm_agent.py 增加一个 `chat(sys, user)` 方法。
        # 下面演示假设你的 QuantLLM 有个通用调用能力，如果没有，请去修改 llm_agent.py
        
        # 临时直接构造
        response = self.llm.client.chat.completions.create(
            model=self.llm.model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)

    def select_top_picks(self, market_data):
        """
        4. 让 LLM 选币 (Stock Picking)
        """
        # 缩减数据量，只发给 LLM 必要字段，省 Token
        lean_data = []
        for c in market_data[:10]: # 只看前10
            on_chain = self.fetch_on_chain_data(c['symbol'])
            lean_data.append({
                "symbol": c['symbol'].upper(),
                "price": c['current_price'],
                "24h_change": c['price_change_percentage_24h'],
                "market_cap_rank": c['market_cap_rank'],
                "on_chain_summary": on_chain['summary'] # 把链上分析喂给 LLM
            })

        system_prompt = """
        你是一名激进的量化基金经理。请从候选列表中挑选 3-5 个最有潜力的币种进行交易。
        依据：24h涨幅动量、链上资金流向分析。
        
        请输出 JSON 格式:
        {
            "selected_pairs": ["BTC/USDT", "ETH/USDT"...],
            "reasoning": "选择理由..."
        }
        """
        
        logger.info("🤖 正在让 AI 挑选最佳币种...")
        response = self.llm.client.chat.completions.create(
            model=self.llm.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"候选列表: {json.dumps(lean_data)}"}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)

    def run_daily_analysis(self):
        """
        🔥 主执行函数
        """
        logger.info("=== 开始每日战略分析 ===")
        
        # 1. 获取数据
        market_data = self.fetch_market_data()
        if not market_data:
            return

        # 2. 宏观分析
        macro_sentiment = self.analyze_market_regime(market_data)
        self.db.update_market_sentiment(macro_sentiment)
        logger.info(f"宏观情绪已更新: {macro_sentiment['macro_summary']}")

        # 3. 选币决策
        picks = self.select_top_picks(market_data)
        selected_pairs = picks.get('selected_pairs', [])
        logger.info(f"AI 选出的目标币种: {selected_pairs}")

        # 4. 更新每一个币种的档案 (Profile)
        for coin in market_data:
            symbol_pair = f"{coin['symbol'].upper()}/USDT"
            is_active = 1 if symbol_pair in selected_pairs else 0
            
            # 获取链上数据
            on_chain_info = self.fetch_on_chain_data(coin['symbol'])
            
            profile = {
                "fundamental_summary": f"Rank #{coin['market_cap_rank']}, 24h Change: {coin['price_change_percentage_24h']}%",
                "on_chain_analysis": on_chain_info['summary'],
                "on_chain_data": on_chain_info,
                "active_status": is_active,
                # 技术面分析留给 Strategist (每小时更新)，这里先填空
                "technical_analysis": "等待策略师更新...",
                "trend_direction": "NEUTRAL"
            }
            
            self.db.update_coin_profile(symbol_pair, profile)

        logger.info("=== 每日分析完成，数据库已更新 ===")
        return selected_pairs

if __name__ == "__main__":
    agent = ResearchAgent()
    agent.run_daily_analysis()