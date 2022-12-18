class UnknownBeaconTypeError(Exception):
    def __init__(self, beacon_type: str):
        super().__init__(f"Unknown beacon type '{beacon_type}'")


class InvalidBeaconStateError(Exception):
    def __init__(self):
        super().__init__("Provided beacon state is invalid")


class InvalidBeaconIDError(Exception):
    def __init__(self):
        super().__init__("Provided beacon ID is invalid")
