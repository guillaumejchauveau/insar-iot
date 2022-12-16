import asyncio
import ipaddress
from typing import Optional

from zeroconf import Zeroconf, ServiceStateChange
from zeroconf.asyncio import AsyncZeroconf, AsyncServiceBrowser, AsyncServiceInfo

from ._client import BridgeClient


class Bridge:
    __id: str
    __name: Optional[str]
    __client: BridgeClient

    group_ids: set[str]

    def __init__(self, bridge_id: str, username: str = None):
        self.__id = bridge_id
        self.__name = None
        self.group_ids = set()

        self.__client = BridgeClient(username=username)

    def __clean_groups(self):
        self.group_ids = self.group_ids.intersection(self.available_groups.keys())

    @property
    def id(self) -> str:
        return self.__id

    @property
    def connected(self):
        return self.__client.ip and self.__client.username

    @property
    def name(self) -> str:
        try:
            if self.__client.ip:
                self.__name = self.__client.get_public_config()['name']
        finally:
            return self.__name

    @property
    def available_groups(self) -> dict[str, str]:
        groups = {}
        try:
            groups = {group_id: group['name'] for group_id, group in self.__client.get_groups().items()}
        finally:
            return groups

    def connect(self, ip: str = None, username: str = None):
        if ip:
            self.__client.ip = ip
        if username:
            self.__client.username = username

        if not self.__client.ip:
            raise ValueError("IP required")

        if not self.__client.username:
            # Get API credentials
            try:
                self.__client.username = self.__client.register_app()[0]['success']['username']
            except LookupError as e:
                raise RuntimeError(e)

        # Verify API credentials
        self.__client.get_config()

    def set_groups_on(self, value: bool):
        if not self.connected:
            raise RuntimeError("Not connected")
        self.__clean_groups()
        for group_id in self.group_ids:
            self.__client.set_group_on(group_id, value)

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
    def __setstate__(cls, state):
        bridge = cls(state['id'], state['username'])
        bridge.__name = state['name']
        bridge.group_ids = set(state['group_ids'])
        return bridge


class BridgeManager:
    __available_bridge_ips: dict[str, str]
    __zeroconf: AsyncZeroconf
    __service_browser: Optional[AsyncServiceBrowser]

    bridges: dict[str, Bridge]

    def __init__(self):
        self.__available_bridge_ips = {}
        self.__zeroconf = AsyncZeroconf()
        self.__service_browser = None

        self.bridges = {}

    def __handle_service_event(self, zeroconf: Zeroconf, service_type: str, name: str,
                               state_change: ServiceStateChange) -> None:
        asyncio.ensure_future(self.__async_handle_service_event(zeroconf, service_type, name, state_change))

    async def __async_handle_service_event(self, zeroconf: Zeroconf, service_type: str, name: str,
                                           state_change: ServiceStateChange) -> None:
        info = AsyncServiceInfo(service_type, name)
        await info.async_request(zeroconf, 3000)
        bridge_ip = str(ipaddress.ip_address(info.addresses[0]))
        bridge_id = info.properties[b'bridgeid'].decode('utf-8')

        if state_change is ServiceStateChange.Removed:
            del self.__available_bridge_ips[bridge_id]
        else:
            self.__available_bridge_ips[bridge_id] = bridge_ip

    @property
    def available_bridges(self) -> dict[str, str]:
        bridges = {}
        try:
            bridges = {bridge_id: BridgeClient(bridge_ip).get_public_config()['name'] for bridge_id, bridge_ip in
                       self.__available_bridge_ips.items()}
        finally:
            return bridges

    def get_bridge_ip(self, bridge_id: str) -> str:
        return self.__available_bridge_ips[bridge_id]

    def start(self):
        self.__service_browser = AsyncServiceBrowser(self.__zeroconf.zeroconf, '_hue._tcp.local.',
                                                     handlers=[self.__handle_service_event])

    async def stop(self):
        await self.__service_browser.async_cancel()
        await self.__zeroconf.async_close()
