#!/bin/sh
# Forge3D launcher — usage: ./forge3d.sh <command> [args]
cd "$(dirname "$0")" && python3 -m forge3d.cli "$@"
