Background processing
---------------------

For executing heavier requests and performing background tasks NodeConductor is using Celery_. Celery is a task
queue that supports multiple backends for storing the tasks and results. Currently NodeConductor is relying on
Redis_ backend - Redis server **must be** running for requests triggering background scheduling to succeed.

If you are developing on OS X and have brew installed:

.. code-block:: bash

  brew install redis-server
  redis-server

Please see Redis docs for installation on other platforms. Installation of NC with RPMs will automatically install
and configure proper version of Redis.

.. _Celery: http://celery.readthedocs.org/
.. _Redis: http://redis.io/