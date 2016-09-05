from django.apps import apps
from django.contrib.auth import get_user_model, models as auth_app
from django.db import DEFAULT_DB_ALIAS, router
from django.db.models import signals
from django.dispatch import receiver


@receiver(
    signals.post_migrate,
    dispatch_uid="nodeconductor.core.management.create_permissions",
)
def create_permissions(app_config, verbosity=2, interactive=True, using=DEFAULT_DB_ALIAS, **kwargs):
    """
    Create permissions for the User.groups.through objects so that DjangoObjectPermissions could be applied.
    """
    # Note, this handler is supposed to be in management package of an app,
    # see https://docs.djangoproject.com/en/1.8/ref/signals/#django.db.models.signals.post_migrate for details

    # The implementation is based on django.contrib.auth.management.create_permissions

    try:
        Permission = apps.get_model('auth', 'Permission')
    except LookupError:
        return

    if not router.allow_migrate(using, Permission):
        return

    if app_config.name != 'nodeconductor.core':
        return

    from django.contrib.contenttypes.models import ContentType

    User = get_user_model()

    content_type = ContentType.objects.get_for_model(User.groups.through)
    auth_app.Permission.objects.get_or_create(
        codename='delete_user_groups',
        name='Can delete user groups',
        content_type=content_type,
    )
    auth_app.Permission.objects.get_or_create(
        codename='add_user_groups',
        name='Can add user groups',
        content_type=content_type,
    )
    auth_app.Permission.objects.get_or_create(
        codename='change_user_groups',
        name='Can change user groups',
        content_type=content_type,
    )
