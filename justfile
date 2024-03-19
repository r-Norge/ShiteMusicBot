env_name := "venv"
python := "./" + env_name+'/bin/python3'

default:
    @just --list

# Make a new virtual environment
[private]
make_venv:
    python3 -m venv {{env_name}}
    {{python}} -m pip install --upgrade pip
    {{python}} -m pip install -r requirements.txt

# Make the environment if it does not exit
[private]
@venv:
  [ -d {{env_name}} ] || just make_venv

# Run the bot
run: venv
    {{python}} bot.py

# Run with debug logging enabled
debug: venv
    {{python}} bot.py --debug

clean:
    rm -rf {{env_name}}
# Lint with flake8

# Run ruff
lint: venv
    {{python}} -m ruff check . --fix

# Run tests
test: venv
    {{python}} -m pytest

# Run lints and test
pre_commit: venv
    just lint
    just test

