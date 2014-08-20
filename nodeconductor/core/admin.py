from django.contrib import admin
from django.contrib.auth import admin as auth_admin

from nodeconductor.core import models


class UserAdmin(auth_admin.UserAdmin):
    list_display = ('username', 'uuid', 'email', 'first_name', 'last_name', 'is_staff')
    search_fields = ('username', 'uuid', 'first_name', 'last_name', 'email')

admin.site.register(models.User, UserAdmin)
