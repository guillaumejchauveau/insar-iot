import asyncio
import ipaddress
from typing import Optional

import requests
import zeroconf as zc
import zeroconf.asyncio as azc


class BridgeApi:
    ip: Optional[str]
    username: Optional[str]

    def __init__(self, ip: str = None, username: str = None):
        self.ip = ip
        self.username = username

    def request(self, method: str, endpoint: str, endpoint_args: list[str] = None, public: bool = False, data=None):
        if endpoint_args is None:
            endpoint_args = []
        if not self.ip:
            raise Exception("API needs IP address")
        if not public and not self.username:
            raise Exception("Private endpoint needs username")

        response = requests.request(method, timeout=(1, 0.5), json=data, url="http://{}/api{}{}".format(
            self.ip,
            '' if public else '/' + self.username,
            endpoint.format(*endpoint_args)
        ))
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            for message in data:
                if "error" in message:
                    if message["error"]["type"] == 101:
                        raise Exception("Button not pressed")
        return data

    def get_public_config(self) -> dict[str, any]:
        return self.request("GET", "/config", public=True)

    def get_config(self) -> dict[str, any]:
        return self.request("GET", "/config")

    def register_app(self) -> list[dict[str, any]]:
        return self.request("POST", "", public=True, data={"devicetype": "elessar"})

    def get_groups(self) -> dict[str, dict[str, any]]:
        return self.request("GET", "/groups")

    def set_group_on(self, group_id: str, value: bool) -> list[dict[str, any]]:
        return self.request("PUT", "/groups/{}/action", [group_id], data={"on": value})


class Bridge:
    __id: str
    __name: Optional[str]
    __api: BridgeApi

    group_ids: set[str]

    def __init__(self, bridge_id: str, username: str = None):
        self.__id = bridge_id
        self.__name = None
        self.group_ids = set()

        self.__api = BridgeApi(username=username)

    def __clean_groups(self):
        self.group_ids = self.group_ids.intersection(self.available_groups.keys())

    def connect(self, ip: str = None, username: str = None):
        if ip:
            self.__api.ip = ip
        if username:
            self.__api.username = username

        if not self.__api.ip:
            raise Exception('ip required')

        if not self.__api.username:
            # Get API credentials
            try:
                self.__api.username = self.__api.register_app()[0]['success']['username']
            except Exception as e:
                print(e)
                return

        # Verify API credentials
        try:
            self.__api.get_config()
            # Credentials are valid
        except Exception as e:
            # Credentials are invalid
            print(e)
            self.__api.username = None

    @property
    def id(self) -> str:
        return self.__id

    @property
    def name(self) -> str:
        if self.__api.ip:
            try:
                self.__name = self.__api.get_public_config()['name']
            except Exception as e:
                print(e)
                # self.__api.ip = None

        return self.__name

    @property
    def connected(self):
        return self.__api.ip and self.__api.username

    @property
    def available_groups(self) -> dict[str, str]:
        if not self.connected:
            raise Exception('not connected')
        return {group_id: group['name'] for group_id, group in self.__api.get_groups().items()}

    def set_groups_on(self, value: bool):
        if not self.connected:
            raise Exception('not connected')
        self.__clean_groups()
        for group_id in self.group_ids:
            try:
                self.__api.set_group_on(group_id, value)
            except Exception as e:
                print(e)

    def __eq__(self, other):
        return isinstance(other, Bridge) and other.id == self.id

    def __hash__(self):
        return hash(self.id)

    def __getstate__(self):
        return {
            'id': self.__id,
            'name': self.__name,
            'group_ids': list(self.group_ids),
            'username': self.__api.username
        }

    @classmethod
    def __setstate__(cls, state):
        bridge = cls(state['id'], state['username'])
        bridge.__name = state['name']
        bridge.group_ids = set(state['group_ids'])
        return bridge


class BridgeManager:
    __available_bridge_ips: dict[str, str]
    __zeroconf: azc.AsyncZeroconf
    __service_browser: Optional[azc.AsyncServiceBrowser]

    bridges: dict[str, Bridge]

    def __init__(self):
        self.__available_bridge_ips = {}
        self.__zeroconf = azc.AsyncZeroconf()
        self.__service_browser = None

        self.bridges = {}

    def __handle_service_event(self, zeroconf: zc.Zeroconf, service_type: str, name: str,
                               state_change: zc.ServiceStateChange) -> None:
        asyncio.ensure_future(self.__async_handle_service_event(zeroconf, service_type, name, state_change))

    async def __async_handle_service_event(self, zeroconf: zc.Zeroconf, service_type: str, name: str,
                                           state_change: zc.ServiceStateChange) -> None:
        info = azc.AsyncServiceInfo(service_type, name)
        await info.async_request(zeroconf, 3000)
        bridge_ip = str(ipaddress.ip_address(info.addresses[0]))
        bridge_id = info.properties[b'bridgeid'].decode('utf-8')

        if state_change is zc.ServiceStateChange.Removed:
            del self.__available_bridge_ips[bridge_id]
        else:
            self.__available_bridge_ips[bridge_id] = bridge_ip

    @property
    def available_bridges(self) -> dict[str, str]:
        return {bridge_id: BridgeApi(bridge_ip).get_public_config()['name'] for bridge_id, bridge_ip in
                self.__available_bridge_ips.items()}

    def get_bridge_ip(self, bridge_id: str) -> str:
        return self.__available_bridge_ips[bridge_id]

    def start(self):
        self.__service_browser = azc.AsyncServiceBrowser(self.__zeroconf.zeroconf, "_hue._tcp.local.",
                                                         handlers=[self.__handle_service_event])

    async def stop(self):
        await self.__service_browser.async_cancel()
        await self.__zeroconf.async_close()
