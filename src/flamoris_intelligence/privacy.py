"""Redact HTTP diagnostics only while this task is handling private provider I/O."""

import logging
from contextlib import contextmanager
from contextvars import ContextVar

_private = ContextVar("intelligence_provider_io", default=False)


class _PrivateLog(logging.Filter):
    def filter(self, record):
        if _private.get():
            record.msg = "Intelligence transport event"
            record.args = ()
            record.exc_info = record.exc_text = record.stack_info = None
        return True


for name in (
    "httpx",
    "httpcore",
    "httpcore.connection",
    "httpcore.http11",
    "httpcore.http2",
    "httpcore.proxy",
    "httpcore.socks",
):
    logging.getLogger(name).addFilter(_PrivateLog())


@contextmanager
def private_transport():
    token = _private.set(True)
    try:
        yield
    finally:
        _private.reset(token)
