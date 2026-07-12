"""
缓存模块 - Redis多级缓存策略
"""
import json
import hashlib
from datetime import timedelta
from typing import Optional, Any

import redis
from functools import wraps

from .core.config import settings

# 连接Redis
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    password=settings.REDIS_PASSWORD,
    db=settings.REDIS_DB,
    decode_responses=True
)

# 缓存前缀
CACHE_PREFIX = "police_exam:"
USER_CACHE_PREFIX = f"{CACHE_PREFIX}user:"
QUESTION_CACHE_PREFIX = f"{CACHE_PREFIX}question:"
PAPER_CACHE_PREFIX = f"{CACHE_PREFIX}paper:"
EXAM_CACHE_PREFIX = f"{CACHE_PREFIX}exam:"
CONFIG_CACHE_PREFIX = f"{CACHE_PREFIX}config:"

# 缓存过期时间
DEFAULT_EXPIRE = 3600  # 1小时
SHORT_EXPIRE = 600      # 10分钟
LONG_EXPIRE = 86400     # 24小时

def generate_cache_key(prefix: str, *args) -> str:
    """
    生成缓存键
    """
    key_parts = [str(arg) for arg in args]
    key = f"{prefix}{':'.join(key_parts)}"
    # 如果key过长，使用MD5哈希
    if len(key) > 250:
        hash_suffix = hashlib.md5(':'.join(key_parts).encode()).hexdigest()
        key = f"{prefix}{hash_suffix}"
    return key

def get_cache(key: str) -> Optional[Any]:
    """
    获取缓存
    """
    try:
        value = redis_client.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None
    except Exception as e:
        # Redis不可用时降级
        return None

def set_cache(key: str, value: Any, expire: int = DEFAULT_EXPIRE) -> bool:
    """
    设置缓存
    """
    try:
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        elif isinstance(value, bool):
            value = str(value).lower()
        else:
            value = str(value)
        
        redis_client.setex(key, expire, value)
        return True
    except Exception as e:
        # Redis不可用时降级
        return False

def delete_cache(key: str) -> bool:
    """
    删除缓存
    """
    try:
        redis_client.delete(key)
        return True
    except Exception as e:
        return False

def cache_decorator(prefix: str, expire: int = DEFAULT_EXPIRE):
    """
    缓存装饰器
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            key_parts = []
            for arg in args:
                if isinstance(arg, (int, str)):
                    key_parts.append(str(arg))
                elif hasattr(arg, 'user_id'):
                    key_parts.append(str(arg.user_id))
            for k, v in kwargs.items():
                if isinstance(v, (int, str)):
                    key_parts.append(f"{k}:{v}")
            
            cache_key = generate_cache_key(prefix, *key_parts)
            
            # 尝试获取缓存
            cached_result = get_cache(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 执行函数
            result = func(*args, **kwargs)
            
            # 设置缓存
            set_cache(cache_key, result, expire)
            
            return result
        return wrapper
    return decorator

# ------------------------------
# 缓存击穿防护（热点数据永不过期+定时更新）
# ------------------------------

def set_hot_cache(key: str, value: Any) -> bool:
    """
    设置热点缓存（永不过期）
    """
    return set_cache(key, value, expire=0)

def refresh_hot_cache(key: str, value: Any) -> bool:
    """
    刷新热点缓存
    """
    return set_hot_cache(key, value)

# ------------------------------
# 缓存穿透防护（布隆过滤器）
# ------------------------------

class BloomFilter:
    """
    布隆过滤器实现
    """
    def __init__(self, key_prefix: str = "bloom:", expected_elements: int = 100000, false_positive_rate: float = 0.01):
        self.key_prefix = key_prefix
        self.expected_elements = expected_elements
        self.false_positive_rate = false_positive_rate
        
        # 计算最佳位数和哈希函数数量
        import math
        self.num_bits = int(-(expected_elements * math.log(false_positive_rate)) / (math.log(2) ** 2))
        self.num_hashes = int((self.num_bits / expected_elements) * math.log(2))
        
        # 预定义哈希种子
        self.seeds = [i * 97 + 37 for i in range(self.num_hashes)]
    
    def _hash(self, value: str, seed: int) -> int:
        """
        计算哈希值
        """
        hash_val = 0
        for char in value:
            hash_val = hash_val * seed + ord(char)
        return hash_val % self.num_bits
    
    def add(self, value: str) -> bool:
        """
        添加元素到布隆过滤器
        """
        try:
            key = f"{self.key_prefix}filter"
            for seed in self.seeds:
                bit_pos = self._hash(str(value), seed)
                redis_client.setbit(key, bit_pos, 1)
            return True
        except Exception as e:
            return False
    
    def contains(self, value: str) -> bool:
        """
        检查元素是否存在
        """
        try:
            key = f"{self.key_prefix}filter"
            for seed in self.seeds:
                bit_pos = self._hash(str(value), seed)
                if not redis_client.getbit(key, bit_pos):
                    return False
            return True
        except Exception as e:
            # Redis不可用时返回True（允许查询）
            return True

# 创建全局布隆过滤器
question_bloom_filter = BloomFilter("question:", 1000000, 0.001)
user_bloom_filter = BloomFilter("user:", 100000, 0.001)

# ------------------------------
# 缓存雪崩预防（随机过期时间）
# ------------------------------

def get_random_expire(base_expire: int, jitter: float = 0.1) -> int:
    """
    获取带随机抖动的过期时间
    """
    import random
    jitter_amount = int(base_expire * jitter)
    return base_expire + random.randint(-jitter_amount, jitter_amount)

# ------------------------------
# 缓存更新策略
# ------------------------------

def invalidate_related_cache(prefix: str, *args):
    """
    失效相关缓存
    """
    try:
        # 生成匹配模式
        pattern = generate_cache_key(prefix, *args)
        if '*' not in pattern:
            pattern += '*'
        
        # 删除所有匹配的缓存
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
        return True
    except Exception as e:
        return False

def warm_up_cache():
    """
    预热缓存（系统启动时调用）
    """
    # 可以在这里添加缓存预热逻辑
    pass