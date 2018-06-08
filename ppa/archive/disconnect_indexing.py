'''pytest plugin to disconnect index signal handlers at the beginning
of the testing session'''


def pytest_sessionstart(session):
    from ppa.archive.signals import IndexableSignalHandler
    IndexableSignalHandler.disconnect()
