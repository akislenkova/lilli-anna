"""Shared rate-limiter instance (slowapi / in-memory).

Import ``limiter`` wherever you need to apply rate limits.
In production, swap the default in-memory storage for Redis::

    from slowapi import Limiter
    from slowapi.util import get_remote_address
    limiter = Limiter(key_func=get_remote_address, storage_uri="redis://...")
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
