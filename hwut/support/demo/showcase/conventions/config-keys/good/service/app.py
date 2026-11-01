"""app.py -- the measurement service of the motor bench."""
import configparser
import os

cfg = configparser.ConfigParser()
cfg.read(os.getenv("APP_CONFIG", "/etc/bench/app.ini"))

HOST  = cfg.get("server", "host")
PORT  = cfg.getint("server", "port")
POOL  = cfg["db"].getint("pool_size")
DSN   = cfg["db"]["dsn"]
LEVEL = os.environ.get("APP_LOG_LEVEL", "info")
