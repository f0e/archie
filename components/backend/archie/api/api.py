from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routes import router

DEBUG = True
PORT = 5000
CORS_ORIGINS = ["*"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # with load_config() as _config:
    yield


app = FastAPI(title="archie", version="0.0.1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


def run():
    uvicorn.run("archie.api.api:app", port=PORT, reload=DEBUG)
