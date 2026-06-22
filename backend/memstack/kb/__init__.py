"""L3 团队知识库（KnowledgeBackend）。"""

from memstack.kb.protocol import KB_SCHEME, KnowledgeBackend
from memstack.kb.registry import get_kb_backend, list_kb_backends, register_kb_backend

__all__ = [
    "KB_SCHEME",
    "KnowledgeBackend",
    "get_kb_backend",
    "list_kb_backends",
    "register_kb_backend",
]
