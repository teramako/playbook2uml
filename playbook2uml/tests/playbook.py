import unittest
import glob
import os.path
import playbook2uml.cli as cli
import playbook2uml.umlstate as umlstate

class Test_PlantUML_PLAYBOOK(unittest.TestCase):
    '''For PlantUML
    Compare between the generated results and the expects.
    '''
    BASE_DIR = 'test_playbook'
    TEST_CASES = []
    @classmethod
    def setUpClass(cls):
        '''
        Get all test playbook files and it's expected result files
        '''
        books = glob.glob(os.path.join(cls.BASE_DIR, '*.yml'))
        test_cases = []
        for book_file in books:
            base_name, _ = os.path.splitext(os.path.basename(book_file))
            expect_file = os.path.join(cls.BASE_DIR, 'expects', f'{base_name}.puml')
            if os.path.exists(expect_file):
                test_cases.append((book_file, expect_file))

        cls.TEST_CASES = test_cases

    def test_play(self):
        for case in self.TEST_CASES:
            with self.subTest(case):
                args = cli.parse_args([case[0]])
                book = umlstate.load(args)
                result_lines = [line for line in book.generate()]
                with open(case[1], 'r') as f:
                    expect_lines = f.read().strip().splitlines()

                self.assertListEqual(result_lines, expect_lines)

class Test_Mermaid_PLAYBOOK(unittest.TestCase):
    '''For Marmaid
    Compare between the generated results and the expects.
    '''
    BASE_DIR = 'test_playbook'
    TEST_CASES = []
    @classmethod
    def setUpClass(cls):
        '''
        Get all test playbook files and it's expected result files
        '''
        books = glob.glob(os.path.join(cls.BASE_DIR, '*.yml'))
        test_cases = []
        for book_file in books:
            base_name, _ = os.path.splitext(os.path.basename(book_file))
            expect_file = os.path.join(cls.BASE_DIR, 'expects', f'{base_name}.mmd')
            if os.path.exists(expect_file):
                test_cases.append((book_file, expect_file))

        cls.TEST_CASES = test_cases

    def test_play(self):
        for case in self.TEST_CASES:
            with self.subTest(case):
                args = cli.parse_args(['-t', 'mermaid', case[0]])
                book = umlstate.load(args)
                result_lines = [line for line in book.generate()]
                with open(case[1], 'r') as f:
                    expect_lines = f.read().strip().splitlines()

                self.assertListEqual(result_lines, expect_lines)
