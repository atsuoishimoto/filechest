all: clean exe
.PHONY: all

clean:
	rm -rf dist build
exe:
	pyinstaller src/main.py --collect-all django_filechest --collect-all filechest --collect-all whitenoise
