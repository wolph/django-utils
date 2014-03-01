import os
import setuptools

# Little hack to make sure tests work
os.environ['DJANGO_SETTINGS_MODULE'] = 'tests.settings'

import django_utils as metadata

if os.path.isfile('README.rst'):
    long_description = open('README.rst').read()
else:
    long_description = 'See http://pypi.python.org/pypi/%s/' % (
        metadata.__package_name__)

setuptools.setup(
    name=metadata.__package_name__,
    version=metadata.__version__,
    author=metadata.__author__,
    author_email=metadata.__author_email__,
    description=metadata.__description__,
    url=metadata.__url__,
    license='BSD',
    packages=setuptools.find_packages(),
    install_requires=[
        'python-utils>=1.5.0',
        'anyjson>=0.3.0'
    ],
    long_description=long_description,
    test_suite='nose.collector',
    classifiers=['License :: OSI Approved :: BSD License'],
)

