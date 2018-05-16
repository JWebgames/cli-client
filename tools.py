from functools import wraps
from logging import getLogger

logger = getLogger(__name__)


def async_tryexcept(func):
    @wraps(func)
    async def wrapped(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except:
            logger.exception("Error in async function")
    return wrapped
