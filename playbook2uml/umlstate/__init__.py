import importlib
from argparse import Namespace
from playbook2uml.logger import getLogger, setLoggerLevel
logger = getLogger(__name__)

DIAGRAM_TYPES = (
    'plantuml',
    'mermaid'
)

def load(args:Namespace):
    setLoggerLevel(logger, args.verbose)
    if args.type not in DIAGRAM_TYPES:
        raise ValueError(f'invalid type: {args.type}')

    umlstate = importlib.import_module('playbook2uml.umlstate.' + args.type)
    logger.debug(f'loaded {umlstate.__name__}')

    return umlstate.UMLStatePlaybook(args.PLAYBOOK, option=args)
