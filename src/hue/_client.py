from typing import Optional

import requests

from ._exceptions import *


class BridgeClient:
    ip: Optional[str]
    username: Optional[str]

    def __init__(self, ip: str = None, username: str = None):
        self.ip = ip
        self.username = username

    def request(self, method: str, endpoint: str, endpoint_args: list[str] = None, public: bool = False, data=None):
        if endpoint_args is None:
            endpoint_args = []
        if not self.ip:
            raise ClientError("API needs IP address")
        if not public and not self.username:
            raise ClientError("Private endpoint needs username")

        try:
            response = requests.request(method, timeout=(1, 0.5), json=data, url='http://{}/api{}{}'.format(
                self.ip,
                '' if public else '/' + self.username,
                endpoint.format(*endpoint_args)
            ))
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                for message in data:
                    if 'error' not in message:
                        continue
                    error = message['error']
                    if error['type'] == 1:
                        raise UnauthorizedUserError(error)
                    if error['type'] == 3:
                        raise ResourceUnavailable(error)
                    if error['type'] == 4:
                        raise MethodUnavailable(error)
                    if error['type'] == 101:
                        raise ButtonNotPressedError(error)
            return data
        except ValueError or TypeError or requests.URLRequired as e:
            raise ClientError(e)
        except requests.ConnectionError as e:
            self.ip = None
            raise ConnectionError(e)
        except UnauthorizedUserError as e:
            self.username = None
            raise e
        except requests.RequestException as e:
            raise BridgeError("Unknown error", exception=e)

    def get_public_config(self) -> dict[str, any]:
        return self.request('GET', '/config', public=True)

    def get_config(self) -> dict[str, any]:
        return self.request('GET', '/config')

    def register_app(self) -> list[dict[str, any]]:
        return self.request('POST', '', public=True, data={'devicetype': 'elessar'})

    def get_groups(self) -> dict[str, dict[str, any]]:
        return self.request('GET', '/groups')

    def set_group_on(self, group_id: str, value: bool) -> list[dict[str, any]]:
        return self.request('PUT', '/groups/{}/action', [group_id], data={'on': value})
