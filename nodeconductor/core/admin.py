import logging

from django import forms
from django.contrib import admin
from django.contrib.auth import admin as auth_admin, get_user_model
from django.utils.translation import ugettext_lazy as _

from nodeconductor.core import models
from nodeconductor.core.log import EventLoggerAdapter


logger = logging.getLogger(__name__)
event_logger = EventLoggerAdapter(logger)


class UserCreationForm(auth_admin.UserCreationForm):
    class Meta(object):
        model = get_user_model()
        fields = ("username",)

    # overwritten to support custom User model
    def clean_username(self):
        # Since User.username is unique, this check is redundant,
        # but it sets a nicer error message than the ORM. See #13147.
        username = self.cleaned_data["username"]
        try:
            get_user_model()._default_manager.get(username=username)
        except get_user_model().DoesNotExist:
            return username
        raise forms.ValidationError(
            self.error_messages['duplicate_username'],
            code='duplicate_username',
        )


class UserChangeForm(auth_admin.UserChangeForm):
    class Meta(object):
        model = get_user_model()
        fields = '__all__'

    def clean_civil_number(self):
        # See http://stackoverflow.com/a/1400046/175349
        # and https://code.djangoproject.com/ticket/9039
        return self.cleaned_data['civil_number'].strip() or None


class UserAdmin(auth_admin.UserAdmin):
    list_display = ('username', 'uuid', 'email', 'full_name', 'native_name', 'is_staff')
    search_fields = ('username', 'uuid', 'full_name', 'native_name', 'email')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('civil_number', 'full_name', 'native_name', 'email')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    form = UserChangeForm
    add_form = UserCreationForm


class SshPublicKeyAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'fingerprint')
    search_fields = ('user', 'name', 'fingerprint')
    readonly_fields = ('user', 'name', 'fingerprint', 'public_key')

    def log_addition(self, request, object, *args, **kwargs):
        event_logger.info(
            'SSH key has been created %s', object,
            extra={'ssh_key': object, 'event_type': 'ssh_key_created'}
        )
        return super(SshPublicKeyAdmin, self).log_addition(request, object, *args, **kwargs)

    def log_change(self, request, object, *args, **kwargs):
        event_logger.info(
            'SSH key has been updated %s', object,
            extra={'ssh_key': object, 'event_type': 'ssh_key_updated'}
        )
        return super(SshPublicKeyAdmin, self).log_change(request, object, *args, **kwargs)

    def log_deletion(self, request, object, *args, **kwargs):
        event_logger.info(
            'SSH key has been deleted %s', object,
            extra={'ssh_key': object, 'event_type': 'ssh_key_deleted'}
        )
        return super(SshPublicKeyAdmin, self).log_deletion(request, object, *args, **kwargs)


admin.site.register(models.User, UserAdmin)
admin.site.register(models.SshPublicKey, SshPublicKeyAdmin)

