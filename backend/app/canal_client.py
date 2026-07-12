"""
Canal客户端 - 实时数据同步
"""
import json
import time
import threading
from typing import Callable, Optional

import redis

from .core.config import settings

class CanalClient:
    """
    Canal客户端实现
    用于实时捕获MySQL数据库变更并同步到其他存储系统
    """
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        self.canal_topic = "canal.police_exam"
        self.listeners = []
        self.running = False
        self.thread = None
    
    def add_listener(self, table_name: str, callback: Callable):
        """
        添加表变更监听器
        :param table_name: 表名
        :param callback: 回调函数，接收变更数据
        """
        self.listeners.append({
            "table": table_name,
            "callback": callback
        })
    
    def remove_listener(self, table_name: str):
        """
        移除表变更监听器
        :param table_name: 表名
        """
        self.listeners = [l for l in self.listeners if l["table"] != table_name]
    
    def start(self):
        """
        启动Canal客户端
        """
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()
        print("Canal客户端已启动")
    
    def stop(self):
        """
        停止Canal客户端
        """
        self.running = False
        if self.thread:
            self.thread.join()
        print("Canal客户端已停止")
    
    def _listen(self):
        """
        监听Canal消息（模拟实现）
        实际生产环境应使用Canal官方Python客户端或Kafka消费者
        """
        while self.running:
            try:
                # 从Redis队列获取Canal消息
                # 实际中应该从Kafka或Canal Server直接消费
                message = self.redis_client.rpop(self.canal_topic)
                
                if message:
                    self._process_message(message)
                
                time.sleep(0.1)
            except Exception as e:
                print(f"Canal监听异常: {e}")
                time.sleep(1)
    
    def _process_message(self, message: str):
        """
        处理Canal消息
        :param message: Canal JSON消息
        """
        try:
            data = json.loads(message)
            
            # 解析Canal消息结构
            header = data.get("header", {})
            table_name = header.get("tableName")
            event_type = header.get("eventType")  # INSERT/UPDATE/DELETE
            
            # 获取变更数据
            rows = data.get("data", [])
            
            # 调用对应表的监听器
            for listener in self.listeners:
                if listener["table"] == table_name:
                    try:
                        listener["callback"](event_type, rows)
                    except Exception as e:
                        print(f"监听器处理异常 [{table_name}]: {e}")
            
            # 更新缓存
            self._update_cache(table_name, event_type, rows)
            
        except json.JSONDecodeError as e:
            print(f"Canal消息解析失败: {e}")
    
    def _update_cache(self, table_name: str, event_type: str, rows: list):
        """
        根据数据库变更更新缓存
        :param table_name: 表名
        :param event_type: 事件类型
        :param rows: 变更数据
        """
        cache_prefixes = {
            "question_bank": "police_exam:question:",
            "exam_paper": "police_exam:paper:",
            "sys_user": "police_exam:user:",
            "exam_record": "police_exam:exam:"
        }
        
        prefix = cache_prefixes.get(table_name)
        if not prefix:
            return
        
        for row in rows:
            # 获取主键ID
            if table_name == "question_bank":
                pk_id = row.get("question_id")
            elif table_name == "exam_paper":
                pk_id = row.get("paper_id")
            elif table_name == "sys_user":
                pk_id = row.get("user_id")
            elif table_name == "exam_record":
                pk_id = row.get("record_id")
            else:
                pk_id = None
            
            if pk_id:
                cache_key = f"{prefix}{pk_id}"
                
                if event_type in ("DELETE", "UPDATE"):
                    # 删除或更新时清除缓存
                    self.redis_client.delete(cache_key)
                    print(f"缓存已清除: {cache_key}")
                
                elif event_type == "INSERT":
                    # 插入时可以选择性地预热缓存
                    # 这里简化处理，不预热
                    pass
    
    def simulate_canal_message(self, table_name: str, event_type: str, rows: list):
        """
        模拟Canal消息（用于测试）
        :param table_name: 表名
        :param event_type: 事件类型
        :param rows: 数据行
        """
        message = json.dumps({
            "header": {
                "tableName": table_name,
                "eventType": event_type,
                "executeTime": int(time.time() * 1000)
            },
            "data": rows
        })
        
        # 将消息放入Redis队列
        self.redis_client.lpush(self.canal_topic, message)
        print(f"模拟Canal消息已发送: {table_name} {event_type}")

# ------------------------------
# 数据同步管道
# ------------------------------

class DataSyncPipeline:
    """
    数据同步管道
    负责将MySQL变更同步到Elasticsearch、MongoDB等
    """
    
    def __init__(self):
        self.canal_client = CanalClient()
        self._setup_listeners()
    
    def _setup_listeners(self):
        """
        设置数据同步监听器
        """
        # 题目数据同步到Elasticsearch
        self.canal_client.add_listener("question_bank", self._sync_question_to_es)
        
        # 用户行为数据同步到MongoDB
        self.canal_client.add_listener("exam_record", self._sync_exam_to_mongo)
        self.canal_client.add_listener("practice_record", self._sync_practice_to_mongo)
        
        # 用户数据更新缓存
        self.canal_client.add_listener("sys_user", self._sync_user_cache)
    
    def _sync_question_to_es(self, event_type: str, rows: list):
        """
        同步题目数据到Elasticsearch
        """
        # 实际实现应调用Elasticsearch API
        for row in rows:
            print(f"同步题目到ES: {event_type} - {row.get('question_id')}")
            # TODO: 调用ES API进行索引更新
    
    def _sync_exam_to_mongo(self, event_type: str, rows: list):
        """
        同步考试记录到MongoDB
        """
        # 实际实现应调用MongoDB API
        for row in rows:
            print(f"同步考试记录到MongoDB: {event_type} - {row.get('record_id')}")
            # TODO: 调用MongoDB API插入/更新/删除文档
    
    def _sync_practice_to_mongo(self, event_type: str, rows: list):
        """
        同步刷题记录到MongoDB
        """
        for row in rows:
            print(f"同步刷题记录到MongoDB: {event_type} - {row.get('record_id')}")
            # TODO: 调用MongoDB API
    
    def _sync_user_cache(self, event_type: str, rows: list):
        """
        同步用户数据到缓存
        """
        redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        
        for row in rows:
            user_id = row.get("user_id")
            if user_id:
                cache_key = f"police_exam:user:{user_id}"
                if event_type == "DELETE":
                    redis_client.delete(cache_key)
                else:
                    # 更新缓存
                    user_data = {k: v for k, v in row.items() if v is not None}
                    redis_client.setex(cache_key, 3600, json.dumps(user_data))
    
    def start(self):
        """
        启动数据同步管道
        """
        self.canal_client.start()
        print("数据同步管道已启动")
    
    def stop(self):
        """
        停止数据同步管道
        """
        self.canal_client.stop()
        print("数据同步管道已停止")

# 全局数据同步管道实例
data_sync_pipeline = DataSyncPipeline()