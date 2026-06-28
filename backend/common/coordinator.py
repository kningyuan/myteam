"""统一协调者 ID 获取函数。

所有需要引用协调者 agent_id 的模块统一从这里导入，
避免代码中硬编码"main"。
"""
from store.system_config import system_config


def get_coordinator_id() -> str:
    """返回当前协调者 agent_id，默认 'main'"""
    return system_config.get("system", "coordinator_agent_id", default="main")