#!env python
# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division, print_function, annotations)
from argparse import ArgumentParser
from playbook2uml.umlstate import UMLStatePlaybook
import sys
import os.path

def parse_args(args: list[str]):
    ap = ArgumentParser(prog='playbook2uml' ,description='Ansible playbook/role to PlantUML', usage='''
    %(prog)s [options] PLAYBOOK
    %(prog)s [options] -R ROLE_NAME [BASE_DIR]
    ''')
    ap.add_argument('-T', '--title', type=str, help='The title of the playbook/role')
    ap.add_argument('--theme', type=str, default=None, help='PlantUML theme')
    ap.add_argument('--left-to-right', action='store_true', help='left to right direction')

    playbook_group = ap.add_argument_group('Playbook', 'Generate a graph of the playbook')
    playbook_group.add_argument('PLAYBOOK', nargs='?', default='.', type=str, help='playbook file')

    role_group = ap.add_argument_group('Role', 'Generate a graph of the role only')
    role_group.add_argument('-R', '--role', type=str, help='The role name')
    role_group.add_argument('BASE_DIR', nargs='?', help='The base directory.[default=current directory]')

    option = ap.parse_args(args)

    if option.role:
        option.BASE_DIR = option.PLAYBOOK
        if not os.path.isdir(option.BASE_DIR):
            ap.error('BASE_DIR must be a directory.')
    elif not os.path.isfile(option.PLAYBOOK):
        ap.error('PLAYBOOK must be a file.')

    return option

def main():
    '''main'''
    option = parse_args(sys.argv[1:])

    umlplaybook = UMLStatePlaybook(option.PLAYBOOK, option=option)
    for line in umlplaybook.generate():
        print(line)

if __name__ == '__main__':
    main()
