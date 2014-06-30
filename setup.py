#!/usr/bin/env python

from setuptools import setup, find_packages


dev_requires = [
    'Sphinx==1.2.2'
]

tests_requires = [
]

install_requires = [
    'Django>=1.6.2,<1.7',
    'djangorestframework>=2.3.12,<2.4.0',
    'South==0.8.4',
    'logan==0.5.9.1',
    'django-background-task==0.1.6',
    'django-sshkey>=2.2.0'
]


setup(
    name='nodeconductor',
    version='0.1.0-dev',
    author='OpenNode Team',
    author_email='info@opennodecloud.com',
    url='https://code.opennodecloud.com/nodeconductor/nodeconductor',
    description='Node Conductor.',
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
