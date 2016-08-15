ADMIN_INSTALLED_APPS = (
    'fluent_dashboard',
    'admin_tools',
    'admin_tools.theming',
    'admin_tools.menu',
    'admin_tools.dashboard',
    'django.contrib.admin',
)

# FIXME: Move generic (not related to admin) context processors to base_settings
# Note: replace 'django.core.context_processors' with 'django.template.context_processors' in Django 1.8+
ADMIN_TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.request',  # required by django-admin-tools >= 0.7.0
    'django.core.context_processors.static',
    'django.core.context_processors.tz',
)

ADMIN_TEMPLATE_LOADERS = (
    'admin_tools.template_loaders.Loader',  # required by django-admin-tools >= 0.7.0
)

FLUENT_DASHBOARD_APP_ICONS = {
    'core/user': 'system-users.png',
    'structure/customer': 'system-users.png',
    'structure/servicesettings': 'preferences-other.png',
    'structure/project': 'folder.png',
    'structure/projectgroup': 'folder-bookmark.png',
    'backup/backup': 'document-export-table.png',
    'backup/backupschedule': 'view-resource-calendar.png',
    'nodeconductor_killbill/invoice': 'help-donate.png',
    'cost_tracking/pricelistitem': 'view-bank-account.png',
    'cost_tracking/priceestimate': 'feed-subscribe.png',
    'cost_tracking/defaultpricelistitem': 'view-calendar-list.png'
}

ADMIN_TOOLS_INDEX_DASHBOARD = 'nodeconductor.server.admin.dashboard.CustomIndexDashboard'
ADMIN_TOOLS_APP_INDEX_DASHBOARD = 'nodeconductor.server.admin.dashboard.CustomAppIndexDashboard'
ADMIN_TOOLS_MENU = 'nodeconductor.server.admin.menu.CustomMenu'

# Should be specified, otherwise all Applications dashboard will be included.
FLUENT_DASHBOARD_APP_GROUPS = ()
