Settings policy
===============

Settings are used to configure behaviour of NodeConductor deployment. Settings can be used for configuration of both
core and plugins, or dependent libraries.

Below is a policy for the settings.

Plugins settings
----------------

Plugins are defining their settings in the **extension.py**. However, most probably not all settings might make sense to
override in production. Responsibility for highlighting what settings could be overridden in production are on
plugin developer.

Deployment settings
-------------------

Deployment specific settings (e.g. for CentOS-7) are maintained as Python files and are kept in **/etc/nodeconductor/**.
They are read in by a packaging specific **settings.py** file residing on PYTHONPATH (**nodeconductor.server.settings**).

The following settings files are supported:

 - **settings.py** - all settings overwritten for the deployment apart from logging settings.

 - **logging.py** - contains definition of loggers for the deployment.

