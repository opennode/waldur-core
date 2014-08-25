Name: nodeconductor
Summary: NodeConductor
Version: 0.1.0dev
Release: 15
License: Copyright 2014 OpenNode LLC.  All rights reserved.

Requires: logrotate
Requires: python-django16 >= 1.6.5
Requires: python-django-background-task = 0.1.6
Requires: python-django-fsm = 2.1.0
Requires: python-django-rest-framework >= 2.3.12
Requires: python-django-sshkey >= 2.2.0
Requires: python-django-taggit = 0.12
Requires: python-django-uuidfield = 0.5.0
Requires: python-logan = 0.5.9.1
Requires: python-setuptools
Requires: python-south = 0.8.4
Requires: python-django-auth-ldap >= 1.2.0
Requires: python-django-guardian >= 1.2.4
Requires: python-six >= 1.7.3

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
%define __conf_dir %{_sysconfdir}/%{name}
%define __data_dir %{_datadir}/%{name}
%define __log_dir %{_localstatedir}/log/%{name}
%define __work_dir %{_sharedstatedir}/%{name}

rm -rf %{buildroot}
python setup.py install --single-version-externally-managed -O1 --root=%{buildroot} --record=INSTALLED_FILES

mkdir -p %{buildroot}%{__data_dir}/static
echo "%{__data_dir}" >> INSTALLED_FILES

mkdir -p %{buildroot}%{__log_dir}
echo "%{__log_dir}" >> INSTALLED_FILES

mkdir -p %{buildroot}%{__work_dir}
echo "%{__work_dir}" >> INSTALLED_FILES

mkdir -p %{buildroot}%{_sysconfdir}/%{name}
cp nodeconductor/server/settings.py.template %{buildroot}%{__conf_dir}/settings.py
sed -i 's,{{ db_file_path }},%{__work_dir}/db.sqlite3,' %{buildroot}%{__conf_dir}/settings.py
sed -i 's,{{ static_root }},%{__data_dir}/static,' %{buildroot}%{__conf_dir}/settings.py
echo "%{__conf_dir}" >> INSTALLED_FILES

mkdir -p %{buildroot}%{_sysconfdir}/init
cp packaging/upstart/%{name}.conf %{buildroot}%{_sysconfdir}/init/
echo "%{_sysconfdir}/init/%{name}.conf" >> INSTALLED_FILES

mkdir -p %{buildroot}%{_sysconfdir}/logrotate.d
cp packaging/logrotate/%{name} %{buildroot}%{_sysconfdir}/logrotate.d/
echo "%{_sysconfdir}/logrotate.d/%{name}" >> INSTALLED_FILES

%clean
rm -rf %{buildroot}

%files -f INSTALLED_FILES
%defattr(-,root,root,-)

%post
sed -i "s,{{ secret_key }},$(head -c32 /dev/urandom | base64)," %{__conf_dir}/settings.py
nodeconductor syncdb --noinput
nodeconductor migrate
nodeconductor collectstatic --noinput

%changelog
* Mon Aug 25 2014 Ilja Livenson <ilja@opennodecloud.com> - 0.1.0dev-15
- Bugfix

* Mon Aug 25 2014 Ilja Livenson <ilja@opennodecloud.com> - 0.1.0dev-14
- Exposed user management through REST

* Sun Aug 24 2014 Ilja Livenson <ilja@opennodecloud.com> - 0.1.0dev-13
- Exposed project permission management
- Exposed user information

* Thu Aug 21 2014 Ihor Kaharlichenko <ihor@opennodecloud.com> - 0.1.0dev-12
- Enforced authentication on all endpoints
- Exposed clouds and enforced proper authorization on them
- Renamed organization resource to customer
- Implemented purchase history

* Tue Aug 19 2014 Ilja Livenson <ilja@opennodecloud.com> - 0.1.0dev-11
- Added missing branding to REST console and admin

* Mon Aug 18 2014 Ilja Livenson <ilja@opennodecloud.com> - 0.1.0dev-10
- Added dependency on six package

* Sun Aug 17 2014 Ilja Livenson <ilja@opennodecloud.com> - 0.1.0dev-9
- Dependency relaxation for minor libraries

* Sun Aug 17 2014 Ilja Livenson <ilja@opennodecloud.com> - 0.1.0dev-8
- Added dependency on django-guardian

* Sun Aug 17 2014 Ilja Livenson <ilja@opennodecloud.com> - 0.1.0dev-7
- Added support for ldap integration

* Mon Jul 21 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.1.0dev-6
- Logging improved (NC-48)
- Default config file location fixed for nodeconductor tool

* Fri Jul 18 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.1.0dev-5
- settings.py is now provided with RPM
- Database initialization done on RPM install
- NodeConductor is not started autoamtically on system boot -- use nodeconductor-wsgi instead

* Tue Jul 15 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.1.0dev-4
- Added new dependencies: django-taggit, django-uuidfield

* Mon Jul 14 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.1.0dev-3
- Added Upstart script

* Mon Jul 7 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.1.0dev-2
- Package dependencies fixed

* Mon Jun 30 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.1.0dev-1
- Initial version of the package
