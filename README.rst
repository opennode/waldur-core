NodeConductor
=============

Requirements
------------

* Python 2.7

Development Environment Setup
-----------------------------

1. Get the code::

    $ git clone git@code.opennodecloud.com:nodeconductor/nodeconductor.git

2. Create a virtualenv::

    $ cd nodeconductor
    $ virtualenv venv

3. Install nodeconductor in development mode along with dependencies::

    $ venv/bin/python setup.py develop

4. Create settings file::

    $ venv/bin/nodeconductor init /path/to/settings.py
    $ vi /path/to/settings.py

Development Guidelines
----------------------

1. Follow `PEP8 <http://python.org/dev/peps/pep-0008/>`_
2. Use `git flow <https://github.com/nvie/gitflow>`_
3. Write docstrings
4. Use absolute imports, each import on its own line. Keep imports sorted:

  .. code:: python
    from nodeconductor.bar import foo
    from nodeconductor.foo import bar
    from nodeconductor.foo import baz

Resources
---------

* `Bug Tracker <https://opennode.atlassian.net/browse/DM>`_
* `Code <https://code.opennodecloud.com/nodeconductor/nodeconductor>`_