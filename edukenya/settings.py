from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'dev-secret-key'
DEBUG = True
ALLOWED_HOSTS = ['*']
ROOT_URLCONF = 'edukenya.urls'

INSTALLED_APPS = [
    'django.contrib.staticfiles',
    'landing',
]

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.request',
        ],
    },
}]

STATIC_URL = '/static/'
