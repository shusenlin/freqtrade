import sys
import os
from datetime import datetime
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade

# --- 导入你的 AI 模块 ---
# 将 user_data 加入路径，确保能找到模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
try:
    # ⚠️ 确保这里的 'ai_logic.llm_agent' 与你的实际文件名一致
    from user_data.ai_logic.llm_agent import QuantLLM
    from user_data.ai_logic.db_manager import AIDBManager
except ImportError:
    print("❌ 无法导入 QuantLLM，请检查 user_data/ai_logic/ 文件夹下的文件名。")
    # 如果导入失败，使用一个空类防止报错
    class QuantLLM:
        def analyze_market(self, data): return {"signal": "hold", "confidence": 0}

class LLMStrategy(IStrategy):
    """
    LLM 驱动的混合策略
    逻辑：传统指标筛选 -> LLM 二次确认 -> 执行交易
    """
    # 最小 ROI (投资回报率) 设置
    minimal_roi = {
        "60": 0.01,
        "30": 0.02,
        "0": 0.04
    }

    # 止损设置 (-10%)
    stoploss = -0.10
    timeframe = '5m'

    # 初始化 AI 客户端
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.llm_brain = QuantLLM()
        self.db = AIDBManager()
        print("✅ LLMStrategy 已加载，AI 大脑与记忆库就绪。")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算技术指标，这些指标会被喂给 AI
        """
        # 1. RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # 2. 布林带
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_lowerband'] = bollinger['lowerband']
        dataframe['bb_middleband'] = bollinger['middleband']
        dataframe['bb_upperband'] = bollinger['upperband']

        # 3. MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macd_signal'] = macd['macdsignal']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        第一层过滤：传统指标粗筛
        """
        # 宽松的条件：只要 RSI < 40 就视为潜在买入机会
        # 这会触发后续的 confirm_trade_entry 钩子
        dataframe.loc[
            (
                (dataframe['rsi'] < 40) &  # RSI 处于弱势区
                (dataframe['volume'] > 0)  # 确保有成交量
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        离场逻辑 (暂时只用传统指标，避免浪费 Token)
        """
        dataframe.loc[
            (
                (dataframe['rsi'] > 80) # RSI 超买离场
            ),
            'exit_long'] = 1
        return dataframe

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                                time_in_force: str, current_time: datetime, entry_tag: str,
                                side: str, **kwargs) -> bool:
            
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            last_candle = dataframe.iloc[-1].squeeze()

            # 1. 组装数据
            market_data = {
                "symbol": pair,
                "price": last_candle['close'],
                "rsi": round(last_candle['rsi'], 2),
                "macd": round(last_candle['macd'], 2),
                "bollinger_width": round((last_candle['bb_upperband'] - last_candle['bb_lowerband']) / last_candle['bb_middleband'], 4),
                "timestamp": str(current_time)
            }

            print(f"\n🤖 [AI 思考中] 正在分析 {pair} ...")
            
            try:
                # 2. 调用 AI
                decision = self.llm_brain.analyze_market(market_data)
                
                signal = decision.get('signal', 'hold').lower()
                confidence = decision.get('confidence', 0.0)
                reasoning = decision.get('reasoning', '')

                print(f"   👉 AI 建议: {signal.upper()} (置信度: {confidence})")
                print(f"   📝 理由: {reasoning}")

                # 3. 决策逻辑
                should_trade = False
                if signal == 'buy' and confidence >= 0.6: # 降低一点门槛方便测试
                    print("   ✅ AI 批准交易！")
                    should_trade = True
                else:
                    print("   ⛔ AI 拒绝交易。")
                    should_trade = False

                # 4. ⭐ 核心：数据存储 ⭐
                # 不管交易是否执行，都把这次“思考”存下来
                self.db.log_decision(pair, market_data, decision, executed=should_trade)

                return should_trade

            except Exception as e:
                print(f"   ⚠️ AI/DB 错误: {e}")
                return False