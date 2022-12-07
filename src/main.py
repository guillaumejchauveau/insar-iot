import asyncio
import bleak
import signal
import phue

class LightManager:
    def __init__(self, timeout, bridge_ip):
        self.stop_event = asyncio.Event()
        self.counter = 0
        self.previous_state = False
        self.timeout = timeout
        self.bridge = phue.Bridge(bridge_ip)
        self.lights = phue.AllLights(self.bridge)

    def turn_on(self):
        self.lights.on = True
        print("light on")

    def turn_off(self):
        self.lights.on = False
        print("light off")

    def reset(self):
        self.counter = self.timeout

    async def start(self):
        while not self.stop_event.is_set():
            if self.counter > 0:
                self.counter -= 1
                if not self.previous_state:
                    self.turn_on()
                    self.previous_state = True
            elif self.previous_state:
                self.turn_off()
                self.previous_state = False
            await asyncio.sleep(1)

    def stop(self):
        self.stop_event.set()

class IBeaconScanner:
    APPLE_CID = 76

    def __init__(self, callback, uuids):
        self.stop_event = asyncio.Event()
        self.scanner = bleak.BleakScanner(self.scan_callback)
        self.callback = callback
        self.uuids = uuids

    def scan_callback(self, device, advertising_data):
        if self.APPLE_CID in advertising_data.manufacturer_data:
            if advertising_data.manufacturer_data[self.APPLE_CID][2:18] in self.uuids:
                self.callback(device, advertising_data)

    async def start(self):
        await self.scanner.start()
        await self.stop_event.wait()
        await self.scanner.stop()

    def stop(self):
        self.stop_event.set()

def SIGINT_handler(scanner, light_manager):
    scanner.stop()
    light_manager.stop()

async def main():
    light_manager = LightManager(timeout=3, bridge_ip="192.168.2.20")
    scanner = IBeaconScanner(lambda device, data: light_manager.reset(), uuids=[
        b"\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee"
    ])

    signal.signal(signal.SIGINT, lambda s, f: SIGINT_handler(scanner, light_manager))

    await asyncio.gather(scanner.start(), light_manager.start())

if __name__ == "__main__":
    asyncio.run(main())
