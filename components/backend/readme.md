## requirements
- mongodb

## dev setup
- install pipx
    - (windows) `scoop install pipx`
    - `pipx ensurepath`
    - `pipx install poetry`
- set up poetry
    (optional i think, but i use it and it's good)
    - `poetry config virtualenvs.in-project true`
    - `poetry install`
    - `poetry shell` (to enter venv if not already in it)
    - `poetry run archie`
    - from then you can use `poetry add` etc to manage packages
- set up vscode
    - may have to set interpreter to the venv if it isn't detected

## usage
### example
- `archie create music`
- `archie add-entity music [name]`
- `archie add-entity-account music [name] soundcloud [account url]`
- `archie run `

you can also just edit
- (windows) `~/AppData/Roaming/archie/config.yaml`
- (mac) `~/Library/Application Support/archie/config.yaml`

once it exists instead of using the cli to manage your config
