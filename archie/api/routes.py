from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

router = APIRouter()


class ChannelResponse(BaseModel):
    test: str


@router.get("/channel", response_model=ChannelResponse)
async def get_channel(
    id: str = Query(..., description="Channel ID"),
):
    return ChannelResponse(test="hello")
