"""Hub API 统一错误类型。"""


class APIError(Exception):
    """统一 API 错误，含机器可读 code、人话 message、建议动作 hint、排查链接 doc_url。"""

    def __init__(
        self,
        code: str,
        message: str,
        hint: str = "",
        doc_url: str = "",
        status_code: int = 400,
    ):
        self.code = code
        self.message = message
        self.hint = hint
        self.doc_url = doc_url
        self.status_code = status_code
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "hint": self.hint,
                "doc_url": self.doc_url,
            }
        }
