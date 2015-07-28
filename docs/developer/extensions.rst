NodeConductor Extensions
========================

NodeConductor extensions are developed as auto-configurable plugins. It's only
required to add desired application to INSTALLED_APPS. Extensions' URL's will
be registered automatically if settings.NODECONDUCTOR['EXTENSIONS_AUTOREGISTER']
is True, which is default.

The plugin is expected to expose of all the application to be included in the
``entry_points``, for example:

.. code-block:: python

    entry_points={
       'nodeconductor_extensions': (
           'nodeconductor_plugin_app = nodeconductor_plugin.app.urls',
           ),
    }
