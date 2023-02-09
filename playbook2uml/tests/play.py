import unittest
import re
from ansible.playbook.play import Play
from ansible.playbook import Playbook
from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
import playbook2uml.umlstate.plantuml as plantuml

class Test_PlantUML_Play(unittest.TestCase):
    '''Test PlantUML Play definitions
    Test outputs of 'gather_facts', 'strategy' and 'serial' 
    '''
    def create_play(self, play_data: dict):
        dataloader = DataLoader()
        variable_manager = VariableManager(loader=dataloader)
        pb = Playbook(loader=dataloader)
        play = Play.load(play_data, variable_manager=variable_manager, loader=pb._loader, vars=None)

        plantuml.UMLStatePlay.ID = 1
        return plantuml.UMLStatePlay(play)

    def test_defaults(self):
        '''
        Test implicit values of 'gather_facts', 'strategy' and 'serial',
        those should not be outputed
        '''
        umlplay = self.create_play({
            'hosts': 'localhost',
            'tasks': [ { 'ping': None } ]
        })
        play_def = tuple(umlplay.generateDefinition())
        with self.subTest('not in gather_facts'):
            for line in play_def:
                self.assertNotIn(' | gather_facts | ', line)

        with self.subTest('not in stragety'):
            for line in play_def:
                self.assertNotIn(' | strategy | ', line)

        with self.subTest('not in serial'):
            for line in play_def:
                self.assertNotIn(' | serial | ', line)

    def test_gather_facts(self):
        '''
        Test explicit value of 'gather_facts', this should be outputed
        '''
        umlplay = self.create_play({
            'hosts': 'localhost',
            'gather_facts': False,
            'tasks': [ { 'ping': None } ]
        })
        play_def = tuple(umlplay.generateDefinition())
        self.assertIn('    play_1 : | gather_facts | False |', play_def)

    def test_strategy(self):
        '''
        Test explicit value of 'strategy', this should be outputed
        '''
        umlplay = self.create_play({
            'hosts': 'localhost',
            'strategy': 'linear',
            'tasks': [ { 'ping': None } ]
        })
        play_def = tuple(umlplay.generateDefinition())
        self.assertIn('    play_1 : | strategy | linear |', play_def)

    def test_serial(self):
        '''
        Test explicit value of 'serial', this should be outputed
        '''
        umlplay = self.create_play({
            'hosts': 'host1, host2',
            'serial': 2,
            'tasks': [ { 'ping': None } ]
        })
        play_def = tuple(umlplay.generateDefinition())
        self.assertIn('    play_1 : | serial | 2 |', play_def)
