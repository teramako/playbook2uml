#!env python
# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division, print_function, annotations)
from argparse import ArgumentParser
from playbook2uml.umlstate import UMLStatePlaybook

def main():
    '''main'''
    ap = ArgumentParser(description='Ansible-Playbook to PlantUML')
    ap.add_argument('PLAYBOOK', help='playbook file')
    ap.add_argument('-T', '--title', type=str, help='The title of the playbook')
    ap.add_argument('--theme', type=str, default=None, help='The theme')
    ap.add_argument('--left-to-right', action='store_true', help='left to right direction')
    args = ap.parse_args()

    umlplaybook = UMLStatePlaybook(args.PLAYBOOK, option=args)
    for line in umlplaybook.generate():
        print(line)

if __name__ == '__main__':
    main()
