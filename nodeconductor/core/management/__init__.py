from django.contrib.auth import get_user_model, models as auth_app
from django.db import DEFAULT_DB_ALIAS, router
from django.db.models import get_model, signals, UnavailableApp
from django.dispatch import receiver


@receiver(
    signals.post_syncdb,
    dispatch_uid="nodeconductor.core.management.create_permissions",
)
def create_permissions(app, created_models, verbosity, db=DEFAULT_DB_ALIAS, **kwargs):
    """
    Create permissions for the User.groups.through objects so that DjangoObjectPermissions could be applied.
    """
    # Note, this handler is supposed to be in management package of an app,
    # see https://docs.djangoproject.com/en/1.6/ref/signals/#post-syncdb for details

    # The implementation is based on django.contrib.auth.management.create_permissions
    if not app.__name__ == 'nodeconductor.core.models':
        return

    try:
        get_model('auth', 'Permission')
    except UnavailableApp:
        return

    if not router.allow_syncdb(db, auth_app.Permission):
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
