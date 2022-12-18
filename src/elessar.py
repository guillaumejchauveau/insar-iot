import asyncio
import json
import logging
from typing import Generator, Optional

import quart

import ble
import ble.vendors
import hue


class Elessar(quart.Quart):
    __beacon_manager: ble.BeaconManager
    __hue_bridge_manager: hue.BridgeManager
    __configuration_path: str
    __lights_state: Optional[bool]
    __force_lights_state: bool

    def __init__(self, configuration_path: str):
        super().__init__('Elessar')

        self.__beacon_manager = ble.BeaconManager(self.__available_beacons_updated, [
            ble.vendors.iBeacon,
            ble.vendors.Eddystone
        ])
        self.__hue_bridge_manager = hue.BridgeManager()
        self.__configuration_path = configuration_path
        self.__lights_state = None
        self.__force_lights_state = False

        self.add_url_rule('/', 'index', self.index, methods=['GET'])
        self.add_url_rule('/', 'configure', self.configure, methods=['POST'])

        logging.getLogger(ble.__name__).parent = self.logger
        logging.getLogger(hue.__name__).parent = self.logger

    async def __connected_bridges(self, available_bridges: dict[str, str]) -> Generator[hue.Bridge, None, None]:
        for bridge in self.__hue_bridge_manager.bridges.values():
            if bridge.id not in available_bridges:
                continue
            try:
                if not bridge.connected:
                    await bridge.connect(self.__hue_bridge_manager.get_bridge_ip(bridge.id))
                yield bridge
            except hue.ButtonNotPressedError as e:
                self.logger.debug(e)
            except Exception as e:
                self.logger.warning(e if e.args else type(e))

    async def __set_lights(self, value: bool):
        if self.__lights_state is not None and not self.__force_lights_state:
            if value == self.__lights_state:
                return

        available_bridges = await self.__hue_bridge_manager.available_bridges
        remaining = len(self.__hue_bridge_manager.bridges)
        async for bridge in self.__connected_bridges(available_bridges):
            try:
                await bridge.set_groups_on(value)
                remaining -= 1
                self.logger.debug("Lights set to '%s' on bridge '%s'", "on" if value else "off", bridge.id)
            except Exception as e:
                self.logger.warning(e if e.args else type(e))

        self.__lights_state = value if remaining == 0 else None

    def __available_beacons_updated(self):
        if len(self.__beacon_manager.beacons) == 0:
            return
        asyncio.ensure_future(self.__set_lights(self.__beacon_manager.has_active_beacon))

    def load_configuration(self):
        try:
            with open(self.__configuration_path, 'r') as file:
                data = json.load(file)
        except Exception as e:
            self.logger.info(e if e.args else type(e))
            return

        try:
            self.__beacon_manager.scan_period = int(data['scan_period'])
        except Exception as e:
            self.logger.warning(e if e.args else type(e))

        try:
            self.__force_lights_state = bool(data['force_lights_state'])
        except Exception as e:
            self.logger.warning(e if e.args else type(e))

        beacons = {}
        for beacon_state in data.get('beacons', []):
            try:
                beacon = self.__beacon_manager.from_state(beacon_state)
                beacons[beacon.id] = beacon
            except Exception as e:
                self.logger.warning(e if e.args else type(e))
        self.__beacon_manager.beacons = beacons

        bridges = {}
        for bridge_state in data.get('bridges', []):
            try:
                bridge = hue.Bridge.from_state(self.__hue_bridge_manager.session, bridge_state)
                bridges[bridge.id] = bridge
            except Exception as e:
                self.logger.warning(e if e.args else type(e))
        self.__hue_bridge_manager.bridges = bridges
        self.logger.debug('Configuration loaded')

    def save_configuration(self):
        try:
            data = {
                'scan_period': self.__beacon_manager.scan_period,
                'force_lights_state': self.__force_lights_state,
                'beacons': [beacon.__getstate__() for beacon in self.__beacon_manager.beacons.values()],
                'bridges': [bridge.__getstate__() for bridge in self.__hue_bridge_manager.bridges.values()]
            }
            with open(self.__configuration_path, 'w') as file:
                json.dump(data, file, indent=4)
            self.logger.debug('Configuration saved')
        except Exception as e:
            self.logger.warning(e if e.args else type(e))

    async def index(self):
        available_bridges = await self.__hue_bridge_manager.available_bridges
        # Try to connect to all configured bridges.
        async for _ in self.__connected_bridges(available_bridges):
            pass

        return await quart.render_template('index.html',
                                           scan_period=self.__beacon_manager.scan_period,
                                           force_lights_state=self.__force_lights_state,
                                           available_beacons=self.__beacon_manager.available_beacons,
                                           beacons=self.__beacon_manager.beacons,
                                           available_bridges=available_bridges,
                                           bridges=self.__hue_bridge_manager.bridges)

    async def configure(self):
        data = await quart.request.form

        self.__beacon_manager.scan_period = int(data['scan_period'])

        beacons_ids = set(data.getlist('beacon[]'))

        for remove_beacon_id in set(self.__beacon_manager.beacons.keys()).difference(beacons_ids):
            del self.__beacon_manager.beacons[remove_beacon_id]

        for add_beacon_id in beacons_ids.difference(self.__beacon_manager.beacons.keys()):
            self.__beacon_manager.beacons[add_beacon_id] = self.__beacon_manager.available_beacons.get(
                add_beacon_id, self.__beacon_manager.from_id(add_beacon_id))

        self.__force_lights_state = 'force_lights_state' in data

        bridge_ids = set(data.getlist('bridge[]'))

        for remove_bridge_id in set(self.__hue_bridge_manager.bridges.keys()).difference(bridge_ids):
            del self.__hue_bridge_manager.bridges[remove_bridge_id]

        for add_bridge_id in bridge_ids.difference(self.__hue_bridge_manager.bridges.keys()):
            self.__hue_bridge_manager.bridges[add_bridge_id] = hue.Bridge(self.__hue_bridge_manager.session,
                                                                          add_bridge_id)

        for bridge_id in self.__hue_bridge_manager.bridges.keys():
            group_ids = data.getlist(f"group[{bridge_id}][]")
            self.__hue_bridge_manager.bridges[bridge_id].group_ids = set(group_ids)

        self.save_configuration()

        return quart.redirect('/')

    async def startup(self):
        await super().startup()
        async with self.app_context():
            self.add_background_task(self.__beacon_manager.start)
            self.__hue_bridge_manager.start()
            self.load_configuration()

    async def shutdown(self):
        async with self.app_context():
            self.__beacon_manager.stop()
            await self.__hue_bridge_manager.stop()
        await super().shutdown()
