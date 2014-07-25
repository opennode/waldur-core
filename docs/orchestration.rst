Orchestration & configuration management
----------------------------------------

Configuration management is a great way to describe and implement best practices for deployment and lifecycle
management of the applications. However, for multi-tenant cases when we have multiple environments,
with potentially different lifecycles, maintaining a single set of configuration management scrips becomes too
restrictive. Moreover, we don't want to depend on upstream as it might be down, decide to introduce destructive
changes or do something equally evil.


Configuration repository structure
++++++++++++++++++++++++++++++++++

- **Template** - central store shared by all environments.
- **Application component** - forked repository of a formula.
- **Orchestration** - an 'overstate' binding together hosts and application's component.
- **Environment** - a group containing Application instance repositories.


Example structure
+++++++++++++++++

Input data:

- **Client:** Elvis P.
- **Application:** Django-based e-commerce "MyTunes"
- **Environment:** Staging

Results in the logical structure.

**/elvisp (group)**
  A client specific area.

**/elvisp/mytunes (group)**
  Application specific area.

**/elvisp/mytunes/stg (group)**
  Staging environment of the application.

**/elvisp/mytunes/stg/mysql-formula**
  Fork of the upstream mysql-formula.

**/elvisp/mytunes/stg/django-formula**
  Fork of upstream django-formula.

**/elvisp/mytunes/stg/mytunes-orchestration**
  Orchestration and targeting for the staging environment of "MyTunes".

**/elvisp/mytunes/stg/mytunes-pillar**
  A standalone repository containing sensitive data - passwords, keys, etc.
