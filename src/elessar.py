import asyncio
import json
from typing import Generator

import quart

import ble_beacons
import hue


class Elessar(quart.Quart):
    __beacon_manager: ble_beacons.BeaconManager
    __hue_bridge_manager: hue.BridgeManager
    __save_filename: str

    def __init__(self, save_filename: str):
        super().__init__('Elessar')

        self.__beacon_manager = ble_beacons.BeaconManager(self.__available_beacons_updated, [
            ble_beacons.IBeacon,
            ble_beacons.EddystoneBeacon
        ])
        self.__hue_bridge_manager = hue.BridgeManager()
        self.__save_filename = save_filename

        self.load_save()

        self.add_url_rule('/', 'index', self.index, methods=['GET'])
        self.add_url_rule('/beacons', 'set_beacons', self.set_beacons, methods=['POST'])
        self.add_url_rule('/bridges', 'set_bridges', self.set_bridges, methods=['POST'])

    def __connected_bridges(self) -> Generator[hue.Bridge, None, None]:
        for bridge in self.__hue_bridge_manager.bridges.values():
            if bridge.id not in self.__hue_bridge_manager.available_bridges:
                continue
            try:
                if not bridge.connected:
                    bridge.connect(self.__hue_bridge_manager.get_bridge_ip(bridge.id))
                    self.save()
                yield bridge
            except Exception as e:
                self.logger.warning(e)

    def __set_lights(self, value: bool):
        for bridge in self.__connected_bridges():
            try:
                bridge.set_groups_on(value)
            except Exception as e:
                self.logger.warning(e)

    def __available_beacons_updated(self):
        if len(self.__beacon_manager.beacons) == 0:
            return
        self.__set_lights(self.__beacon_manager.has_active_beacon)

    def load_save(self):
        try:
            file = open(self.__save_filename, 'r')
            data = json.load(file)
            file.close()
        except Exception as e:
            self.logger.warning(e)
            return

        try:
            self.__beacon_manager.scan_period = int(data['scan_period'])
        except Exception as e:
            self.logger.warning(e)

        beacons = {}
        for beacon_state in data.get('beacons', []):
            try:
                beacon = self.__beacon_manager.from_state(beacon_state)
                beacons[beacon.id] = beacon
            except Exception as e:
                self.logger.warning(e)
        self.__beacon_manager.beacons = beacons

        bridges = {}
        for bridge_state in data.get('bridges', []):
            try:
                bridge = hue.Bridge.__setstate__(bridge_state)
                bridges[bridge.id] = bridge
            except Exception as e:
                self.logger.warning(e)
        self.__hue_bridge_manager.bridges = bridges

    def save(self):
        try:
            data = {
                'scan_period': self.__beacon_manager.scan_period,
                'beacons': [beacon.__getstate__() for beacon in self.__beacon_manager.beacons.values()],
                'bridges': [bridge.__getstate__() for bridge in self.__hue_bridge_manager.bridges.values()]
            }
            file = open(self.__save_filename, 'w')
            json.dump(data, file, indent=4)
            file.close()
        except Exception as e:
            self.logger.warning(e)

    async def index(self):
        # Try to connect to all configured bridges.
        for _ in self.__connected_bridges():
            pass

        return await quart.render_template('index.html',
                                           scan_period=self.__beacon_manager.scan_period,
                                           available_beacons=self.__beacon_manager.available_beacons,
                                           beacons=self.__beacon_manager.beacons,
                                           available_bridges=self.__hue_bridge_manager.available_bridges,
                                           bridges=self.__hue_bridge_manager.bridges)

    async def set_beacons(self):
        data = await quart.request.form

        self.__beacon_manager.scan_period = int(data['scan_period'])

        beacons_ids = set(data.getlist('beacon[]'))

        for remove_beacon_id in set(self.__beacon_manager.beacons.keys()).difference(beacons_ids):
            del self.__beacon_manager.beacons[remove_beacon_id]

        for add_beacon_id in beacons_ids.difference(self.__beacon_manager.beacons.keys()):
            self.__beacon_manager.beacons[add_beacon_id] = self.__beacon_manager.available_beacons.get(
                add_beacon_id, self.__beacon_manager.from_id(add_beacon_id))

        self.save()

        return quart.redirect('/')

    async def set_bridges(self):
        data = await quart.request.form
        bridge_ids = set(data.getlist('bridge[]'))

        for remove_bridge_id in set(self.__hue_bridge_manager.bridges.keys()).difference(bridge_ids):
            del self.__hue_bridge_manager.bridges[remove_bridge_id]

        for add_bridge_id in bridge_ids.difference(self.__hue_bridge_manager.bridges.keys()):
            self.__hue_bridge_manager.bridges[add_bridge_id] = hue.Bridge(add_bridge_id)

        for bridge_id in self.__hue_bridge_manager.bridges.keys():
            group_ids = data.getlist(f"group[{bridge_id}][]")
            self.__hue_bridge_manager.bridges[bridge_id].group_ids = set(group_ids)

        self.save()

        return quart.redirect('/')

    async def startup(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self.__beacon_manager.start())
        self.__hue_bridge_manager.start()

    async def shutdown(self):
        self.__beacon_manager.stop()
        await self.__hue_bridge_manager.stop()
