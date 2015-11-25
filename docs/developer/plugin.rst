Plugin structure
================

In order to create proper plugin repository structure, please execute following steps:

1. `Install cookiecutter <http://cookiecutter.readthedocs.org/en/latest/installation.html>`_

2. Install NodeConductor plugin cookiecutter:

  .. code-block:: bash

    cookiecutter https://github.com/opennode/cookiecutter-nodeconductor-plugin.git


You will be prompted to enter values of some variables.
Note, that in brackets will be suggested default values.


Plugin documentation
====================

1. Keep plugin's documentation within plugin's code repository.
2. The documentation page should start with plugin's title and description.
3. Keep plugin's documentation page structure similar to the NodeConductor's main documentation page:

    * **Guide**
        * should contain at least **installation** steps.
    * **API**
        * should include description of API extension, if any.

4. Setup `readthedocs <https://readthedocs.org/>`_ documentation rendering and issue a merge request
   against NodeConductor's repository with a link.
5. Add section with description and link of the plugin to
   NodeConductor's plugin `section <../index.html#nodeconductor-plugins>`_.
