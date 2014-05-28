#!/bin/sh

set -e

if [ $# -lt 1 ]; then
	echo "Usage: $(basename $0) /path/to/settings.py"
	echo ""
	echo "/path/to/settings.py is Django settings file that will be created."
	exit 1
fi

export NODECONDUCTOR_CONF="$1"

python setup.py develop
nodeconductor init "$NODECONDUCTOR_CONF"
nodeconductor syncdb --noinput
nodeconductor migrate
nodeconductor collectstatic --noinput

echo "# Modifications made by installer script" >> "$NODECONDUCTOR_CONF"
echo "ALLOWED_HOSTS += []" >> "$NODECONDUCTOR_CONF"

echo "All done."
echo ""
echo "Modified NodeConductor configuration file: $NODECONDUCTOR_CONF"
echo ""
echo "To launch NodeConductor service in test mode, run"
echo ""
echo "  nodeconductor --config=\"$NODECONDUCTOR_CONF\" runserver 0.0.0.0:8000"
echo ""
