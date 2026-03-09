import sqlite3
import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StrategicDB:
    def __init__(self, db_path="user_data/strategic_data.sqlite"):
        """
        战略指挥部数据库管理器
        用于存储 Researcher (研究员) 和 Strategist (策略师) 的分析结果
        """
        # 确保路径存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._create_tables()

    def _get_conn(self):
        # 使用 check_same_thread=False 允许在不同线程中使用连接 (Freqtrade 是多线程的)
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _create_tables(self):
        """初始化三张核心表：市场情绪、币种档案、交易日志"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # 1. 宏观市场情绪表 (Market Sentiment)
        # 频率：每天或每4小时更新
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_sentiment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                fear_greed_index INTEGER,    -- 恐慌贪婪指数 (0-100)
                btc_dominance REAL,          -- 比特币市值占比
                trending_narratives TEXT,    -- 热门赛道 (JSON list)
                macro_summary TEXT,          -- LLM 对大盘的综合评述
                bullish_score REAL           -- 0-100 看涨评分
            )
        ''')

        # 2. 币种深度档案表 (Coin Profiles)
        # 频率：每1-4小时更新，这是 Freqtrade 交易的主要依据
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS coin_profiles (
                pair TEXT PRIMARY KEY,       -- 交易对 (e.g., BTC/USDT)
                last_updated TEXT,           -- 最后更新时间
                
                -- 基本面 (Fundamental)
                fundamental_summary TEXT,    -- 项目方动态、解锁、新闻摘要
                
                -- 技术面 (Technical)
                technical_analysis TEXT,     -- LLM 对 K 线形态的分析
                trend_direction TEXT,        -- 趋势方向: LONG / SHORT / NEUTRAL
                
                -- 核心点位 (Key Levels)
                support_level REAL,          -- 建议买入支撑位
                resistance_level REAL,       -- 建议卖出压力位
                stop_loss_level REAL,        -- 建议止损位
                
                -- 🔴 新增：链上数据 (On-Chain)
                on_chain_analysis TEXT,      -- 链上资金流向分析文本
                on_chain_data TEXT,          -- 链上原始数据 (JSON: 流入流出量、持币地址数变化等)
                
                -- 综合决策
                confidence_score REAL,       -- 置信度 (0.0 - 1.0)
                active_status INTEGER        -- 1=在白名单中(允许交易), 0=剔除
            )
        ''')

        # 3. 交易决策日志 (Decision Logs - 继承自 Phase 4)
        # 用于复盘和微调
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS decision_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                pair TEXT,
                input_context TEXT,          -- 喂给 AI 的所有数据 (Price, Indicators, On-chain)
                ai_output TEXT,              -- AI 返回的原始 JSON
                final_action TEXT,           -- 最终执行动作 (BUY/SELL/HOLD)
                pnl REAL DEFAULT 0.0,        -- 该笔交易的最终盈亏 (事后回填)
                review_comments TEXT         -- 复盘智能体的事后评价
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("✅ 战略数据库表结构已初始化 (含链上资金流向字段)")

    # --- 核心操作方法 ---

    def update_market_sentiment(self, data: Dict[str, Any]):
        """更新宏观市场情绪"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO market_sentiment 
            (timestamp, fear_greed_index, btc_dominance, trending_narratives, macro_summary, bullish_score)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            data.get('fear_greed_index', 50),
            data.get('btc_dominance', 0.0),
            json.dumps(data.get('trending_narratives', [])),
            data.get('macro_summary', "无数据"),
            data.get('bullish_score', 50.0)
        ))
        conn.commit()
        conn.close()

    def update_coin_profile(self, pair: str, profile: Dict[str, Any]):
        """
        更新单个币种的深度档案 (Upsert: 存在则更新，不存在则插入)
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        sql = '''
            INSERT INTO coin_profiles (
                pair, last_updated, 
                fundamental_summary, technical_analysis, 
                trend_direction, support_level, resistance_level, stop_loss_level,
                on_chain_analysis, on_chain_data,
                confidence_score, active_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(pair) DO UPDATE SET
                last_updated=excluded.last_updated,
                fundamental_summary=excluded.fundamental_summary,
                technical_analysis=excluded.technical_analysis,
                trend_direction=excluded.trend_direction,
                support_level=excluded.support_level,
                resistance_level=excluded.resistance_level,
                stop_loss_level=excluded.stop_loss_level,
                on_chain_analysis=excluded.on_chain_analysis,
                on_chain_data=excluded.on_chain_data,
                confidence_score=excluded.confidence_score,
                active_status=excluded.active_status
        '''
        
        cursor.execute(sql, (
            pair,
            datetime.now().isoformat(),
            profile.get('fundamental_summary', ''),
            profile.get('technical_analysis', ''),
            profile.get('trend_direction', 'NEUTRAL'),
            profile.get('support_level', 0.0),
            profile.get('resistance_level', 0.0),
            profile.get('stop_loss_level', 0.0),
            # 新增链上字段的处理
            profile.get('on_chain_analysis', '无链上数据'),
            json.dumps(profile.get('on_chain_data', {})),
            
            profile.get('confidence_score', 0.0),
            profile.get('active_status', 1)
        ))
        
        conn.commit()
        conn.close()

    def get_active_strategy(self, pair: str) -> Optional[Dict]:
        """
        Freqtrade 调用的接口：获取某个币当前的交易策略
        """
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row # 允许通过列名访问
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM coin_profiles WHERE pair = ? AND active_status = 1", (pair,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            data = dict(row)
            # 解析 JSON 字段
            if data.get('on_chain_data'):
                data['on_chain_data'] = json.loads(data['on_chain_data'])
            return data
        return None

    def get_whitelist(self) -> List[str]:
        """获取所有激活状态的币种列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT pair FROM coin_profiles WHERE active_status = 1")
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]