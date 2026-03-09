import os
import json
import logging
from dotenv import load_dotenv
from openai import OpenAI

# 加载 .env 环境变量
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../.env'))

logger = logging.getLogger(__name__)

class QuantLLM:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL")
        self.model = os.getenv("LLM_MODEL", "deepseek-chat")
        
        if not self.api_key:
            logger.warning("OPENAI_API_KEY 未在 .env 中设置，AI 功能将不可用！")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def analyze_market(self, market_data: dict) -> dict:
        """
        核心函数：接收行情数据，返回 JSON 决策
        """
        system_prompt = """
        你是一个专业的加密货币量化交易员。
        你的任务是根据提供的技术指标数据，判断当前的市场趋势并给出交易建议。
        
        必须且只能输出严格的 JSON 格式，不要包含 markdown 代码块或其他文本。
        JSON 格式要求如下：
        {
            "signal": "buy" | "sell" | "hold",
            "confidence": 0.0 到 1.0 之间的浮点数,
            "reasoning": "简短的分析理由 (50字以内)"
        }
        """

        user_message = f"""
        当前市场数据 (BTC/USDT):
        {json.dumps(market_data, indent=2)}
        
        请分析并给出决策。
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.2, # 降低随机性
                response_format={"type": "json_object"} # 强制 JSON 模式 (如果模型支持)
            )
            
            content = response.choices[0].message.content
            decision = json.loads(content)
            return decision

        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            # 发生错误时的保底逻辑：观望
            return {"signal": "hold", "confidence": 0, "reasoning": f"AI Error: {str(e)}"}

# --- 单元测试代码 (直接运行此文件时执行) ---
if __name__ == "__main__":
    # 模拟一段行情数据
    dummy_data = {
        "price": 65000,
        "rsi_14": 25,  # 超卖
        "macd": -50,
        "bollinger_lower": 64800,
        "close_price_dist_to_lower_band": "0.3%"
    }
    
    print("正在测试连接大模型...")
    bot = QuantLLM()
    result = bot.analyze_market(dummy_data)
    print("\n-------- AI 回复 --------")
    print(json.dumps(result, indent=4, ensure_ascii=False))
    print("-------------------------")