"""
WSGI config for django_filechest project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_filechest.settings")

application = get_wsgi_application()

# from django.core.handlers.wsgi import WSGIHandler
#
# class FileChestWSGIHandler(WSGIHandler):
#    def __call__(self, environ, start_response):
#        ret = super().__call__(environ, start_response)
#        print(
#            environ["REQUEST_METHOD"],
#            environ["SCRIPT_NAME"],
#            environ["PATH_INFO"],
#            environ["QUERY_STRING"],
#            getattr(ret, "status_code", None),
#        )
#        return ret
#
# application = FileChestWSGIHandler()
