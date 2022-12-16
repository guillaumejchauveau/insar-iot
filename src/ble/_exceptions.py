class UnknownBeaconTypeError(BaseException):
    def __init__(self, beacon_type: str):
        super().__init__(f"Unknown beacon type '{beacon_type}'")


class InvalidBeaconStateError(BaseException):
    def __init__(self):
        super().__init__("Provided beacon state is invalid")


class InvalidBeaconIDError(BaseException):
    def __init__(self):
        super().__init__("Provided beacon ID is invalid")
