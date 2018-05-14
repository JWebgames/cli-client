#!venv/bin/python

import logging
from controller import main
from config import LOGLEVEL

logfile = logging.FileHandler("client.log", mode="w")
logfile.formatter = logging.Formatter(
    "{asctime} [{levelname}] <{name}:{funcName}> {message}", style="{")
logfile.level = LOGLEVEL
logging.root.handlers = [logfile]
logging.root.level = LOGLEVEL

main()
