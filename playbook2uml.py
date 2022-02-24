#!env python
# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division, print_function, annotations)
from typing import Iterator, Optional, Tuple
from abc import ABCMeta, abstractmethod

from ansible.playbook import Playbook
from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
from ansible.playbook import Playbook
from ansible.playbook.play import Play
from ansible.playbook.block import Block
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
        when = task._attributes['when']
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
    def __init__(self, task) -> None:
        self.task = task
        self.id = UMLStateTask.ID
        UMLStateTask.ID += 1

        self.name = 'task_%d' % self.id
        self.entry_point_name = self.name
        self.end_point_name = self.name
        self.when = self.get_when_list(self.task)
        self.has_when = len(self.when) > 0
        if self.has_when:
            self.entry_point_name = '%s_when' % self.name
        
    def generateDefinition(self, level:int=0) -> Iterator[str]:
        prefix = indent * level
        if self.has_when:
            yield from self._generateWhenDefinition(level)

        yield '%sstate "%s" as %s' % (prefix, self.task.get_name(), self.name)
        yield '%s%s : Action **%s**' % (prefix, self.name, self.task.action)
        yield from self._generete_table(self.task.args, level)

    def _generete_table(self, obj:dict, level:int=0) -> Iterator[str]:
        for key in obj:
            val = obj[key]
            if isinstance(val, str):
                lines = val.splitlines()
                if len(lines) > 1:
                    val = '%s ...(+%d lines)' % (lines[0], len(lines)-1)
            yield '%s%s : | %s | %s |' %(indent*level, self.name, key, val)
    
    def _generateWhenDefinition(self, level:int=0) -> Iterator[str]:
        prefix = indent * level
        yield '%sstate task_%d_when <<choice>>' % (prefix, self.id)

    def generateRelation(self, next: Optional[UMLStateBase] = None) -> Iterator[str]:
        if self.has_when:
            yield '%s --> %s : %s' % (self.entry_point_name, self.name, ' and '.join(self.when))
            yield '%s --> %s' % (self.name, next.get_entry_point_name())
            yield '%s --> %s : %s' % (self.entry_point_name, next.get_entry_point_name(), 'skip')
        else:
            yield '%s --> %s' % (self.name, next.get_entry_point_name())

        if self.task.loop is not None:
            if self.task.loop_with is not None:
                loop_name = 'with_%s' % self.task.loop_with
                yield '%s --> %s : loop(%s)\\n %s' % (self.name, self.entry_point_name, loop_name, str(self.task.loop))
            else:
                yield '%s --> %s : loop\\n%s' % (self.name, self.entry_point_name, str(self.task.loop))

    def get_entry_point_name(self) -> str:
        return self.entry_point_name

    def get_end_point_name(self) -> str:
        return self.end_point_name

class UMLStateBlock(UMLStateBase):
    ID = 1
    def __init__(self, block:Block) -> None:
        self.block = block
        self.id = UMLStateBlock.ID
        UMLStateBlock.ID += 1
        self.name = 'block_%d' % self.id
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
            yield '%sstate %s <<choice>>' % (prefix, self.name + '_when')
        if is_explicit:
            yield '%sstate "Block: %s" as %s {' % (prefix, self.block.name, self.name)
            next_level+=1

        for task in self.tasks:
            yield from task.generateDefinition(next_level)

        if is_explicit:
            yield from self._generateAlwaysDefinition(next_level)
            yield from self._generateRescueDefinition(next_level)
            yield '%s}' % prefix
    
    def _generateAlwaysDefinition(self, level:int=0) -> Iterator[str]:
        if not self.has_always:
            return
        prefix = indent * level
        yield '%sstate "Always" as %s {' % (prefix, self.name + '_always')
        for task in self.always:
            yield from task.generateDefinition(level + 1)
        yield '%s}' % prefix
    
    def _generateRescueDefinition(self, level:int=0) -> Iterator[str]:
        if not self.has_rescue:
            return
        prefix = indent * level
        yield '%sstate "Rescue" as %s {' % (prefix, self.name + '_rescue')
        for task in self.rescue:
            yield from task.generateDefinition(level + 1)
        yield '%s}' % prefix
    
    def get_entry_point_name(self) -> str:
        if self.has_when:
            return self.name + '_when'
        return self.tasks[0].get_entry_point_name()

    def get_end_point_name(self) -> str:
        if self.has_always:
            return self.always[-1].get_end_point_name()
        return self.tasks[-1].get_end_point_name()

    def generateRelation(self, next:UMLStateBase) -> Iterator[str]:
        if self.has_when:
            #yield '%s' % self.when
            yield '%s --> %s : %s' % (self.name + '_when', self.tasks[0].get_entry_point_name(), ' and '.join(self.when))
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
        self.name = 'play_%d' % self.id
        self.pre_tasks = [UMLStateBlock(block) for block in play.pre_tasks]
        self.tasks = [UMLStateBlock(block) for block in play.tasks]
        self.roles = [UMLStateBlock(block) for role in play.roles if not role.from_include for block in role.get_task_blocks()]
        self.post_tasks = [UMLStateBlock(block) for block in play.post_tasks]

    def get_all_tasks(self) -> list[UMLStateBase]:
        return self.pre_tasks + self.tasks + self.roles + self.post_tasks

    def _generateVarsFilesDefition(self, level:int=0) -> Iterator[str]:
        '''
        generate `vars_files` definition
        '''
        if len(self.play.vars_prompt) > 0:
            key_name = 'vars_files'
            for var_file in self.play.vars_files:
                yield '%s%s : | %s | %s |' % (indent*level, self.name, key_name, var_file)
                key_name = ''

    def _generateVarsPromptDefinition(self, level:int=0) -> Iterator[str]:
        '''
        generate `vars_prompt` definition
        '''
        if len(self.play.vars_prompt) > 0:
            key_name = 'vars_prompt'
            for prompt in self.play.vars_prompt:
                yield '%s%s : | %s | %s |' % (indent*level, self.name, key_name, prompt['name'])
                key_name = ''

    def generateDefinition(self, level:int=0) -> Iterator[str]:
        yield '%sstate "%s" as %s {' % (indent*level, self.play.get_name(), self.name)
        for key in ['hosts', 'gather_facts', 'strategy', 'serial']:
            val = self.play._attributes[key]
            if val is Sentinel:
                continue

            yield '%s%s : | %s | %s |' % (indent*(level+1), self.name, key, val)

        yield from self._generateVarsFilesDefition(level=level+1)
        yield from self._generateVarsPromptDefinition(level=level+1)

        for tasks in self.get_all_tasks():
            yield from tasks.generateDefinition(level+1)

        yield '%s}' % (indent*level)

    def generateRelation(self, next_play:UMLStatePlay=None) -> Iterator[str]:
        for current_state, next_state in pair_state_iter(*self.get_all_tasks(), next_play):
            yield from current_state.generateRelation(next_state)

    def get_entry_point_name(self) -> str:
        return self.get_all_tasks()[0].get_entry_point_name()

    def get_end_point_name(self) -> str:
        return self.get_all_tasks()[-1].get_end_point_name()

class UMLStatePlaybook:
    def __init__(self, playbook:str):
        dataloader = DataLoader()
        variable_manager = VariableManager(loader=dataloader)
        self.name = playbook
        self.playbook = Playbook.load(playbook, loader=dataloader, variable_manager=variable_manager)
        self.plays = [UMLStatePlay(play) for play in self.playbook.get_plays()]

    def generate(self) -> Iterator[str]:
        '''
        Generate PlantUML codes
        '''
        yield '@startuml'
        for umlplay in self.plays:
            yield from umlplay.generateDefinition()

        start_end = UMLStateStart()
        for current_state, next_state in pair_state_iter(start_end, *self.plays, start_end):
            yield from current_state.generateRelation(next_state)

        yield '@enduml'

def main(args):
    '''main'''
    umlplaybook = UMLStatePlaybook(args.PLAYBOOK)
    for line in umlplaybook.generate():
        print(line)

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Ansible-Playbook to PlantUML')
    ap.add_argument('PLAYBOOK', help='playbook file')
    args = ap.parse_args()
    main(args)
