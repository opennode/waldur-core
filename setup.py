#!/usr/bin/env python

from setuptools import setup, find_packages


dev_requires = [
    'Sphinx==1.2.2'
]

tests_requires = [
    'factory_boy==2.4.1',
    'mock==1.0.1',
    'mock-django==0.6.6',
    'six>=1.7.3',
    'django-celery==3.1.16',
]

install_requires = [
    'Celery>=3.1.15,<3.2',
    'croniter==0.3.5',
    'Django>=1.6.5,<1.7',
    'django-auth-ldap==1.2.0',
    'django-filter==0.7',
    'django-fsm==2.2.0',
    'django-permission==0.8.2',
    'django-requestlogging==1.0.1',
    'django-uuidfield==0.5.0',
    'djangorestframework>=2.3.12,<2.4.0',
    'djangosaml2>=0.11.0,<0.12',
    'drf-extensions==0.2.6',
    'logan==0.5.9.1',
    'python-keystoneclient>=0.9.0,<0.11.2',
    'python-novaclient>=2.17.0,<2.19.0',
    'redis==2.10.3',
    'South==0.8.4',
]


setup(
    name='nodeconductor',
    version='0.7.0',
    author='OpenNode Team',
    author_email='info@opennodecloud.com',
    url='https://github.com/opennode/nodeconductor',
    description='NodeConductor is REST server for infrastructure management.',
    long_description=open('README.rst').read(),
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    install_requires=install_requires,
    extras_require={
        'tests': tests_requires,
        'dev': dev_requires,
    },
    entry_points={
        'console_scripts': ('nodeconductor = nodeconductor.server.logan_runner:main',)
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
