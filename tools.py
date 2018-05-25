import asyncio
from functools import wraps
from logging import getLogger, Handler
from tenacity import TryAgain
import view

logger = getLogger(__name__)


class APIError(Exception):
    def __init__(self, status, reason):
        super().__init__(status, reason)


def async_tryexcept(func):
    @wraps(func)
    async def wrapped(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except APIError as exc:
            if exc.args[0] == 500:
                logger.exception("%s, see logs for details.", str(exc))
                raise
            logger.error("%d: %s", *exc.args)
        except Exception as exc:
            logger.exception("%s, see logs for details.", str(exc))
            raise
    return wrapped

def tryexcept(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            logger.exception("%s, see logs for details.", str(exc))
            raise
    return wrapped



class UrwidHandler(Handler):
    def emit(self, record):
        msg = self.format(record)
        try:
            view.footer.set_text(msg[:msg.index("\n")])
        except ValueError:
            view.footer.set_text(msg)

def find(key, iterable):
    for item in iterable:
        if key(item):
            return item
    return None
