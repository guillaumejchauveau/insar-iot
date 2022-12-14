import abc
import asyncio
import types
from typing import Optional, Type
from uuid import UUID

import bleak


class Beacon(abc.ABC):
    STATE_VENDOR_KEY = '_vendor'
    BASE_UUID_16 = '0000{}-0000-1000-8000-00805f9b34fb'

    @classmethod
    @abc.abstractmethod
    def vendor(cls) -> str:
        pass

    @classmethod
    @abc.abstractmethod
    def match(cls, device: bleak.BLEDevice, advertising_data: bleak.AdvertisementData) -> Optional['Beacon']:
        pass

    @classmethod
    @abc.abstractmethod
    def from_id(cls, _id: str) -> 'Beacon':
        pass

    @property
    def id(self) -> str:
        return self.vendor() + ':' + self._get_id()

    @abc.abstractmethod
    def _get_id(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def name(self) -> str:
        pass

    @abc.abstractmethod
    def __eq__(self, other):
        pass

    @abc.abstractmethod
    def __hash__(self):
        pass

    def __getstate__(self):
        state = self._getstate()
        state[Beacon.STATE_VENDOR_KEY] = self.vendor()
        return state

    @abc.abstractmethod
    def _getstate(self) -> dict:
        pass

    @classmethod
    @abc.abstractmethod
    def __setstate__(cls, state):
        pass


class BeaconManager:
    __stop_event: asyncio.Event
    __scanner: bleak.BleakScanner
    __beacon_types: dict[str, Type[Beacon]]
    __callback: callable
    __available_beacons: dict[str, Beacon]

    scan_period: int
    beacons: dict[str, Beacon]

    def __init__(self, callback: callable, beacon_types: list[Type[Beacon]]):
        self.__stop_event = asyncio.Event()
        self.__scanner = bleak.BleakScanner(self.__scan_callback)
        self.__beacon_types = {beacon_type.vendor(): beacon_type for beacon_type in beacon_types}
        self.__callback = callback

        self.scan_period = 3
        self.beacons = {}
        self.__available_beacons = {}

    def __process_discovered_device(self, device: bleak.BLEDevice, advertisement_data: bleak.AdvertisementData) -> bool:
        added = False

        for beacon_type in self.__beacon_types.values():
            beacon = beacon_type.match(device, advertisement_data)
            if beacon:
                if beacon.id not in self.__available_beacons:
                    added = True

                self.__available_beacons[beacon.id] = beacon

                if beacon.id in self.beacons:
                    self.beacons[beacon.id] = beacon

        return added

    def __scan_callback(self, device: bleak.BLEDevice, advertisement_data: bleak.AdvertisementData):
        if self.__process_discovered_device(device, advertisement_data):
            self.__callback()

    @property
    def available_beacons(self) -> types.MappingProxyType[str, Beacon]:
        return types.MappingProxyType(self.__available_beacons)

    @property
    def has_active_beacon(self) -> bool:
        return not self.available_beacons.keys().isdisjoint(self.beacons.keys())

    def from_id(self, data: str) -> Beacon:
        vendor, _id = data.split(':', 1)
        if vendor not in self.__beacon_types:
            raise Exception('invalid data')

        return self.__beacon_types[vendor].from_id(_id)

    def from_state(self, state: dict) -> Beacon:
        if state[Beacon.STATE_VENDOR_KEY] not in self.__beacon_types:
            raise Exception('unknown beacon type')

        return self.__beacon_types[state[Beacon.STATE_VENDOR_KEY]].__setstate__(state)

    async def start(self):
        while not self.__stop_event.is_set():
            await self.__scanner.start()
            await asyncio.sleep(self.scan_period)
            self.__available_beacons = {}
            for device, advertisement_data in self.__scanner.discovered_devices_and_advertisement_data.values():
                self.__process_discovered_device(device, advertisement_data)
            await self.__scanner.stop()
            self.__callback()

    def stop(self):
        self.__stop_event.set()


class IBeacon(Beacon):
    @classmethod
    def vendor(cls) -> str:
        return 'ibeacon'

    __APPLE_CID = 0x004c
    __UNKNOWN_CID = 0xffff

    @classmethod
    def match(cls, device: bleak.BLEDevice, advertising_data: bleak.AdvertisementData) -> Optional[Beacon]:
        data = advertising_data.manufacturer_data.get(IBeacon.__APPLE_CID, None)
        if not data:
            data = advertising_data.manufacturer_data.get(IBeacon.__UNKNOWN_CID, None)

        if not data or (data[0] != 0x02 and data[0:2] != [0xbe, 0xac]):
            return

        uuid = UUID(bytes=data[2:18])
        major = int.from_bytes(bytearray(data[18:20]), 'big', signed=False)
        minor = int.from_bytes(bytearray(data[20:22]), 'big', signed=False)
        tx_pwr = int.from_bytes([data[22]], 'big', signed=True)
        return cls(uuid, major, minor)

    @classmethod
    def from_id(cls, _id: str) -> Beacon:
        uuid, major, minor = _id.split(':', 3)

        return cls(UUID(uuid), int(major), int(minor))

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
        return all([isinstance(other, IBeacon),
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
        return cls(UUID(state['uuid']), int(state['major']), int(state['minor']))


class EddystoneBeacon(Beacon):
    @classmethod
    def vendor(cls) -> str:
        return 'eddystone'

    __SVC_UUID = Beacon.BASE_UUID_16.format('feaa')
    __UID_BEACON = 0x00
    __URL_BEACON = 0x10
    __TLM_BEACON = 0x20
    __EID_BEACON = 0x30

    @classmethod
    def match(cls, device: bleak.BLEDevice, advertising_data: bleak.AdvertisementData) -> Optional[Beacon]:
        if EddystoneBeacon.__SVC_UUID not in advertising_data.service_data:
            return

        data = advertising_data.service_data[EddystoneBeacon.__SVC_UUID]
        beacon_type = data[0]
        tx_pwr = int.from_bytes([data[1]], 'big', signed=True)

        if beacon_type == EddystoneBeacon.__UID_BEACON:
            namespace = bytes(data[2:12]).hex()
            instance = bytes(data[12:18]).hex()
            return cls(namespace, instance, advertising_data.local_name)

    @classmethod
    def from_id(cls, _id: str) -> Beacon:
        namespace, instance = _id.split(':', 2)

        return cls(namespace, instance)

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
        return all([isinstance(other, EddystoneBeacon),
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
        return cls(state['namespace'], state['instance'], state['name'])
