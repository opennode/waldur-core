from collections import defaultdict

from django import forms
from django.conf import settings
from django.conf.urls import url
from django.contrib import admin, messages
from django.contrib.admin import forms as admin_forms
from django.contrib.auth import admin as auth_admin, get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from rest_framework import permissions as rf_permissions
from reversion.admin import VersionAdmin

from nodeconductor.core import models


def get_admin_url(obj):
    return reverse('admin:%s_%s_change' % (obj._meta.app_label, obj._meta.model_name), args=[obj.id])


def render_to_readonly(value):
    return "<p>{0}</p>".format(value)


class ReadonlyTextWidget(forms.TextInput):
    def _format_value(self, value):
        return value

    def render(self, name, value, attrs=None):
        return render_to_readonly(self._format_value(value))


class OptionalChoiceField(forms.ChoiceField):
    def __init__(self, choices=(), *args, **kwargs):
        empty = [('', '---------')]
        choices = empty + sorted(choices, key=lambda (code, label): label)
        super(OptionalChoiceField, self).__init__(choices, *args, **kwargs)


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

    def __init__(self, *args, **kwargs):
        super(UserChangeForm, self).__init__(*args, **kwargs)
        competences = [(key, key) for key in settings.NODECONDUCTOR.get('USER_COMPETENCE_LIST', [])]
        self.fields['preferred_language'] = OptionalChoiceField(choices=settings.LANGUAGES, required=False)
        self.fields['competence'] = OptionalChoiceField(choices=competences, required=False)

    def clean_civil_number(self):
        # See http://stackoverflow.com/a/1400046/175349
        # and https://code.djangoproject.com/ticket/9039
        return self.cleaned_data['civil_number'].strip() or None


class UserAdmin(auth_admin.UserAdmin):
    list_display = ('username', 'uuid', 'email', 'full_name', 'native_name', 'is_active', 'is_staff', 'is_support')
    search_fields = ('username', 'uuid', 'full_name', 'native_name', 'email')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'is_support')
    fieldsets = (
        (None, {'fields': ('username', 'password', 'registration_method')}),
        (_('Personal info'), {'fields': (
            'civil_number', 'full_name', 'native_name', 'email',
            'preferred_language', 'competence', 'phone_number'
        )}),
        (_('Organization'), {'fields': ('organization', 'organization_approved')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_support')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined', 'agreement_date')}),
    )
    readonly_fields = ('registration_method', 'agreement_date')
    form = UserChangeForm
    add_form = UserCreationForm


class SshPublicKeyAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'fingerprint')
    search_fields = ('user', 'name', 'fingerprint')
    readonly_fields = ('user', 'name', 'fingerprint', 'public_key')


class CustomAdminAuthenticationForm(admin_forms.AdminAuthenticationForm):
    error_messages = {
        'invalid_login': _("Please enter the correct %(username)s and password "
                           "for a staff or a support account. Note that both fields may be "
                           "case-sensitive."),
    }

    def confirm_login_allowed(self, user):
        if not user.is_active or not user.is_support:
            return super(CustomAdminAuthenticationForm, self).confirm_login_allowed(user)


class CustomAdminSite(admin.AdminSite):
    site_title = _('Waldur MasterMind admin')
    site_header = _('Waldur MasterMind administration')
    index_title = _('Waldur MasterMind administration')
    login_form = CustomAdminAuthenticationForm

    def has_permission(self, request):
        if request.method in rf_permissions.SAFE_METHODS:
            return request.user.is_active and (request.user.is_staff or request.user.is_support)

        return request.user.is_active and request.user.is_staff

    @classmethod
    def clone_default(cls):
        instance = cls()
        instance._registry = admin.site._registry.copy()
        instance._actions = admin.site._actions.copy()
        instance._global_actions = admin.site._global_actions.copy()
        return instance

admin_site = CustomAdminSite.clone_default()
admin.site = admin_site
admin.site.register(models.User, UserAdmin)
admin.site.register(models.SshPublicKey, SshPublicKeyAdmin)
admin.site.unregister(Group)


class ReversionAdmin(VersionAdmin):
    ignore_duplicate_revisions = True

    def log_change(self, request, object, message):
        # Revision creation is ignored in this method because it has to be implemented in model.save method
        super(VersionAdmin, self).log_change(request, object, message)

    def log_addition(self, request, object, change_message=None):
        # Revision creation is ignored in this method because it has to be implemented in model.save method
        super(VersionAdmin, self).log_addition(request, object)


class ExecutorAdminAction(object):
    """ Add executor as action to admin model.

    Usage example:
        class PullSecurityGroups(ExecutorAdminAction):
            executor = executors.TenantPullSecurityGroupsExecutor  # define executor
            short_description = 'Pull security groups'  # description for admin page

            def validate(self, tenant):
                if tenant.state != Tenant.States.OK:
                    raise ValidationError('Tenant has to be in state OK to pull security groups.')

        pull_security_groups = PullSecurityGroups()  # this action could be registered as admin action

    """
    executor = NotImplemented

    def __call__(self, admin_class, request, queryset):
        errors = defaultdict(list)
        successfully_executed = []
        for instance in queryset:
            try:
                self.validate(instance)
            except ValidationError as e:
                errors[str(e)].append(instance)
            else:
                self.executor.execute(instance)
                successfully_executed.append(instance)

        if successfully_executed:
            message = _('Operation was successfully scheduled for %(count)d instances: %(names)s') % dict(
                count=len(successfully_executed),
                names=', '.join([str(i) for i in successfully_executed])
            )
            admin_class.message_user(request, message)

        for error, instances in errors.items():
            message = _('Failed to schedule operation for %(count)d instances: %(names)s. Error: %(message)s') % dict(
                count=len(instances),
                names=', '.join([str(i) for i in instances]),
                message=error,
            )
            admin_class.message_user(request, message, level=messages.ERROR)

    def validate(self, instance):
        """ Raise validation error if action cannot be performed for given instance """
        pass


class ExtraActionsMixin(object):
    """
    Allows to add extra actions to admin list page.
    """
    change_list_template = 'admin/core/change_list.html'

    def get_extra_actions(self):
        raise NotImplementedError('Method "get_extra_actions" should be implemented in ExtraActionsMixin.')

    def get_urls(self):
        """
        Inject extra action URLs.
        """
        urls = []

        for action in self.get_extra_actions():
            regex = r'^{}/$'.format(self._get_action_href(action))
            view = self.admin_site.admin_view(action)
            urls.append(url(regex, view))

        return urls + super(ExtraActionsMixin, self).get_urls()

    def changelist_view(self, request, extra_context=None):
        """
        Inject extra links into template context.
        """
        links = []

        for action in self.get_extra_actions():
            links.append({
                'label': self._get_action_label(action),
                'href': self._get_action_href(action)
            })

        extra_context = extra_context or {}
        extra_context['extra_links'] = links

        return super(ExtraActionsMixin, self).changelist_view(
            request, extra_context=extra_context,
        )

    def _get_action_href(self, action):
        return action.__name__

    def _get_action_label(self, action):
        return getattr(action, 'name', action.__name__.replace('_', ' ').capitalize())
