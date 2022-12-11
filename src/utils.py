import asyncio


class SwitchTimer:
    __stop_event: asyncio.Event
    __counter: int
    __on: callable
    __off: callable

    timeout: int

    def __init__(self, on: callable, off: callable):
        self.__stop_event = asyncio.Event()
        self.__counter = 0
        self.__on = on
        self.__off = off

        self.timeout = 3

    def reset(self):
        self.__counter = self.timeout

    async def start(self):
        while not self.__stop_event.is_set():
            if self.timeout:
                try:
                    if self.__counter > 0:
                        self.__counter -= 1
                        self.__on()
                    else:
                        self.__off()
                except Exception as e:
                    print(e)

            await asyncio.sleep(1)

    def stop(self):
        self.__stop_event.set()
