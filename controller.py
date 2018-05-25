import asyncio
import aiohttp
import logging
import atexit
import urwid
import json
from itertools import chain
from base64 import urlsafe_b64decode
from functools import wraps

loop = asyncio.get_event_loop()
loop.set_debug(True)

import view
import model
import dialog
from tools import tryexcept, async_tryexcept, find
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
    view.main_loop = urwid.MainLoop(
        view.interface,
        palette=dialog.DialogDisplay.palette,
        event_loop=urwid.AsyncioEventLoop(loop=loop))
    try:
        view.main_loop.run()
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
    urwid.connect_signal(view.b_invite, "click", on_invite_clicked)
    urwid.connect_signal(view.b_leave, "click", button_handler(on_leave_clicked))
    urwid.connect_signal(view.b_ready, "click", button_handler(on_ready_clicked))
    urwid.connect_signal(view.b_start, "click", button_handler(on_start_clicked))
    urwid.connect_signal(view.b_home, "click", button_handler(on_tmp_clicked))

async def on_tmp_clicked():
    dialog.do_inputbox("Player name to invite", 8, 30).call(lambda *args: logger.info(args))



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


def on_invite_clicked(_button):
    async def callback(exitcode, player):
        if exitcode != 0:
            return
        asyncio.ensure_future(async_tryexcept(onlyone(model.invite))(player))
        view.footer.set_text("%s has been invited." % player)
    
    dialog.do_inputbox("Player name to invite", 8, 30).call(
        lambda *args: asyncio.ensure_future(callback(*args)))

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
    render_group()

def render_group():
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

@async_tryexcept
@onlyone
async def on_leave_clicked():
    raise NotImplementedError()

@async_tryexcept
@onlyone
async def on_ready_clicked():
    if find(lambda member: member["id"] == model.container.user.userid,
            model.container.group.members)["ready"]:
        await model.mark_as_not_ready()
    else:
        await model.mark_as_ready()

@async_tryexcept
@onlyone
async def on_start_clicked():
    raise NotImplementedError()

@model.event_handler("user", "group", "invitation recieved")
def invited(payload):
    @async_tryexcept
    @onlyone
    async def callback(exitcode, _):
        if exitcode != 0:
            return

        await model.join_group(payload["to"]["groupid"])
        tasks.append(asyncio.ensure_future(model.msgqueue("group")))

        group = await model.get_my_group()
        update_group(group)

        view.t_game_name.set_text("Game name: %s" % payload["to"]["gamename"])

        change_navbar_to(view.n_in_group)
        change_screen_to(view.s_in_group)

    dialog.do_yesno(
        "You have been invited by {} to join a game of {}. "
        "Would you like to join the group ?".format(
            payload["from"]["username"], payload["to"]["gamename"]),
        8, 40).call(lambda *args: asyncio.ensure_future(callback(*args)))

@model.event_handler("group", "group", "user joined")
def group_user_joined(payload):
    model.container.group.members.append({
        "id": payload["user"]["userid"],
        "name": payload["user"]["username"],
        "ready": False
    })

    view.p_members.contents.append((
        urwid.Columns([
            urwid.Text(payload["user"]["username"]),
            urwid.Text("not ready", align="right")]),
        view.p_members.options()))
    
    logger.info("%s joined the group.", payload["user"]["username"])

@model.event_handler("group", "group", "user left")
def group_user_left(payload):
    model.container.group.members.remove(
        find(lambda member: member["id"] == payload["user"]["userid"],
             model.container.group.members))
    render_group()
    logger.info("%s left the group.", payload["user"]["username"])

@model.event_handler("group", "group", "user is ready")
def group_user_is_ready(payload):
    find(lambda member: member["id"] == payload["user"]["userid"],
         model.container.group.members)["ready"] = True
    render_group()
    logger.info("%s is ready.", payload["user"]["username"])

@model.event_handler("group", "group", "user is not ready")
def group_user_is_not_ready(payload):
    find(lambda member: member["id"] == payload["user"]["userid"],
         model.container.group.members)["ready"] = False
    render_group()
    logger.info("%s is no more ready.", payload["user"]["username"])

@model.event_handler("group", "group", "queue joined")
def group_queue_joined(payload):
    pass

@model.event_handler("user", "server", "notice")
def user_server_notice(payload):
    logger.info("Notice from server: %s", payload["notice"])

@model.event_handler("group", "server", "notice")
def group_server_notice(payload):
    logger.info("Notice from server: %s", payload["notice"])

@model.event_handler("party", "server", "notice")
def party_server_notice(payload):
    logger.info("Notice from server: %s", payload["notice"])

