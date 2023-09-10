from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

import archie.database.database as db


@asynccontextmanager
async def lifespan(app: FastAPI):
    with db.connect():
        # with load_config() as _config:
        yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/channel/{id}")
def channel(id: str):
    return db.Channel.get(id, True)


def run():
    uvicorn.run(app, port=5000, log_level="info")
