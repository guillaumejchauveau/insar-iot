import asyncio
import sys
from logging.config import dictConfig

from hypercorn.asyncio import serve
from hypercorn.config import Config

import elessar

if __name__ == '__main__':
    dictConfig({
        'version': 1,
        'loggers': {
            'ble': {
                'level': 'INFO',
            },
            'hue': {
                'level': 'INFO',
            },
        },
    })
    config = Config()
    config.bind = '0.0.0.0:80'
    asyncio.run(serve(elessar.Elessar(sys.argv[1]), config))
