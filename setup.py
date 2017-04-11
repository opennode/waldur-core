#!/usr/bin/env python
from setuptools import setup, find_packages


dev_requires = [
    'Sphinx==1.2.2',
]

tests_requires = [
    'ddt>=1.0.0,<1.1.0',
    'factory_boy==2.4.1',
    'freezegun==0.3.7',
    'mock>=1.0.1',
    'mock-django==0.6.9',
    'six>=1.9.0',
    'sqlalchemy>=1.0.12',
]

install_requires = [
    'Celery>=3.1.23,<3.2',
    'croniter>=0.3.4,<0.3.6',
    'Django>=1.9,<1.10',
    'django-admin-tools==0.7.0',
    'django-filter==0.15.3',
    'django-fluent-dashboard==0.6.1',
    'django-fsm==2.3.0',
    'django-model-utils==2.5.2',
    'django-permission==0.9.2',
    'django-redis-cache>=1.6.5',
    'django-reversion>=1.10.0,<=1.10.2',
    'django-rest-swagger==2.1.1',
    'django-taggit>=0.20.2',
    'djangorestframework>=3.5.3,<3.6.0',
    'elasticsearch>=1.0.0,<2.0.0',
    'hiredis>=0.2.0',
    'iptools>=0.6.1',
    'jsonfield==1.0.0',
    'PrettyTable<0.8,>=0.7.1',
    'Pillow>=2.0.0',
    'PyYAML>=3.10',
    'pycountry>=1.20,<2.0',
    'pyvat>=1.3.1,<2.0',
    'redis==2.10.3',
    'requests>=2.6.0,!=2.12.2,!=2.13.0',
    'sqlparse>=0.1.11',
    'urllib3<1.18',
    'django-jsoneditor>=0.0.5',
]

setup(
    name='nodeconductor',
    version='0.133.0',
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
        'console_scripts': ('nodeconductor = nodeconductor.server.manage:main',),
    },
    tests_require=tests_requires,
    test_suite='nodeconductor.server.test_runner.run_tests',
    include_package_data=True,
    classifiers=[
        'Framework :: Django',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)
