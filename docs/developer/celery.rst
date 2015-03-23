Celry workflow
==============

**Transition state management**

While working with some entities it's required to honour their transition state.
There's a decorator which allows to safely execute state transition.

.. code-block:: python

    from celery import shared_task
    from nodeconductor.core.tasks import transition

    @shared_task(name='nodeconductor.iaas.stop_instance')
    @transition(Instance, 'begin_stopping')
    def stop_instance(instance_uuid, transition_entity=None):
        # Every task with transition decorator *must* define
        # an additional argument 'transition_entity'
        instance = transition_entity
        openstack_shutdown.apply_async(
            args=(instance.backend_id,)
            link=stop_instance_succeeded.si(instance_uuid)
        )


    @shared_task
    def openstack_shutdown(backend_id):
        OpenStackBackend.stop(backend_id)


    @shared_task
    @transition(Instance, 'set_offline')
    def stop_instance_succeeded(instance_uuid, transition_entity=None):
        pass


**Throttle and route 'heavy' tasks**

There's could be heavy parts in your complex task which you might want to throttle and
avoid parallel execution. Here's an example of how you can achieve this.

.. code-block:: python

    from celery import shared_task, chain
    from nodeconductor.core.tasks import throttle

    @shared_task(name='nodeconductor.demo')
    def demo(uuid=0):
        """ This whole task will be partialy throttled by it's "slow/dangerous" part. """
        chain(
            slow.si(uuid),
            fast.si(uuid),
            dangerous.si(uuid),
        )()


    # Place task into a separate queue for heavy tasks
    @shared_task(is_heavy_task=True)
    def slow(uuid=0):
        # Run only one task at a time
        # It will be throttled based on task name and key pair
        throttle_key = key_by_uuid(uuid)
        with throttle(key=throttle_key):
            print '** Start %s' % uuid
            time.sleep(50)
            print '** End %s' % uuid


    @shared_task()
    @throttle(concurrency=3)
    def dangerous(uuid=0):
        print '** Dangerous %s' % uuid


    @shared_task()
    def fast(uuid):
        print '** Fast %s' % uuid

Now you can schedule two similar tasks:

.. code-block:: python

    demo.delay(10)
    demo.delay(20)

But they will be executed one after another due to concurrency=1
