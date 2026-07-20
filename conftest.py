import os


def pytest_configure(config):
    # Set DJANGO_ENV before Django is configured so settings/__init__.py
    # loads environments/test.py (FakeWebpackLoader, DEBUG=False, etc.)
    os.environ.setdefault("DJANGO_ENV", "test")
