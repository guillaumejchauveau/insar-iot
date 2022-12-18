import abc
import asyncio
import logging
import types
from typing import Optional, Type

import bleak

from ._exceptions import UnknownBeaconTypeError


class Common:
    STATE_VENDOR_KEY = '_vendor'


class Beacon(abc.ABC):
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
        state[Common.STATE_VENDOR_KEY] = self.vendor()
        return state

    @abc.abstractmethod
    def _getstate(self) -> dict:
        pass

    @classmethod
    @abc.abstractmethod
    def __setstate__(cls, state):
        pass


class BeaconManager:
    __logger: logging.Logger
    __stop_event: asyncio.Event
    __scanner: bleak.BleakScanner
    __beacon_types: dict[str, Type[Beacon]]
    __callback: callable
    __available_beacons: dict[str, Beacon]

    scan_period: int
    beacons: dict[str, Beacon]

    def __init__(self, callback: callable, beacon_types: list[Type[Beacon]]):
        self.__logger = logging.getLogger(__name__)
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
            try:
                beacon = beacon_type.match(device, advertisement_data)
                if beacon:
                    if beacon.id not in self.__available_beacons:
                        added = True

                    self.__available_beacons[beacon.id] = beacon

                    if beacon.id in self.beacons:
                        self.beacons[beacon.id] = beacon

                    self.__logger.debug("Processed beacon '%s'", beacon.name)
            except Exception as e:
                self.__logger.warning(e if e.args else type(e))

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
        beacon_type, _id = data.split(':', 1)
        if beacon_type not in self.__beacon_types:
            raise UnknownBeaconTypeError(beacon_type)

        return self.__beacon_types[beacon_type].from_id(_id)

    def from_state(self, state: dict) -> Beacon:
        beacon_type = state[Common.STATE_VENDOR_KEY]
        if beacon_type not in self.__beacon_types:
            raise UnknownBeaconTypeError(beacon_type)

        return self.__beacon_types[state[Common.STATE_VENDOR_KEY]].__setstate__(state)

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
