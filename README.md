# playbook2uml
Ansible-playbook to PlantUML

## Usage

The PlantUML code is out to stdout.
```console
$ playbook2uml path/to/playbook.yml --title "hello_world.yml"
@startuml
title hello_world.yml
state "= Play: Hello playbook2uml" as play_1 {
    play_1 : | hosts | localhost |
    play_1 : | gather_facts | False |
    state "== Hello playbook2uml" as task_1
    task_1 : Action **debug**
    task_1 : | msg | Hello ansible playbook to UML |
}
[*] --> task_1
task_1 --> [*]
@enduml
```

You maybe pipe to a PlantUML server with `curl`.
```sh
playbook2uml path/to/playbook.yml --title "Sample 1" | \
    curl --data-binary @- http://plantuml-server.example.com/svg/ -o - > path/to/foo.svg
```

## Output

![plantuml svg](docs/img/sample_1.svg)

## Requirements

- `ansible` >= 2.9

## Install

```sh
pip install git+https://github.com/teramako/playbook2uml
```
