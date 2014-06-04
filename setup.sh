#!/bin/sh

set -e

if [ $# -lt 1 ]; then
	echo "Usage: $(basename $0) /path/to/settings.py [ /path/to/nc-admin ]"
	echo ""
	echo "/path/to/settings.py -- Django settings file that will be created"
	echo "/path/to/nc-admin -- nc-admin distribution (cloned Git repository)"
	exit 1
fi

export NODECONDUCTOR_CONF="$1"

# Initialize virtualenv
[ -d "venv" ] || virtualenv venv

# Build and configure nodeconductor
venv/bin/python setup.py develop

[ -f "$NODECONDUCTOR_CONF" ] && mv "$NODECONDUCTOR_CONF" "$NODECONDUCTOR_CONF.bak"
venv/bin/nodeconductor init "$NODECONDUCTOR_CONF"

echo "# Modifications made by installer script" >> "$NODECONDUCTOR_CONF"
echo "ALLOWED_HOSTS += ['*']" >> "$NODECONDUCTOR_CONF"

# Build and configure nc-admin
if [ $# -gt 1 ]; then
	NC_ADMIN_DIR="$2"

	venv/bin/python "$NC_ADMIN_DIR/setup.py" develop

	[ -e nc_admin ] || ln -s "$NC_ADMIN_DIR/nc_admin"

	echo "INSTALLED_APPS += ('nc_admin.base',)" >> "$NODECONDUCTOR_CONF"
fi

# Prepare database and collect static files
venv/bin/nodeconductor syncdb --noinput
venv/bin/nodeconductor migrate
venv/bin/nodeconductor collectstatic --noinput

echo "All done."
echo ""
echo "Modified NodeConductor configuration file: $NODECONDUCTOR_CONF"
echo ""
echo "To launch NodeConductor service in test mode, run"
echo ""
echo "  nodeconductor --config=\"$NODECONDUCTOR_CONF\" runserver 0.0.0.0:8000"
echo ""
