#!env python
# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division, print_function, annotations)
from typing import ClassVar, Iterator, Optional
from playbook2uml.umlstate.base import (
    indent,
    logger,
    pair_state_iter,
    UMLStatePlaybookBase,
    UMLStatePlayBase,
    UMLStateBase,
    UMLStateTaskBase,
    UMLStateBlockBase,
    UMLStateStart
)
from ansible.utils.sentinel import Sentinel

class UMLStateTask(UMLStateTaskBase):
    ID : ClassVar[int] = 1

    def generateDefinition(self, level:int=0) -> Iterator[str]:
        self.logger.debug(f'start {self}')
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

        self.logger.debug(f'end {self}')

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
        self.logger.debug(f'start {self}')
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

        self.logger.debug(f'end {self}')

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

class UMLStateBlock(UMLStateBlockBase):
    ID = 1

    TASK_CLASS = UMLStateTask

    def generateDefinition(self, level:int=0) -> Iterator[str]:
        self.logger.debug(f'start {self}')
        is_explicit = self.block.name or self.has_always or self.has_rescue
        next_level = level
        prefix = indent * level
        if is_explicit:
            yield '%sstate "Block: %s" as %s {' % (prefix, self.block.name, self._name)
            next_level+=1

        for task in self.tasks:
            yield from task.generateDefinition(next_level)

        if is_explicit:
            yield from self._generateAlwaysDefinition(next_level)
            yield from self._generateRescueDefinition(next_level)
            yield '%s}' % prefix

        self.logger.debug(f'end {self}')
    
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
    
class UMLStatePlay(UMLStatePlayBase):
    ID = 1
    BLOCK_CLASS = UMLStateBlock

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
        self.logger.debug(f'start {self}')
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

        self.logger.debug(f'end {self}')

    def generateRelation(self, next_play:UMLStatePlay=None) -> Iterator[str]:
        self.logger.debug(f'start {self}')
        for current_state, next_state in pair_state_iter(*self.get_all_tasks(), next_play):
            yield from current_state.generateRelation(next_state)

        self.logger.debug(f'end {self}')

class UMLStatePlaybook(UMLStatePlaybookBase):

    PLAY_CLASS  = UMLStatePlay
    BLOCK_CLASS = UMLStateBlock
    TASK_CLASS  = UMLStateTask

    def generate(self) -> Iterator[str]:
        '''
        Generate PlantUML codes
        '''
        self.logger.info('START [PlantUML]')
        only_role = False
        yield '@startuml'
        if self.options:
            if title := self.options.title:
                self.logger.debug(f'set title "{title}"')
                yield 'title %s' % title
            if theme := self.options.theme:
                self.logger.debug(f'set theme "{theme}"')
                yield '!theme %s' % theme
            if self.options.left_to_right:
                self.logger.debug(f'set left-to-right-direction')
                yield 'left to right direction'

            only_role = self.options.role != ''

        self.logger.info(f'START generate definitions (role-mode={only_role})')
        for umlplay in self.plays:
            yield from umlplay.generateDefinition(only_role=only_role)
        self.logger.info('END generate definitions')

        self.logger.info(f'START generate relations (role-mode={only_role})')
        start_end = UMLStateStart()
        for current_state, next_state in pair_state_iter(start_end, *self.plays, start_end):
            yield from current_state.generateRelation(next_state)
        self.logger.info('END generate relations')

        yield '@enduml'
        self.logger.info('END')
