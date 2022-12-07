import discoverhue
import re
import urllib.request
import xml.etree.ElementTree as ET
from phue import Bridge
from phue import AllLights

def get_bridge_friendly_name(bridge_ip):
    try:
        req = urllib.request.Request("http://" + bridge_ip + "/description.xml")
        with urllib.request.urlopen(req) as response:
            xml_description = response.read().decode()
            root = ET.fromstring(xml_description)
            rootname = {'root': root.tag[root.tag.find('{')+1:root.tag.find('}')]}
            device = root.find('root:device', rootname)
            bridge_friendly_name = device.find('root:friendlyName', rootname).text
            
            return bridge_friendly_name
    except:
        return (bridge_ip, bridge_ip)

def discover_bridges():
    try:
        found = discoverhue.find_bridges()
        return [ re.search(".*https?://(.*):\d*", bridge_ip).group(1) for bridge_ip in found.values() ]
    except:
        return []

def get_bridges():
    return [(get_bridge_friendly_name(bridge_ip), bridge_ip) for bridge_ip in discover_bridges()]

bridges = get_bridges()
print(bridges)

# take in argument
import sys
brightness_val = int(int(sys.argv[1]) * 255 / 100)
print("brightness : " + str(brightness_val))
for b in bridges:
    print(b)
    print(b[1])
    bridge = Bridge(b[1])
    bridge.connect()
    lights = AllLights(bridge)
    lights.on = False
    lights.brightness = brightness_val

