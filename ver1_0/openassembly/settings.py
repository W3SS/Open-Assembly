#from djangoappengine.settings_base import *
import os
import json
import djcelery

FACEBOOK_API_KEY = ''
FACEBOOK_APP_ID = ''
FACEBOOK_SECRET_KEY = ''

TWITTER_CONSUMER_KEY = ''
TWITTER_CONSUMER_SECRET_KEY = ''
TWITTER_REQUEST_TOKEN_URL = ''
TWITTER_ACCESS_TOKEN_URL = ''
TWITTER_AUTHORIZATION_URL = ''

settings_dir = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.dirname(settings_dir))

#your secret key
SECRET_KEY = '=r-$b*8hglm+858&9t043hlm6-&6-3d3vfc4((7yd0dbrakhvi'

#using haystack search with solr
HAYSTACK_SITECONF = 'openassembly.search_sites'
HAYSTACK_SEARCH_ENGINE = 'solr'
HAYSTACK_INCLUDE_SPELLING = True

AWS_STORAGE_BUCKET_NAME = 'oa-public-downloads'
AWS_BUCKET_NAME = AWS_STORAGE_BUCKET_NAME

#change this to the file storage you prefer http://django-storages.readthedocs.org/en/latest/
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto.S3BotoStorage'

#gather our secret and confidential keys from either the dotcloud environment or the local computer
try:
    ###IF DEPLOYING ON DOTCLOUD THIS WILL SUCCEED
    env = json.load(open(os.path.expanduser('~/environment.json')))

except:
    ###localhost, check the home directory
    env = json.load(open(os.path.expanduser('~/local_environment.json')))


#RECAPTCHA
try:
    #recaptcha services, if you have specified your own key
    RECAPTCHA_PUBLIC_KEY = env['RECAPTCHA_PUBLIC_KEY']
    RECAPTCHA_PRIVATE_KEY = env['RECAPTCHA_PRIVATE_KEY']
except:
    #recaptcha not configured correctly, here's some insecure keys
    RECAPTCHA_PUBLIC_KEY = '6LehG9oSAAAAAD256YWh5x_STpHRlEIxd3TKR3is'
    RECAPTCHA_PRIVATE_KEY = '6LehG9oSAAAAAKU-4rViXJrsGBgj7gImL0MMu3ae'

### Specify your email in the environmental variables for dotcloud.
##  If you hack the throwaway account I will be a sad panda, and waste 30 seconds creating another.
try:
    DEFAULT_FROM_EMAIL = env['EMAIL_HOST_USER']
    EMAIL_USE_TLS = True
    EMAIL_HOST = env['EMAIL_HOST']
    EMAIL_HOST_USER = env['EMAIL_HOST_USER']
    EMAIL_HOST_PASSWORD = env['EMAIL_PASSWORD']
    EMAIL_PORT = 587
except:
    DEFAULT_FROM_EMAIL = 'htusybrmlaosirgtntksurtasrr@gmail.com'
    EMAIL_USE_TLS = True
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_HOST_USER = 'htusybrmlaosirgtntksurtasrr@gmail.com'
    EMAIL_HOST_PASSWORD = 'this is a password'
    EMAIL_PORT = 587



try:
    #DOTCLOUD ASSUMES S3 STORAGE. CANNOT USE HASHSTORAGE DUE TO DOTCLOUD SCALING.
    #please either specify your own S3 or use a different backend
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto.S3BotoStorage'
    AWS_ACCESS_KEY_ID = env['S3FS_ACCESSKEY']
    AWS_SECRET_ACCESS_KEY = env['S3FS_SECRETKEY']

    HAYSTACK_SOLR_URL = env['DOTCLOUD_SEARCH_HTTP_URL']

    #check the dotcloud environment variables for your DOTCLOUD_WWW_HTTP_URL
    if env['DOTCLOUD_WWW_HTTP_URL'] == "http://openassembly1-fragro.dotcloud.com/":
        DOMAIN_NAME = 'http://www.openassembly.org/'
        DOMAIN = 'http://www.openassembly.org'
    else:
        DOMAIN_NAME = env['DOTCLOUD_WWW_HTTP_URL']
        DOMAIN = env['DOTCLOUD_WWW_HTTP_URL'][:-1]

    DEBUG = True
    TEMPLATE_DEBUG = False

    DATABASES = {
        'default': {
            'ENGINE': 'django_mongodb_engine',
            'NAME': 'admin',
            'HOST': env['DOTCLOUD_DB_MONGODB_URL'],
            'SUPPORTS_TRANSACTIONS': False,
        }
    }

    # Additional locations of static files
    STATICFILES_DIRS = (
        os.path.join(PROJECT_ROOT, 'openassembly/static/'),
    )

    MEDIA_ROOT = '/home/dotcloud/store/media/'
    STATIC_ROOT = '/home/dotcloud/current/data/static/'
    MEDIA_URL = '/media/'

    GEOIP_PATH = STATIC_ROOT + 'GeoLiteCity.dat'

    # Configure Celery using the RabbitMQ credentials found in the DotCloud
    # environment.
    djcelery.setup_loader()

    BROKER_BACKEND = "redis"
    #BROKER_URL = 'redis://' + env['DOTCLOUD_CACHE_REDIS_PASSWORD'] + '@' + env['DOTCLOUD_CACHE_REDIS_HOST'] + ':' + env['DOTCLOUD_CACHE_REDIS_PORT'] + '/0'

    BROKER_HOST = env['DOTCLOUD_CACHE_REDIS_HOST']
    BROKER_PORT = int(env['DOTCLOUD_CACHE_REDIS_PORT'])
    BROKER_USER = env['DOTCLOUD_CACHE_REDIS_LOGIN']
    BROKER_PASSWORD = env['DOTCLOUD_CACHE_REDIS_PASSWORD']
    BROKER_VHOST = 0
    BROKER_DB = 0

    CELERY_RESULT_BACKEND = 'redis'
    REDIS_CONNECT_RETRY = True

    try:
        ETHERPAD_API = env['ETHERPAD_API']
    except:
        #maybe etherpad api is not setup yet
        ETHERPAD_API = None

    #SWITCHED TO REDIS
    CACHES = {
        'default': {
            'BACKEND': 'redis_cache.cache.RedisCache',
            'LOCATION': env['DOTCLOUD_CACHE_REDIS_HOST'] + ':' + env['DOTCLOUD_CACHE_REDIS_PORT'],
            'OPTIONS': {
                'DB': 1,
                'PASSWORD': env['DOTCLOUD_CACHE_REDIS_PASSWORD'],
                'PARSER_CLASS': 'redis.connection.HiredisParser'
            },
        },
    }

    #New NODEJS integration
    NODEJS_HOST = env['DOTCLOUD_NODEJS_WWW_HOST']
    NODEJS_PORT = int(env['DOTCLOUD_NODEJS_WWW_PORT'])


except:
    # make sure that you have the local_environment.json file in your home folder here.
    # this setup assumes that you have left the ports of the various services as the default.
    try:
        #FOR S3 UPLOADS
        AWS_ACCESS_KEY_ID = env['S3FS_ACCESSKEY']
        AWS_SECRET_ACCESS_KEY = env['S3FS_SECRETKEY']

    except:
        DEFAULT_FILE_STORAGE = 'storages.backends.hashpath.HashPathStorage'

    HAYSTACK_SOLR_URL = 'http://127.0.0.1:8983/solr'

    DOMAIN_NAME = 'http://localhost:8000/'
    DOMAIN = 'http://localhost:8000'

    DEBUG = True
    TEMPLATE_DEBUG = True

    DATABASES = {
        'default': {
            'ENGINE': 'django_mongodb_engine',
            'NAME': 'admin'
        }
    }
    STATICFILES_DIRS = (
        "static/",
    )
    STATIC_ROOT = 'static_dev_serve/static/'
    MEDIA_ROOT = 'static_dev_serve/media/'
    MEDIA_URL = '/media/'

    GEOIP_PATH = PROJECT_ROOT + '/openassembly/static/GeoLiteCity.dat'

    BROKER_HOST = 'localhost'
    BROKER_PORT = 6379
    BROKER_URL = 'redis://localhost:6379/0'
    BROKER_DB = 0
    BROKER_PASSWORD = ''

    CELERY_RESULT_BACKEND = BROKER_URL
    REDIS_CONNECT_RETRY = True

    DEFAULT_FROM_EMAIL = 'htusybrmlaosirgtntksurtasrr@gmail.com'
    EMAIL_USE_TLS = True
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_HOST_USER = 'htusybrmlaosirgtntksurtasrr@gmail.com'
    EMAIL_HOST_PASSWORD = 'this is a password'
    EMAIL_PORT = 587

    ETHERPAD_API = None

    CACHES = {
        'default': {
            'BACKEND': 'redis_cache.cache.RedisCache',
            'LOCATION': 'localhost:6379',
            'OPTIONS': {
                'DB': 1,
            },
        },
    }

    NODEJS_HOST = 'localhost'
    NODEJS_PORT = 8080

#SETUP RECAPTCHA KEYS

ADMINS = (('Open Assembly', 'openassemblycongresscritter@gmail.com'),)
MANAGERS = ADMINS

AUTOLOAD_SITECONF = 'indexes'

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'django.contrib.markup',
    'haystack',
    'customtags',
    'tagging',
    'filetransfers',
    'pirate_core',
    'pirate_deliberation',
    'pirate_permissions',
    'pirate_ranking',
    'pirate_consensus',
    'pirate_reputation',
    'pirate_messages',
    'pirate_login',
    'pirate_profile',
    'pirate_sources',
    'pirate_comments',
    'pirate_badges',
    'pirate_flags',
    'pirate_social',
    'pirate_forum',
    'pirate_actions',
    'pirate_topics',
    'markitup',
    'oa_verification',
    'oa_filmgenome',
    'notification',
    'search',
    'oa_suggest',
    'tracking',
    'djcelery',
    'oa_dashboard',
    'sorl.thumbnail',
    'oa_cache',
    'django_mongodb_engine',
    'oa_location',
    'pygeoip',
    'dbindexer',
    'autoload',
    'djangotoolbox',
    'oa_search', #openassemblys implementation of django-haystack
    'storages',
    'ajaxuploader',
    'captcha',
]


STATIC_URL = STATIC_ROOT

ADMIN_MEDIA_PREFIX = '/static/admin/'

MARKITUP_MEDIA_URL = '/static/'

MARKITUP_FILTER = ('markdown.markdown', {'safe_mode': True, 'previewParserPath': '/markitup/preview/'})
MARKITUP_SET = 'markitup/sets/markdown'
MARKITUP_SKIN = 'simple'

JQUERY_URL = '/static/js/jquery-1.7.1.min.js'

EMAIL_USE_TLS = True
EMAIL_HOST = ''
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_PORT = 587

TEST_RUNNER = 'djangotoolbox.test.CapturingTestSuiteRunner'

ROOT_URLCONF = 'urls'

TEMPLATE_DIRS = (os.path.join(os.path.dirname(__file__), 'oa_template2'),)

FAIL_SILENTLY = True

AUTHENTICATION_BACKENDS = ('openassembly.pirate_login.backends.CaseInsensitiveModelBackend',)


DJANGO_BUILTIN_TAGS = (
    'native_tags.templatetags.native',
    'django.contrib.markup.templatetags.markup',
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'autoload.middleware.AutoloadMiddleware',
    'tracking.middleware.BannedIPMiddleware',
    'pirate_core.middleware.UrlMiddleware',
    'customtags.middleware.AddToBuiltinsMiddleware',
    'johnny.middleware.LocalStoreClearMiddleware',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "django.contrib.messages.context_processors.messages",
    "django.core.context_processors.request",
)

SEARCH_BACKEND = 'search.backends.immediate_update'
PISTON_DISPLAY_ERRORS = True

OPENASSEMBLY_AGENT = 'http://localhost:8888/jsonrpc'
OPENASSEMBLY_KEY = "frank"


# we also are going to use redis for our session cache as well.
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'

JOHNNY_MIDDLEWARE_KEY_PREFIX = 'jc_openassembly'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        },
    },
    'handlers': {
        'null': {
            'level': 'DEBUG',
            'class': 'django.utils.log.NullHandler',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
        }
    },
    'loggers': {
        'django': {
            'handlers': ['null'],
            'propagate': True,
            'level': 'INFO',
        },
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'tracking.models': {
            'handlers': ['console', 'mail_admins'],
            'level': 'DEBUG',
        }
    }
}

########CELERY

CELERY_DEFAULT_QUEUE = 'default'
CELERY_QUEUES = {
    'default': {
        'exchange': 'default',
        'exchange_type': 'topic',
        'binding_key': 'tasks.#'
    }
}

ABSOLUTE_URL_OVERRIDES = {
    'auth.user': lambda o: "/p/user/k-%s" % o.username,
}
