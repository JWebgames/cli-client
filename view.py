import urwid
from functools import partial

SubmitButton = partial(urwid.Button, "Submit")

# Navigation buttons
b_home = urwid.Button("Home")
b_quit = urwid.Button("Quit")
b_new_group = urwid.Button("New group")
b_group = urwid.Button("Group")
b_party = urwid.Button("Party")

# Navigation bars
n_not_connected = urwid.Columns([b_home, b_quit])
n_connected = urwid.Columns([b_home, b_new_group, b_quit])
n_in_group = urwid.Columns([b_home, b_group, b_quit])
n_in_party = urwid.Columns([b_home, b_group, b_party, b_quit])

# Text fields
t_connected_as = urwid.Text("Connected as: ")
t_user_id = urwid.Text("User id: ")
t_user_type = urwid.Text("User type: ")

# Register form
sb_register = SubmitButton()
f_register = urwid.Pile([
    urwid.Edit("Username: "),
    urwid.Edit("Email: "),
    urwid.Edit("Password: ", mask="*"),
    urwid.Edit("Retype the password: ", mask="*"),
    urwid.Divider(),
    sb_register
])

# Login form
sb_login = SubmitButton()
f_login = urwid.Pile([
    urwid.Edit("Login: "),
    urwid.Edit("Password: ", mask="*"),
    urwid.Divider(),
    sb_login
])

# New group form, populated in controller
f_new_group = urwid.SimpleFocusListWalker([])

# Group members
p_members = urwid.Pile([])
# Group buttons
b_ready = urwid.Button("Mark as ready")
b_invite = urwird.Button("Invite")
b_leave = urwid.Button("Leave")

# Screens
s_not_connected_home = urwid.Columns([
    urwid.LineBox(f_register, "Sign up"),
    urwid.LineBox(f_login, "Sign in")])

s_connected_home = urwid.LineBox(urwid.Pile([
    t_connected_as,
    urwid.Divider(),
    t_user_id,
    t_user_type
]), "Profile")

s_new_group = urwid.LineBox(urwid.BoxAdapter(urwid.ListBox(f_new_group), 10), "Select a game")

s_in_group = urwid.Pile([
    urwid.LineBox(p.members, "Group"),
    urwid.Divider(),
    urwid.Columns([
        b_ready,
        b_invite,
        b_leave
    ])
])

# Page structure
header = urwid.Pile([
    urwid.Text("Webgames Terminal User Interface", align="center"),
    urwid.Divider()])
body = urwid.Pile([n_not_connected, s_not_connected_home])
footer = urwid.Text("")
interface = urwid.Frame(urwid.Filler(body, valign="top"), header, footer)
