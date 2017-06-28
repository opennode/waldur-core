# BuildRequiresRepo: https://opennodecloud.com/centos/7/waldur-release.rpm

%define __conf_dir %{_sysconfdir}/waldur
%define __conf_file %{__conf_dir}/core.ini
%define __data_dir %{_datadir}/waldur
%define __log_dir %{_localstatedir}/log/waldur
%define __user waldur
%define __work_dir %{_sharedstatedir}/waldur

%define __celery_conf_file %{__conf_dir}/celery.conf
%define __celery_service_name waldur-celery
%define __celery_systemd_unit_file %{_unitdir}/%{__celery_service_name}.service
%define __celerybeat_service_name waldur-celerybeat
%define __celerybeat_systemd_unit_file %{_unitdir}/%{__celerybeat_service_name}.service

%define __logrotate_dir %{_sysconfdir}/logrotate.d
%define __logrotate_conf_file %{__logrotate_dir}/waldur

%define __uwsgi_service_name waldur-uwsgi
%define __uwsgi_conf_file %{__conf_dir}/uwsgi.ini
%define __uwsgi_systemd_unit_file %{_unitdir}/%{__uwsgi_service_name}.service

Name: waldur-core
Summary: Waldur Core
Version: 0.142.0
Release: 1.el7
License: MIT

Obsoletes: nodeconductor

# python-django-cors-headers is packaging-specific dependency; it is not required in upstream code
# mailcap is required for /etc/mime.types of static files served by uwsgi
Requires: logrotate
Requires: mailcap
Requires: python-celery >= 3.1.23, python-celery < 3.2
Requires: python-country >= 1.20, python-country < 2.0
Requires: python-croniter >= 0.3.4, python-croniter < 0.3.6
Requires: python-django >= 1.11, python-django < 2.0
Requires: python-django-admin-tools = 0.8.0
Requires: python-django-cors-headers = 2.1.0
Requires: python-django-filter = 1.0.2
Requires: python-django-fluent-dashboard = 0.6.1
Requires: python-django-fsm = 2.3.0
Requires: python-django-jsoneditor >= 0.0.7
Requires: python-django-model-utils = 3.0.0
Requires: python-django-redis-cache >= 1.6.5
Requires: python-django-rest-framework >= 3.6.3, python-django-rest-framework < 3.7.0
Requires: python-django-rest-swagger = 2.1.2
Requires: python-django-reversion = 2.0.8
Requires: python-django-taggit >= 0.20.2
Requires: python-elasticsearch = 5.4.0
Requires: python-hiredis >= 0.2.0
Requires: python-iptools >= 0.6.1
Requires: python-pillow >= 2.0.0
Requires: python-prettytable >= 0.7.1, python-prettytable < 0.8
Requires: python-psycopg2 >= 2.5.4
Requires: python-redis = 2.10.3
Requires: python-requests >= 2.6.0
Requires: python-sqlparse >= 0.1.11
Requires: python-tlslite = 0.4.8
Requires: python-urllib3 >= 1.10.1, python-urllib3 < 1.18
Requires: python-vat >= 1.3.1, python-vat < 2.0
Requires: PyYAML
Requires: uwsgi-plugin-python

Source0: %{name}-%{version}.tar.gz

BuildArch: noarch
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot

# gettext package is needed to run 'django-admin compilemessages'
# python-django* packages are needed to generate static files
# python-setuptools package is needed to run 'python setup.py <cmd>'
# systemd package provides _unitdir RPM macro
BuildRequires: python-celery >= 3.1.23, python-celery < 3.2
BuildRequires: gettext
BuildRequires: python-django >= 1.11, python-django < 2.0
BuildRequires: python-django-filter = 1.0.2
BuildRequires: python-django-fluent-dashboard
BuildRequires: python-django-jsoneditor >= 0.0.7
BuildRequires: python-django-rest-framework >= 3.6.3, python-django-rest-framework < 3.7.0
BuildRequires: python-django-rest-swagger = 2.1.2
BuildRequires: python-setuptools
BuildRequires: systemd

%description
Waldur Core is an open-source RESTful server for multi-tenant resource
management. It provides an easy way for sharing access to external systems.
It is used as a platform for creating private and public clouds.

Additional information can be found at http://docs.waldur.com.

%prep
%setup -q -n %{name}-%{version}

%build
cp packaging/settings.py nodeconductor/server/settings.py
django-admin compilemessages
%{__python} setup.py build

%install
rm -rf %{buildroot}
%{__python} setup.py install -O1 --root=%{buildroot}

mkdir -p %{buildroot}%{_unitdir}
cp packaging%{__celery_systemd_unit_file} %{buildroot}%{__celery_systemd_unit_file}
cp packaging%{__celerybeat_systemd_unit_file} %{buildroot}%{__celerybeat_systemd_unit_file}
cp packaging%{__uwsgi_systemd_unit_file} %{buildroot}%{__uwsgi_systemd_unit_file}

mkdir -p %{buildroot}%{__conf_dir}
cp packaging%{__celery_conf_file} %{buildroot}%{__celery_conf_file}
cp packaging%{__conf_file} %{buildroot}%{__conf_file}
cp packaging%{__uwsgi_conf_file} %{buildroot}%{__uwsgi_conf_file}

mkdir -p %{buildroot}%{__data_dir}/static
cat > tmp_settings.py << EOF
# Minimal settings required for 'collectstatic' command
INSTALLED_APPS = (
    'admin_tools',
    'admin_tools.dashboard',
    'admin_tools.menu',
    'admin_tools.theming',
    'fluent_dashboard',  # should go before 'django.contrib.admin'
    'django.contrib.contenttypes',
    'django.contrib.admin',
    'django.contrib.staticfiles',
    'jsoneditor',
    'nodeconductor.landing',
    'rest_framework',
    'rest_framework_swagger',
    'django_filters',
)
SECRET_KEY = 'tmp'
STATIC_ROOT = '%{buildroot}%{__data_dir}/static'
STATIC_URL = '/static/'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['nodeconductor/templates'],
        'OPTIONS': {
            'context_processors': (
                'django.template.context_processors.debug',
                'django.template.context_processors.request',  # required by django-admin-tools >= 0.7.0
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
            ),
            'loaders': (
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
                'admin_tools.template_loaders.Loader',  # required by django-admin-tools >= 0.7.0
            ),
        },
    },
]
EOF
%{__python} manage.py collectstatic --noinput --settings=tmp_settings

mkdir -p %{buildroot}%{__log_dir}

mkdir -p %{buildroot}%{__logrotate_dir}
cp packaging%{__logrotate_conf_file} %{buildroot}%{__logrotate_conf_file}

mkdir -p %{buildroot}%{__work_dir}/media

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%{python_sitelib}/*
%{_bindir}/*
%{_unitdir}/*
%{__data_dir}
%{__logrotate_dir}/*
%attr(0750,%{__user},%{__user}) %{__log_dir}
%attr(0750,%{__user},%{__user}) %{__work_dir}
%config(noreplace) %{__celery_conf_file}
%config(noreplace) %{__conf_file}
%config(noreplace) %{__uwsgi_conf_file}

%pre
# User must exist in the system before package installation, otherwise setting file permissions will fail
if ! id %{name} 2> /dev/null > /dev/null; then
    echo "[%{name}] Adding new system user %{__user}..."
    useradd --home %{__work_dir} --shell /bin/sh --system --user-group %{__user}
fi

%post
%systemd_post %{__celery_service_name}.service
%systemd_post %{__celerybeat_service_name}.service
%systemd_post %{__uwsgi_service_name}.service

if [ "$1" = 1 ]; then
    # This package is being installed for the first time
    echo "[%{name}] Generating secret key..."
    sed -i "s,{{ secret_key }},$(head -c32 /dev/urandom | base64)," %{__conf_file}
fi

cat <<EOF
------------------------------------------------------------------------
Waldur Core installed successfully.

Next steps:

1. Configure database server connection in %{__conf_file}.
   Database server (PostgreSQL) must be running already.

2. Configure task queue backend connection in %{__conf_file}.
   Key-value store (Redis) must be running already.

3. Review and modify other settings in %{__conf_file}.

4. Create database (if not yet done):

     CREATE DATABASE waldur ENCODING 'UTF8';
     CREATE USER waldur WITH PASSWORD 'waldur';

5. Migrate the database:

     su - %{__user} -c "nodeconductor migrate --noinput"

   Note: you will need to run this again on next Waldur Core update.

6. Start Waldur Core services:

     systemctl start %{__celery_service_name}
     systemctl start %{__celerybeat_service_name}
     systemctl start %{__uwsgi_service_name}

7. Create first superuser (if needed and not yet done):

     su - %{__user} -c "nodeconductor createsuperuser"

All done.
------------------------------------------------------------------------
EOF

%preun
%systemd_preun %{__celery_service_name}.service
%systemd_preun %{__celerybeat_service_name}.service
%systemd_preun %{__uwsgi_service_name}.service

%postun
%systemd_postun_with_restart %{__celery_service_name}.service
%systemd_postun_with_restart %{__celerybeat_service_name}.service
%systemd_postun_with_restart %{__uwsgi_service_name}.service

%changelog
* Tue Jun 27 2017 Juri Hudolejev <juri@opennodecloud.com> - 0.142.0-1
- Rename package to Waldur Core
