import asyncio
import json

import quart

import ble_beacons
import hue
import utils


class Elessar(quart.Quart):
    __switch_timer: utils.SwitchTimer
    __beacon_manager: ble_beacons.BeaconManager
    __hue_bridge_manager: hue.BridgeManager
    __save_filename: str

    def __init__(self, save_filename: str):
        super().__init__("Elessar")

        self.__switch_timer = utils.SwitchTimer(self.on, self.off)
        self.__beacon_manager = ble_beacons.BeaconManager(self.__switch_timer.reset, [
            ble_beacons.IBeacon()
        ])
        self.__hue_bridge_manager = hue.BridgeManager()
        self.__save_filename = save_filename

        try:
            self.load_save()
        except Exception as e:
            print(e)

        self.add_url_rule("/", "index", self.index, methods=["GET"])
        self.add_url_rule("/timeout", "set_switch_timer_timeout", self.set_switch_timer_timeout, methods=["POST"])
        self.add_url_rule("/beacons", "set_beacons", self.set_beacons, methods=["POST"])
        self.add_url_rule("/bridges", "set_bridges", self.set_bridges, methods=["POST"])

    def load_save(self):
        file = open(self.__save_filename, "r")
        data = json.load(file)
        file.close()
        self.__switch_timer.timeout = data['switch_timer_timeout']
        self.__beacon_manager.beacons = data['beacons']
        self.__hue_bridge_manager.bridges = {bridge_data['id']: hue.Bridge.__setstate__(bridge_data) for bridge_data in
                                             data['bridges']}

    def save(self):
        data = {
            'switch_timer_timeout': self.__switch_timer.timeout,
            'beacons': self.__beacon_manager.beacons,
            'bridges': [bridge.__getstate__() for bridge in self.__hue_bridge_manager.bridges.values()]
        }
        file = open(self.__save_filename, "w")
        json.dump(data, file, indent=4)
        file.close()

    async def index(self):
        return await quart.render_template("index.html",
                                           switch_timer_timeout=self.__switch_timer.timeout,
                                           available_beacons=self.__beacon_manager.available_beacons,
                                           beacons=self.__beacon_manager.beacons,
                                           available_bridges=self.__hue_bridge_manager.available_bridges,
                                           bridges=self.__hue_bridge_manager.bridges)

    async def set_switch_timer_timeout(self):
        data = await quart.request.form

        self.__switch_timer.timeout = int(data['switch_timer_timeout'])

        self.save()

        return quart.redirect('/')

    async def set_beacons(self):
        data = await quart.request.form
        beacons_ids = set(data.getlist("beacon[]"))

        for remove_beacon_id in set(self.__beacon_manager.beacons.keys()).difference(beacons_ids):
            del self.__beacon_manager.beacons[remove_beacon_id]

        for add_beacon_id in beacons_ids.difference(self.__beacon_manager.beacons.keys()):
            self.__beacon_manager.beacons[add_beacon_id] = self.__beacon_manager.available_beacons[add_beacon_id]

        self.save()

        return quart.redirect('/')

    async def set_bridges(self):
        data = await quart.request.form
        bridge_ids = set(data.getlist("bridge[]"))

        for remove_bridge_id in set(self.__hue_bridge_manager.bridges.keys()).difference(bridge_ids):
            del self.__hue_bridge_manager.bridges[remove_bridge_id]

        for add_bridge_id in bridge_ids.difference(self.__hue_bridge_manager.bridges.keys()):
            self.__hue_bridge_manager.bridges[add_bridge_id] = hue.Bridge(add_bridge_id)

        for bridge_id in self.__hue_bridge_manager.bridges.keys():
            bridge_group_list_name = "group[{}][]".format(bridge_id)
            if bridge_group_list_name in data:
                group_ids = data.getlist(bridge_group_list_name)
                self.__hue_bridge_manager.bridges[bridge_id].group_ids = set(group_ids)

        self.save()

        return quart.redirect('/')

    def __set_lights(self, value: bool):
        for bridge in self.__hue_bridge_manager.bridges.values():
            if bridge.id not in self.__hue_bridge_manager.available_bridges:
                continue
            try:
                if not bridge.connected:
                    bridge.connect(self.__hue_bridge_manager.get_bridge_ip(bridge.id))
                    self.save()
                bridge.set_groups_on(value)
            except Exception as e:
                print("Elessar.__set_lights", e)

    def on(self):
        self.__set_lights(True)

    def off(self):
        self.__set_lights(False)

    async def startup(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self.__beacon_manager.start())
        self.__hue_bridge_manager.start()
        loop.create_task(self.__switch_timer.start())

    async def shutdown(self):
        self.__beacon_manager.stop()
        await self.__hue_bridge_manager.stop()
        self.__switch_timer.stop()
