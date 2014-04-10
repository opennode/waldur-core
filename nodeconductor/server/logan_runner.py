from logan.runner import run_app

CONFIG_TEMPLATE = """
# Django settings for nodeconductor project.
from nodeconductor.server.base_settings import *

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = %(secret_key)r

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

TEMPLATE_DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1']

# Application definition

# Database
# https://docs.djangoproject.com/en/1.6/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}
"""


def generate_settings():
    """
    This command is run when ``default_path`` doesn't exist, or ``init`` is
    run and returns a string representing the default data to put into their
    settings file.
    """
    import os
    import base64

    return CONFIG_TEMPLATE % {
        'secret_key': base64.b64encode(os.urandom(32)),
    }


def main():
    run_app(
        project='nodeconductor',
        default_config_path='~/.nodeconductor/nodeconductor.conf.py',
        default_settings='nodeconductor.server.base_settings',
        settings_initializer=generate_settings,
        settings_envvar='NODECONDUCTOR_CONF',
    )

if __name__ == '__main__':
    main()
