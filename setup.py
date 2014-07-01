#!/usr/bin/env python

from setuptools import setup, find_packages

# Currently, a bug in setuptools prevents dependencies from being installed
# into site-packages/foo/ when zip_safe=False.
# Instead, they'll be installed ass .egg zip files. This breaks Django
# migrations.  So, base requirements have to be installed before `python
# setup.py develop` can be executed.

from pip.req import parse_requirements
#install_requirements = parse_requirements("./requirements.txt")
#install_requires = [str(ir.req) for ir in install_requirements]
dev_requirements = parse_requirements("./dev_requirements.txt")
dev_requires = [str(ir.req) for ir in dev_requirements]
tests_requirements = parse_requirements("./tests_requirements.txt")
tests_requires = [str(ir.req) for ir in tests_requirements]

setup(
    name='nodeconductor',
    version='0.1.0-dev',
    author='OpenNode Team',
    author_email='info@opennodecloud.com',
    url='https://code.opennodecloud.com/nodeconductor/nodeconductor',
    description='Node Conductor.',
    long_description=open('README.rst').read(),
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    #install_requires=install_requires,
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
