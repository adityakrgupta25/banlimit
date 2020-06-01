# coding=utf-8
from __future__ import absolute_import

import hashlib
import re
from functools import wraps
from importlib import import_module

from django.conf import settings
from django.core.cache import caches
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from ratelimit.exceptions import Ratelimited
from ratelimit.utils import (
    _ACCESSOR_KEYS,
    _PERIODS,
    _SIMPLE_KEYS,
    _split_rate,
    is_ratelimited,
)

from . import ALL


__all__ = ['banlimit']


# def get_ip(group=None, request=None):
#     # Proxy function that follows the definition required by django-ratelimit.
#     # ref: https://django-ratelimit.readthedocs.io/en/stable/keys.
#     return utils_get_ip(request)


class banlimit:
    """
    This class based decorator provides improvement over the existing django-ratelimit library- allowing the banning
    of users for custom time.
    (Ratelimit ref: https://django-ratelimit.readthedocs.io/en/stable/usage.html)

    Usage:
    @banlimit('ip', '1/m', '2m', block=True)
    def func():
        pass

    Recommended Usage:
    @banlimit(key='ip', rate='1/m', ban='2m', block=True)
    def func():
        pass


    group – A group of rate limits to count together.
    key –  'ip', 'user', 'user_or_ipp', What key to use.
    rate – ‘1/m’ The number of requests per unit time allowed. Valid units are:

    s - seconds
    m - minutes
    h - hours
    d - days
    Also accepts callables. See Rates.

    method –ALL, UNSAFE (which includes POST, PUT, DELETE and PATCH).
            Which HTTP method(s) to rate-limit. May be a string, a list/tuple of strings, or the special values for

    block – False, True
            Whether to block the request instead of annotating.
    """

    EXPIRATION_FUDGE = 5  # Extend the ban_cache_key expiration time by a few seconds to avoid misses.
    ban_re = re.compile('(\d*)([a-z])')
    cache_name = getattr(settings, 'RATELIMIT_USE_CACHE', 'default')
    cache = caches[cache_name]


    def __init__(self, key, rate, ban, group=None, method=ALL, block=True):
        self.group = group
        self.key = key
        self.rate = rate
        self.method = method
        self.block = block
        self.ban = ban

    def get_key_value(self, group=None, request=None):
        """
        Returns request making entity's unique identification corresponding to the 'key' provided in configuration.
        This has been taken from ratelimt.utils.get_usage_count().
        """
        if not self.key:
            raise ImproperlyConfigured('Ratelimit key must be specified')
        if callable(self.key):
            value = self.key(group, request)
        elif self.key in _SIMPLE_KEYS:
            value = _SIMPLE_KEYS[self.key](request)
        elif ':' in self.key:
            accessor, k = self.key.split(':', 1)
            if accessor not in _ACCESSOR_KEYS:
                raise ImproperlyConfigured('Unknown ratelimit key: %s' % self.key)
            value = _ACCESSOR_KEYS[accessor](request, k)
        elif '.' in self.key:
            mod, attr = self.key.rsplit('.', 1)
            keyfn = getattr(import_module(mod), attr)
            value = keyfn(group, request)
        else:
            raise ImproperlyConfigured('Could not understand ratelimit key: %s' % self.key)
        return value

    def _extract_ban_duration(self, ban, request=None):
        """Returns ban time in seconds."""
        if callable(ban):
            ban = ban(self.group, request)
        vals = banlimit.ban_re.match(ban).groups()
        period = vals[1]
        if period not in _PERIODS:
            raise ImproperlyConfigured
        return int(vals[0]) * _PERIODS[period]

    def get_group(self, fn):
        group_local = self.group
        if group_local is None:
            if hasattr(fn, '__self__'):
                parts = fn.__module__, fn.__self__.__class__.__name__, fn.__name__
            else:
                parts = (fn.__module__, fn.__name__)
            group_local = '.'.join(parts)
        return group_local

    def is_banned(self, ban_cache_key):
        if self.cache.get(ban_cache_key):
            return True

        return False

    @staticmethod
    def _make_ban_cache_key(group, rate, key_value, methods, ban):
        """
        Wrt. to the  django-ratelimit library function, this implementation does not make use of Time-Window.
        :param group:
        :param rate: Rate in format '1/m'
        :param key_value: Contains the value (username or ip) corresponding to the key of the request making entity
        :param methods:
        :param ban: Ban-time period in seconds.
        """
        count, period = _split_rate(rate)
        safe_rate = '%d/%ds' % (count, period)
        parts = [group + safe_rate, key_value, str(ban)]
        if methods is not None:
            if methods == ALL:
                methods = ''
            elif isinstance(methods, (list, tuple)):
                methods = ''.join(sorted([m.upper() for m in methods]))
            parts.append(methods)
        return "BAN_KEY" + hashlib.md5(u''.join(parts).encode('utf-8')).hexdigest()

    def __call__(self, fn):
        @wraps(fn)
        def _wrapped(*args, **kwargs):
            request = args[0] if isinstance(args[0], HttpRequest) else args[1]
            request.limited = getattr(request, 'limited', False)

            if not getattr(settings, 'RATELIMIT_ENABLE', True):
                request.limited = False
                return fn(*args, **kwargs)

            rate_local = self.rate
            if callable(rate_local):
                rate_local = rate_local(self.group, request)

            if rate_local is None:
                """
                This has been taken from the original ratelimit function.
                Ideally it should raise ImproperlyConfigured.
                """
                return fn(*args, **kwargs)

            ban_duration = self._extract_ban_duration(self.ban, request)
            group_local = self.get_group(fn)
            key_value = self.get_key_value(group=group_local, request=request)
            ban_cache_key = self._make_ban_cache_key(group_local, rate_local, key_value, self.method, ban_duration)

            banned = self.is_banned(ban_cache_key)
            if banned and self.block:
                raise Ratelimited

            # Checks if the user is ratelimited.
            ratelimited = is_ratelimited(request=request, group=self.group, fn=fn,
                                         key=self.key, rate=self.rate, method=self.method,
                                         increment=True)

            if ratelimited:
                self.cache.add(ban_cache_key, ban_duration, ban_duration + self.EXPIRATION_FUDGE)
                if self.block:
                    exception = Ratelimited()
                    exception.banlimit_data = {
                        "key": self.key,
                        "key_value": key_value,
                        "ban_duration": ban_duration
                    }
                    # Raise Ratelimited exception with details about banned entity.
                    raise exception
            response = fn(*args, **kwargs)
            return response

        return _wrapped
