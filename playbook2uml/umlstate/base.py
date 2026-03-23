from __future__ import (absolute_import, division, print_function, annotations)
from typing import ClassVar, Iterator, Optional, Tuple, override
from collections.abc import Iterable
from abc import ABCMeta, abstractmethod
from argparse import Namespace
from playbook2uml.umlstate import logger
from logging import Logger

from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
from ansible.playbook import Playbook
from ansible.playbook.play import Play
from ansible.playbook.block import Block
from ansible.playbook.task import Task
from ansible.utils.sentinel import Sentinel
from ansible.plugins.loader import init_plugin_loader
__metaclass__ = type

indent = '    '

class UMLStateBase(metaclass=ABCMeta):
    """
    Abstract base class for UML State diagram elements.

    This class defines the interface for objects that can be represented in UML State diagrams.
    It provides abstract methods for generating diagram definitions, managing state relations,
    and handling entry/exit points.
    """

    name: str
    """
    UMLState diagram's identifier
    """

    @abstractmethod
    def generateDefinition(self, level:int=0) -> Iterator[str]:
        """
        Generate UMLState diagram's definition
        """
        pass

    @abstractmethod
    def generateRelation(self, next:Optional[UMLStateBase], level:int=0) -> Iterator[str]:
        pass

    @abstractmethod
    def get_entry_point_name(self) -> str:
        """
        Get the name of the entry point.

        Returns:
            str: The name of the entry point.
        """
        pass

    @abstractmethod
    def get_end_point_name(self) -> str:
        """
        Get the name of the end point.

        Returns:
            str: The name of the end point.
        """
        pass

    def __str__(self) -> str:
        return f"<{self.__class__.__name__}({self.name})>"

def pair_state_iter(*args) -> Iterator[Tuple[UMLStateBase, UMLStateBase | None]]:
    """
    Iterate over consecutive pairs of states from the given arguments.

    Yields tuples of (current_state, next_state) for each consecutive pair
    of states in the input arguments. The last state is paired with None.

    Example:
        >>> states = [state1, state2, state3]
        >>> for current, next_state in pair_state_iter(*states):
        ...     print(current, next_state)
        # Output:
        # state1 state2
        # state2 state3
        # state3 None
    """
    current = args[0]
    for next in args[1:]:
        yield (current, next)
        current = next

class UMLStateTaskBase(UMLStateBase, metaclass=ABCMeta):
    """
    UMLStateTaskBase is an abstract base class that represents a UML state for an Ansible task.

    This class manages the lifecycle and metadata of a task within a UML state diagram,
    including task naming, conditional logic (when), and loop logic (until).
    """

    ID: ClassVar[int]
    logger : ClassVar[Logger] = logger.getChild("UMLStateTask")

    def __init__(self, task:Task) -> None:
        self.logger.debug('start')
        self.task = task
        self.id = self.__class__.ID
        self.__class__.ID += 1

        self.name = 'task_%d' % self.id
        self.logger.debug(f'set name "{self.name}"')
        self._entry_point_name = self.name
        self._end_point_name = self.name
        self.when = self.get_when_list(self.task)
        self.has_when = len(self.when) > 0
        if self.has_when:
            self._entry_point_name = '%s_when' % self.name
            self.logger.debug(f'{self.name} has `when`. set `_entry_point_name "{self._entry_point_name}"')

        self.has_until = False
        if self.task.until:
            self.has_until = True
            self._end_point_name = '%s_until' % self.name
            self.logger.debug(f'{self.name} has `until`. set `_end_point_name "{self._end_point_name}"')

        self.logger.debug('end')

    def get_when_list(self, task) -> list[str]:
        when = task.when
        if when is Sentinel:
            return []
        elif isinstance(when, list):
            return when
        else:
            return [when]

    @override
    def get_entry_point_name(self) -> str:
        return self._entry_point_name

    @override
    def get_end_point_name(self) -> str:
        return self._end_point_name

class UMLStateBlockBase(UMLStateBase, metaclass=ABCMeta):
    """
    Abstract base class for UML state blocks in Ansible playbook diagrams.

    This class represents a block construct in Ansible playbooks and manages the conversion
    of block structures (including tasks, rescue, and always sections) into UML state diagram
    elements.
    """

    ID: ClassVar[int]
    TASK_CLASS: ClassVar[type[UMLStateTaskBase]]
    logger : ClassVar[Logger] = logger.getChild("UMLStateBlock")

    @classmethod
    def load(cls, block:Block) -> Iterator[UMLStateBlockBase | UMLStateTaskBase]:
        if block.name or block.always or block.rescue:
            cls.logger.debug(f'load block as explicit: {cls.ID}')
            yield cls(block)
        elif isinstance(block.block, Iterable):
            cls.logger.debug(f'load block as implicit')
            for task in block.block:
                if isinstance(task, Block):
                    yield from cls.load(task)
                elif getattr(task, 'implicit', False):
                    cls.logger.debug(f'skip: {task.get_name()} is implicit')
                    continue
                else:
                    yield cls.TASK_CLASS(task)

    @classmethod
    def load_tasks(cls, tasks:Iterable[Block|Task]) -> Iterator[UMLStateBlockBase | UMLStateTaskBase]:
        for task in tasks:
            if isinstance(task, Block):
                yield from cls.load(task)
            elif getattr(task, 'implicit', False):
                cls.logger.debug(f'skip: {task.get_name()} is implicit')
                # Skip when the tasks is implicit `role_complete` block
                # See: https://github.com/ansible/ansible/commit/1b70260d5aa2f6c9782fd2b848e8d16566e50d85
                continue
            else:
                yield cls.TASK_CLASS(task)

    def __init__(self, block:Block) -> None:
        self.block = block
        self.id = self.__class__.ID
        self.__class__.ID += 1
        self.name = 'block_%d' % self.id
        self.logger.debug(f'start: {self}')
        if isinstance(block.block, Iterable):
            self.tasks = tuple(self.load_tasks(block.block))
        if isinstance(block.always, Iterable):
            self.always = tuple(self.load_tasks(block.always))
        if isinstance(block.rescue, Iterable):
            self.rescue = tuple(task for task in self.load_tasks(block.rescue))
        self.has_always = len(self.always) > 0
        self.has_rescue = len(self.rescue) > 0

        self.logger.debug(f'end: {self}')

    @override
    def get_entry_point_name(self) -> str:
        return self.tasks[0].get_entry_point_name()

    @override
    def get_end_point_name(self) -> str:
        if self.has_always:
            return self.always[-1].get_end_point_name()
        return self.tasks[-1].get_end_point_name()

    @override
    def generateRelation(self, next:Optional[UMLStateBase], level:int=0) -> Iterator[str]:
        self.logger.debug(f'start {self}')
        for current_state, next_state in pair_state_iter(*self.tasks, *self.always, next):
            yield from current_state.generateRelation(next_state, level=level)

        if self.has_rescue:
            states = pair_state_iter(*self.rescue, self.always[0] if self.has_always else next)
            for current_state, next_state in states:
                yield from current_state.generateRelation(next_state, level=level)

        self.logger.debug(f'end {self}')

class UMLStateStart(UMLStateBase):
    """
    UMLStateStart represents the initial state in a UML state diagram.

    This class generates the start point notation '[*]' for UML state diagrams
    and handles transitions from the start state to the next state.
    """
    logger = logger.getChild('UMLStateStart')

    @override
    def generateDefinition(self, level: int = 0) -> Iterator[str]:
        yield ''

    @override
    def generateRelation(self, next:Optional[UMLStateBase], level:int=0) -> Iterator[str]:
        if next is not None:
            self.logger.debug('start')
            yield '%s[*] --> %s' % (indent * level, next.get_entry_point_name())
            self.logger.debug('end')

    @override
    def get_entry_point_name(self) -> str:
        return '[*]'

    @override
    def get_end_point_name(self) -> str:
        return '[*]'

class UMLStatePlayBase(UMLStateBase, metaclass=ABCMeta):
    """
    A base class for representing UML state diagrams of Ansible plays.

    This class extends UMLStateBase and serves as an abstract base for play-level state
    representations. It manages the hierarchical structure of play components including
    pre-tasks, roles, tasks, and post-tasks.
    """

    ID: ClassVar[int]
    BLOCK_CLASS: ClassVar[type[UMLStateBlockBase]]
    logger = logger.getChild("UMLStatePlay")

    def __init__(self, play:Play) -> None:
        self.logger.debug('start')
        self.play = play
        self.id = self.__class__.ID
        self.__class__.ID += 1
        self.name = 'play_%d' % self.id
        if isinstance(play.pre_tasks, Iterable):
            self.pre_tasks = tuple(self.BLOCK_CLASS.load_tasks(play.pre_tasks))
        if isinstance(play.roles, Iterable):
            self.roles = tuple(self.BLOCK_CLASS.load_tasks(
                block for role in play.roles if not getattr(role, 'from_include', getattr(role, '_from_include', False))
                for block in role.get_task_blocks()))
        if isinstance(play.tasks, Iterable):
            self.tasks = tuple(self.BLOCK_CLASS.load_tasks(play.tasks))
        if isinstance(play.post_tasks, Iterable):
            self.post_tasks = tuple(self.BLOCK_CLASS.load_tasks(play.post_tasks))
        self.logger.debug(f'{self}: {len(self.pre_tasks)} pre_tasks: {[str(t) for t in self.pre_tasks]}')
        self.logger.debug(f'{self}: {len(self.roles)} roles: {[str(t) for t in self.roles]}')
        self.logger.debug(f'{self}: {len(self.tasks)} tasks: {[str(t) for t in self.tasks]}')
        self.logger.debug(f'{self}: {len(self.post_tasks)} post_tasks: {[str(t) for t in self.post_tasks]}')
        self.logger.debug('end')

    def get_all_tasks(self) -> tuple[UMLStateBase, ...]:
        return self.pre_tasks + self.roles + self.tasks + self.post_tasks

    @override
    def get_entry_point_name(self) -> str:
        return self.get_all_tasks()[0].get_entry_point_name()

    @override
    def get_end_point_name(self) -> str:
        return self.get_all_tasks()[-1].get_end_point_name()

class UMLStatePlaybookBase(metaclass=ABCMeta):
    """
    Abstract base class for converting Ansible playbooks to UML state diagrams.

    This class handles loading and parsing Ansible playbook data, supporting both
    full playbook parsing and role-only modes. It initializes the necessary Ansible
    loaders and variable managers, then converts plays into UML state representations.

    Raises:
        Various Ansible loader exceptions if the playbook or role cannot be loaded.

    Note:
        When option.role is specified, a dummy playbook is created that imports only
        the specified role. Otherwise, all plays from the playbook file are loaded.
    """

    logger = logger.getChild('UMLStatePlaybook')
    PLAY_CLASS: ClassVar[type[UMLStatePlayBase]]
    BLOCK_CLASS: ClassVar[type[UMLStateBlockBase]]
    TASK_CLASS: ClassVar[type[UMLStateTaskBase]]

    def __init__(self, playbook:str, option:Namespace):
        """
        Initialize the UML state generator from an Ansible playbook or role.

        Args:
            playbook (str): Path to the Ansible playbook file to parse.
            option (Namespace): Configuration options containing:
                - role (str, optional): Role name to load instead of playbook
                - tasks_from (str, optional): Specific tasks file to import from the role
                - BASE_DIR (str): Base directory for loading roles and playbooks

        Initializes the playbook parser by:
        - Setting up Ansible's DataLoader and VariableManager
        - Creating PLAY, BLOCK, and TASK class instances with ID counters
        - Loading either a dummy play (if role mode) or the full playbook
        - Storing the plays and options for later processing

        In role mode, creates a dummy playbook that imports the specified role.
        In playbook mode, loads all plays from the given playbook file.
        """
        self.logger.debug('start')
        self.PLAY_CLASS.ID = 1
        self.BLOCK_CLASS.ID = 1
        self.TASK_CLASS.ID = 1
        dataloader = DataLoader()
        variable_manager = VariableManager(loader=dataloader)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            init_plugin_loader()

        if option.role:
            '''
            For only role mode.
            Load a dummy play data which imports the role only.
            '''
            role_name = option.role
            dummy_play = {
                'hosts': 'all',
                'tasks': [
                    {
                        'import_role': {
                            'name': role_name,
                            'tasks_from': option.tasks_from
                        }
                    }
                ]
            }
            self.logger.debug(f'load dummy play: {dummy_play}')
            dataloader.set_basedir(option.BASE_DIR)
            pb = Playbook(loader=dataloader)
            self.plays = [
                self.PLAY_CLASS(Play.load(dummy_play, variable_manager=variable_manager, loader=pb._loader, vars=None))
            ]
        else:
            '''
            For whole of the playbook.
            '''
            self.logger.debug(f'load playbook: {playbook}')
            pb = Playbook.load(playbook, variable_manager=variable_manager, loader=dataloader)
            self.plays = [self.PLAY_CLASS(play) for play in pb.get_plays()]

        self.options = option

    @abstractmethod
    def generate(self) -> Iterator[str]:
        pass
