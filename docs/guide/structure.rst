Customers, Projects, Resources and Users
----------------------------------------

NodeConductor is a service for sharing resources across projects. It is based on the delegation model where a customer
can allocate certain users to perform technical or non-technical actions in the projects. A more detailed definition
is below:

.. glossary::

    User
      An account in NodeConductor belonging to a person or a robot. A user can belong to groups that can grant him
      different roles.

    Customer
      A standalone entity. Represents a company or a department.

    Cloud
      Represents an account in IaaS like OpenStack. Currently for OpenStack it should be an account with admin
      privileges.

    Customer owner
      A role of the user that allows her to represent a corresponding customer. In this role, a user can create new
      projects, register resources, as well as allocate them to the projects.

    Project
      A project is an entity within a customer. Project has a linked group of users collaborating on work - 'project
      administrators'. Project aggregates and isolates resources. A customer owner can allow usage of certain clouds
      within a project - defining what resource pools project administrators can use.

    Project administrator
      A project role responsible for the day-to-day technical operations within a project.
      Limited access to project management and billing.

    Resource
      A resource is a provisioned entitiy of a cloud, for example, a VM in OpenStack or AWS, or a repository in Github.
      Each resource belongs to a particular project.

    Project group
      Projects can be grouped together for convenience or permission delegation from Customer owner to Project group
      manager.

    Project group manager
      An optional non-technical role that a customer can use to delegate management of certain projects to selected
      users. Project group manager can create new projects and manage administrators within a scope of a certain
      project group.
