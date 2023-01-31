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

class UMLStateTask(UMLStateTaskBase):
    ID : ClassVar[int] = 1

    def generateDefinition(self, level:int=0) -> Iterator[str]:
        self.logger.debug(f'start {self}')
        prefix = indent * level
        if self.has_when:
            yield from self._generateWhenDefinition(level)

        yield f'{prefix}state "{self.task.get_name()}<hr>action: {self.task.action}" as {self._name}'

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
        yield '%swhen' % note_indent
        for when in self.when:
            yield '%s - %s' % (note_indent, when)
        yield '%send note' % (indent*level)

    def generateRelation(self, next: Optional[UMLStateBase] = None, level:int=0) -> Iterator[str]:
        self.logger.debug(f'start {self}')
        prefix = indent * level
        if self.has_when:
            yield '%s%s --> %s' % (prefix, self._entry_point_name, self._name)
            yield '%s%s --> %s' % (prefix, self._end_point_name, next.get_entry_point_name())
            yield '%s%s --> %s : %s' % (prefix, self._entry_point_name, next.get_entry_point_name(), 'skip')
        else:
            yield '%s%s --> %s' % (prefix, self._end_point_name, next.get_entry_point_name())

        yield from self._generateLoopRelation(level=level)

        if self.has_until:
            yield '%s%s --> %s' % (prefix, self._name, self._end_point_name)
            yield '%s%s --> %s : retry' % (prefix, self._end_point_name, self._entry_point_name)

        self.logger.debug(f'end {self}')

    def _generateLoopRelation(self, level:int=0) -> Iterator[str]:
        if self.task.loop is None:
            return
        prefix = indent * level
        loop_name = ('loop(with_%s)' % self.task.loop_with) if self.task.loop_with else 'loop'
        # loops can either be a string (one-item loop) or a list
        loop_items = [loop_name]
        if isinstance(self.task.loop, list):
            for loop_item in self.task.loop:
                loop_items.append(f' - {loop_item}')
        else:
            loop_items.append(self.task.loop)
        yield '%s%s --> %s : %s' % (prefix, self._name, self._entry_point_name, '\\n'.join(loop_items))

class UMLStateBlock(UMLStateBlockBase):
    ID = 1

    TASK_CLASS = UMLStateTask

    def generateDefinition(self, level:int=0) -> Iterator[str]:
        self.logger.debug(f'start {self}')
        is_explicit = self.block.name or self.has_always or self.has_rescue
        next_level = level
        prefix = indent * level
        if is_explicit:
            yield f'{prefix}{self._name} : {self.block.name}'
            yield f'{prefix}state {self._name} {{'
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
        yield f'{prefix}{self._name}_always : Always'
        yield f'{prefix}state {self._name}_always {{'
        for task in self.always:
            yield from task.generateDefinition(level + 1)
        yield f'{prefix}}}'

    def _generateRescueDefinition(self, level:int=0) -> Iterator[str]:
        if not self.has_rescue:
            return
        prefix = indent * level
        yield f'{prefix}{self._name}_rescue : Rescue'
        yield f'{prefix}state {self._name}_rescue {{'
        for task in self.rescue:
            yield from task.generateDefinition(level + 1)
        yield f'{prefix}}}'

class UMLStatePlay(UMLStatePlayBase):
    ID = 1
    BLOCK_CLASS = UMLStateBlock

    def generateDefinition(self, level:int=0, only_role=False) -> Iterator[str]:
        self.logger.debug(f'start {self}')
        if not only_role:
            yield '%sstate "Play: %s" as %s {' % (indent*level, self.play.get_name(), self._name)
            level += 1

        for tasks in self.get_all_tasks():
            yield from tasks.generateDefinition(level)

        if not only_role:
            yield '%s}' % (indent*(level-1))

        self.logger.debug(f'end {self}')

    def generateRelation(self, next_play:UMLStatePlay=None, level=0) -> Iterator[str]:
        self.logger.debug(f'start {self}')
        for current_state, next_state in pair_state_iter(*self.get_all_tasks(), next_play):
            yield from current_state.generateRelation(next_state, level=level)

        self.logger.debug(f'end {self}')

class UMLStatePlaybook(UMLStatePlaybookBase):

    PLAY_CLASS  = UMLStatePlay
    BLOCK_CLASS = UMLStateBlock
    TASK_CLASS  = UMLStateTask

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
