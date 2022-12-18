import asyncio
import ipaddress
import logging
from typing import Optional

from zeroconf import Zeroconf, ServiceStateChange
from zeroconf.asyncio import AsyncZeroconf, AsyncServiceBrowser, AsyncServiceInfo

from ._client import BridgeClient, BridgeClientSession


class Bridge:
    __id: str
    __name: Optional[str]
    __client: BridgeClient

    group_ids: set[str]

    def __init__(self, session: BridgeClientSession, bridge_id: str, username: str = None):
        self.__id = bridge_id
        self.__name = None
        self.group_ids = set()

        self.__client = BridgeClient(session, username=username)

    async def __clean_groups(self):
        available_groups = await self.available_groups
        self.group_ids = self.group_ids.intersection(available_groups.keys())

    @property
    def id(self) -> str:
        return self.__id

    @property
    def connected(self):
        return self.__client.ip and self.__client.username

    @property
    async def name(self) -> str:
        try:
            if self.__client.ip:
                config = await self.__client.get_public_config()
                self.__name = config['name']
        except Exception:
            pass

        return self.__name

    @property
    async def available_groups(self) -> dict[str, str]:
        try:
            groups = await self.__client.get_groups()
            return {group_id: group['name'] for group_id, group in groups.items()}
        except Exception:
            return {}

    async def connect(self, ip: str = None, username: str = None):
        if ip:
            self.__client.ip = ip
        if username:
            self.__client.username = username

        if not self.__client.ip:
            raise ValueError("IP required")

        if not self.__client.username:
            # Get API credentials
            try:
                result = await self.__client.register_app()
                self.__client.username = result[0]['success']['username']
            except LookupError as e:
                raise RuntimeError(e)

        # Verify API credentials
        await self.__client.get_config()

    async def set_groups_on(self, value: bool):
        if not self.connected:
            raise RuntimeError("Not connected")
        await self.__clean_groups()

        tasks = []
        for group_id in self.group_ids:
            tasks.append(asyncio.ensure_future(self.__client.set_group_on(group_id, value)))
        await asyncio.gather(*tasks)

    def __eq__(self, other):
        return isinstance(other, Bridge) and other.id == self.id

    def __hash__(self):
        return hash(self.id)

    def __getstate__(self):
        return {
            'id': self.__id,
            'name': self.__name,
            'group_ids': list(self.group_ids),
            'username': self.__client.username
        }

    @classmethod
    def from_state(cls, session: BridgeClientSession, state: dict[str, any]) -> 'Bridge':
        bridge = cls(session, state['id'], state['username'])
        bridge.__name = state['name']
        bridge.group_ids = set(state['group_ids'])
        return bridge


class BridgeManager:
    __BRIDGE_SERVICE = '_hue._tcp.local.'
    __logger: logging.Logger
    __session: BridgeClientSession
    __hue_service_records: dict[str, AsyncServiceInfo]
    __hue_service_records_updating: bool
    __available_bridge_ips: dict[str, str]
    __zeroconf: Optional[AsyncZeroconf]
    __service_browser: Optional[AsyncServiceBrowser]

    bridges: dict[str, Bridge]

    def __init__(self):
        self.__logger = logging.getLogger(__name__)
        self.__session = BridgeClientSession()
        self.__hue_service_records = {}
        self.__hue_service_records_updating = False
        self.__available_bridge_ips = {}
        # Instantiate zeroconfig later to make sure it uses the same asyncio loop as the rest.
        self.__zeroconf = None
        self.__service_browser = None

        self.bridges = {}

    def __handle_service_event(self, zeroconf: Zeroconf, service_type: str, name: str,
                               state_change: ServiceStateChange) -> None:
        if state_change is ServiceStateChange.Removed:
            del self.__hue_service_records[name]
            self.__logger.info("Bridge service '%s' removed", name)
        elif state_change is ServiceStateChange.Added:
            self.__hue_service_records[name] = AsyncServiceInfo(service_type, name)
            self.__logger.info("Bridge service '%s' added", name)
        else:
            self.__logger.debug("Bridge service '%s' updated", name)

        self.__update_bridge_records()

    def __update_bridge_records(self, clear_cache: bool = False):
        if self.__hue_service_records_updating:
            return
        self.__hue_service_records_updating = True

        async def process():
            if clear_cache:
                self.__zeroconf.zeroconf.cache.cache.clear()
                self.__zeroconf.zeroconf.cache.service_cache.clear()
                self.__logger.debug("Zeroconf cache cleared")

            self.__available_bridge_ips.clear()
            for name, service_info in list(self.__hue_service_records.items()):
                if clear_cache:
                    service_info.text = None
                if not await service_info.async_request(self.__zeroconf.zeroconf, 1000):
                    del self.__hue_service_records[name]
                    self.__logger.info("Bridge service '%s' removed", name)
                    continue

                try:
                    bridge_id = service_info.properties[b'bridgeid'].decode('utf-8')
                    bridge_ip = str(ipaddress.ip_address(service_info.addresses[0]))
                    self.__available_bridge_ips[bridge_id] = bridge_ip
                except Exception as e:
                    self.__logger.error(e if e.args else type(e))

            self.__hue_service_records_updating = False

        asyncio.ensure_future(process())

    @property
    def session(self) -> BridgeClientSession:
        return self.__session

    @property
    async def available_bridges(self) -> dict[str, str]:
        bridges = {}
        update_bridge_records = False
        for bridge_id, bridge_ip in self.__available_bridge_ips.items():
            try:
                config = await BridgeClient(self.__session, bridge_ip).get_public_config()
                bridges[bridge_id] = config['name']
            except ConnectionError:
                update_bridge_records = True
            except Exception as e:
                self.__logger.error(e if e.args else type(e))

        if update_bridge_records:
            self.__update_bridge_records(clear_cache=True)

        return bridges

    def get_bridge_ip(self, bridge_id: str) -> str:
        return self.__available_bridge_ips[bridge_id]

    def start(self):
        self.__session.create()
        self.__zeroconf = AsyncZeroconf()
        self.__service_browser = AsyncServiceBrowser(self.__zeroconf.zeroconf,
                                                     self.__BRIDGE_SERVICE,
                                                     handlers=[self.__handle_service_event])

    async def stop(self):
        await self.__service_browser.async_cancel()
        await self.__zeroconf.async_close()
        await self.__session.close()
