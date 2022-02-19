#!env python
# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division, print_function, annotations)
from typing import Iterator, Optional
from abc import ABCMeta, abstractmethod

from ansible.playbook import Playbook
from ansible.parsing.dataloader import DataLoader
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

    def get_when_list(self, task):
        when = task._attributes['when']
        if when is Sentinel:
            return []
        elif isinstance(when, list):
            return when
        else:
            return [when]

class UMLState(UMLStateBase):
    ID = 1
    def __init__(self, task) -> None:
        self.task = task
        self.id = UMLState.ID
        UMLState.ID += 1

        self.name = 'task_%d' % self.id
        self.entry_point_name = self.name
        self.end_point_name = self.name
        self.when = self.get_when_list(self.task)
        if len(self.when) > 0:
            self.entry_point_name = '%s_when' % self.name
        
    def generateDefinition(self, level:int=0) -> Iterator[str]:
        prefix = indent * level
        if len(self.when) > 0:
            yield from self._generateWhenDefinition(level)

        yield '%sstate "%s" as %s' % (prefix, self.task.get_name(), self.name)
        yield '%s%s : Action **%s**' % (prefix, self.name, self.task.action)
        yield from self._generete_table(self.task.args, level)

    def _generete_table(self, obj:dict, level:int=0) -> Iterator[str]:
        for key in obj:
            if key.startswith('_'):
                continue
            yield '%s%s : | %s | %s |' %(indent*level, self.name, key, obj[key])
    
    def _generateWhenDefinition(self, level:int=0) -> Iterator[str]:
        prefix = indent * level
        yield '%sstate task_%d_when <<choice>>' % (prefix, self.id)

    def generateRelation(self, next: Optional[UMLStateBase] = None) -> Iterator[str]:
        if len(self.when) > 0:
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

    def get_UMLTasks(self, tasks) -> list[UMLStateBase]:
        results = []
        for task in tasks:
            if isinstance(task, Block):
                results.append(UMLStateBlock(task))
            else:
                results.append(UMLState(task))
        return results

    def generateDefinition(self, level:int=0) -> Iterator[str]:
        is_explicit = self.block.name or len(self.always) > 0 or len(self.rescue) > 0
        next_level = level
        prefix = indent * level
        if len(self.when) > 0:
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
        if len(self.always) == 0:
            return
        prefix = indent * level
        yield '%sstate "Always" as %s {' % (prefix, self.name + '_always')
        for task in self.always:
            yield from task.generateDefinition(level + 1)
        yield '%s}' % prefix
    
    def _generateRescueDefinition(self, level:int=0) -> Iterator[str]:
        if len(self.rescue) == 0:
            return
        prefix = indent * level
        yield '%sstate "Rescue" as %s {' % (prefix, self.name + '_rescue')
        for task in self.rescue:
            yield from task.generateDefinition(level + 1)
        yield '%s}' % prefix
    
    def get_entry_point_name(self) -> str:
        if len(self.when) > 0:
            return self.name + '_when'
        return self.tasks[0].get_entry_point_name()

    def get_end_point_name(self) -> str:
        if len(self.always) > 0:
            return self.always[-1].get_end_point_name()
        return self.tasks[-1].get_end_point_name()

    def generateRelation(self, next:UMLStateBase) -> Iterator[str]:
        if len(self.when) > 0:
            #yield '%s' % self.when
            yield '%s --> %s : %s' % (self.name + '_when', self.tasks[0].get_entry_point_name(), ' and '.join(self.when))
            yield '%s --> %s : %s' % (self.get_entry_point_name(), next.get_entry_point_name(), 'skip')

        tasks = iter(self.tasks + self.always)
        current_task = tasks.__next__()
        for next_task in tasks:
            yield from current_task.generateRelation(next_task)
            current_task = next_task
        else:
            yield from current_task.generateRelation(next)

        if len(self.rescue) > 0:
            if len(self.always) > 0:
                rescue_tasks = iter(self.rescue + [self.always[0]])
            else:
                rescue_tasks = iter(self.rescue + [next])
            current_rescue_task = rescue_tasks.__next__()
            for next_rescue_task in rescue_tasks:
                yield from current_rescue_task.generateRelation(next_rescue_task)
                current_rescue_task = next_rescue_task

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
        self.pre_tasks = [UMLStateBlock(block) for block in play.pre_tasks]
        self.tasks = [UMLStateBlock(block) for block in play.tasks]
        self.roles = [UMLStateBlock(block) for role in play.roles if not role.from_include for block in role.get_task_blocks()]
        self.post_tasks = [UMLStateBlock(block) for block in play.post_tasks]

    def get_all_tasks(self) -> Iterator[UMLStateBase]:
        yield from self.pre_tasks
        yield from self.tasks
        yield from self.roles
        yield from self.post_tasks

    def get_all_relations(self) -> Iterator[UMLStateBase]:
        start_end = UMLStateStart()
        yield start_end
        yield from self.get_all_tasks()
        yield start_end

    def generate(self) -> Iterator[str]:
        yield from self.generateDefinition()
        yield from self.generateRelation()

    def generateDefinition(self, level:int=0) -> Iterator[str]:
        yield 'title %s' % self.play.get_name()
        for tasks in self.get_all_tasks():
            yield from tasks.generateDefinition(level)

    def generateRelation(self) -> Iterator[str]:
        current_state = None
        for next_state in self.get_all_relations():
            if current_state is None:
                current_state = next_state
                continue
            yield from current_state.generateRelation(next_state)
            current_state = next_state

    def get_entry_point_name(self) -> str:
        return 'play_' + self.id

    def get_end_point_name(self) -> str:
        return 'play_' + self.id

def playbook2PlantUML(playbook:str):
    dataloader = DataLoader()
    pb = Playbook.load(playbook, loader=dataloader)
    print('@startuml')

    for play in pb.get_plays():
        umlstateplay = UMLStatePlay(play)
        for line in umlstateplay.generate():
            print(line)

    print('@enduml')

def main(args):
    '''main'''
    playbook2PlantUML(args.PLAYBOOK)

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Ansible-Playbook to PlantUML')
    ap.add_argument('PLAYBOOK', help='playbook file')
    args = ap.parse_args()
    main(args)
