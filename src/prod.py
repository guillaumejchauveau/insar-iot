import asyncio
import sys

from hypercorn.asyncio import serve
from hypercorn.config import Config

import elessar

config = Config()
config.bind = '0.0.0.0:80'
asyncio.run(serve(elessar.Elessar(sys.argv[1]), config))
