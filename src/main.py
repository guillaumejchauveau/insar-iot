import asyncio
import bleak
import signal
import phue

class LightManager:
    def __init__(self):
        self.stop_event = asyncio.Event()
        self.counter = 0

        self.timeout = None
        self.groups = []

    def turn_on(self):
        print("Turning on")
        for group in self.groups:
            group.on = True

    def turn_off(self):
        print("Turning off")
        for group in self.groups:
            group.on = False

    def reset(self):
        self.counter = self.timeout

    async def start(self):
        while not self.stop_event.is_set():
            if self.timeout:
                if self.counter > 0:
                    self.counter -= 1
                    self.turn_on()
                else:
                    self.turn_off()

            await asyncio.sleep(1)

    def stop(self):
        self.stop_event.set()

class IBeaconFilter:
    APPLE_CID = 76

    def __init__(self):
        self.uuids = []

    def filter(self, device, advertising_data):
        if self.APPLE_CID in advertising_data.manufacturer_data:
            if advertising_data.manufacturer_data[self.APPLE_CID][2:18] in self.uuids:
                return True
        return False

class Scanner:
    def __init__(self, callback):
        self.stop_event = asyncio.Event()
        self.scanner = bleak.BleakScanner(self.scan_callback)
        self.filters = []
        self.callback = callback

    def add_filter(self, filter):
        if filter not in self.filters:
            self.filters.append(filter)

    async def start(self):
        await self.scanner.start()
        await self.stop_event.wait()
        await self.scanner.stop()

    def scan_callback(self, device, advertising_data):
        for filter in self.filters:
            if filter.filter(device, advertising_data):
                self.callback()
                return

    def stop(self):
        self.stop_event.set()


class Elessar:
    def __init__(self):
        self.light_manager = LightManager()
        self.light_manager.timeout = 3
        self.light_manager.groups = []#[phue.Group(phue.Bridge("192.168.2.20"), 0)]
        self.scanner = Scanner(self.light_manager.reset)
        self.ibeacon_filter = IBeaconFilter()
        self.ibeacon_filter.uuids = [
            b"\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee"
        ]
        self.scanner.add_filter(self.ibeacon_filter)

    async def run(self):
        signal.signal(signal.SIGINT, lambda s, f: self.stop())
        await asyncio.gather(self.scanner.start(), self.light_manager.start())

    def stop(self):
        self.scanner.stop()
        self.light_manager.stop()

if __name__ == "__main__":
    asyncio.run(Elessar().run())
