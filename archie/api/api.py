from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .routes import router

DEBUG = True


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    return "Hi"


def run():
    uvicorn.run("archie.api.api:app", port=5000, reload=DEBUG)
