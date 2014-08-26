from django.contrib import admin
from django.contrib.auth import admin as auth_admin, get_user_model

from nodeconductor.core import models


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
        raise auth_admin.forms.ValidationError(
            self.error_messages['duplicate_username'],
            code='duplicate_username',
        )


class UserChangeForm(auth_admin.UserChangeForm):
    class Meta(object):
        model = get_user_model()
        fields = '__all__'


class UserAdmin(auth_admin.UserAdmin):
    list_display = ('username', 'uuid', 'email', 'first_name', 'last_name', 'is_staff')
    search_fields = ('username', 'uuid', 'first_name', 'last_name', 'email')
    form = UserChangeForm
    add_form = UserCreationForm


admin.site.register(models.User, UserAdmin)
