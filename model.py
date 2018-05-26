import aiohttp
import aiohttp.client_exceptions
import asyncio
import atexit
import json
from collections import defaultdict
from logging import getLogger, INFO
from functools import partial
from operator import itemgetter, iand
from urllib.parse import urljoin
from contextlib import suppress

import tenacity

import controller
from config import APIURL
from tools import async_tryexcept, APIError, find
import view

logger = getLogger(__name__)
http = aiohttp.ClientSession(loop=controller.loop)

class Container:
    pass
container = Container()
container.token = None
container.user = Container()
container.group = Container()
container.slot = Container()
container.party = Container()
container.games = None

retry = partial(tenacity.retry,
                retry=tenacity.retry_if_exception_type(aiohttp.client_exceptions.ClientConnectorError),
                wait=tenacity.wait_fixed(3) + tenacity.wait_random_exponential(max=7),
                stop=tenacity.stop_after_attempt(10),
                before=tenacity.before_log(logger, INFO),
                reraise=True)

def req(method, url, headers=None, *args, **kwargs):
    if headers is None:
        headers = {}
    if container.token is not None:
        headers["Authorization"] = "Bearer: %s" % container.token
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

async def reader(res):
    buffer = b""
    while True:
        chunk = await asyncio.wait_for(res.content.readany(), 65)
        if not chunk:
            break
        buffer += chunk
        raw_messages = buffer.split(bytes([30]))
        if len(raw_messages) == 1:
            continue

        buffer = raw_messages[-1]
        for raw_message in raw_messages[:-1]:
            yield json.loads(raw_message)


@retry()
@async_tryexcept
async def msgqueue(scope):
    with suppress(asyncio.CancelledError):
        async with req("get", "v1/msgqueues/%s" % scope, timeout=None) as res:
            logger.info("Getting messages from scope %s", scope)
            async for message in reader(res):
                if message["type"] == "heartbeat":
                    continue

                categ, cmd = message["type"].split(":")

                callback = event_handlers[scope].get(categ, {}).get(cmd)
                if callback is None:
                    logger.warning("Cannot handle event type \"%s\" for queue %s",
                                   message["type"], scope)
                    continue
                logger.debug("Event %s recieved !", message["type"])
                view.footer.set_text("Event %s recieved !" % message["type"])
                del message["type"]

                if asyncio.iscoroutinefunction(callback):
                    asyncio.ensure_future(callback(message))
                else:
                    callback(message)
            logger.info("End of stream for scope %s", scope)
            raise tenacity.TryAgain()

@retry()
async def register(username, email, password):
    payload = {"username": username, "email": email, "password": password}
    async with req("post", "v1/auth/register", json=payload) as res:
        if res.status != 200:
            await handle_error(res)
        
        json_body = await res.json()
        return json_body["userid"]

@retry()
async def connect(login, password):
    payload = {"login": login, "password": password}
    async with req("post", "v1/auth", json=payload) as res:
        if res.status != 200:
            await handle_error(res)

        json_body = await res.json()
        return json_body["token"]

@retry()
async def disconnect():
    async with req("delete", "v1/auth/") as res:
        if res.status != 204:
            await handle_error(res)

@retry()
async def get_game_list():
    if container.games is None:
        async with req("get", "/v1/games") as res:
            if res.status != 200:
                await handle_error(res)        
            container.games = await res.json()
    return container.games

@retry()
async def create_group(gameid):
    async with req("post", "v1/groups/create/%d" % gameid) as res:
        if res.status != 200:
            await handle_error(res)
        json_body = await res.json()
        return json_body["groupid"]

@retry()
async def get_my_group():
    async with req("get", "v1/groups/") as res:
        if res.status == 404:
            return None
        if res.status != 200:
            await handle_error(res)
        json_body = await res.json()
        return json_body

@retry()
async def get_game_by_id(gameid):
    if container.games:
        game = find(lambda game: game["gameid"] == gameid, container.games)
        if game:
            return game

    async with req("get", "v1/games/byid/%d" % gameid) as res:
        if res.status != 200:
            await handle_error(res)
        json_body = await res.json()
        return json_body

@retry()
async def invite(name):
    async with req("post", "v1/groups/invite/byname/%s" % name) as res:
        if res.status != 204:
            await handle_error(res)

@retry()
async def join_group(groupid):
    async with req("post", "v1/groups/join/%s" % groupid) as res:
        if res.status != 204:
            await handle_error(res)

@retry()
async def mark_as_ready():
    async with req("post", "v1/groups/ready") as res:
        if res.status != 204:
            await handle_error(res)

@retry()
async def mark_as_not_ready():
    async with req("delete", "v1/groups/ready") as res:
        if res.status != 204:
            await handle_error(res)

@retry()
async def leave_group():
    async with req("delete", "v1/groups/leave") as res:
        if res.status != 204:
            await handle_error(res)

@retry()
async def start():
    async with req("post", "v1/groups/start") as res:
        if res.status != 204:
            await handle_error(res)
