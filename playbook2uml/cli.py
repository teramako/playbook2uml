#!env python
# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division, print_function, annotations)
from argparse import ArgumentParser
from playbook2uml.umlstate import UMLStatePlaybook
import os.path

def main():
    '''main'''
    ap = ArgumentParser(description='Ansible playbook/role to PlantuML', usage='''
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

    args = ap.parse_args()

    if args.role:
        args.BASE_DIR = args.PLAYBOOK
        if not os.path.isdir(args.BASE_DIR):
            ap.error('BASE_DIR must be a directory.')
    elif not os.path.isfile(args.PLAYBOOK):
        ap.error('PLAYBOOK must be a file.')

    umlplaybook = UMLStatePlaybook(args.PLAYBOOK, option=args)
    for line in umlplaybook.generate():
        print(line)

if __name__ == '__main__':
    main()
