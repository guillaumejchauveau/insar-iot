import abc
import asyncio
import types
import uuid
from typing import Optional

import bleak


class BeaconVendor(abc.ABC):
    @abc.abstractmethod
    def match(self, device: bleak.BLEDevice, advertising_data: bleak.AdvertisementData) -> Optional[tuple[str, str]]:
        pass


class BeaconManager:
    __stop_event: asyncio.Event
    __scanner: bleak.BleakScanner
    __vendors: list[BeaconVendor]
    __callback: callable
    __available_beacons: dict[str, str]

    beacons: dict[str, str]

    def __init__(self, callback: callable, vendors: list[BeaconVendor]):
        self.__stop_event = asyncio.Event()
        self.__scanner = bleak.BleakScanner(self.__scan_callback)
        self.__vendors = vendors
        self.__callback = callback

        self.beacons = {}
        self.__available_beacons = {}

    def __scan_callback(self, device: bleak.BLEDevice, advertising_data: bleak.AdvertisementData):
        for vendor in self.__vendors:
            match = vendor.match(device, advertising_data)
            if match:
                (beacon_id, beacon_name) = match
                self.__available_beacons[beacon_id] = beacon_name

                if beacon_id in self.beacons:
                    self.beacons[beacon_id] = beacon_name
                    self.__callback()
                return

    @property
    def available_beacons(self) -> types.MappingProxyType[str, str]:
        return types.MappingProxyType(self.__available_beacons)

    async def start(self):
        await self.__scanner.start()
        await self.__stop_event.wait()
        await self.__scanner.stop()

    def stop(self):
        self.__stop_event.set()


class IBeacon(BeaconVendor):
    __APPLE_CID = 76

    def match(self, device: bleak.BLEDevice, advertising_data: bleak.AdvertisementData) -> Optional[tuple[str, str]]:
        if self.__APPLE_CID in advertising_data.manufacturer_data:
            data = advertising_data.manufacturer_data[self.__APPLE_CID][2:18]
            if len(data) == 16:
                beacon = str(uuid.UUID(bytes=data))
                return "ibeacon:{}".format(beacon), "iBeacon [{}]".format(beacon)
        return None
