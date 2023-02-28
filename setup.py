import os

import setuptools

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
        include_package_data=True,
        install_requires=[
            'python-utils>=3.5.2',
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
                'jinja2',
                'pygments',
            ],
        },
        long_description=long_description,
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
