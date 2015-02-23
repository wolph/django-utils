import os
import sys
import setuptools
from setuptools.command.test import test as TestCommand

import django_utils as metadata

if os.path.isfile('README.rst'):
    long_description = open('README.rst').read()
else:
    long_description = ('See http://pypi.python.org/pypi/' +
                        metadata.__package_name__)


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.test_args)
        sys.exit(errno)


if __name__ == '__main__':
    setuptools.setup(
        name=metadata.__package_name__,
        version=metadata.__version__,
        author=metadata.__author__,
        author_email=metadata.__author_email__,
        description=metadata.__description__,
        url=metadata.__url__,
        license='BSD',
        packages=setuptools.find_packages(exclude=['tests']),
        install_requires=[
            'python-utils>=1.6.0',
            'anyjson>=0.3.0'
            'six',
        ],
        long_description=long_description,
        cmdclass={'test': PyTest},
        classifiers=['License :: OSI Approved :: BSD License'],
    )

