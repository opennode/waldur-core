.. image:: https://travis-ci.org/opennode/nodeconductor.svg?branch=develop
    :target: https://travis-ci.org/opennode/nodeconductor

NodeConductor
=============

Requirements
------------

* Python 2.7+ (Python 3 is not supported)

Development Environment Setup
-----------------------------

Instructions here: http://nodeconductor.readthedocs.org/en/latest/guide/intro.html#installation-from-source

Development Guidelines
----------------------

1. Follow `PEP8 <http://python.org/dev/peps/pep-0008/>`_, except:

  - Limit all lines to a maximum of 119 characters

2. Use `git flow <https://github.com/nvie/gitflow>`_
3. Write docstrings
4. Use absolute imports, each import on its own line. Keep imports sorted:

  .. code:: python

    from nodeconductor.bar import foo
    from nodeconductor.foo import bar
    from nodeconductor.foo import baz
