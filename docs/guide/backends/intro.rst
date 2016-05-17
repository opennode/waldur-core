Shareable services
------------------

NodeConductor is designed to support multiple API-based services for access sharing. Services can range from IaaS to
SaaS, the common denominator is the ability to control services over APIs. Currently supported services are listed below.

+------------------+----------------+--------+---------+---------------------------+----------+------------+
| Backend          | Provision      | Import | Destroy | Manage                    | Monitor  | Backup     |
+==================+================+========+=========+===========================+==========+============+
| Amazon *         | -              | yes    | -       | -                         | –        | –          |
+------------------+----------------+--------+---------+---------------------------+----------+------------+
| Azure *          | VirtualMachine | yes    | yes     | restart                   | –        | –          |
+------------------+----------------+--------+---------+---------------------------+----------+------------+
| DigitalOcean *   | VirtualMachine | yes    | yes     | start/stop/restart        | –        | –          |
+------------------+----------------+--------+---------+---------------------------+----------+------------+
| GitLab *         | Group, Project | yes    | yes     | –                         | –        | –          |
+------------------+----------------+--------+---------+---------------------------+----------+------------+
| JIRA *           | –              | yes    | –       | –                         | –        | –          |
+------------------+----------------+--------+---------+---------------------------+----------+------------+
| OpenStack *      | VirtualMachine | yes    | yes     | start/stop/restart/resize | zabbix   | snapshots  |
+------------------+----------------+--------+---------+---------------------------+----------+------------+
| Oracle *         | Database       | –      | –       | start/stop/restart        | –        | –          |
+------------------+----------------+--------+---------+---------------------------+----------+------------+
| SugarCRM *       | CRM            | –      | yes     | user CRUD                 | –        | –          |
+------------------+----------------+--------+---------+---------------------------+----------+------------+

\* available via NodeConductor extensions

