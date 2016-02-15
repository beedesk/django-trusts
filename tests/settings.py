SECRET_KEY = '01)%8q7ub=+yw7^#dz5s!6kkff6%al5f)_ayvep9_b&w1q-dvs'

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'trusts',
)

AUTHENTICATION_BACKENDS = (
    'trusts.backends.TrustModelBackend',
)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

ROOT_URLCONF = 'tests.urls'
