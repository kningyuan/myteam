"""用户/团队偏好 — PreferencesBackend。"""

from memstack.preferences.protocol import PreferenceBackend, PreferenceRecord
from memstack.preferences.registry import get_preference_backend, list_preference_backends

__all__ = [
    "PreferenceBackend",
    "PreferenceRecord",
    "get_preference_backend",
    "list_preference_backends",
]
