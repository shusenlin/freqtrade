import logging
import sqlite3
import os
import time
from typing import List, Any, Dict
from freqtrade.plugins.pairlist.IPairList import IPairList

logger = logging.getLogger(__name__)

class StrategicPairList(IPairList):
    """
    AI 驱动的白名单生成器
    直接从 strategic_data.sqlite 数据库中读取 active_status=1 的币种
    """

    def __init__(self, exchange, pairlistmanager, config, pairlistconfig, pairlist_pos):
        # 注意：这里也必须把所有参数传给父类 super().__init__
        super().__init__(exchange, pairlistmanager, config, pairlistconfig, pairlist_pos)
        
        # 你的自定义初始化逻辑写在下面
        # self.name = "StrategicPairList"
        
        # 数据库路径
        self._db_path = os.path.join(config['user_data_dir'], 'strategic_data.sqlite')
        
        # 刷新频率
        self._refresh_period = pairlistconfig.get('refresh_period', 60)
        self._last_refresh = 0
        self._whitelist = []

    @property
    def needstickers(self) -> bool:
        """
        Freqtrade 用这个属性判断是否需要下载 Ticker 数据（如 24h 交易量、价格变化等）。
        如果你的逻辑需要根据交易量过滤，必须设为 True。
        """
        return True

    @property
    def short_desc(self) -> str:
        """
        Pairlist 的简短描述，用于日志显示。
        注意：旧版本可能是 description，新版本通常用 short_desc。
        为了保险，我们可以两个都写，或者根据报错补全。
        """
        return "StrategicPairList - Custom LLM Strategy"

    # 根据你的报错信息，它明确要求 'description'，所以必须加上这个：
    @property
    def description(self) -> str:
        return "StrategicPairList - Custom LLM Strategy"
    
    @property
    def is_pairlist_generator(self) -> bool:
        """
        设置为 True，告诉 Freqtrade 这个 Pairlist 可以放在配置列表的第一位。
        这意味着它不依赖上一步的输入，而是自己产生交易对列表。
        """
        return True
    @property
    def short_desc(self) -> str:
        return f"{self.name} - Running AI selection from {self._db_path}"

    def filter_pairlist(self, pairlist: List[str], tickers: Dict) -> List[str]:
        # 缓存机制
        if (time.time() - self._last_refresh) < self._refresh_period and self._whitelist:
            return self._whitelist

        new_whitelist = self._fetch_from_db()
        
        if new_whitelist:
            self._whitelist = new_whitelist
            self._last_refresh = time.time()
            
        return self._whitelist

    def _fetch_from_db(self) -> List[str]:
        if not os.path.exists(self._db_path):
            if self._last_refresh == 0:
                logger.warning(f"StrategicDB not found at {self._db_path}. Waiting for Researcher Agent...")
            return []

        try:
            # 只读模式读取数据库
            uri = f"file:{self._db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
            cursor = conn.cursor()
            
            cursor.execute("SELECT pair FROM coin_profiles WHERE active_status = 1")
            rows = cursor.fetchall()
            conn.close()
            
            pairs = [row[0] for row in rows]
            # 简单的格式验证
            valid_pairs = [p for p in pairs if '/' in p]
            
            if valid_pairs:
                logger.info(f"🤖 AI 战略更新: 选中 {len(valid_pairs)} 个币种 -> {valid_pairs}")
            
            return valid_pairs

        except Exception as e:
            logger.error(f"读取战略数据库失败: {e}")
            return []