import logging

import ble
import elessar
import hue

if __name__ == '__main__':
    logging.getLogger(ble.__name__).setLevel(logging.INFO)
    logging.getLogger(hue.__name__).setLevel(logging.DEBUG)
    elessar.Elessar('elessar.json').run()
