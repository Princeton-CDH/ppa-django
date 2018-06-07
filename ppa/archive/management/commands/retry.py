'''
This decorator modifies a function to re-run until it does not throw given
`Exception`(s) using an exponential backoff strategy: the first failure will cause
it to wait for `delay` seconds, with each successive attempt multipying the
failure delay by `backoff`.

After `tries` attempts have been exhausted, the function will return the final
result instead of attempting to execute again.

The Exception(s) to handle can be passed as a single argument or tuple, e.g.
```
@retry((errors.HttpError, socket.error), tries=10)
def some_network_func():
    ...
```
'''

import time


class Retry(object):
    '''
    Retries a function or method until it does not return given Exception(s).
    Delay between retries increases exponentially in the form `delay`^`backoff`.
    The function will "give up" after `tries` executions and return.
    '''

    def __init__(self, exceptions, tries=4, delay=3, backoff=2):
        self.exceptions = exceptions
        self.tries = tries
        self.delay = delay
        self.backoff = backoff

    def __call__(self, function):
        def retry_function(*args, **kwargs):
            '''Decorated function that will retry itself.'''
            tries, delay = self.tries, self.delay
            while tries > 1:
                try:
                    return function(*args, **kwargs)
                except self.exceptions as err:
                    msg = "%s, Retrying in %d seconds..." % (err, delay)
                    try:
                        # instance method of Command with access to terminal
                        function.__self__.stdout.write(msg)
                    except AttributeError:
                        # fallback
                        print(msg)
                    time.sleep(delay)
                    tries -= 1
                    delay *= self.backoff
            return function(*args, **kwargs)
        return retry_function
