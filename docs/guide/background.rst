Background processing
---------------------

For executing heavier requests and performing background tasks Waldur is using Celery_. Celery is a task
queue that supports multiple backends for storing the tasks and results. Currently Waldur is relying on
Redis_ backend - Redis server **must be** running for requests triggering background scheduling to succeed.

If you are developing on OS X and have brew installed:

.. code-block:: bash

  brew install redis-server
  redis-server

Please see Redis docs for installation on other platforms.

.. _Celery: http://celery.readthedocs.org/
.. _Redis: http://redis.io/


Error state of background tasks
+++++++++++++++++++++++++++++++

If a background task has failed to achieve it's goal, it should transit into an error state. To propagate
more information to the user each model with an FSM field should include a field for error
message information - **error_message**. The field should be exposed via REST. Background task should update this
field before transiting into an erred state.

Cleaning of the error state of the model instance should clean up also **error_message** field.
