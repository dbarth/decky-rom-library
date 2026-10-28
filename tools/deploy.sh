#!/bin/sh
# Build the plugin, pack it as out/rom-library.zip and install it on a device.
# Decky gives the plugin folder to root when it loads it, so the install asks
# for the device's sudo password.
# Usage: tools/deploy.sh [user@host]    (default armada@armada.local; "-" packs only)
set -eu
cd "$(dirname "$0")/.."
HOST=${1:-armada@armada.local}

npm run build
rm -rf out
mkdir -p out/rom-library/py_modules
cp -R package.json LICENSE dist src/backend/main.py src/backend/plugin.json out/rom-library/
cp -R src/backend/rom_library out/rom-library/py_modules/
cp -R src/backend/defaults/. out/rom-library/
find out -name __pycache__ -prune -exec rm -rf {} +
(cd out && zip -qr rom-library.zip rom-library)

if [ "$HOST" != - ]; then
    # Decky reloads a plugin when its main.py changes, only with the debug flag.
    # The device's copy gets the flag; the zip does not.
    python3 -c 'import json, sys; p = json.load(open(sys.argv[1])); p["flags"] = ["debug"]
json.dump(p, open(sys.argv[1], "w"), indent=2)' out/rom-library/plugin.json
    rsync -a --delete out/rom-library/ "$HOST:.cache/rom-library/"
    ssh -t "$HOST" 'sudo rsync -a --delete --chown=root:root ~/.cache/rom-library/ ~/homebrew/plugins/rom-library/ &&
        sudo touch ~/homebrew/plugins/rom-library/main.py'
fi
