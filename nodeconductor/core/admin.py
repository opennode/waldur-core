from django import forms
from django.contrib import admin
from django.contrib.auth import admin as auth_admin, get_user_model
from django.contrib.auth.models import Group
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
import reversion

from nodeconductor.core import models


def get_admin_url(obj):
    return reverse('admin:%s_%s_change' % (obj._meta.app_label, obj._meta.model_name), args=[obj.id])


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
    list_display = ('username', 'uuid', 'email', 'full_name', 'native_name', 'is_active', 'is_staff')
    search_fields = ('username', 'uuid', 'full_name', 'native_name', 'email')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('civil_number', 'full_name', 'native_name', 'email')}),
        (_('Organization'), {'fields': ('organization', 'organization_approved')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    form = UserChangeForm
    add_form = UserCreationForm


class SshPublicKeyAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'fingerprint')
    search_fields = ('user', 'name', 'fingerprint')
    readonly_fields = ('user', 'name', 'fingerprint', 'public_key')


admin.site.register(models.User, UserAdmin)
admin.site.register(models.SshPublicKey, SshPublicKeyAdmin)
admin.site.unregister(Group)


class ReversionAdmin(reversion.VersionAdmin):
    ignore_duplicate_revisions = True

    def log_change(self, request, object, message):
        # Revision creation is ignored in this method because it has to be implemented in model.save method
        super(reversion.VersionAdmin, self).log_change(request, object, message)

    def log_addition(self, request, object):
        # Revision creation is ignored in this method because it has to be implemented in model.save method
        super(reversion.VersionAdmin, self).log_addition(request, object)
