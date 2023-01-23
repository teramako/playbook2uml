.PHONY: install
install: ## Install playbook2uml package
	pip install .

.PHONY: build
build: ## Create package to "dist" directory
	python -m setup sdist

.PHONY: clean
clean: ## Remove "dist" directory and egg-info
	rm -rv dist playbook2uml.egg-info

.PHONY: help
help: ## This help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
