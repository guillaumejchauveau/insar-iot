import discoverhue
import re
import urllib.request
import xml.etree.ElementTree as ET
import phue


def _extract_ip_from_url(url: str) -> str:
    if not url:
        return None

    result = re.search(r'//([^/:]+)', url)
    if result:
        return result.group(1)

    return None


class Bridge:
    @staticmethod
    def get_friendly_name(ip: str) -> str:
        req = urllib.request.Request("http://" + ip + "/description.xml")
        with urllib.request.urlopen(req) as response:
            xml_description = response.read().decode()
            root = ET.fromstring(xml_description)
            rootname = {'root': root.tag[root.tag.find('{')+1:root.tag.find('}')]}
            device = root.find('root:device', rootname)
            return device.find('root:friendlyName', rootname).text

    __serial_number: str
    __ip: str
    __name: str
    __bridge: phue.Bridge
    group_ids: list[int]

    def __init__(self, serial_number: str):
        self.__serial_number = serial_number
        self.__ip = None
        self.__name = None
        self.__bridge = None
        self.group_ids = []

    @property
    def serial_number(self) -> str:
        return self.__serial_number

    @property
    def ip(self) -> str:
        return self.__ip

    @ip.setter
    def ip(self, ip: str):
        self.__ip = ip
        self.__bridge = None

    @property
    def name(self) -> str:
        if not self.__name:
            try:
                self.__name = Bridge.get_friendly_name(self.ip)
            except Exception as e:
                print(e)
                self.__name = self.serial_number + " (" + self.ip + ")"

        return self.__name

    def reload(self):
        discovered_url = None
        if self.ip:
            found = discoverhue.find_bridges({self.serial_number: self.ip})
            discovered_url = found.get(self.serial_number, None)
        else:
            discovered_url = discoverhue.find_bridges(self.serial_number)

        self.ip = _extract_ip_from_url(discovered_url)
        if not self.ip:
            raise Exception("Bridge not found")

        self.__name = None

        try:
            self.__bridge = phue.Bridge(self.ip)
        except phue.PhueRegistrationException as e:
            raise Exception(e)
        except:
            raise Exception("unknown error")

    @property
    def available_groups(self) -> dict[int, str]:
        if self.__bridge is None:
            raise Exception("Bridge not connected")

        return { group.group_id : group.name for group in self.__bridge.groups }

    def set_groups_state(self, value: bool):
        if self.__bridge is None:
            raise Exception("Bridge not connected")

        for group_id in self.group_ids:
            phue.Group(self.__bridge, group_id).on = value


class BridgeManager:
    __bridges: dict[str, Bridge]
    __available_bridges: list[Bridge]

    def __init__(self):
        self.__bridges = {}
        self.__available_bridges = []

    @property
    def bridges(self) -> list[Bridge]:
        return list(self.__bridges.values())

    @property
    def available_bridges(self) -> list[Bridge]:
        return self.__available_bridges

    def reload(self):
        self.__available_bridges = []
        try:
            for (serial_number, url) in discoverhue.find_bridges().items():
                available = Bridge(serial_number)
                available.ip = _extract_ip_from_url(url)

                self.__available_bridges.append(available)

                if serial_number in self.__bridges:
                    self.__bridges[serial_number].ip = ip
        except Exception as e:
            print(e)

    def add_bridge(self, bridge: Bridge):
        bridge.reload()
        self.__bridges[bridge.serial_number] = bridge

    def get_bridge(self, serial_number: str) -> Bridge:
        return self.__bridges[serial_number]

    def remove_bridge(self, serial_number: str):
        del self.__bridges[serial_number]

    def set_bridges_groups_state(self, value: bool):
        for bridge in self.bridges:
            try:
                bridge.set_groups_state(value)
            except Exception as e:
                print(e)
