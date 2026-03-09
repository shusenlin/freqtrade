import sqlite3
import json
import os
from datetime import datetime

class AIDBManager:
    def __init__(self, db_path="user_data/ai_decisions.sqlite"):
        # 确保路径存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        """初始化表结构"""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                pair TEXT,
                market_data TEXT,      -- 存入 Input (JSON)
                ai_response TEXT,      -- 存入 Output (JSON)
                decision TEXT,         -- BUY/SELL/HOLD
                confidence REAL,
                is_trade_executed INTEGER DEFAULT 0
            )
        ''')
        self.conn.commit()

    def log_decision(self, pair, market_data, ai_response, executed=False):
        """记录一次 AI 的决策"""
        try:
            cursor = self.conn.cursor()
            
            # 解析决策结果
            decision = ai_response.get("signal", "unknown")
            confidence = ai_response.get("confidence", 0.0)

            cursor.execute('''
                INSERT INTO ai_logs (timestamp, pair, market_data, ai_response, decision, confidence, is_trade_executed)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                pair,
                json.dumps(market_data),
                json.dumps(ai_response),
                decision,
                confidence,
                1 if executed else 0
            ))
            self.conn.commit()
            print(f"   💾 [数据存储] 已保存 {pair} 的决策记录。")
        except Exception as e:
            print(f"   ❌ 数据库写入失败: {e}")

    def close(self):
        self.conn.close()