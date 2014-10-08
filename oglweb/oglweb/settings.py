"""
Django settings for oglweb project.

For more information on this file, see
https://docs.djangoproject.com/en/dev/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/dev/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
BASE_DIR = os.path.dirname(os.path.dirname(__file__))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/dev/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '@^z4z&io2apa&^+(_afrvd=f(31suab!8kg&+4##2as!li1i$u'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = bool(os.environ.get('OGL_SERVER_DEBUG', '') == 'TRUE')

TEMPLATE_DIRS = [os.path.join(BASE_DIR, 'templates')]
TEMPLATE_DEBUG = True

# must be populated when DEBUG is False (ie on "public" servers)
ALLOWED_HOSTS = ''
if os.environ.get('OGL_SERVER_HOSTNAMES', ''):
    ALLOWED_HOSTS = os.environ.get('OGL_SERVER_HOSTNAMES', '').split(',')

# Application definition

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'listings',
)

# This doesn't really belong here but I'm reusing the django on the home
# dev server for another app, so...
if os.environ.get('OGL_SERVER_RUN_DEV_APPS','') == 'TRUE':
    INSTALLED_APPS = INSTALLED_APPS +  ('todo',)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'oglweb.urls'

WSGI_APPLICATION = 'oglweb.wsgi.application'


# Database
# https://docs.djangoproject.com/en/dev/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'HOST': os.environ.get('OGL_DB_HOST','localhost'),
        'NAME': os.environ.get('OGL_DB','carsdb'),
# uncomment these lines and add password when/if you need to be admin (e.g. migrations)
#        'USER': 'carsdbadmin',
#        'PASSWORD': 'cars4Me',
        'USER': os.environ.get('OGL_DB_USERACCOUNT','carsdbuser'),
        'PASSWORD': os.environ.get('OGL_DB_USERACCOUNT_PASSWORD', 'nopassword'),
        'CHARSET': 'utf8', # GEE this may apply only to creating test DBs??
    }
}

# Internationalization
# https://docs.djangoproject.com/en/dev/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/Los_Angeles'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/dev/howto/static-files/

# this URL is where static files are to be loaded from
# (modulo the apache server's translation of this URL in its conf file)
STATIC_URL = '/static/'

# this directory (not URL) is where the 'collectfiles' program should collect
# the static files so that apache can point the STATIC_URL at them
# (ie STATIC_ROOT is the actual filepath that will underly STATIC_URL)
# note that this is ONLY used by collectfiles, not while serving the files, so
# it *is* safe to reference env variables that may not be set while serving.
STATIC_ROOT = os.path.join(os.environ.get('OGL_STAGE','/home/ubuntu'),'../static')

TEMPLATE_CONTEXT_PROCESSORS=(
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "django.core.context_processors.static",
    "django.core.context_processors.tz",
    "django.contrib.messages.context_processors.messages",
    # above are "default" (although not spec'd in settings.py?)
    # below are added for OGL
    "django.core.context_processors.request",
    "listings.context_processors.basic_context",
)
