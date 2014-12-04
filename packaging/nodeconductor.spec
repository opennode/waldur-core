%define __celeryd_run_dir %{_localstatedir}/run/%{name}-celeryd
%define __conf_dir %{_sysconfdir}/%{name}
%define __data_dir %{_datadir}/%{name}
%define __init_dir %{_sysconfdir}/init.d
%define __log_dir %{_localstatedir}/log/%{name}
%define __logrotate_dir %{_sysconfdir}/logrotate.d
%define __saml2_conf_dir %{__conf_dir}/saml2
%define __system_conf_dir %{_sysconfdir}/sysconfig
%define __work_dir %{_sharedstatedir}/%{name}

%define __celeryd_conf_file %{__system_conf_dir}/%{name}-celeryd
%define __celeryd_init_file %{__init_dir}/%{name}-celeryd
%define __conf_file %{__conf_dir}/settings.ini
%define __logrotate_conf_file %{__logrotate_dir}/%{name}
%define __saml2_cert_file %{__saml2_conf_dir}/dummy.crt
%define __saml2_key_file %{__saml2_conf_dir}/dummy.pem

Name: nodeconductor
Summary: NodeConductor
Version: 0.10.0
Release: 1.el7
License: Copyright 2014 OpenNode LLC.  All rights reserved.

Requires: logrotate
Requires: MySQL-python
Requires: openssl  # needed to generate SAML2 keys during install
Requires: python-celery >= 3.1.15, python-celery < 3.2
Requires: python-croniter >= 0.3.4, python-croniter < 0.3.6
Requires: python-django >= 1.6.5
Requires: python-django-auth-ldap = 1.2.0
Requires: python-django-filter = 0.7
Requires: python-django-fsm = 2.2.0
Requires: python-django-permission = 0.8.2
Requires: python-django-request-logging = 1.0.1
Requires: python-django-rest-framework >= 2.3.12, python-django-rest-framework < 2.4.0
Requires: python-django-rest-framework-extensions = 0.2.6
Requires: python-django-saml2 >= 0.11.0, python-django-saml2 < 0.12
Requires: python-django-uuidfield = 0.5.0
Requires: python-cinderclient >= 1.0.7, python-cinderclient <= 1.1.1
Requires: python-glanceclient >= 1:0.12.0, python-glanceclient < 1:0.13.0
Requires: python-keystoneclient >= 1:0.9.0, python-keystoneclient < 1:0.11.2
Requires: python-logan = 0.5.9.1
Requires: python-neutronclient >= 2.3.4, python-neutronclient < 2.4.0
Requires: python-novaclient >= 1:2.17.0, python-novaclient < 1:2.19.0
Requires: python-redis = 2.10.3
Requires: python-south = 0.8.4
Requires: python-zabbix >= 0.7.2
Requires: xmlsec1-openssl  # needed for SAML2

Source0: %{name}-%{version}.tar.gz

Patch0001: 0001-wsgi-default-settings-path.patch
Patch0002: 0002-logan-runner-default-settings-path.patch
Patch0003: 0003-celery-default-settings-path.patch
Patch0004: 0004-default-settings-ini-path.patch

BuildArch: noarch
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot

BuildRequires: python-setuptools

%description
NodeConductor is a infrastructure and application management server developed by OpenNode.

%prep
%setup -q -n %{name}-%{version}

%patch0001 -p1
%patch0002 -p1
%patch0003 -p1
%patch0004 -p1

%build
python setup.py build

%install
rm -rf %{buildroot}
python setup.py install --single-version-externally-managed -O1 --root=%{buildroot} --record=INSTALLED_FILES

mkdir -p %{buildroot}%{__celeryd_run_dir}
echo "%{__celeryd_run_dir}" >> INSTALLED_FILES

mkdir -p %{buildroot}%{__conf_dir}
echo "%{__conf_dir}" >> INSTALLED_FILES
cp packaging%{__conf_file} %{buildroot}%{__conf_file}

mkdir -p %{buildroot}%{__data_dir}/static
echo "%{__data_dir}" >> INSTALLED_FILES

mkdir -p %{buildroot}%{__init_dir}
cp packaging%{__celeryd_init_file} %{buildroot}%{__celeryd_init_file}
echo "%{__celeryd_init_file}" >> INSTALLED_FILES

mkdir -p %{buildroot}%{__log_dir}
echo "%{__log_dir}" >> INSTALLED_FILES

mkdir -p %{buildroot}%{__logrotate_dir}
cp packaging%{__logrotate_conf_file} %{buildroot}%{__logrotate_conf_file}
echo "%{__logrotate_dir}/%{name}" >> INSTALLED_FILES

mkdir -p %{buildroot}%{__saml2_conf_dir}
# TODO: Maybe use attribute-maps from PySAML2
cp -r attribute-maps %{buildroot}%{__saml2_conf_dir}/

mkdir -p %{buildroot}%{__system_conf_dir}
cp packaging%{__celeryd_conf_file} %{buildroot}%{__celeryd_conf_file}
echo "%{__celeryd_conf_file}" >> INSTALLED_FILES

mkdir -p %{buildroot}%{__work_dir}
echo "%{__work_dir}" >> INSTALLED_FILES

cat INSTALLED_FILES | sort | uniq > INSTALLED_FILES_CLEAN

%clean
rm -rf %{buildroot}

%files -f INSTALLED_FILES_CLEAN
%defattr(-,root,root,-)
%config(noreplace) %{__conf_file}
%config(noreplace) %{__celeryd_conf_file}

%post
echo "[nodeconductor] Generating secret key..."
sed -i "s,{{ secret_key }},$(head -c32 /dev/urandom | base64)," %{__conf_file}

echo "[nodeconductor] Generating SAML2 keypair..."
if [ ! -f %{__saml2_cert_file} -a ! -f %{__saml2_key_file} ]; then
    openssl req -batch -newkey rsa:2048 -new -x509 -days 3652 -nodes -out %{__saml2_cert_file} -keyout %{__saml2_key_file}
fi

useradd --home %{__work_dir} --shell /sbin/nologin --system --user-group %{name}
chown -R %{name}:%{name} %{__celeryd_run_dir}
chown -R %{name}:%{name} %{__log_dir}
chmod -R g+w %{__log_dir}
chown -R %{name}:%{name} %{__work_dir}

cat <<EOF
------------------------------------------------------------------------
NodeConductor installed successfully.

Next steps:

1. Configure database server connection in %{__conf_file}.
   Database server (default: MySQL) must be running already.

2. Configure task queue backend connection in %{__conf_file}.
   Key-value store (default: Redis) must be running already.

3. Create database (if not yet done):

    CREATE DATABASE nodeconductor CHARACTER SET = utf8 COLLATE = utf8_bin;
    CREATE USER 'nodeconductor'@'%' IDENTIFIED BY 'nodeconductor';
    GRANT ALL PRIVILEGES ON nodeconductor.* to 'nodeconductor'@'%';

4. Initialize application:

    sudo -u nodeconductor nodeconductor syncdb --noinput
    sudo -u nodeconductor nodeconductor migrate --noinput
    nodeconductor collectstatic --noinput

Note: you will need to run this again on next NodeConductor update.

5. Start task queue backend:

    service nodeconductor-celeryd start

6. Create first superuser (if needed and not yet done):

    nodeconductor createsuperuser

7. Configure SAML2 details in %{__conf_file}:

    [saml2]
    entityid = ...
    acs_url = ...
    metadata_file = ...

All done. Happy NodeConducting!
------------------------------------------------------------------------
EOF

%changelog
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
