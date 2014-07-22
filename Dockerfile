from python:2.7
maintainer Sam Alba <sam@docker.com>

add . /code
workdir /code

run curl https://bootstrap.pypa.io/get-pip.py | python
run pip install -r requirements.txt

env PYTHONUNBUFFERED true

cmd ["bin/bender"]
