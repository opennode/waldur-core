Name: nodeconductor
Summary: NodeConductor
Version: 0.1.0dev
Release: 5
License: Copyright 2014 OpenNode LLC.  All rights reserved.

Requires: python-django16 >= 1.6.5
Requires: python-django-background-task = 0.1.6
Requires: python-django-fsm = 2.1.0
Requires: python-django-rest-framework >= 2.3.12
Requires: python-django-sshkey >= 2.2.0
Requires: python-django-taggit = 0.12
Requires: python-django-uuidfield = 0.5.0
Requires: python-logan = 0.5.9.1
Requires: python-south = 0.8.4

Source0: %{name}-%{version}.tar.gz

Patch0001: 0001-wsgi-default-settings-path.patch

BuildArch: noarch
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot

BuildRequires: python-setuptools

%description
NodeConductor is a infrastructure and application management server developed by OpenNode.

%prep
%setup -q -n %{name}-%{version}

%patch0001 -p1

%build
python setup.py build

%install
%define __conf_dir %{_sysconfdir}/%{name}
%define __data_dir %{_datadir}/%{name}
%define __work_dir %{_sharedstatedir}/%{name}

rm -rf %{buildroot}
python setup.py install --single-version-externally-managed -O1 --root=%{buildroot} --record=INSTALLED_FILES

mkdir -p %{buildroot}%{__data_dir}/static
echo "%{__data_dir}" >> INSTALLED_FILES

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

%clean
rm -rf %{buildroot}

%files -f INSTALLED_FILES
%defattr(-,root,root,-)

%post
sed -i "s,{{ secret_key }},$(head -c32 /dev/urandom | base64)," %{__conf_dir}/settings.py
nodeconductor --config=%{__conf_dir}/settings.py syncdb --noinput
nodeconductor --config=%{__conf_dir}/settings.py migrate
nodeconductor --config=%{__conf_dir}/settings.py collectstatic --noinput

%changelog
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
