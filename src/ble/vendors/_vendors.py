from typing import Optional
from uuid import UUID

import bleak

from .._beacon import Beacon
from .._exceptions import InvalidBeaconIDError, InvalidBeaconStateError


class Common:
    BASE_UUID_16 = '0000{}-0000-1000-8000-00805f9b34fb'


class iBeacon(Beacon):
    @classmethod
    def vendor(cls) -> str:
        return 'ibeacon'

    __APPLE_CID = 0x004c
    __UNKNOWN_CID = 0xffff

    @classmethod
    def match(cls, device: bleak.BLEDevice, advertising_data: bleak.AdvertisementData) -> Optional[Beacon]:
        data = advertising_data.manufacturer_data.get(iBeacon.__APPLE_CID, None)
        if not data:
            data = advertising_data.manufacturer_data.get(iBeacon.__UNKNOWN_CID, None)

        if not data or (data[0] != 0x02 and data[0:2] != [0xbe, 0xac]):
            return

        uuid = UUID(bytes=data[2:18])
        major = int.from_bytes(bytearray(data[18:20]), 'big', signed=False)
        minor = int.from_bytes(bytearray(data[20:22]), 'big', signed=False)
        tx_pwr = int.from_bytes([data[22]], 'big', signed=True)
        return cls(uuid, major, minor)

    @classmethod
    def from_id(cls, _id: str) -> Beacon:
        try:
            uuid, major, minor = _id.split(':', 3)

            return cls(UUID(uuid), int(major), int(minor))
        except ValueError or TypeError:
            raise InvalidBeaconIDError()

    __uuid: UUID
    __major: int
    __minor: int

    def __init__(self, uuid: UUID, major: int, minor: int):
        self.__uuid = uuid
        self.__major = major
        self.__minor = minor

    @property
    def name(self) -> str:
        return f"iBeacon: {self.__uuid}:{self.__major}:{self.__minor}"

    def _get_id(self) -> str:
        return f"{self.__uuid}:{self.__major}:{self.__minor}"

    def __eq__(self, other):
        return all([isinstance(other, iBeacon),
                    other.__uuid == self.__uuid,
                    other.__major == self.__major,
                    other.__minor == self.__minor])

    def __hash__(self):
        return hash((self.__uuid, self.__major, self.__minor))

    def _getstate(self):
        return {
            'uuid': str(self.__uuid),
            'major': str(self.__major),
            'minor': str(self.__minor)
        }

    @classmethod
    def __setstate__(cls, state):
        try:
            return cls(UUID(state['uuid']), int(state['major']), int(state['minor']))
        except KeyError or ValueError or TypeError:
            raise InvalidBeaconStateError()


class Eddystone(Beacon):
    @classmethod
    def vendor(cls) -> str:
        return 'eddystone'

    __SVC_UUID = Common.BASE_UUID_16.format('feaa')
    __UID_BEACON = 0x00
    __URL_BEACON = 0x10
    __TLM_BEACON = 0x20
    __EID_BEACON = 0x30

    @classmethod
    def match(cls, device: bleak.BLEDevice, advertising_data: bleak.AdvertisementData) -> Optional[Beacon]:
        if Eddystone.__SVC_UUID not in advertising_data.service_data:
            return

        data = advertising_data.service_data[Eddystone.__SVC_UUID]
        beacon_type = data[0]
        tx_pwr = int.from_bytes([data[1]], 'big', signed=True)

        if beacon_type == Eddystone.__UID_BEACON:
            namespace = bytes(data[2:12]).hex()
            instance = bytes(data[12:18]).hex()
            return cls(namespace, instance, advertising_data.local_name)

    @classmethod
    def from_id(cls, _id: str) -> Beacon:
        try:
            namespace, instance = _id.split(':', 2)

            return cls(namespace, instance)
        except ValueError or TypeError:
            raise InvalidBeaconIDError()

    __namespace: str
    __instance: str
    __name: Optional[str]

    def __init__(self, namespace: str, instance: str, name: Optional[str] = None):
        self.__namespace = namespace
        self.__instance = instance
        self.__name = name

    @property
    def name(self) -> str:
        return self.__name or f"Eddystone: {self.__namespace}:{self.__instance}"

    def _get_id(self) -> str:
        return f"{self.__namespace}:{self.__instance}"

    def __eq__(self, other):
        return all([isinstance(other, Eddystone),
                    other.__namespace == self.__namespace,
                    other.__instance == self.__instance])

    def __hash__(self):
        return hash((self.__namespace, self.__instance))

    def _getstate(self):
        return {
            'namespace': self.__namespace,
            'instance': self.__instance,
            'name': self.__name
        }

    @classmethod
    def __setstate__(cls, state):
        try:
            return cls(state['namespace'], state['instance'], state['name'])
        except KeyError or ValueError or TypeError:
            raise InvalidBeaconStateError()
