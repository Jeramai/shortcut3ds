IMAGE ?= devkitpro/devkitarm:latest

.PHONY: stub test
stub:
	docker run --rm -v "$(CURDIR)/stub:/stub" -w /stub $(IMAGE) make
	cp stub/stub.elf src/shortcut3ds/data/stub.elf

test:
	python3 -m pytest -q
