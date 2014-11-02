NodeConductor
=============

Requirements
------------

* Python 2.6+ (Python 3 not supported)

Development Environment Setup
-----------------------------

Additional requirements: ``git``, ``virtualenv``,
C compiler and development libraries needed to build dependencies
(CentOS: ``gcc openldap-devel python-devel``,
Ubuntu: ``gcc libldap2-dev libsasl2-dev python-dev``)

**NodeConductor installation**

1. Get the code::

    git clone https://github.com/opennode/nodeconductor.git

2. Create a virtualenv::

    cd nodeconductor
    virtualenv venv

    # Workaround for CentOS 6 / setuptools 0.6.10 -- not needed for other setups
    # CentOS 6 has an old version of Setuptools that fails to install all the
    # dependencies correctly. To work around the problem, install
    # python-keystoneclient from RDO repository *before* installing
    # NodeConductor. To use that, create virtualenv that includes system
    # site-packages.
    rpm -Uvh https://repos.fedorapeople.org/repos/openstack/openstack-icehouse/rdo-release-icehouse-4.noarch.rpm
    yum install python-keystoneclient
    virtualenv --system-site-packages venv

3. Install nodeconductor in development mode along with dependencies::

    venv/bin/python setup.py develop

4. Create settings file -- settings files will be created in
``~/.nodeconductor`` directory::

    venv/bin/nodeconductor init

5. Initialise database -- SQLite3 database will be created in
``~/.nodeconductor/db.sqlite`` unless specified otherwise in settings files::

    venv/bin/nodeconductor syncdb --noinput
    venv/bin/nodeconductor migrate --noinput

6. Collect static data -- static files will be copied to ``static_files`` in the
same directory::

    venv/bin/nodeconductor collectstatic --noinput

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
