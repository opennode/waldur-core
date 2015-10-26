#!/usr/bin/env python
import sys
from setuptools import setup, find_packages


dev_requires = [
    'Sphinx==1.2.2',
]

tests_requires = [
    'ddt>=1.0.0',
    'factory_boy==2.4.1',
    'mock==1.0.1',
    'mock-django==0.6.6',
    'six>=1.9.0',
    'django-celery==3.1.16',
]

install_requires = [
    'Celery>=3.1.15,<3.2',
    'croniter>=0.3.4,<0.3.6',
    'Django>=1.7.1,<1.8',
    'django-auth-ldap==1.2.0',
    'django-filter==0.10',
    'django-fluent-dashboard==0.5.1',
    'django-fsm==2.2.0',
    'django-model-utils==2.2',
    'django-permission==0.8.2',
    'django-polymorphic>=0.7',
    'django-reversion>=1.8.7',
    'django-uuidfield==0.5.0',
    'djangorestframework>=3.1.0,<3.2.0',
    'djangosaml2==0.13.0',
    'elasticsearch>=1.0.0,<2.0.0',
    'jira>=0.47',
    'jsonfield==1.0.0',
    'lxml>=3.2',
    'paypalrestsdk>=1.10.0',
    'Pillow>=2.0.0,<3.0.0',
    'python-ceilometerclient==1.0.12',
    'python-cinderclient==1.1.1',
    'python-glanceclient==0.15.0',
    'python-keystoneclient==0.11.1',
    'python-neutronclient==2.3.9',
    'python-novaclient==2.20.0',
    'PyYAML>=3.10',
    'pyzabbix>=0.7.2',
    'redis==2.10.3',
    'requests>=2.6.0',
    'sqlparse>=0.1.11',
    'xhtml2pdf>=0.0.6',
]


# RPM installation does not need oslo, cliff and stevedore libs -
# they are required only for installation with setuptools
try:
    action = sys.argv[1]
except IndexError:
    pass
else:
    if action in ['develop', 'install', 'test']:
        install_requires += [
            'cliff==1.7.0',
            'oslo.config==1.4.0',
            'oslo.i18n==1.0.0',
            'oslo.utils==1.0.0',
            'stevedore==1.0.0',
        ]


setup(
    name='nodeconductor',
    version='0.76.0',
    author='OpenNode Team',
    author_email='info@opennodecloud.com',
    url='https://github.com/opennode/nodeconductor',
    description='NodeConductor is REST server for infrastructure management.',
    long_description=open('README.rst').read(),
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    install_requires=install_requires,
    extras_require={
        'dev': dev_requires,
        'tests': tests_requires,
    },
    entry_points={
        'backup_strategies': ('Instance = nodeconductor.iaas.backup.instance_backup:InstanceBackupStrategy',),
        'template_services': ('IaaS = nodeconductor.iaas.template.strategy:IaasTemplateServiceStrategy',),
        'console_scripts': ('nodeconductor = nodeconductor.server.manage:main',),
    },
    tests_require=tests_requires,
    test_suite='nodeconductor.server.test_runner.run_tests',
    include_package_data=True,
    classifiers=[
        'Framework :: Django',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
    ],
)
