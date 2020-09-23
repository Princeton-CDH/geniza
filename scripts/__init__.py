import json
import os

# folder in which package.json is located
pkg_path = os.path.dirname(os.path.dirname(__file__))

# load package.json to get current version info
with open(os.path.join(pkg_path, 'package.json')) as file:
    pkg = json.loads(file.read())

__version__ = pkg['version']
