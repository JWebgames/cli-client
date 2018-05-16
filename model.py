import aiohttp
import asyncio
import atexit
import json
from collections import defaultdict
from logging import getLogger, WARNING
from operator import itemgetter, iand
from urllib.parse import urljoin
from contextlib import suppress

import tenacity

import controller
from config import APIURL
from tools import async_tryexcept
import view

logger = getLogger(__name__)
http = aiohttp.ClientSession(loop=controller.loop)

token = None
userid = None
groupid = None
partyid = None

group = []

def retry(func):
    return tenacity.retry(
        wait=tenacity.wait_random_exponential(multiplier=.5, max=60),
        stop=tenacity.stop_after_attempt(10),
        reraise=True)(func)

def req(method, url, headers=None, *args, **kwargs):
    if headers is None:
        headers = {}
    if token is not None:
        headers["Authorization"] = "Bearer: %s" % token
    return http.request(method, urljoin(APIURL, url), headers=headers, *args, **kwargs)

async def handle_error(res):
    if res.content_type == "application/json":
        error = (await res.json())["error"]
        logger.error(
            "Error for url %s, status: %d, error: %s",
            res.url, res.status, error)
        raise APIError(res.status, error)
    else:
        logger.error(
            "Error for url %s, status: %d, body:\n%s",
            res.url, res.status, await res.text())
        raise APIError(res.status, res.reason)

class APIError(Exception):
    def __init__(self, status, reason):
        super().__init__(status, reason)


event_handlers = {
    "user": defaultdict(dict),
    "group": defaultdict(dict),
    "party": defaultdict(dict),
    "server": defaultdict(dict)}
def event_handler(scope, categ, command):
    def register(func):
        event_handlers[scope][categ][command] = func
        return func
    return register

async def payload_getter(res):
    buffer = b""
    while True:
        chunk = await res.content.read(64)
        if not chunk:
            break
        buffer += chunk
        raw_messages = buffer.split(bytes([30]))
        if len(raw_messages) == 1:
            continue

        buffer = raw_messages[-1]
        for raw_message in raw_messages[:-1]:
            yield json.loads(raw_message)


@async_tryexcept
@retry
async def msgqueue(scope):
    with suppress(asyncio.CancelledError):
        async with req("get", "v1/msgqueues/%s" % scope) as res:
            logger.info("Getting messages from scope %s", scope)
            async for message in payload_getter(res):
                categ, cmd = message["type"].split(":")

                callback = event_handlers[scope].get(categ, {}).get(cmd)
                if callback is None:
                    logger.warning(
                        "Cannot handle event type %s", message["type"])
                view.footer.set_text("Event %s recieved !" % message["type"])
                del message["type"]

                if asyncio.iscoroutinefunction(callback):
                    asyncio.ensure_future(callback(**message))
                else:
                    callback(**message)
            logger.info("End of stream for scope %s", scope)

@retry
async def register(username, email, password):
    payload = {"username": username, "email": email, "password": password}
    async with req("post", "v1/auth/register", json=payload) as res:
        if res.status != 200:
            await handle_error(res)
        
        json_body = await res.json()
        return json_body["userid"]

@retry
async def connect(login, password):
    logger.debug("in connect")
    await asyncio.sleep(5)
    payload = {"login": login, "password": password}
    async with req("post", "v1/auth", json=payload) as res:
        if res.status != 200:
            await handle_error(res)

        json_body = await res.json()
        return json_body["token"]

@retry
async def disconnect():
    async with req("delete", "v1/auth") as res:
        if res.status != 204:
            await handle_error(res)

games = None
@retry
async def get_game_list():
    global games
    if games is None:
        async with req("get", "/v1/games") as res:
            if res.status != 200:
                await handle_error(res)        
            games = await res.json()
    return games

@retry
async def create_group(gameid):
    async with req("post", "/create/%d" % gameid) as res:
        if res.status != 200:
            await handle_error(res)
        json_body = await res.json()
        return json_body["groupid"]