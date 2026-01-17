package: clean collectstatic build
exe: package pyinstaller

.PHONY: package exe

clean:
	rm -rf dist build

collectstatic:
	uv run python -m manage collectstatic --noinput

build:
	uv build

pyinstaller:
	uv run pyinstaller src/main.py --collect-all django_filechest --collect-all filechest --collect-all whitenoise
