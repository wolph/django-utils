import os
from setuptools import setup

if os.path.isfile('README.rst'):
    long_description = open('README.rst').read()
else:
    long_description = 'See http://pypi.python.org/pypi/django-utils/'

setup(
    name = 'django-utils',
    version = '1.0',
    author = 'Rick van Hattem',
    author_email = 'Rick.van.Hattem@Fawo.nl',
    description = '''Django Utils is a module with some convenient utilities
        not included with the standard Django install''',
    url='https://github.com/WoLpH/django-utils',
    license = 'BSD',
    packages=['django_utils', 'django_utils.management.commands'],
    long_description=long_description,
#    test_suite='nose.collector',
#    setup_requires=['nose'],
    classifiers=[
        'License :: OSI Approved :: BSD License',
    ],
)
