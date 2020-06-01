import time

from django.core.cache import (
    InvalidCacheBackendError,
    cache,
)
from django.test import RequestFactory, TestCase
from django.test.utils import override_settings
from django.views.generic import View
from ratelimit.exceptions import Ratelimited
from . import UNSAFE

from banlimit import banlimit

rf = RequestFactory()


class MockUser(object):
    def __init__(self, authenticated=False):
        self.pk = 1
        self.is_authenticated = authenticated


def mykey(group, request):
    return request.META['REMOTE_ADDR'][::-1]


class BanlimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_ip(self):
        @banlimit(key='ip', rate='1/m', ban='60s', block=True)
        def view(request):
            return True

        req = rf.get('/')
        assert view(req), 'First request works.'
        with self.assertRaises(Ratelimited):
            view(req)

    def test_block(self):
        @banlimit(key='ip', rate='1/m', ban='60s', block=True)
        def blocked(request):
            return request.limited

        @banlimit(key='ip', rate='1/m', ban='60s', block=False)
        def unblocked(request):
            return request.limited

        req = rf.get('/')

        assert not blocked(req), 'First request works.'
        with self.assertRaises(Ratelimited):
            blocked(req)

        assert unblocked(req), 'Request is limited but not blocked.'

    def test_method(self):
        post = rf.post('/')
        get = rf.get('/')

        @banlimit(key='ip', ban='60s', rate='1/m', method='POST', group='a', block=False)
        def limit_post(request):
            return request.limited

        @banlimit(key='ip', ban='60s', method=['POST', 'GET'], rate='1/m', group='a', block=False)
        def limit_get(request):
            return request.limited

        assert not limit_post(post), 'Do not limit first POST.'
        assert limit_post(post), 'Limit second POST.'
        assert not limit_post(get), 'Do not limit GET.'

        assert limit_get(post), 'Limit first POST.'
        assert limit_get(get), 'Limit first GET.'

    def test_unsafe_methods(self):
        @banlimit(key='ip', ban='60s', method=UNSAFE, rate='0/m', block=False)
        def limit_unsafe(request):
            return request.limited

        get = rf.get('/')
        head = rf.head('/')
        options = rf.options('/')

        delete = rf.delete('/')
        post = rf.post('/')
        put = rf.put('/')

        assert not limit_unsafe(get)
        assert not limit_unsafe(head)
        assert not limit_unsafe(options)
        assert limit_unsafe(delete)
        assert limit_unsafe(post)
        assert limit_unsafe(put)

        if hasattr(rf, 'patch'):
            patch = rf.patch('/')
            assert limit_unsafe(patch)

    def test_key_get(self):
        req_a = rf.get('/', {'foo': 'a'})
        req_b = rf.get('/', {'foo': 'b'})

        @banlimit(key='get:foo', ban='60s', rate='1/m', method='GET', block=False)
        def view(request):
            return request.limited

        assert not view(req_a)
        assert view(req_a)
        assert not view(req_b)
        assert view(req_b)

    def test_key_post(self):
        req_a = rf.post('/', {'foo': 'a'})
        req_b = rf.post('/', {'foo': 'b'})

        @banlimit(key='post:foo', ban='60s', rate='1/m', block=False)
        def view(request):
            return request.limited

        assert not view(req_a)
        assert view(req_a)
        assert not view(req_b)
        assert view(req_b)

    def test_key_header(self):
        req = rf.post('/')
        req.META['HTTP_X_REAL_IP'] = '1.2.3.4'

        @banlimit(key='header:x-real-ip', ban='60s', rate='1/m', block=False)
        @banlimit(key='header:x-missing-header', ban='60s', rate='1/m', block=False)
        def view(request):
            return request.limited

        assert not view(req)
        assert view(req)

    def test_rate(self):
        req = rf.post('/')

        @banlimit(key='ip', ban='60s', rate='2/m', block=False)
        def twice(request):
            return request.limited

        assert not twice(req), 'First request is not limited.'
        del req.limited
        assert not twice(req), 'Second request is not limited.'
        del req.limited
        assert twice(req), 'Third request is limited.'

    def test_zero_rate(self):
        req = rf.post('/')

        @banlimit(key='ip', ban='60s', rate='0/m', block=False)
        def never(request):
            return request.limited

        assert never(req)

    def test_none_rate(self):
        req = rf.post('/')

        @banlimit(key='ip', ban='60s', rate=None, block=False)
        def always(request):
            return request.limited

        assert not always(req)
        del req.limited
        assert not always(req)
        del req.limited
        assert not always(req)
        del req.limited
        assert not always(req)
        del req.limited
        assert not always(req)
        del req.limited
        assert not always(req)

    def test_callable_rate(self):
        auth = rf.post('/')
        unauth = rf.post('/')
        auth.user = MockUser(authenticated=True)
        unauth.user = MockUser(authenticated=False)

        def get_rate(group, request):
            if request.user.is_authenticated:
                return (2, 60)
            return (1, 60)

        @banlimit(key='user_or_ip', ban='60s', rate=get_rate, block=False)
        def view(request):
            return request.limited

        assert not view(unauth)
        assert view(unauth)
        assert not view(auth)
        assert not view(auth)
        assert view(auth)

    def test_callable_rate_none(self):
        req = rf.post('/')
        req.never_limit = False

        def get_rate(g, r):
            if r.never_limit:
                return None
            else:
                return '1/m'

        @banlimit(key='ip', ban='60s', rate=get_rate, block=False)
        def view(request):
            return request.limited

        assert not view(req)
        del req.limited
        assert view(req)
        req.never_limit = True
        del req.limited
        assert not view(req)
        del req.limited
        assert not view(req)

    def test_callable_rate_zero(self):
        auth = rf.post('/')
        unauth = rf.post('/')
        auth.user = MockUser(authenticated=True)
        unauth.user = MockUser(authenticated=False)

        def get_rate(group, request):
            if request.user.is_authenticated:
                return '1/m'
            return '0/m'

        @banlimit(key='ip', rate=get_rate, ban='60s', block=False)
        def view(request):
            return request.limited

        assert view(unauth)
        del unauth.limited
        assert not view(auth)
        del auth.limited
        assert view(auth)
        assert view(unauth)

    @override_settings(RATELIMIT_USE_CACHE='fake-cache')
    def test_bad_cache(self):
        """The RATELIMIT_USE_CACHE setting works if the cache exists."""

        @banlimit(key='ip', ban='60s', rate='1/m', block=False)
        def view(request):
            return request

        req = rf.post('/')

        with self.assertRaises(InvalidCacheBackendError):
            view(req)

    def test_user_or_ip(self):
        """Allow custom functions to set cache keys."""

        @banlimit(key='user_or_ip', rate='1/m', ban='60s', block=False)
        def view(request):
            return request.limited

        unauth = rf.post('/')
        unauth.user = MockUser(authenticated=False)

        assert not view(unauth), 'First unauthenticated request is allowed.'
        assert view(unauth), 'Second unauthenticated request is limited.'

        auth = rf.post('/')
        auth.user = MockUser(authenticated=True)

        assert not view(auth), 'First authenticated request is allowed.'
        assert view(auth), 'Second authenticated is limited.'

    def test_key_path(self):
        @banlimit(key='ratelimit.tests.mykey', rate='1/m', ban='60s', block=False)
        def view(request):
            return request.limited

        req = rf.post('/')
        assert not view(req)
        assert view(req)

    def test_callable_key(self):
        @banlimit(key=mykey, ban='60s', rate='1/m', block=False)
        def view(request):
            return request.limited

        req = rf.post('/')
        assert not view(req)
        assert view(req)

    def test_stacked_decorator(self):
        """Allow @banlimit to be stacked."""

        # Put the shorter one first and make sure the second one doesn't
        # reset request.limited back to False.
        @banlimit(rate='1/m', ban='60s', key=lambda x, y: 'min', block=False)
        @banlimit(rate='10/d', ban='60s', key=lambda x, y: 'day', block=False)
        def view(request):
            return request.limited

        req = rf.post('/')
        assert not view(req), 'First unauthenticated request is allowed.'
        assert view(req), 'Second unauthenticated request is limited.'

    def test_stacked_methods(self):
        """Different methods should result in different counts."""

        @banlimit(rate='1/m', ban='60s', key='ip', method='GET', block=False)
        @banlimit(rate='1/m', ban='60s', key='ip', method='POST', block=False)
        def view(request):
            return request.limited

        get = rf.get('/')
        post = rf.post('/')

        assert not view(get)
        assert not view(post)
        assert view(get)
        assert view(post)

    def test_sorted_methods(self):
        """Order of the methods shouldn't matter."""

        @banlimit(rate='1/m', key='ip', ban='60s', method=['GET', 'POST'], group='a', block=False)
        def get_post(request):
            return request.limited

        @banlimit(rate='1/m', key='ip', ban='60s', method=['POST', 'GET'], group='a', block=False)
        def post_get(request):
            return request.limited

        req = rf.get('/')
        assert not get_post(req)
        assert post_get(req)

    def test_cache_timeout(self):
        @banlimit(key='ip', rate='1/m', ban='60s', block=True)
        def view(request):
            return True

        req = rf.get('/')
        assert view(req), 'First request works.'
        with self.assertRaises(Ratelimited):
            view(req)

    def test_ban_time(self):
        @banlimit(key='ip', rate='2/1s', block=True, ban='2s')
        def view(request):
            return True

        req = rf.get('/')

        assert view(req)
        assert view(req)

        with self.assertRaises(Ratelimited):
            view(req)

        time.sleep(1)
        with self.assertRaises(Ratelimited):
            view(req)

        time.sleep(10)
        assert view(req)

    def test_method_decorator(self):
        class TestView(View):
            @banlimit(key='ip', rate='1/m', ban='60s', block=False)
            def post(self, request):
                return request.limited

        view = TestView.as_view()
        req = rf.post('/')
        assert not view(req)
        assert view(req)
