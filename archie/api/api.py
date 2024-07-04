from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from .routes import router
import archie.database.database as db

DEBUG = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    with db.connect():
        # with load_config() as _config:
        yield


app = FastAPI(title="archie", version="0.0.1", lifespan=lifespan)

app.include_router(router)


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    error_msg = f"[API Error] {request.url} - {str(exc)}"
    if DEBUG:
        print(error_msg)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


@app.get("/channel/{id}")
def channel(id: str):
    print(id)
    return db.Channel.get(id, True)


def run():
    uvicorn.run("archie.api.api:app", port=5000, reload=DEBUG)
