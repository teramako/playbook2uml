#!env python
# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division, print_function, annotations)
from argparse import Namespace
from typing import Iterator, Optional, Tuple
from abc import ABCMeta, abstractmethod

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
    def generateRelation(self, next:Optional[UMLStateBase] = None) -> Iterator[str]:
        pass

    @abstractmethod
    def get_entry_point_name(self) -> str:
        pass

    @abstractmethod
    def get_end_point_name(self) -> str:
        pass

    def get_when_list(self, task) -> list[str]:
        when = task.when
        if when is Sentinel:
            return []
        elif isinstance(when, list):
            return when
        else:
            return [when]

def pair_state_iter(*args) -> Iterator[Tuple[UMLStateBase, UMLStateBase]]:
    current = args[0]
    for next in args[1:]:
        yield (current, next)
        current = next

class UMLStateTask(UMLStateBase):
    ID = 1
    def __init__(self, task:Task) -> None:
        self.task = task
        self.id = UMLStateTask.ID
        UMLStateTask.ID += 1

        self._name = 'task_%d' % self.id
        self._entry_point_name = self._name
        self._end_point_name = self._name
        self.when = self.get_when_list(self.task)
        self.has_when = len(self.when) > 0
        if self.has_when:
            self._entry_point_name = '%s_when' % self._name

        self.has_until = False
        if self.task.until:
            self.has_until = True
            self._end_point_name = '%s_until' % self._name
        
    def generateDefinition(self, level:int=0) -> Iterator[str]:
        prefix = indent * level
        if self.has_when:
            yield from self._generateWhenDefinition(level)

        yield '%sstate "== %s" as %s' % (prefix, self.task.get_name(), self._name)
        yield '%s%s : Action **%s**' % (prefix, self._name, self.task.action)
        yield from self._generete_table(self.task.args, level)
        if any((getattr(self.task, attr) is not None for attr in ['become', 'register', 'delegate_to'])):
            yield '%s%s : ....' % (prefix, self._name)
            yield from self._generateBecomeDefinition(level=level)
            yield from self._generateRegisterDefinition(level=level)
            yield from self._generateDelegateDefinition(level=level)

        if self.has_until:
            yield from self._generateUntilDefinition(level)

    def _generete_table(self, obj:dict, level:int=0) -> Iterator[str]:
        for key in obj:
            val = obj[key]
            if isinstance(val, str):
                lines = val.splitlines()
                if len(lines) > 1:
                    val = '%s ...(+%d lines)' % (lines[0], len(lines)-1)
            yield '%s%s : | %s | %s |' %(indent*level, self._name, key, val)
    
    def _generateRegisterDefinition(self, level:int=0) -> Iterator[str]:
        register = self.task.register
        if not register:
            return
        yield '%s%s : **register** //%s//' % (indent*level, self._name, register)

    def _generateBecomeDefinition(self, level:int=0) -> Iterator[str]:
        if self.task.become:
            if become_user := self.task.become_user:
                yield '%s%s : **become** yes (to %s)' % (indent*level, self._name, become_user)
            else:
                yield '%s%s : **become** yes' % (indent*level, self._name)

    def _generateDelegateDefinition(self, level:int=0) -> Iterator[str]:
        if val := self.task.delegate_to:
            yield '%s%s : **delegate_to** %s' % (indent*level, self._name, val)

    def _generateUntilDefinition(self, level:int=0) -> Iterator[str]:
        yield '%sstate %s <<choice>>' % (indent*level, self._end_point_name)
        yield '%snote right of %s' % (indent*level, self._end_point_name)
        yield '%s**until**: %s' % (indent*(level+1), self.task.until)
        yield '%s**retres**: %s' % (indent*(level+1), self.task.retries)
        yield '%s**delay**: %s (secconds)' % (indent*(level+1), self.task.delay)
        yield '%send note' % (indent*level)

    def _generateWhenDefinition(self, level:int=0) -> Iterator[str]:
        yield '%sstate %s <<choice>>' % (indent*level, self._entry_point_name)
        yield '%snote right of %s' % (indent*level, self._entry_point_name)
        note_indent = indent * (level+1)
        yield '%s=== when' % note_indent
        yield '%s----' % note_indent
        for when in self.when:
            yield '%s - %s' % (note_indent, when)
        yield '%send note' % (indent*level)

    def generateRelation(self, next: Optional[UMLStateBase] = None) -> Iterator[str]:
        if self.has_when:
            yield '%s --> %s' % (self._entry_point_name, self._name)
            yield '%s --> %s' % (self._end_point_name, next.get_entry_point_name())
            yield '%s --> %s : %s' % (self._entry_point_name, next.get_entry_point_name(), 'skip')
        else:
            yield '%s --> %s' % (self._end_point_name, next.get_entry_point_name())

        yield from self._generateLoopRelation()

        if self.has_until:
            yield '%s --> %s' % (self._name, self._end_point_name)
            yield '%s --> %s : retry' % (self._end_point_name, self._entry_point_name)

    def _generateLoopRelation(self) -> Iterator[str]:
        if self.task.loop is None:
            return
        loop_name = ('loop(with_%s)' % self.task.loop_with) if self.task.loop_with else 'loop'
        yield '%s --> %s' % (self._name, self._entry_point_name)
        yield 'note on link'
        yield '%s=== %s' % (indent, loop_name)
        yield '%s----' % indent
        # loops can either be a string (one-item loop) or a list
        if isinstance(self.task.loop, list):
            for loop_item in self.task.loop:
                yield '%s- %s' % (indent, loop_item)
        else:
            yield '%s- %s' % (indent, self.task.loop)
        yield 'end note'

    def get_entry_point_name(self) -> str:
        return self._entry_point_name

    def get_end_point_name(self) -> str:
        return self._end_point_name

class UMLStateBlock(UMLStateBase):
    ID = 1
    def __init__(self, block:Block) -> None:
        self.block = block
        self.id = UMLStateBlock.ID
        UMLStateBlock.ID += 1
        self._name = 'block_%d' % self.id
        self.tasks = self.get_UMLTasks(block.block)
        self.always = self.get_UMLTasks(block.always)
        self.rescue = self.get_UMLTasks(block.rescue)
        self.when = self.get_when_list(block)
        self.has_always = len(self.always) > 0
        self.has_rescue = len(self.rescue) > 0
        self.has_when = len(self.when) > 0

    def get_UMLTasks(self, tasks) -> list[UMLStateBase]:
        results = []
        for task in tasks:
            if isinstance(task, Block):
                results.append(UMLStateBlock(task))
            else:
                results.append(UMLStateTask(task))
        return results

    def generateDefinition(self, level:int=0) -> Iterator[str]:
        is_explicit = self.block.name or self.has_always or self.has_rescue
        next_level = level
        prefix = indent * level
        if self.has_when:
            yield from self._generateWhenDefinition(level)

        if is_explicit:
            yield '%sstate "Block: %s" as %s {' % (prefix, self.block.name, self._name)
            next_level+=1

        for task in self.tasks:
            yield from task.generateDefinition(next_level)

        if is_explicit:
            yield from self._generateAlwaysDefinition(next_level)
            yield from self._generateRescueDefinition(next_level)
            yield '%s}' % prefix
    
    def _generateWhenDefinition(self, level:int=0) -> Iterator[str]:
        name = '%s_when'% self._name
        yield '%sstate %s <<choice>>' % (indent*level, name)
        yield '%snote right of %s' % (indent*level, name)
        note_indent = indent * (level+1)
        yield '%s=== when' % note_indent
        yield '%s----' % note_indent
        for when in self.when:
            yield '%s - %s' % (note_indent, when)
        yield '%send note' % (indent*level)

    def _generateAlwaysDefinition(self, level:int=0) -> Iterator[str]:
        if not self.has_always:
            return
        prefix = indent * level
        yield '%sstate "Always" as %s {' % (prefix, self._name + '_always')
        for task in self.always:
            yield from task.generateDefinition(level + 1)
        yield '%s}' % prefix
    
    def _generateRescueDefinition(self, level:int=0) -> Iterator[str]:
        if not self.has_rescue:
            return
        prefix = indent * level
        yield '%sstate "Rescue" as %s {' % (prefix, self._name + '_rescue')
        for task in self.rescue:
            yield from task.generateDefinition(level + 1)
        yield '%s}' % prefix
    
    def get_entry_point_name(self) -> str:
        if self.has_when:
            return self._name + '_when'
        return self.tasks[0].get_entry_point_name()

    def get_end_point_name(self) -> str:
        if self.has_always:
            return self.always[-1].get_end_point_name()
        return self.tasks[-1].get_end_point_name()

    def generateRelation(self, next:UMLStateBase) -> Iterator[str]:
        if self.has_when:
            #yield '%s' % self.when
            yield '%s --> %s' % (self._name + '_when', self.tasks[0].get_entry_point_name())
            yield '%s --> %s : %s' % (self.get_entry_point_name(), next.get_entry_point_name(), 'skip')

        for current_state, next_state in pair_state_iter(*self.tasks, *self.always, next):
            yield from current_state.generateRelation(next_state)

        if self.has_rescue:
            states = pair_state_iter(*self.rescue, self.always[0] if self.has_always else next)
            for current_state, next_state in states:
                yield from current_state.generateRelation(next_state)

class UMLStateStart(UMLStateBase):
    def generateDefinition(self, level: int = 0) -> Iterator[str]:
        return
    def generateRelation(self, next:UMLStateBase) -> Iterator[str]:
        yield '[*] --> %s' % next.get_entry_point_name()
    def get_entry_point_name(self) -> str:
        return '[*]'
    def get_end_point_name(self) -> str:
        return '[*]'


class UMLStatePlay(UMLStateBase):
    ID = 1
    def __init__(self, play:Play) -> None:
        self.play = play
        self.id = UMLStatePlay.ID
        UMLStatePlay.ID += 1
        self._name = 'play_%d' % self.id
        self.pre_tasks = [UMLStateBlock(block) for block in play.pre_tasks]
        self.roles = [UMLStateBlock(block) for role in play.roles if not role.from_include for block in role.get_task_blocks()]
        self.tasks = [UMLStateBlock(block) for block in play.tasks]
        self.post_tasks = [UMLStateBlock(block) for block in play.post_tasks]

    def get_all_tasks(self) -> list[UMLStateBase]:
        return self.pre_tasks + self.roles + self.tasks + self.post_tasks

    def _generateVarsFilesDefition(self, level:int=0) -> Iterator[str]:
        '''
        generate `vars_files` definition
        '''
        if len(self.play.vars_prompt) > 0:
            key_name = 'vars_files'
            for var_file in self.play.vars_files:
                yield '%s%s : | %s | %s |' % (indent*level, self._name, key_name, var_file)
                key_name = ''

    def _generateVarsPromptDefinition(self, level:int=0) -> Iterator[str]:
        '''
        generate `vars_prompt` definition
        '''
        if len(self.play.vars_prompt) > 0:
            key_name = 'vars_prompt'
            for prompt in self.play.vars_prompt:
                yield '%s%s : | %s | %s |' % (indent*level, self._name, key_name, prompt['name'])
                key_name = ''

    def generateDefinition(self, level:int=0, only_role=False) -> Iterator[str]:
        if not only_role:
            yield '%sstate "= Play: %s" as %s {' % (indent*level, self.play.get_name(), self._name)
            level += 1
            for key in dir(self.play):
                if key in ['hosts', 'gather_facts', 'strategy', 'serial']:
                    val = getattr(self.play, key)
                    if val is Sentinel:
                        continue

                    yield '%s%s : | %s | %s |' % (indent*level, self._name, key, val)

            yield from self._generateVarsFilesDefition(level=level)
            yield from self._generateVarsPromptDefinition(level=level)

        for tasks in self.get_all_tasks():
            yield from tasks.generateDefinition(level)

        if not only_role:
            yield '%s}' % (indent*(level-1))

    def generateRelation(self, next_play:UMLStatePlay=None) -> Iterator[str]:
        for current_state, next_state in pair_state_iter(*self.get_all_tasks(), next_play):
            yield from current_state.generateRelation(next_state)

    def get_entry_point_name(self) -> str:
        return self.get_all_tasks()[0].get_entry_point_name()

    def get_end_point_name(self) -> str:
        return self.get_all_tasks()[-1].get_end_point_name()

class UMLStatePlaybook:
    def __init__(self, playbook:str, option:Namespace=None):
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
                            'name': role_name
                        }
                    }
                ]
            }
            pb._loader.set_basedir(option.BASE_DIR)
            self.plays = [
                UMLStatePlay(Play.load(dummy_play, variable_manager=variable_manager, loader=pb._loader, vars=None))
            ]
        else:
            '''
            For whole of the playbook.
            '''
            pb._load_playbook_data(file_name=playbook, variable_manager=variable_manager)
            self.plays = [UMLStatePlay(play) for play in pb.get_plays()]

        self.options = option

    def generate(self) -> Iterator[str]:
        '''
        Generate PlantUML codes
        '''
        yield '@startuml'
        if self.options:
            if title := self.options.title:
                yield 'title %s' % title
            if theme := self.options.theme:
                yield '!theme %s' % theme
            if self.options.left_to_right:
                yield 'left to right direction'

            only_role = self.options.role != ''
            for umlplay in self.plays:
                yield from umlplay.generateDefinition(only_role=only_role)

        start_end = UMLStateStart()
        for current_state, next_state in pair_state_iter(start_end, *self.plays, start_end):
            yield from current_state.generateRelation(next_state)

        yield '@enduml'
