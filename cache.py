import time
from functools import wraps

_cache = {}

def ttl_cache(ttl_seconds=60):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = (func.__name__, args, frozenset(kwargs.items()))
            now = time.time()
            if key in _cache:
                value, timestamp = _cache[key]
                if now - timestamp < ttl_seconds:
                    return value
            
            # Cache miss or expired
            value = func(*args, **kwargs)
            _cache[key] = (value, now)
            return value
        return wrapper
    return decorator
