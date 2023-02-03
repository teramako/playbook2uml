from __future__ import (absolute_import, division, print_function, annotations)
from typing import ClassVar, Iterator, Optional, Tuple
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
__metaclass__ = type

indent = '    '

class UMLStateBase(metaclass=ABCMeta):
    @abstractmethod
    def generateDefinition(self, level:int=0) -> Iterator[str]:
        pass

    @abstractmethod
    def generateRelation(self, next:Optional[UMLStateBase] = None, level:int=0) -> Iterator[str]:
        pass

    @abstractmethod
    def get_entry_point_name(self) -> str:
        pass

    @abstractmethod
    def get_end_point_name(self) -> str:
        pass

    def __str__(self) -> str:
        return f"<{self.__class__.__name__}({self._name})>"

def pair_state_iter(*args) -> Iterator[Tuple[UMLStateBase, UMLStateBase]]:
    current = args[0]
    for next in args[1:]:
        yield (current, next)
        current = next

class UMLStateTaskBase(UMLStateBase, metaclass=ABCMeta):
    ID : ClassVar[int]
    logger : ClassVar[Logger] = logger.getChild("UMLStateTask")
    def __init__(self, task:Task) -> None:
        self.logger.debug('start')
        self.task = task
        self.id = self.__class__.ID
        self.__class__.ID += 1

        self._name = 'task_%d' % self.id
        self.logger.debug(f'set name "{self._name}"')
        self._entry_point_name = self._name
        self._end_point_name = self._name
        self.when = self.get_when_list(self.task)
        self.has_when = len(self.when) > 0
        if self.has_when:
            self._entry_point_name = '%s_when' % self._name
            self.logger.debug(f'{self._name} has `when`. set `_entry_point_name "{self._entry_point_name}"')

        self.has_until = False
        if self.task.until:
            self.has_until = True
            self._end_point_name = '%s_until' % self._name
            self.logger.debug(f'{self._name} has `until`. set `_end_point_name "{self._end_point_name}"')

        self.logger.debug('end')

    def get_when_list(self, task) -> list[str]:
        when = task.when
        if when is Sentinel:
            return []
        elif isinstance(when, list):
            return when
        else:
            return [when]

    def get_entry_point_name(self) -> str:
        return self._entry_point_name

    def get_end_point_name(self) -> str:
        return self._end_point_name

class UMLStateBlockBase(UMLStateBase, metaclass=ABCMeta):
    ID : ClassVar[int] = 1
    TASK_CLASS: ClassVar[UMLStateTaskBase]
    logger : ClassVar[Logger] = logger.getChild("UMLStateBlock")

    @classmethod
    def load(cls, block:Block) -> Iterator[UMLStateBlockBase | UMLStateTaskBase]:
        if block.name or len(block.always) > 0 or len(block.rescue) > 0:
            cls.logger.debug(f'load block as explicit: {cls.ID}')
            yield cls(block)
        else:
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
        self._name = 'block_%d' % self.id
        self.logger.debug(f'start: {self}')
        self.tasks = tuple(self.load_tasks(block.block))
        self.always = tuple(self.load_tasks(block.always))
        self.rescue = tuple(task for task in self.load_tasks(block.rescue))
        self.has_always = len(self.always) > 0
        self.has_rescue = len(self.rescue) > 0

        self.logger.debug(f'end: {self}')

    def get_entry_point_name(self) -> str:
        return self.tasks[0].get_entry_point_name()

    def get_end_point_name(self) -> str:
        if self.has_always:
            return self.always[-1].get_end_point_name()
        return self.tasks[-1].get_end_point_name()

    def generateRelation(self, next:UMLStateBase, level:int=0) -> Iterator[str]:
        self.logger.debug(f'start {self}')
        for current_state, next_state in pair_state_iter(*self.tasks, *self.always, next):
            yield from current_state.generateRelation(next_state, level=level)

        if self.has_rescue:
            states = pair_state_iter(*self.rescue, self.always[0] if self.has_always else next)
            for current_state, next_state in states:
                yield from current_state.generateRelation(next_state, level=level)

        self.logger.debug(f'end {self}')

class UMLStateStart(UMLStateBase):
    logger = logger.getChild('UMLStateStart')

    def generateDefinition(self, level: int = 0) -> Iterator[str]:
        return
    def generateRelation(self, next:UMLStateBase, level:int=0) -> Iterator[str]:
        self.logger.debug('start')
        yield '%s[*] --> %s' % (indent * level, next.get_entry_point_name())
        self.logger.debug('end')
    def get_entry_point_name(self) -> str:
        return '[*]'
    def get_end_point_name(self) -> str:
        return '[*]'

class UMLStatePlayBase(UMLStateBase, metaclass=ABCMeta):
    ID = 1
    BLOCK_CLASS: UMLStateBlockBase
    logger = logger.getChild("UMLStatePlay")

    def __init__(self, play:Play) -> None:
        self.logger.debug('start')
        self.play = play
        self.id = self.__class__.ID
        self.__class__.ID += 1
        self._name = 'play_%d' % self.id
        self.pre_tasks = tuple(self.BLOCK_CLASS.load_tasks(play.pre_tasks))
        self.roles = tuple(self.BLOCK_CLASS.load_tasks(block for role in play.roles if not role.from_include for block in role.get_task_blocks()))
        self.tasks = tuple(self.BLOCK_CLASS.load_tasks(play.tasks))
        self.post_tasks = tuple(self.BLOCK_CLASS.load_tasks(play.post_tasks))
        self.logger.debug(f'{self}: {len(self.pre_tasks)} pre_tasks: {[str(t) for t in self.pre_tasks]}')
        self.logger.debug(f'{self}: {len(self.roles)} roles: {[str(t) for t in self.roles]}')
        self.logger.debug(f'{self}: {len(self.tasks)} tasks: {[str(t) for t in self.tasks]}')
        self.logger.debug(f'{self}: {len(self.post_tasks)} post_tasks: {[str(t) for t in self.post_tasks]}')
        self.logger.debug('end')

    def get_all_tasks(self) -> list[UMLStateBase]:
        return self.pre_tasks + self.roles + self.tasks + self.post_tasks

    def get_entry_point_name(self) -> str:
        return self.get_all_tasks()[0].get_entry_point_name()

    def get_end_point_name(self) -> str:
        return self.get_all_tasks()[-1].get_end_point_name()

class UMLStatePlaybookBase(metaclass=ABCMeta):
    logger = logger.getChild('UMLStatePlaybook')
    PLAY_CLASS: UMLStatePlayBase
    BLOCK_CLASS: UMLStateBlockBase
    TASK_CLASS: UMLStateTaskBase
    def __init__(self, playbook:str, option:Namespace=None):
        self.logger.debug('start')
        self.PLAY_CLASS.ID = 1
        self.BLOCK_CLASS.ID = 1
        self.TASK_CLASS.ID = 1
        dataloader = DataLoader()
        variable_manager = VariableManager(loader=dataloader)
        pb = Playbook(loader=dataloader)
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
            pb._loader.set_basedir(option.BASE_DIR)
            self.plays = [
                self.PLAY_CLASS(Play.load(dummy_play, variable_manager=variable_manager, loader=pb._loader, vars=None))
            ]
        else:
            '''
            For whole of the playbook.
            '''
            self.logger.debug(f'load playbook: {playbook}')
            pb._load_playbook_data(file_name=playbook, variable_manager=variable_manager)
            self.plays = [self.PLAY_CLASS(play) for play in pb.get_plays()]

        self.options = option

    @abstractmethod
    def generate(self) -> Iterator[str]:
        pass
