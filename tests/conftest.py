"""
Pytest configuration for Django tests.

The DJANGO_SETTINGS_MODULE env var is set here so pytest-django picks it up
before any test module is imported.
"""

import django
from django.conf import settings


def pytest_configure(config):
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "saas.settings")
