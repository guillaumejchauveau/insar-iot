import asyncio
import bleak


class Scanner:
    __stop_event: asyncio.Event
    __scanner: bleak.BleakScanner
    filters: list[callable]
    __callback: callable

    def __init__(self, callback: callable):
        self.__stop_event = asyncio.Event()
        self.__scanner = bleak.BleakScanner(self.scan_callback)
        self.filters = []
        self.__callback = callback

    def add_filter(self, filter: callable):
        if filter not in self.filters:
            self.filters.append(filter)

    async def start(self):
        await self.__scanner.start()
        await self.__stop_event.wait()
        await self.__scanner.stop()

    def scan_callback(self, device: bleak.BLEDevice, advertising_data: bleak.AdvertisementData):
        for filter in self.filters:
            if filter.filter(device, advertising_data):
                self.__callback()
                return

    def stop(self):
        self.__stop_event.set()

class IBeaconFilter:
    APPLE_CID = 76
    uuids: list[bytes]

    def __init__(self):
        self.uuids = []

    def filter(self, device: bleak.BLEDevice, advertising_data: bleak.AdvertisementData) -> bool:
        if self.APPLE_CID in advertising_data.manufacturer_data:
            if advertising_data.manufacturer_data[self.APPLE_CID][2:18] in self.uuids:
                return True
        return False
