import stripe
from contextlib import contextmanager


class InstrumentedClient(stripe.http_client.HTTPClient):
    def __init__(self, client):
        self.client = client
        self.calls = []

    def __getattr__(self, name):
        return getattr(self.client, name)

    def request(self, method, url, headers, post_data=None):
        data = [method, url, -1]
        try:
            content, status_code, headers = self.client.request(method, url, headers, post_data)
            data[2] = status_code
        finally:
            self.calls.append(data)
        return content, status_code, headers


@contextmanager
def instrument_client(client=None):
    from stripe import verify_ssl_certs as verify
    from stripe import proxy

    previous_client = client or stripe.default_http_client or \
        stripe.http_client.new_default_http_client(
            verify_ssl_certs=verify, proxy=proxy)

    try:
        instrumented_client = InstrumentedClient(previous_client)
        stripe.default_http_client = instrumented_client
        yield instrumented_client.calls
    finally:
        stripe.default_http_client = previous_client
