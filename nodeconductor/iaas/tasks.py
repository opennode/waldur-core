from background_task import background

from nodeconductor.iaas import models


@background(schedule=1)
def stop_instance(instance_id):
    instance = models.Instance.objects.get(pk=instance_id)
    # XXX: What if TransitionNotAllowed is raised here? Is it possible?
    instance.stop()
    instance.save()
