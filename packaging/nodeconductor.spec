%define __conf_dir %{_sysconfdir}/%{name}
%define __data_dir %{_datadir}/%{name}
%define __log_dir %{_localstatedir}/log/%{name}
%define __logrotate_dir %{_sysconfdir}/logrotate.d
%define __work_dir %{_sharedstatedir}/%{name}

%define __celery_conf_file %{__conf_dir}/celery.conf
%define __celery_systemd_unit_file %{_unitdir}/%{name}-celery.service
%define __celerybeat_systemd_unit_file %{_unitdir}/%{name}-celerybeat.service
%define __conf_file %{__conf_dir}/settings.ini
%define __logrotate_conf_file %{__logrotate_dir}/%{name}
%define __uwsgi_conf_file %{__conf_dir}/uwsgi.ini
%define __uwsgi_systemd_unit_file %{_unitdir}/%{name}-uwsgi.service

Name: nodeconductor
Summary: NodeConductor
Version: 0.113.1
Release: 1.el7
License: MIT

# python-django-cors-headers is packaging-specific dependency; it is not required in upstream code
# python-psycopg2 is needed to use PostgreSQL as database backend
Requires: logrotate
Requires: python-celery >= 3.1.23, python-celery < 3.2
Requires: python-croniter >= 0.3.4, python-croniter < 0.3.6
Requires: python-django >= 1.8, python-django < 1.9
Requires: python-django-admin-tools = 0.7.0
Requires: python-django-cors-headers
Requires: python-django-filter >= 0.10
Requires: python-django-fluent-dashboard = 0.5.1
Requires: python-django-fsm = 2.3.0
Requires: python-django-gm2m = 0.4.2
Requires: python-django-model-utils = 2.5.2
Requires: python-django-permission = 0.9.2
Requires: python-django-redis-cache >= 1.6.5
Requires: python-django-rest-framework >= 3.1.3, python-django-rest-framework < 3.2.0
Requires: python-django-reversion >= 1.8.7, python-django-reversion <= 1.9.3
Requires: python-django-taggit >= 0.20.2
Requires: python-elasticsearch = 1.4.0
Requires: python-hiredis >= 0.2.0
Requires: python-iptools >= 0.6.1
Requires: python-jsonfield = 1.0.0
Requires: python-pillow >= 2.0.0
Requires: python-psycopg2
Requires: python-country >= 1.20, python-country < 2.0
Requires: python-vat >= 1.3.1, python-vat < 2.0
Requires: python-redis = 2.10.3
Requires: python-requests >= 2.6.0
Requires: python-sqlparse >= 0.1.11
Requires: python-tlslite = 0.4.8
Requires: python-urllib3 >= 1.10.1, python-urllib3 < 1.18
Requires: PyYAML
Requires: uwsgi-plugin-python

Source0: %{name}-%{version}.tar.gz

BuildArch: noarch
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot

# python-django* packages are needed to generate static files
# python-setuptools package is needed to run 'python setup.py <cmd>'
# systemd package provides _unitdir RPM macro
BuildRequires: python-django >= 1.8
BuildRequires: python-django-fluent-dashboard
BuildRequires: python-django-rest-framework >= 3.1.3, python-django-rest-framework < 3.2.0
BuildRequires: python-setuptools
BuildRequires: systemd

%description
NodeConductor is an infrastructure and application management server developed by OpenNode.

%prep
%setup -q -n %{name}-%{version}

%build
cp packaging/settings.py nodeconductor/server/settings.py
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
    'django.contrib.admin',
    'django.contrib.staticfiles',
    'nodeconductor.landing',
    'rest_framework',
)
SECRET_KEY = 'tmp'
STATIC_ROOT = '%{buildroot}%{__data_dir}/static'
STATIC_URL = '/static/'
TEMPLATE_CONTEXT_PROCESSORS = (
    'django.template.context_processors.request',  # required by django-admin-tools >= 0.7.0
)
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    'admin_tools.template_loaders.Loader',  # required by django-admin-tools >= 0.7.0
)
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
%{_unitdir}/*
%{_bindir}/*
%{__data_dir}
%{__log_dir}
%{__logrotate_dir}/*
%{__work_dir}
%config(noreplace) %{__celery_conf_file}
%config(noreplace) %{__conf_file}
%config(noreplace) %{__uwsgi_conf_file}

%post
%systemd_post %{name}-celery.service
%systemd_post %{name}-celerybeat.service
%systemd_post %{name}-uwsgi.service

if [ "$1" = 1 ]; then
    # This package is being installed for the first time
    echo "[%{name}] Generating secret key..."
    sed -i "s,{{ secret_key }},$(head -c32 /dev/urandom | base64)," %{__conf_file}

    echo "[%{name}] Adding new system user %{name}..."
    useradd --home %{__work_dir} --shell /bin/sh --system --user-group %{name}
elif [ "$1" = 2 ]; then
    # This package is being upgraded
    # Applicable to nodeconductor-0.103.0 and before
    [ "$(getent passwd nodeconductor | cut -d: -f7)" = "/sbin/nologin" ] && usermod -s /bin/sh nodeconductor
fi

echo "[%{name}] Setting directory permissions..."
chown -R %{name}:%{name} %{__log_dir}
chmod -R g+w %{__log_dir}
chown -R %{name}:%{name} %{__work_dir}

cat <<EOF
------------------------------------------------------------------------
NodeConductor installed successfully.

Next steps:

1. Configure database server connection in %{__conf_file}.
   Database server (PostgreSQL) must be running already.

2. Configure task queue backend connection in %{__conf_file}.
   Key-value store (Redis) must be running already.

3. Review and modify other settings in %{__conf_file}.

4. Create database (if not yet done):

     CREATE DATABASE nodeconductor ENCODING 'UTF8';
     CREATE USER nodeconductor WITH PASSWORD 'nodeconductor';

5. Migrate the database:

     su - nodeconductor -c "nodeconductor migrate --noinput"

   Note: you will need to run this again on next NodeConductor update.

6. Start NodeConductor services:

     systemctl start nodeconductor-celery
     systemctl start nodeconductor-celerybeat
     systemctl start nodeconductor-uwsgi

7. Create first superuser (if needed and not yet done):

     su - nodeconductor -c "nodeconductor createsuperuser"

All done. Happy NodeConducting!
------------------------------------------------------------------------
EOF

%preun
%systemd_preun %{name}-celery.service
%systemd_preun %{name}-celerybeat.service
%systemd_preun %{name}-uwsgi.service

%postun
%systemd_postun_with_restart %{name}-celery.service
%systemd_postun_with_restart %{name}-celerybeat.service
%systemd_postun_with_restart %{name}-uwsgi.service

%changelog
* Fri Dec 30 2016 Jenkins <jenkins@opennodecloud.com> - 0.113.1-1.el7
- New upstream release

* Fri Dec 30 2016 Jenkins <jenkins@opennodecloud.com> - 0.113.0-1.el7
- New upstream release

* Tue Dec 27 2016 Jenkins <jenkins@opennodecloud.com> - 0.112.1-1.el7
- New upstream release

* Fri Dec 23 2016 Jenkins <jenkins@opennodecloud.com> - 0.112.0-1.el7
- New upstream release

* Fri Dec 16 2016 Juri Hudolejev <juri@opennodecloud.com> - 0.111.0-2.el7
- Drop MySQL and SQLite3 database backend support

* Wed Dec 14 2016 Jenkins <jenkins@opennodecloud.com> - 0.111.0-1.el7
- New upstream release

* Fri Nov 11 2016 Jenkins <jenkins@opennodecloud.com> - 0.110.0-1.el7
- New upstream release

* Wed Oct 26 2016 Jenkins <jenkins@opennodecloud.com> - 0.109.0-1.el7
- New upstream release

* Mon Oct 10 2016 Jenkins <jenkins@opennodecloud.com> - 0.108.3-1.el7
- New upstream release

* Fri Oct 7 2016 Jenkins <jenkins@opennodecloud.com> - 0.108.2-1.el7
- New upstream release

* Tue Sep 27 2016 Jenkins <jenkins@opennodecloud.com> - 0.108.1-1.el7
- New upstream release

* Tue Sep 27 2016 Jenkins <jenkins@opennodecloud.com> - 0.108.0-1.el7
- New upstream release

* Thu Sep 15 2016 Jenkins <jenkins@opennodecloud.com> - 0.107.1-1.el7
- New upstream release

* Thu Sep 15 2016 Jenkins <jenkins@opennodecloud.com> - 0.107.0-1.el7
- New upstream release

* Tue Sep 13 2016 Jenkins <jenkins@opennodecloud.com> - 0.106.0-1.el7
- New upstream release

* Fri Sep 2 2016 Jenkins <jenkins@opennodecloud.com> - 0.105.0-2.el7
- Add uWSGI as WSGI runner

* Wed Aug 31 2016 Jenkins <jenkins@opennodecloud.com> - 0.105.0-1.el7
- New upstream release

* Thu Aug 18 2016 Jenkins <jenkins@opennodecloud.com> - 0.104.1-1.el7
- New upstream release

* Sun Aug 14 2016 Jenkins <jenkins@opennodecloud.com> - 0.104.0-1.el7
- New upstream release

* Fri Jul 15 2016 Jenkins <jenkins@opennodecloud.com> - 0.103.0-1.el7
- New upstream release

* Wed Jul 6 2016 Jenkins <jenkins@opennodecloud.com> - 0.102.5-1.el7
- New upstream release

* Mon Jul 4 2016 Jenkins <jenkins@opennodecloud.com> - 0.102.4-1.el7
- New upstream release

* Thu Jun 30 2016 Jenkins <jenkins@opennodecloud.com> - 0.102.3-1.el7
- New upstream release

* Wed Jun 29 2016 Jenkins <jenkins@opennodecloud.com> - 0.102.2-1.el7
- New upstream release

* Mon Jun 27 2016 Jenkins <jenkins@opennodecloud.com> - 0.102.1-1.el7
- New upstream release

* Wed Jun 22 2016 Jenkins <jenkins@opennodecloud.com> - 0.102.0-1.el7
- New upstream release

* Thu Jun 16 2016 Jenkins <jenkins@opennodecloud.com> - 0.101.3-1.el7
- New upstream release

* Tue Jun 14 2016 Jenkins <jenkins@opennodecloud.com> - 0.101.2-1.el7
- New upstream release

* Mon Jun 13 2016 Jenkins <jenkins@opennodecloud.com> - 0.101.1-1.el7
- New upstream release

* Mon Jun 13 2016 Jenkins <jenkins@opennodecloud.com> - 0.101.0-1.el7
- New upstream release

* Tue Jun 7 2016 Jenkins <jenkins@opennodecloud.com> - 0.100.0-1.el7
- New upstream release

* Wed Jun 1 2016 Jenkins <jenkins@opennodecloud.com> - 0.99.1-1.el7
- New upstream release

* Wed Jun 1 2016 Jenkins <jenkins@opennodecloud.com> - 0.99.0-1.el7
- New upstream release

* Fri May 27 2016 Juri Hudolejev <juri@opennodecloud.com> - 0.98.0-2.el7
- Fix RPM dependencies

* Tue May 24 2016 Jenkins <jenkins@opennodecloud.com> - 0.98.0-1.el7
- New upstream release

* Tue May 24 2016 Juri <juri@opennodecloud.com> - 0.97.0-2.el7
- Fixed dependency versions

* Mon May 16 2016 Jenkins <jenkins@opennodecloud.com> - 0.97.0-1.el7
- New upstream release

* Sun Apr 24 2016 Jenkins <jenkins@opennodecloud.com> - 0.96.0-1.el7
- New upstream release

* Tue Apr 19 2016 Jenkins <jenkins@opennodecloud.com> - 0.95.0-1.el7
- New upstream release

* Mon Apr 18 2016 Jenkins <jenkins@opennodecloud.com> - 0.94.0-1.el7
- New upstream release

* Tue Apr 5 2016 Jenkins <jenkins@opennodecloud.com> - 0.93.0-1.el7
- New upstream release

* Mon Apr 4 2016 Jenkins <jenkins@opennodecloud.com> - 0.92.0-1.el7
- New upstream release

* Wed Mar 30 2016 Jenkins <jenkins@opennodecloud.com> - 0.91.0-1.el7
- New upstream release

* Wed Mar 16 2016 Jenkins <jenkins@opennodecloud.com> - 0.90.0-1.el7
- New upstream release

* Wed Mar 2 2016 Jenkins <jenkins@opennodecloud.com> - 0.89.0-1.el7
- New upstream release

* Wed Feb 17 2016 Jenkins <jenkins@opennodecloud.com> - 0.88.0-1.el7
- New upstream release

* Mon Feb 15 2016 Jenkins <jenkins@opennodecloud.com> - 0.87.0-1.el7
- New upstream release

* Sun Feb 7 2016 Jenkins <jenkins@opennodecloud.com> - 0.86.0-1.el7
- New upstream release

* Tue Jan 26 2016 Jenkins <jenkins@opennodecloud.com> - 0.85.0-1.el7
- New upstream release

* Tue Dec 29 2015 Jenkins <jenkins@opennodecloud.com> - 0.84.0-1.el7
- New upstream release

* Tue Dec 8 2015 Jenkins <jenkins@opennodecloud.com> - 0.83.1-1.el7
- New upstream release

* Tue Dec 8 2015 Jenkins <jenkins@opennodecloud.com> - 0.83.0-1.el7
- New upstream release

* Mon Nov 30 2015 Jenkins <jenkins@opennodecloud.com> - 0.82.0-1.el7
- New upstream release

* Mon Nov 23 2015 Jenkins <jenkins@opennodecloud.com> - 0.81.0-1.el7
- New upstream release

* Sun Nov 22 2015 Jenkins <jenkins@opennodecloud.com> - 0.80.0-1.el7
- New upstream release

* Tue Nov 10 2015 Jenkins <jenkins@opennodecloud.com> - 0.79.0-1.el7
- New upstream release

* Fri Oct 30 2015 Jenkins <jenkins@opennodecloud.com> - 0.78.0-1.el7
- New upstream release

* Thu Oct 29 2015 Jenkins <jenkins@opennodecloud.com> - 0.77.0-1.el7
- New upstream release

* Wed Oct 21 2015 Jenkins <jenkins@opennodecloud.com> - 0.76.0-1.el7
- New upstream release

* Mon Oct 5 2015 Jenkins <jenkins@opennodecloud.com> - 0.75.0-1.el7
- New upstream release

* Tue Aug 11 2015 Jenkins <jenkins@opennodecloud.com> - 0.74.0-1.el7
- New upstream release

* Mon Aug 10 2015 Jenkins <jenkins@opennodecloud.com> - 0.73.0-1.el7
- New upstream release

* Sun Aug 9 2015 Jenkins <jenkins@opennodecloud.com> - 0.72.0-1.el7
- New upstream release

* Thu Aug 6 2015 Jenkins <jenkins@opennodecloud.com> - 0.71.0-1.el7
- New upstream release

* Wed Aug 5 2015 Juri Hudolejev <juri@opennodecloud.com> - 0.70.0-2.el7
- Dependencies fixed: python-stevedore is no longer required

* Wed Aug 5 2015 Jenkins <jenkins@opennodecloud.com> - 0.70.0-1.el7
- New upstream release

* Mon Jul 27 2015 Jenkins <jenkins@opennodecloud.com> - 0.69.0-1.el7
- New upstream release

* Sun Jul 26 2015 Jenkins <jenkins@opennodecloud.com> - 0.68.0-1.el7
- New upstream release

* Sat Jul 25 2015 Jenkins <jenkins@opennodecloud.com> - 0.67.0-1.el7
- New upstream release

* Tue Jul 21 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.66.0-2.el7
- New upstream release. Fixed dependencies.

* Wed Jul 15 2015 Jenkins <jenkins@opennodecloud.com> - 0.65.0-1.el7
- New upstream release

* Sun Jul 12 2015 Jenkins <jenkins@opennodecloud.com> - 0.64.0-1.el7
- New upstream release

* Sun Jul 5 2015 Jenkins <jenkins@opennodecloud.com> - 0.63.0-1.el7
- New upstream release

* Tue Jun 30 2015 Jenkins <jenkins@opennodecloud.com> - 0.62.0-1.el7
- New upstream release

* Tue Jun 30 2015 Jenkins <jenkins@opennodecloud.com> - 0.61.0-1.el7
- New upstream release

* Sun Jun 28 2015 Jenkins <jenkins@opennodecloud.com> - 0.60.0-1.el7
- New upstream release

* Sat Jun 27 2015 Jenkins <jenkins@opennodecloud.com> - 0.59.0-1.el7
- New upstream release

* Thu Jun 25 2015  <> - 0.58.0-1.el7
- New upstream release

* Wed Jun 24 2015 Jenkins <jenkins@opennodecloud.com> - 0.57.0-1.el7
- New upstream release

* Wed Jun 24 2015 Jenkins <jenkins@opennodecloud.com> - 0.56.0-1.el7
- New upstream release

* Sun Jun 21 2015 Pavel Marchuk <pavel@opennodecloud.com> - 0.55.1-1.el7
- New upstream release

* Thu Jun 18 2015 Juri Hudolejev <juri@opennodecloud.com> - 0.54.0-1.el7
- New upstream release

* Thu Jun 18 2015 Juri Hudolejev <juri@opennodecloud.com> - 0.53.1-2.el7
- Config fixes

* Wed Jun 17 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.53.1-1.el7
- New upstream bugfix release

* Wed Jun 17 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.53.0-1.el7
- New upstream release

* Tue Jun 16 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.52.0-1.el7
- New upstream release

* Sat Jun 13 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.51.0-1.el7
- New upstream release

* Sun Jun 7 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.50.0-2.el7
- Add missing python-ceilometerclient dependency

* Sat Jun 6 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.50.0-1.el7
- New upstream release

* Tue May 26 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.49.0-1.el7
- New upstream release

* Sat May 16 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.48.0-2.el7
- Fix failing dependency version

* Sat May 16 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.48.0-1.el7
- New upstream release

* Tue May 5 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.47.0-1.el7
- New upstream release

* Fri Apr 24 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.46.0-1.el7
- New upstream release

* Sun Apr 12 2015 Juri Hudolejev <juri@opennodecloud.com> - 0.45.3-2.el7
- Fixed missing configs in RPM

* Sun Apr 12 2015 Pavel Marchuk <pavel@opennodecloud.com> - 0.45.3-1.el7
- New upstream release

* Fri Apr 10 2015 Dmitri Chumak <dmitri@opennodecloud.com> - 0.45.2-2.el7
- Fixed celery.conf and settings.ini twice listed warning

* Thu Apr 9 2015 Ihor Kaharlichenko <ihor@opennodecloud.com> - 0.45.2-1.el7
- New upstream release

* Thu Apr 9 2015 Ihor Kaharlichenko <ihor@opennodecloud.com> - 0.45.1-1.el7
- New upstream release

* Wed Apr 8 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.45.0-1.el7
- New upstream release
- Dropped dependency on python-django-rest-framework-extensions
- Bumped minimal version of python-django-rest-framework

* Tue Apr 7 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.44.0-1.el7
- New upstream release

* Sat Apr 4 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.43.0-1.el7
- New upstream release

* Mon Mar 30 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.42.0-1.el7
- New upstream release

* Sun Mar 22 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.41.0-2.el7
- Fixed settings.py to include correct references to celery tasks

* Thu Mar 19 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.41.0-1.el7
- New upstream release
- Added dependency on python-django-polymorphic

* Tue Mar 3 2015 Ihor Kaharlichenko <ihor@opennodecloud.com> - 0.40.2-1.el7
- New upstream release

* Mon Mar 2 2015 Ihor Kaharlichenko <ihor@opennodecloud.com> - 0.40.1-1.el7
- New upstream release

* Sat Feb 28 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.40.0-1.el7
- New upstream release

* Thu Feb 26 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.39.0-1.el7
- New upstream release

* Sun Feb 22 2015 Ihor Kaharlichenko <ihor@opennodecloud.com> - 0.38.2-1.el7
- New upstream release

* Sat Feb 21 2015 Ihor Kaharlichenko <ihor@opennodecloud.com> - 0.38.1-1.el7
- New upstream release

* Fri Feb 20 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.38.0-1.el7
- New upstream release
- Add service_statistics_update_period setting

* Fri Feb 20 2015 Ihor Kaharlichenko <ihor@opennodecloud.com> - 0.37.0-1.el7
- New upstream release

* Wed Feb 18 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.36.0-1.el7
- New upstream release

* Mon Feb 16 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.35.0-1.el7
- New upstream release

* Mon Feb 16 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.34.0-2.el7
- Modified default name of the security group from ping to icmp

* Fri Feb 13 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.34.0-1.el7
- New upstream release

* Sat Jan 31 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.33.0-1.el7
- New upstream release

* Wed Jan 28 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.32.0-1.el7
- New upstream release

* Mon Jan 26 2015 Juri Hudolejev <juri@opennodecloud.com> - 0.31.0-1.el7
- New upstream release

* Fri Jan 23 2015 Juri Hudolejev <juri@opennodecloud.com> - 0.30.0-1.el7
- New upstream release

* Tue Jan 20 2015 Juri Hudolejev <juri@opennodecloud.com> - 0.29.0-1.el7
- New upstream release

* Sun Jan 18 2015 Juri Hudolejev <juri@opennodecloud.com> - 0.28.0-1.el7
- New upstream release

* Wed Jan 14 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.27.0-1.el7
- New upstream release

* Tue Jan 13 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.26.0-1.el7
- New upstream release

* Tue Jan 13 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.25.0-2.el7
- Added missing jsonfield dependency

* Tue Jan 13 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.25.0-1.el7
- New upstream release

* Mon Jan 12 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.24.0-1.el7
- New upstream release

* Sun Jan 11 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.23.0-1.el7
- New upstream release

* Sat Jan 10 2015 Ilja Livenson <ilja@opennodecloud.com> - 0.22.0-1.el7
- New upstream release

* Tue Jan 6 2015 Juri Hudolejev <juri@opennodecloud.com> - 0.21.0-1.el7
- New upstream release

* Thu Jan 1 2015 Juri Hudolejev <juri@opennodecloud.com> - 0.20.0-1.el7
- New upstream release

* Tue Dec 30 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.19.0-1.el7
- New upstream release

* Mon Dec 29 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.18.0-1.el7
- New upstream release

* Sun Dec 28 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.17.0-1.el7
- New upstream release

* Fri Dec 26 2014 Ihor Kaharlichenko <ihor@opennodecloud.com> - 0.16.1-1.el7
- New upstream release

* Thu Dec 25 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.16.0-1.el7
- New upstream release

* Thu Dec 25 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.15.0-1.el7
- New upstream release
- Sentry integration added

* Wed Dec 24 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.14.0-1.el7
- New upstream release

* Wed Dec 24 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.13.0-1.el7
- New upstream release

* Fri Dec 19 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.12.0-1.el7
- New upstream release

* Wed Dec 10 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.11.0-1.el7
- New upstream release
- Celery startup scripts replaced with systemd units

* Thu Dec 4 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.10.0-1.el7
- Dependencies fixed for CentOS 7

* Wed Dec 3 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.10.0-1
- New upstream release

* Tue Nov 18 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.9.0-1
- New upstream release

* Mon Nov 10 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.8.0-1
- New upstream release

* Tue Nov 4 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.7.0-1
- New upstream release

* Wed Oct 29 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.6.2-1
- New upstream hotfix release

* Tue Oct 28 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.6.1-1
- New upstream hotfix release

* Tue Oct 28 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.6.0-1
- New upstream release

* Tue Oct 21 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.5.0-1
- New upstream release

* Tue Oct 14 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.4.0-1
- New upstream release
- New settings file format: .ini instead of .py

* Wed Oct 1 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.3.0-1
- New upstream release
- Celery scripts added

* Tue Sep 23 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.2.1-1
- New upstream release
- SAML2 keys are generated in the correct dir
- SAML2 configuration hints are now displayed during install

* Mon Sep 22 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.2.0-1
- New upstream release
- Switched to MySQL as default database backend

* Thu Sep 4 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.1.1-1
- First 0.1 release
