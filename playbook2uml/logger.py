import logging
import sys

LEVEL = ['WARNING', 'INFO', 'DEBUG']

black   = '\033[0;30m'
red     = '\033[0;31m'
green   = '\033[0;32m'
yellow  = '\033[0;33m'
blue    = '\033[0;34m'
magenta = '\033[0;35m'
cyan    = '\033[0;36m'
white   = '\033[0;37m'
reset   = '\033[0;0m'

def getLogger(name: str, verbose: int = 0) -> logging.Logger:
    logger = logging.getLogger(name)
    setLoggerLevel(logger, verbose)

    if sys.stderr.isatty():
        format = f'{yellow}playbook2uml/%(filename)s:%(lineno)d{reset}:{cyan}[%(name)s.%(funcName)s]{reset} %(message)s'
    else:
        format = f'playbook2uml/%(filename)s:%(lineno)d:[%(name)s.%(funcName)s] %(message)s'

    formatter = logging.Formatter(format)

    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    return logger

def setLoggerLevel(logger: logging.Logger, verbose: int = 0):
    if verbose > 2:
        verbose = 2
    level = getattr(logging, LEVEL[verbose])
    logger.setLevel(level)
