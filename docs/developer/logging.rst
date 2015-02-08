Event logging
=============

Event log entries is something an end user will see. In order to improve user experience the messages should be written in a consistent way.

Here are the guidelines for writing good log events.

* Use present perfect passive for the message.

  **Right:** :code:`Environment %s has been created.`

  **Wrong:** :code:`Environment %s was created.`

* Build a proper sentence: start with a capital letter, end with a period.

  **Right:** :code:`Environment %s has been created.`

  **Wrong:** :code:`environment %s has been created`

* Include entity names into the message string.

  **Right:** :code:`User %s has gained role of %s in project %s.`

  **Wrong:** :code:`User has gained role in project.`

* Don't include too many details into the message string.

  **Right:** :code:`Environment %s has been updated.`

  **Wrong:** :code:`Environment has been updated with name: %s, description: %s.`

* Use the name of an entity instead of its :code:`__str__`.

  **Right:** :code:`event_logger.info('Environment %s has been updated.', env.name)`

  **Wrong:** :code:`event_logger.info('Environment %s has been updated.', env)`

* Don't put quotes around names or entity types.

  **Right:** :code:`Environment %s has been created.`

  **Wrong:** :code:`Environment "%s" has been created.`

* Don't capitalize entity types.

  **Right:** :code:`User %s has gained role of %s in project %s.`

  **Wrong:** :code:`User %s has gained Role of %s in Project %s.`
