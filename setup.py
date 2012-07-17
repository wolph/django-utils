import django_utils
import os
from setuptools import setup

if os.path.isfile('README.rst'):
    long_description = open('README.rst').read()
else:
    long_description = 'See http://pypi.python.org/pypi/django-utils/'

setup(
    name=django_utils.__name__,
    version=django_utils.__version__,
    author=django_utils.__author__,
    author_email=django_utils.__author_email__,
    description=django_utils.__description__,
    url=django_utils.__url__,
    license='BSD',
    packages=[
        'django_utils',
        'django_utils.management',
        'django_utils.management.commands',
    ],
    install_requires=[
        'python-utils>=1.1.1',
        'anyjson>=0.3.0'
    ],
    long_description=long_description,
    test_suite='nose.collector',
    setup_requires=['nose'],
    classifiers=[
        'License :: OSI Approved :: BSD License',
    ],
)

