from ubuntu:12.04
maintainer Nick Stinemates

run apt-get install -y python-setuptools
run easy_install pip
volume /logs

add . /bot
workdir /bot

run pip install -r /bot/requirements.txt

cmd ["python", "bin/bender"]
