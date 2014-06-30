Name: nodeconductor
Summary: NodeConductor
Version: 0.1.0dev
Release: 1
License: Copyright 2014 OpenNode LLC.  All rights reserved.

Requires: Django
Requires: South
Requires: django-background-task
Requires: djangorestframework
Requires: logan

Source0: %{name}-%{version}.tar.gz

BuildArch: noarch
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root

BuildRequires: python-setuptools

%description

NodeConductor is a infrastructure and application management server developed by OpenNode.

%prep
%setup -n %{name}-%{version}

%build
python setup.py build

%install
python setup.py install --single-version-externally-managed -O1 --root=%{buildroot} --record=INSTALLED_FILES

%clean
rm -rf %{buildroot}

%files -f INSTALLED_FILES
%defattr(-,root,root,-)

%changelog
* Mon Jun 30 2014 Juri Hudolejev <juri@opennodecloud.com> - 0.1.0dev-1
- Initial version of the pacakge
