import os
import setuptools

# Little hack to make sure tests work
os.environ['DJANGO_SETTINGS_MODULE'] = 'tests.settings'

import django_utils

if os.path.isfile('README.rst'):
    long_description = open('README.rst').read()
else:
    long_description = 'See http://pypi.python.org/pypi/django-utils/'

setuptools.setup(
    name=django_utils.__package_name__,
    version=django_utils.__version__,
    author=django_utils.__author__,
    author_email=django_utils.__author_email__,
    description=django_utils.__description__,
    url=django_utils.__url__,
    license='BSD',
    packages=setuptools.find_packages(),
    install_requires=[
        'python-utils>=1.1.1',
        'anyjson>=0.3.0'
    ],
    long_description=long_description,
    test_suite='nose.collector',
    classifiers=['License :: OSI Approved :: BSD License'],
)
