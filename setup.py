#!/usr/bin/env python

from setuptools import setup, find_packages


dev_requires = [
    'Sphinx==1.2.2'
]

tests_requires = [
    'factory_boy==2.4.1',
    'six>=1.7.3',
]

install_requires = [
    'Django>=1.6.5,<1.7',
    'djangorestframework>=2.3.12,<2.4.0',
    'South==0.8.4',
    'logan==0.5.9.1',
    'django-fsm==2.2.0',
    'django-uuidfield==0.5.0',
    'django-permission==0.8.2',
    'django-auth-ldap==1.2.0',
    'django-filter==0.7',
    'djangosaml2>=0.11.0,<0.12',
]


setup(
    name='nodeconductor',
    version='0.2.1',
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
