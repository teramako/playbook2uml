from setuptools import setup, find_packages

setup(
    name='playbook2uml',
    version='0.3.1',
    description='Create a PlantUML or Mermaid.js State Diagram from Ansible-Playbook/role',
    author='teramako',
    author_email='teramako@gmail.com',
    url='https://github.com/teramako/playbook2uml',
    license='MIT',
    packages=find_packages(),
    entry_points={
        'console_scripts': ['playbook2uml = playbook2uml.cli:main']
    },
    requires=['ansible'],
    classifiers=[
        'Programing Langumage :: Python :: 3.8'
    ],
)
