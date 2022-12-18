import asyncio
from typing import Optional

import aiohttp

from ._exceptions import *


class BridgeClientSession:
    __session: Optional[aiohttp.ClientSession]

    def __init__(self):
        self.__session = None

    @property
    def session(self):
        if not self.__session:
            raise RuntimeError("Session not created")

        return self.__session

    def create(self):
        self.__session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=1))

    async def close(self):
        await self.__session.close()


class BridgeClient:
    __session: BridgeClientSession
    ip: Optional[str]
    username: Optional[str]

    def __init__(self, session: BridgeClientSession, ip: str = None, username: str = None):
        self.__session = session
        self.ip = ip
        self.username = username

    async def request(self, method: str, endpoint: str, endpoint_args: list[str] = None, public: bool = False,
                      data=None):
        if endpoint_args is None:
            endpoint_args = []
        if not self.ip:
            raise ClientError("API needs IP address")
        if not public and not self.username:
            raise ClientError("Private endpoint needs username")

        url = 'https://{}/api{}{}'.format(
            self.ip,
            '' if public else '/' + self.username,
            endpoint.format(*endpoint_args)
        )

        try:
            async with self.__session.session.request(method, url, json=data, verify_ssl=False) as response:
                response.raise_for_status()
                data = await response.json()
                if isinstance(data, list):
                    for message in data:
                        if 'error' not in message:
                            continue
                        error = message['error']
                        if error['type'] == 1:
                            raise UnauthorizedUserError(error)
                        if error['type'] == 2:
                            raise RuntimeError(error)
                        if error['type'] == 3:
                            raise ResourceUnavailable(error)
                        if error['type'] == 4:
                            raise MethodUnavailable(error)
                        if error['type'] == 101:
                            raise ButtonNotPressedError(error)
                        raise BridgeError("Bridge returned unknown error", error)
                return data
        except UnauthorizedUserError as e:
            self.username = None
            raise e
        except aiohttp.ClientResponseError as e:
            raise BridgeError(str(e), exception=e)
        except (aiohttp.ClientConnectionError, asyncio.TimeoutError, TimeoutError) as e:
            self.ip = None
            raise ConnectionError(e)
        except (ValueError, TypeError, aiohttp.ClientError) as e:
            raise ClientError(e)

    async def get_public_config(self) -> dict[str, any]:
        return await self.request('GET', '/config', public=True)

    async def get_config(self) -> dict[str, any]:
        return await self.request('GET', '/config')

    async def register_app(self) -> list[dict[str, any]]:
        return await self.request('POST', '', public=True, data={'devicetype': 'elessar'})

    async def get_groups(self) -> dict[str, dict[str, any]]:
        return await self.request('GET', '/groups')

    async def set_group_on(self, group_id: str, value: bool) -> list[dict[str, any]]:
        return await self.request('PUT', '/groups/{}/action', [group_id], data={'on': value})
