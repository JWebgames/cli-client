from logging import DEBUG

APIURL = "http://localhost:22548"
LOGLEVEL = DEBUG

GAMES = {
    1: ["gnome-terminal", "-e", "/home/julien/Projets/Webgames/Shifumi/client.py --addr {host} --port {port}"]
}
