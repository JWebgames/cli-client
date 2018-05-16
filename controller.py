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

logger = logging.getLogger(__name__)
tasks = []

interface_locked = False
def onlyone(func):
    @wraps(func)
    async def wrapped(*args, **kwargs):
        global interface_locked
        if interface_locked:
            view.footer.set_text("Interface locked !")
            return
        interface_locked = True
        view.footer.set_text("Interface locked.")
        value = await func(*args, **kwargs)
        interface_locked = False
        view.footer.set_text("Interface unlocked.")
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

def change_navbar_to(navbar):
    view.body.contents[0] = (navbar, view.body.options())
    view.body.focus_position = 0

def change_screen_to(screen):
    view.body.contents[1] = (screen, view.body.options())
    view.body.focus_position = 0

def on_quit_clicked(_button):
    raise urwid.ExitMainLoop()

@onlyone
async def on_login_submited(login, password):
    token = await model.connect(login, password)
    model.token = token

    b64payload = token.split(".")[1]
    payload = json.loads(urlsafe_b64decode(b64payload + "=" * (len(b64payload) % 4)).decode())

    model.userid = payload["uid"]
    view.t_connected_as.set_text("Connected as %s" % payload["nic"])
    view.t_user_id.set_text("User id: %s" % payload["uid"])
    view.t_user_type.set_text("User type: %s" % payload["typ"])

    change_navbar_to(view.n_connected)
    change_screen_to(view.s_connected_home)
    
    tasks.append(asyncio.ensure_future(model.msgqueue("user")))

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

@onlyone
async def on_game_selected(gameid):
    model.groupid = await model.create_group(gameid)

    model.p_members.content.append()

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
