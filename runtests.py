import os
import sys

import django
from django.conf import settings
from django.test.runner import DiscoverRunner


if __name__ == "__main__":

    os.environ['DJANGO_SETTINGS_MODULE'] = 'tests.django_settings'
    django.setup()
    runner = DiscoverRunner()
    failures = runner.run_tests(["tests"])
    sys.exit(bool(failures))