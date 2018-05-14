import aiohttp
import asyncio
import atexit
import json
from collections import defaultdict
from logging import getLogger
from operator import itemgetter
from urllib.parse import urljoin
from contextlib import suppress

from controller import loop
from config import APIURL
import view

logger = getLogger(__name__)
http = aiohttp.ClientSession(loop=loop)

token = None
userid = None
groupid = None
partyid = None

group = []

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
    "party": defaultdict(dict)}
def event_handler(scope, categ, command):
    def register(func):
        event_handlers[scope][categ][command] = func
        return func
    return register

async def msgqueue(scope):
    seens = []
    with suppress(asyncio.CancelledError):
        while True:
            async with req("get", "v1/msgqueues/%s" % scope) as res:
                if res.status != 200:
                    await handle_error(res)
                
                json_body = await res.json()
                for event in sorted(json_body, key=itemgetter("timestamp")):
                    if event.msgid in seens:
                        continue
                    seens.append(event.msgid)

                    message = json.loads(event.message)
                    categ, cmd = message["type"].split(":")

                    callback = event_handlers[scope].get(categ, {}).get(cmd)
                    if callback is None:
                        logger.warning("Cannot handle event type %s", message["type"])
                    del message["type"]

                    view.footer.set_text("Event recieved !")
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.ensure_future(callback(message))
                    else:
                        callback(message)

                seens = list(map(itemgetter("msgid"), json_body))
            asyncio.sleep(4)

async def register(username, email, password):
    payload = {"username": username, "email": email, "password": password}
    async with req("post", "v1/auth/register", json=payload) as res:
        if res.status != 200:
            await handle_error(res)
        
        json_body = await res.json()
        return json_body["userid"]

async def connect(login, password):
    payload = {"login": login, "password": password}
    async with req("post", "v1/auth", json=payload) as res:
        if res.status != 200:
            await handle_error(res)

        json_body = await res.json()
        return json_body["token"]

async def disconnect():
    async with req("delete", "v1/auth") as res:
        if res.status != 204:
            await handle_error(res)

games = None
async def get_game_list():
    global games
    if games is None:
        async with req("get", "/v1/games") as res:
            if res.status != 200:
                await handle_error(res)        
            games = await res.json()
    return games

async def create_group(gameid):
    async with req("post", "/create/%d" % gameid) as res:
        if res.status != 200:
            await handle_error(res)
        json_body = await res.json()
        return json_body["groupid"]