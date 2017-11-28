State machines
--------------

Some of the models in Waldur have a state field representing their current condition. The state field
is implemented as a finite state machine. Both user requests and background tasks can trigger state transition. A REST
client can observe changes to the model instance through polling the 'state' field of the object.

Example
+++++++
Let's take VM instance in 'offline' state. A user can request the instance to start by issuing a
corresponding request over REST. This will schedule a task in Celery and transition instance status to 'starting_scheduled'.
Further user requests for starting an instance will get state transition validation error. Once the background worker
starts processing the queued task, it updates the Instance status to the 'starting'. On task successful completion,
the state is transitioned to 'online' by the background task.
