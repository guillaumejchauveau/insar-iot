import asyncio
import signal
import ble
import hue


class SwitchTimer:
    __stop_event: asyncio.Event
    __counter: int
    timeout: int
    __on: callable
    __off: callable

    def __init__(self, on: callable, off: callable):
        self.__stop_event = asyncio.Event()
        self.__counter = 0

        self.timeout = None
        self.__on = on
        self.__off = off

    def reset(self):
        self.__counter = self.timeout

    async def start(self):
        while not self.__stop_event.is_set():
            if self.timeout:
                if self.__counter > 0:
                    self.__counter -= 1
                    self.__on()
                else:
                    self.__off()

            await asyncio.sleep(1)

    def stop(self):
        self.__stop_event.set()

class Elessar:
    __switch_timer: SwitchTimer
    __scanner: ble.Scanner
    __ibeacon_filter: ble.IBeaconFilter
    __hue_bridge_manager: hue.BridgeManager

    def __init__(self):
        self.__switch_timer = SwitchTimer(self.on, self.off)

        self.__scanner = ble.Scanner(self.__switch_timer.reset)
        self.__ibeacon_filter = ble.IBeaconFilter()
        self.__scanner.add_filter(self.__ibeacon_filter)

        self.__hue_bridge_manager = hue.BridgeManager()

        self.__switch_timer.timeout = 3
        self.__ibeacon_filter.uuids = [
            b"\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee\xee"
        ]
        self.__hue_bridge_manager.reload()
        self.__hue_bridge_manager.add_bridge(self.__hue_bridge_manager.available_bridges[0])
        self.__hue_bridge_manager.bridges[0].group_ids.append(1)

    def on(self):
        print("Elessar.on")
        self.__hue_bridge_manager.set_bridges_groups_state(True)

    def off(self):
        print("Elessar.off")
        self.__hue_bridge_manager.set_bridges_groups_state(False)

    async def run(self):
        self.__hue_bridge_manager.reload()

        signal.signal(signal.SIGINT, lambda s, f: self.stop())
        await asyncio.gather(self.__scanner.start(), self.__switch_timer.start())

    def scan_callback(self, device, advertising_data):
        for filter in self.filters:
            if filter.filter(device, advertising_data):
                self.callback()
                return

    def stop(self):
        self.__scanner.stop()
        self.__switch_timer.stop()

if __name__ == "__main__":
    asyncio.run(Elessar().run())
