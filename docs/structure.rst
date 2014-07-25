User model: Organisations, Users, Roles and Projects
++++++++++++++++++++++++++++++++++++++++++++++++++++

NodeConductor's user model includes several core models described below.

.. glossary::

    Organisation
      A standalone entity. Represents a company or a department. Responsible for paying for consumed resources.

    Project
      A project is an entity within an organisation. Project is managed by users having different roles. Project
      aggregates and separates resources.

    User
      An account in NodeConductor belonging to a person or robot. A user can have at most a single role in the project.
      A user can work in different projects with different roles. User's Organisation is derived based on what projects
      a user has access to.

    Role
      A grouping of permissions for performing actions on the managed objects. Currently supported are two roles:
      a more technical 'Administrator' role and less technical 'Manager' role.



Project roles
=============

.. glossary::


    Administrator
      Role responsible for the day-to-day technical operations within a project. Limited access to project management and billing.

    Manager
      A non-technical role with access to user management, accounting, billing and reporting.
