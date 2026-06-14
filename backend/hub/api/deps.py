"""Hub API 共享依赖（Store 单例等）。"""

from common.store import Store

_WE_STORE: Store | None = None


def we_store() -> Store:
    global _WE_STORE
    if _WE_STORE is None:
        _WE_STORE = Store()
    return _WE_STORE
