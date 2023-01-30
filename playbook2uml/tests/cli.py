import unittest
import playbook2uml.cli as cli
import playbook2uml.umlstate as umlstate

class Test_Parameter(unittest.TestCase):
    PLAYBOOK = 'test_playbook/book_1.yml'
    def test_args_DEFAULT(self):
        args = cli.parse_args([self.PLAYBOOK])
        test_cases = (
            ('PLAYBOOK', self.PLAYBOOK),
            ('type', 'plantuml'),
            ('theme', None),
            ('left_to_right', False),
            ('verbose', 0),
            ('role', '')
        )
        for case in test_cases:
            with self.subTest(case):
                self.assertEqual(getattr(args, case[0]), case[1])

    def test_args_TYPE(self):
        diagramType = 'mermaid'
        test_cases = (
            ('--type', diagramType),
            ('-t', diagramType)
        )
        for case in test_cases:
            with self.subTest(case):
                args = cli.parse_args([case[0], diagramType, self.PLAYBOOK])
                self.assertEqual(args.type, case[1])

    def test_args_TITLE(self):
        title = 'TITLE 1'
        test_cases = (
            ('--title', title),
            ('-T', title)
        )
        for case in test_cases:
            with self.subTest(case):
                args = cli.parse_args([case[0], title, self.PLAYBOOK])
                self.assertEqual(args.title, case[1])

        with self.subTest('title in UML'):
            book = umlstate.UMLStatePlaybook(args.PLAYBOOK, option=args)
            uml_lines = [line for line in book.generate()]
            self.assertIn(f'title {title}', uml_lines)

    def test_args_THEME(self):
        theme = 'THEME1'
        args = cli.parse_args(['--theme', theme, self.PLAYBOOK])

        with self.subTest(('--theme', theme)):
            self.assertEqual(args.theme, theme)

        with self.subTest('!theme in UML'):
            book = umlstate.UMLStatePlaybook(args.PLAYBOOK, option=args)
            uml_lines = [line for line in book.generate()]
            self.assertIn(f'!theme {theme}', uml_lines)

    def test_args_LEFT_TO_RIGHT(self):
        args = cli.parse_args(['--left-to-right', self.PLAYBOOK])

        with self.subTest(('--left-to-right', True)):
            self.assertEqual(args.left_to_right, True)

        with self.subTest('"left to right direction" in UML'):
            book = umlstate.UMLStatePlaybook(args.PLAYBOOK, option=args)
            uml_lines = [line for line in book.generate()]
            self.assertIn('left to right direction', uml_lines)
