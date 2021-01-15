import os
import sys
import setuptools
from setuptools.command.test import test as TestCommand

# To prevent importing about and thereby breaking the coverage info we use this
# exec hack
about = {}
with open('django_utils/__about__.py') as fp:
    exec(fp.read(), about)


if os.path.isfile('README.rst'):
    long_description = open('README.rst').read()
else:
    long_description = ('See http://pypi.python.org/pypi/' +
                        about['__package_name__'])


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
        name='django-utils2',
        version=about['__version__'],
        author=about['__author__'],
        author_email=about['__author_email__'],
        description=about['__description__'],
        url=about['__url__'],
        license='BSD',
        packages=setuptools.find_packages(exclude=['tests']),
        install_requires=[
            'python-utils>=2.5.0',
            'anyjson>=0.3.0'
        ],
        extras_require={
            'docs': [
                'django',
                'mock',
                'sphinx>=1.7.2',
            ],
            'tests': [
                'sphinx',
                'pytest',
                'pytest-cache',
                'pytest-cov',
                'pytest-django',
                'pytest-flake8',
                'jinja2',
                'pygments',
            ],
        },
        long_description=long_description,
        cmdclass={'test': PyTest},
        classifiers=[
            'Development Status :: 6 - Mature',
            'Environment :: Web Environment',
            'Framework :: Django',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: BSD License',
            'Operating System :: OS Independent',
            'Natural Language :: English',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.4',
            'Programming Language :: Python :: 3.5',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7',
            'Topic :: Internet :: WWW/HTTP',
            'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
            'Topic :: Internet :: WWW/HTTP :: WSGI',
            'Topic :: Software Development :: Libraries :: Python Modules',
        ],
    )

