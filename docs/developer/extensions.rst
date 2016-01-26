NodeConductor extensions
========================

NodeConductor extensions are developed as auto-configurable plugins.
One plugin can contain several extensions which is a pure Django application by its own.
In order to be recognized and automatically connected to NodeConductor
some additional configuration required.

Extensions' URLs will be registered automatically only if
settings.NODECONDUCTOR['EXTENSIONS_AUTOREGISTER'] is True, which is default.

Create a class inherited from `nodeconductor.core.NodeConductorExtension`.
Implement methods which reflect your app functionality. At least `django_app()` should be implemented.

Add an entry point of name "nodeconductor_extensions" to your package setup.py. Example:

.. code-block:: python

    entry_points={
        'nodeconductor_extensions': ('nodeconductor_demo = nodeconductor_demo.extension:DemoExtension',)
    }
