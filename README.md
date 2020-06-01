# banlimit
 Django based rate-limiting library- allowing to ban users for custom time after ratelimit violation.
This class based decorator provides improvement over the existing django-ratelimit library- allowing the banning
    of users for custom time. (Ratelimit ref: https://django-ratelimit.readthedocs.io/en/stable/usage.html)
    
## Configuration
You need to define following in your django-settings file. 
`RATELIMIT_USE_CACHE` - If not defined, `default` cache is used.
`RATELIMIT_ENABLE` - To enable/disable ratelimit.


##Usage:
Usage is pretty similar to django-ratelimit library. 
````python
@banlimit('ip', '1/m', '2m', block=True)
def func():
    pass
````

 Recommended Usage:
   
```python
@banlimit(key='ip', rate='1/m', ban='2m', block=True)
def func():
    pass
```

* `group` – A group of rate limits to count together. \
* `key` –  'ip', 'user', 'user_or_ipp', What key to use. Key can also be a callable function. You would want to use 
callable function if you are using a load balancer/proxy to route requests. In such cases you should provide a function that extracts
the real ip and returns it back. \
* `rate` – ‘1/m’ The number of requests per unit time allowed. Valid units are: \
            s - seconds \
            m - minutes\
            h - hours\
            d - days\
Also accepts callables. See Rates.

* `method` – 'ALL', 'UNSAFE' (which includes POST, PUT, DELETE and PATCH).
            Which HTTP method(s) to rate-limit. May be a string, a list/tuple of strings, or the special values for

* `block` – 'False', 'True'
            Whether to block the request instead of annotating.
            
