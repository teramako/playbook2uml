#!env python
# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division, print_function, annotations)
from typing import Iterator, Optional, override
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

class UMLStateTask(UMLStateTaskBase):

    @override
    def generateDefinition(self, level:int=0) -> Iterator[str]:
        self.logger.debug(f'start {self}')
        prefix = indent * level
        if self.has_when:
            yield from self._generateWhenDefinition(level)

        yield f'{prefix}state "{self.task.get_name()}<hr>action: {self.task.action}" as {self.name}'

        if self.has_until:
            yield from self._generateUntilDefinition(level)

        self.logger.debug(f'end {self}')

    def _generateUntilDefinition(self, level:int=0) -> Iterator[str]:
        yield '%sstate %s <<choice>>' % (indent*level, self._end_point_name)
        yield '%snote right of %s' % (indent*level, self._end_point_name)
        yield '%suntil: %s' % (indent*(level+1), self.task.until)
        yield '%sretres: %s' % (indent*(level+1), self.task.retries)
        yield '%sdelay: %s (seconds)' % (indent*(level+1), self.task.delay)
        yield '%send note' % (indent*level)

    def _generateWhenDefinition(self, level:int=0) -> Iterator[str]:
        yield '%sstate %s <<choice>>' % (indent*level, self._entry_point_name)
        yield '%snote right of %s' % (indent*level, self._entry_point_name)
        note_indent = indent * (level+1)
        yield '%swhen' % note_indent
        for when in self.when:
            yield '%s - %s' % (note_indent, when)
        yield '%send note' % (indent*level)

    @override
    def generateRelation(self, next: Optional[UMLStateBase], level:int=0) -> Iterator[str]:
        self.logger.debug(f'start {self}')
        prefix = indent * level
        if next is not None:
            if self.has_when:
                yield '%s%s --> %s' % (prefix, self._entry_point_name, self.name)
                yield '%s%s --> %s' % (prefix, self._end_point_name, next.get_entry_point_name())
                yield '%s%s --> %s : %s' % (prefix, self._entry_point_name, next.get_entry_point_name(), 'skip')
            else:
                yield '%s%s --> %s' % (prefix, self._end_point_name, next.get_entry_point_name())

        yield from self._generateLoopRelation(level=level)

        if self.has_until:
            yield '%s%s --> %s' % (prefix, self.name, self._end_point_name)
            yield '%s%s --> %s : retry' % (prefix, self._end_point_name, self._entry_point_name)

        self.logger.debug(f'end {self}')

    def _generateLoopRelation(self, level:int=0) -> Iterator[str]:
        if self.task.loop is None:
            return
        prefix = indent * level
        loop_with = getattr(self.task, 'loop_with', None)
        loop_name = f'loop(with_{loop_with})' if loop_with else 'loop'
        # loops can either be a string (one-item loop) or a list
        loop_items = [loop_name]
        if isinstance(self.task.loop, list):
            for loop_item in self.task.loop:
                loop_items.append(f' - {loop_item}')
        else:
            loop_items.append(str(self.task.loop))
        yield '%s%s --> %s : %s' % (prefix, self.name, self._entry_point_name, '\\n'.join(loop_items))

class UMLStateBlock(UMLStateBlockBase):

    TASK_CLASS = UMLStateTask

    @override
    def generateDefinition(self, level:int=0) -> Iterator[str]:
        self.logger.debug(f'start {self}')
        is_explicit = self.block.name or self.has_always or self.has_rescue
        next_level = level
        prefix = indent * level
        if is_explicit:
            yield f'{prefix}{self.name} : {self.block.name}'
            yield f'{prefix}state {self.name} {{'
            next_level+=1

        for task in self.tasks:
            yield from task.generateDefinition(next_level)

        if is_explicit:
            yield from self._generateAlwaysDefinition(next_level)
            yield from self._generateRescueDefinition(next_level)
            yield f'{prefix}}}'

        self.logger.debug(f'end {self}')

    def _generateAlwaysDefinition(self, level:int=0) -> Iterator[str]:
        if not self.has_always:
            return
        prefix = indent * level
        yield f'{prefix}{self.name}_always : Always'
        yield f'{prefix}state {self.name}_always {{'
        for task in self.always:
            yield from task.generateDefinition(level + 1)
        yield f'{prefix}}}'

    def _generateRescueDefinition(self, level:int=0) -> Iterator[str]:
        if not self.has_rescue:
            return
        prefix = indent * level
        yield f'{prefix}{self.name}_rescue : Rescue'
        yield f'{prefix}state {self.name}_rescue {{'
        for task in self.rescue:
            yield from task.generateDefinition(level + 1)
        yield f'{prefix}}}'

class UMLStatePlay(UMLStatePlayBase):
    BLOCK_CLASS = UMLStateBlock

    @override
    def generateDefinition(self, level:int=0, only_role=False) -> Iterator[str]:
        self.logger.debug(f'start {self}')
        if not only_role:
            yield '%sstate "Play: %s" as %s {' % (indent*level, self.play.get_name(), self.name)
            level += 1

        for tasks in self.get_all_tasks():
            yield from tasks.generateDefinition(level)

        if not only_role:
            yield '%s}' % (indent*(level-1))

        self.logger.debug(f'end {self}')

    @override
    def generateRelation(self, next:Optional[UMLStateBase], level:int=0) -> Iterator[str]:
        self.logger.debug(f'start {self}')
        for current_state, next_state in pair_state_iter(*self.get_all_tasks(), next):
            yield from current_state.generateRelation(next_state, level=level)

        self.logger.debug(f'end {self}')

class UMLStatePlaybook(UMLStatePlaybookBase):

    PLAY_CLASS  = UMLStatePlay
    BLOCK_CLASS = UMLStateBlock
    TASK_CLASS  = UMLStateTask

    @override
    def generate(self) -> Iterator[str]:
        '''
        Generate Mermaid.js codes
        '''
        self.logger.info('START [Mermaid.js]')
        only_role = False
        yield 'stateDiagram-v2'
        if self.options:
            if self.options.left_to_right:
                self.logger.debug(f'set left-to-right-direction')
                yield f'{indent}direction LR'

            only_role = self.options.role != ''

        self.logger.info(f'START generate definitions (role-mode={only_role})')
        for umlplay in self.plays:
            yield from umlplay.generateDefinition(level=1, only_role=only_role)
        self.logger.info('END generate definitions')

        self.logger.info(f'START generate relations (role-mode={only_role})')
        start_end = UMLStateStart()
        for current_state, next_state in pair_state_iter(start_end, *self.plays, start_end):
            yield from current_state.generateRelation(next_state, level=1)
        self.logger.info('END generate relations')

        self.logger.info('END')
