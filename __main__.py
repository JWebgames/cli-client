#!venv/bin/python

import logging
from controller import main
from config import LOGLEVEL
from tools import UrwidHandler

logfile = logging.FileHandler("client.log", mode="w")
logfile.formatter = logging.Formatter(
    "{asctime} [{levelname}] <{name}:{funcName}> {message}", style="{")
logfile.level = LOGLEVEL

urwidhdl = UrwidHandler()
urwidhdl.formatter = logging.Formatter("{message}", style="{")
urwidhdl.level = logging.INFO

logging.root.handlers = [logfile, urwidhdl]
logging.root.level = LOGLEVEL

main()
