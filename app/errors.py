"""Error types shared by the services. `retryable` tells the worker whether to try again."""


class ReviewError(Exception):
    retryable: bool = True

    def __init__(self, message: str, *, retryable: bool | None = None):
        super().__init__(message)
        if retryable is not None:
            self.retryable = retryable


class GitHubError(ReviewError):
    def __init__(self, message: str, status: int | None = None):
        # 4xx errors (except rate limits / timeouts) will not fix themselves
        retryable = status is None or status >= 500 or status in (403, 408, 429)
        super().__init__(message, retryable=retryable)
        self.status = status


class LLMError(ReviewError):
    pass


class ConfigError(ReviewError):
    retryable = False
