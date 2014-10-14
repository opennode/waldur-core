Customers, Projects and Users
-----------------------------

NodeConductor is a service for sharing resources across projects. It is based on the delegation model where a customer
can allocate certain users to perform tecnical or non-technical actions in the projects. A more detailed definition
is below:

.. glossary::

    User
      An account in NodeConductor belonging to a person or a robot. A user can belong to groups that can grant him
      different roles.

    Customer
      A standalone entity. Represents a company or a department.

    Customer owner
      A role of the user that allows her to represent a corresponding customer. In this role, a user cancreate new
      projects, register resources, as well as allocate them to the projects.

    Project
      A project is an entity within a customer. Project is managed by users having different roles (administrators and
      managers). Project aggregates and isolates resources (like accounts in OpenStack or AWS).

    Project administrator
      A project role responsible for the day-to-day technical operations within a project.
      Limited access to project management and billing.

    Project manager
      A non-technical project role with access to user management, accounting, billing and reporting.


    Project group
      Projects can be grouped together for convinience, e.g. development environments can be grouped together.