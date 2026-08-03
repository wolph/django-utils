"""Django settings for the django-utils2 test suite."""

DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    },
    # Second alias solely so query_budget's `using` exclusion is testable.
    'other': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    },
}

ALLOWED_HOSTS: list[str] = []

TIME_ZONE = 'UTC'
LANGUAGE_CODE = 'en-us'
SITE_ID = 1
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'

# Test-only key, not a real credential.
SECRET_KEY = 'django-utils2-test-suite-secret-key'

# Test-only Fernet keys for django_utils.crypto_fields, not credentials --
# generated once with Fernet.generate_key() and hardcoded so the test
# suite's default encryption/decryption is deterministic across runs.
# The first key encrypts; both keys decrypt (MultiFernet rotation).
DJANGO_UTILS_FERNET_KEYS = [
    '9LSCQxpLl8Xfl9ogBCyDLhFXirKhVtNLpmuEShBJPc4=',
    'Q7LBlcU2P375f2K8lYWJkEzEVxTuiR_vf9u1rGbBnPU=',
]

MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'tests.urls'

# Django templates only: django_coverage_plugin measures template
# execution and refuses to run when a non-Django engine is configured.
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
        'DIRS': ['tests/templates'],
        'OPTIONS': {
            # django_coverage_plugin needs template debug instrumentation;
            # pytest-django forces settings.DEBUG off, which would otherwise
            # default this to False and silently disable template coverage.
            'debug': True,
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'django_utils',
    'tests.test_app',
]

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
