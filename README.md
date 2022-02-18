# playbook2uml
Ansible-playbook to PlantUML

## Usage

The PlantUML code is out to stdout.
```console
$ python playbook2uml.py path/to/playbook.yml
@startuml
title Hello playbook2uml
state "Hello playbook2uml" as task_1
task_1 : Action **debug**
task_1 : | msg | Hello ansible playbook to UML |
[*] --> task_1
task_1 --> [*]
@enduml
```

You maybe pipe to a PlantUML server with `curl`.
```sh
python playbook2uml.py path/to/playbook.yml | curl --data-binary @- http://plantuml-server.example.com/svg/ -o - > path/to/foo.svg
```

## Output

![plantuml svg](docs/img/sample_1.svg)
