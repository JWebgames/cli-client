import asyncio
import aiohttp
import logging
import atexit
import urwid
import json
from base64 import urlsafe_b64decode
from functools import wraps

loop = asyncio.get_event_loop()
loop.set_debug(True)

import view
import model
from tools import async_tryexcept
import webapi.storage.models

logger = logging.getLogger(__name__)
tasks = []

interface_locked = False
def onlyone(func):
    @wraps(func)
    async def wrapped(*args, **kwargs):
        global interface_locked
        if interface_locked:
            logger.info("Interface locked !")
            return
        interface_locked = True
        logger.info("Interface locked.")
        try:
            value = await func(*args, **kwargs)
        except:
            interface_locked = False
            raise
        finally:
            interface_locked = False
        logger.info("Interface unlocked.")
        return value
    return wrapped

def main():
    register_events()
    try:
        urwid.MainLoop(view.interface, event_loop=urwid.AsyncioEventLoop(loop=loop)).run()
    except KeyboardInterrupt:
        pass
    except urwid.ExitMainLoop:
        pass
    except:
        logger.exception("Unhandled error in main loop")


@atexit.register
def exit_():
    if model.container.token:
        asyncio.get_event_loop().run_until_complete(model.disconnect())
    for task in tasks:
        task.cancel()
    loop.run_until_complete(model.http.close())
    loop.close()

def form_handler(form, handler):
    def handler_call(_):
        fields = [field[0].edit_text for field in form.contents[:-2]]
        asyncio.ensure_future(handler(*fields))
    return handler_call

def button_handler(handler):
    def handler_call(button, *args):
        asyncio.ensure_future(handler(*args))
    return handler_call

def register_events():
    urwid.connect_signal(view.b_quit, "click", on_quit_clicked)
    urwid.connect_signal(view.sb_login, "click", form_handler(view.f_login, on_login_submited))
    urwid.connect_signal(view.b_new_group, "click", button_handler(on_new_group_clicked))
    urwid.connect_signal(view.b_group, "click", on_group_clicked)

def change_navbar_to(navbar):
    view.body.contents[0] = (navbar, view.body.options())
    view.body.focus_position = 0

def change_screen_to(screen):
    view.body.contents[1] = (screen, view.body.options())
    view.body.focus_position = 0

def on_home_clicked(_button):
    change_screen_to(view.s_connected_home)

def on_quit_clicked(_button):
    raise urwid.ExitMainLoop()

def on_group_clicked(_button):
    change_screen_to(view.s_in_group)

@async_tryexcept
@onlyone
async def on_login_submited(login, password):
    model.container.token = await model.connect(login, password)
    b64payload = model.container.token.split(".")[1]
    payload = json.loads(urlsafe_b64decode(b64payload + "=" * (len(b64payload) % 4)).decode())

    update_user_from_token(payload)

    group = await model.get_my_group()
    if group is None:
        change_navbar_to(view.n_connected)
        change_screen_to(view.s_connected_home)
    else:
        update_group(group)
        game = await model.get_game_by_id(group["gameid"])
        view.t_game_name.set_text("Game: %s" % game.name)

        # Player should be able to join its old game
        raise NotImplementedError("")
    
    urwid.connect_signal(view.b_home, "click", on_home_clicked)
    tasks.append(asyncio.ensure_future(model.msgqueue("user")))

def update_user_from_token(token_dict):
    model.container.user.userid = token_dict["uid"]
    model.container.user.type = token_dict["typ"]
    model.container.user.nick = token_dict["nic"]

    view.t_connected_as.set_text("Connected as %s" % model.container.user.nick)
    view.t_user_id.set_text("User id: %s" % model.container.user.userid)
    view.t_user_type.set_text("User type: %s" % model.container.user.type)

def update_group(group):
    model.container.group.state = group["state"]
    model.container.group.members = group["members"]
    model.container.group.groupid = group["groupid"]
    model.container.group.gameid = group["gameid"]
    model.container.group.slotid = group["slotid"]
    model.container.group.partyid = group["partyid"]

    view.t_group_state.set_text("Group status %s" % model.container.group.state)
    view.p_members.contents = [
        (urwid.Columns([urwid.Text(member["name"]),
                        urwid.Text("ready" if member["ready"] else "not ready", align="right")]),
         view.p_members.options()) for member in model.container.group.members]

@async_tryexcept
@onlyone
async def on_new_group_clicked():
    games = await model.get_game_list()

    choices = []
    for game in games:
        button = urwid.Button(game["name"])
        urwid.connect_signal(button, "click", button_handler(on_game_selected), game["gameid"])
        choices.append(urwid.AttrMap(button, None, focus_map="reversed"))

    view.f_new_group.clear()
    view.f_new_group.extend(choices)
    change_screen_to(view.s_new_group)

@async_tryexcept
@onlyone
async def on_game_selected(gameid):
    model.groupid = await model.create_group(gameid)
    group = await model.get_my_group()
    update_group(group)

    game = await model.get_game_by_id(gameid)
    view.t_game_name.set_text("Game name: %s" % game["name"])

    tasks.append(asyncio.ensure_future(model.msgqueue("group")))

    change_navbar_to(view.n_in_group)
    change_screen_to(view.s_in_group)

@model.event_handler("user", "group", "invitation recieved")
def invited(payload):
    pass

@model.event_handler("user", "group", "user joined")
def group_user_joined(payload):
    pass

@model.event_handler("user", "group", "user left")
def group_user_left(payload):
    pass

@model.event_handler("user", "group", "user is ready")
def group_user_is_ready(payload):
    pass

@model.event_handler("user", "group", "user is not ready")
def group_user_is_not_ready(payload):
    pass

@model.event_handler("user", "group", "queue joined")
def group_queue_joined(payload):
    pass

@model.event_handler("user", "server", "notice")
def server_notice(notice):
    logger.info("Notice from server: %s", notice)
