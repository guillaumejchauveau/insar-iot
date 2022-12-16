class ClientError(RuntimeError):
    pass


class BridgeError(BaseException):
    error: dict[str, any]
    exception: BaseException

    def __init__(self, message: str, error: dict[str, any] = None, exception: Exception = None):
        super().__init__(message)
        self.error = error
        self.exception = exception


class UnauthorizedUserError(BridgeError):
    def __init__(self, error: dict[str, any]):
        super().__init__("Unauthorized user", error)


class ResourceUnavailable(BridgeError):
    def __init__(self, error: dict[str, any]):
        super().__init__("Resource unavailable", error)


class MethodUnavailable(BridgeError, ClientError):
    def __init__(self, error: dict[str, any]):
        super().__init__("Method unavailable", error)


class ButtonNotPressedError(BridgeError):
    def __init__(self, error: dict[str, any]):
        super().__init__("Button was not pressed", error)
