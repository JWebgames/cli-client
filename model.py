import aiohttp
import asyncio
import json
from logging import getLogger
from urllib.parse import urljoin
from operator import itemgetter
from collections import defaultdict

from controller import loop
from config import APIURL

logger = getLogger(__name__)
http = aiohttp.ClientSession(loop=loop)
token = None

def req(method, url, headers=None, *args, **kwargs):
    if headers is None:
        headers = {}
    if token is not None:
        headers["Authorization"] = "Bearer: %s" % token
    return http.request(method, urljoin(APIURL, url), headers, *args, **kwargs)

commands = {
    "user": defaultdict({}),
    "group": defaultdict({}),
    "party": defaultdict({})}
def register(scope, categ, command):
    def wrapper(func):
        commands[scope][categ][command] = func
        return func
    return wrapper

async def msgqueue(scope):
    seens = []
    while True:
        async with req("get", "/msgqueues/%s" % score) as res:
            if res.status // 100 != 2:
                logger.error("Error for url %s, status: %d, body: %s",
                             "/msgqueues/%s" % score, res.status, await res.text())
                break
            
            json_body = await res.json()
            for event in sorted(json_body, key=itemgetter("timestamp")):
                if event.msgid in seens:
                    continue
                seens.append(event.msgid)

                message = json.loads(event.message)
                categ, cmd = message["type"].split(":")

                callback = commands[scope].get(categ, {}).get(cmd)
                if callback is None:
                    logger.warning("Cannot handle event type %s", message["type"])
                del message["type"]

                if asyncio.iscoroutinefunction(callback):
                    asyncio.ensure_future(callback(message))
                else:
                    callback(message)

            seens = list(map(itemgetter("msgid"), json_body))
        asyncio.sleep(4)

@register("user", "group", "invitation recieved")
def invited(payload):
    pass

@register("user", "group", "user joined")
def group_user_joined(payload):
    pass

@register("user", "group", "user left")
def group_user_left(payload):
    pass

@register("user", "group", "user is ready")
def group_user_is_ready(payload):
    pass

@register("user", "group", "user is not ready")
def group_user_is_not_ready(payload):
    pass

@register("user", "group", "queue joined")
def group_queue_joined(payload):
    pass
