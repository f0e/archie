import uvicorn

# Importing app here makes the syntax cleaner as it will be picked up by refactors
from archie.api.api import app  # noqa


def start():
    uvicorn.run("archie.debug_server:app", host="0.0.0.0", port=5000, reload=True)
