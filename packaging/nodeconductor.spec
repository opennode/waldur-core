%define __conf_dir %{_sysconfdir}/%{name}
%define __conf_file %{__conf_dir}/settings.py
%define __data_dir %{_datadir}/%{name}
%define __log_dir %{_localstatedir}/log/%{name}
%define __logrotate_dir %{_sysconfdir}/logrotate.d
%define __saml2_conf_dir %{__conf_dir}/saml2
%define __work_dir %{_sharedstatedir}/%{name}

Name: nodeconductor
Summary: NodeConductor
Version: 0.2.0
Release: 1
License: Copyright 2014 OpenNode LLC.  All rights reserved.

Requires: logrotate
Requires: MySQL-python
Requires: python-django16 >= 1.6.5
Requires: python-django-auth-ldap >= 1.2.0
Requires: python-django-filter = 0.7
Requires: python-django-fsm = 2.2.0
Requires: python-django-permission = 0.8.2
Requires: python-django-rest-framework >= 2.3.12, python-django-rest-framework < 2.4.0
Requires: python-django-saml2
Requires: python-django-uuidfield = 0.5.0
Requires: python-logan = 0.5.9.1
Requires: python-south = 0.8.4
Requires: xmlsec1-openssl

Source0: %{name}-%{version}.tar.gz

Patch0001: 0001-wsgi-default-settings-path.patch
Patch0002: 0002-logan-runner-default-settings-path.patch

BuildArch: noarch
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot

BuildRequires: python-setuptools

%description
NodeConductor is a infrastructure and application management server developed by OpenNode.

%prep
%setup -q -n %{name}-%{version}

%patch0001 -p1
%patch0002 -p1

%build
python setup.py build

%install
rm -rf %{buildroot}
python setup.py install --single-version-externally-managed -O1 --root=%{buildroot} --record=INSTALLED_FILES

mkdir -p %{buildroot}%{__data_dir}/static
echo "%{__data_dir}" >> INSTALLED_FILES

mkdir -p %{buildroot}%{__log_dir}
echo "%{__log_dir}" >> INSTALLED_FILES

mkdir -p %{buildroot}%{__logrotate_dir}
echo "%{__logrotate_dir}/%{name}" >> INSTALLED_FILES
cp packaging/logrotate/%{name} %{buildroot}%{__logrotate_dir}/

mkdir -p %{buildroot}%{__work_dir}
echo "%{__work_dir}" >> INSTALLED_FILES

mkdir -p %{buildroot}%{__conf_dir}
echo "%{__conf_dir}" >> INSTALLED_FILES

mkdir -p %{buildroot}%{__saml2_conf_dir}
# TODO: Maybe use attribute-maps from PySAML2
cp -r attribute-maps %{buildroot}%{__saml2_conf_dir}/

cp nodeconductor/server/settings.py.template %{buildroot}%{__conf_file}
sed -i 's,{{ db_file_path }},%{__work_dir}/db.sqlite3,' %{buildroot}%{__conf_file}
sed -i 's,{{ static_root }},%{__data_dir}/static,' %{buildroot}%{__conf_file}
sed -i "s#^    'default': DATABASE_NONE#    'default': DATABASE_MYSQL#" %{buildroot}%{__conf_file}
sed -i "s#^    'attribute_map_dir': '/path/to/attribute-maps',#    'attribute_map_dir': '%{__saml2_conf_dir}attribute-maps',#" %{buildroot}%{__conf_file}
sed -i "s#^    'key_file': '/path/to/key.pem',#    'key_file': '%{__saml2_conf_dir}dummy.pem',#" %{buildroot}%{__conf_file}
sed -i "s#^    'cert_file': '/path/to/certificate.crt',#    'cert_file': '%{__saml2_conf_dir}dummy.crt',#" %{buildroot}%{__conf_file}

%clean
rm -rf %{buildroot}

%files -f INSTALLED_FILES
%defattr(-,root,root,-)

%post
echo "[nodeconductor] Generating secret key..."
sed -i "s,{{ secret_key }},$(head -c32 /dev/urandom | base64)," %{__conf_file}

echo "[nodeconductor] Generating SAML2 keypair..."
if [ ! -f %{__saml2_conf_dir}/dummy.crt -a ! -f %{__saml2_conf_dir}/dummy.pem ]; then
    openssl req -batch -newkey rsa:2048 -new -x509 -days 3652 -nodes -out %{__conf_dir}/dummy.crt -keyout %{__conf_dir}/dummy.pem
fi

cat <<EOF
------------------------------------------------------------------------
NodeConductor installed successfully.

Next steps:

1. Configure database server connection in %{__conf_file}.

2. Create database (if not yet done):

    CREATE DATABASE nodeconductor CHARACTER SET = utf8;
    CREATE USER 'nodeconductor'@'%' IDENTIFIED BY 'nodeconductor';
    GRANT ALL PRIVILEGES ON nodeconductor.* to 'nodeconductor'@'%';

3. Initialize application:

    nodeconductor syncdb --noinput
    nodeconductor migrate --noinput
    nodeconductor collectstatic --noinput

Note: you will need to run this again on next NodeConductor update.

4. Create first superuser (if needed and not yet done):

    nodeconductor createsuperuser

All done. Happy NodeConducting!
------------------------------------------------------------------------
EOF

%changelog
* Mon Sep 22 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.2.0-1
- New upstream release
- Switched to MySQL as default database backend

* Thu Sep 4 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.1.1-1
- First 0.1 release
