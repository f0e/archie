from fastapi import APIRouter, HTTPException

from archie.services import services
from archie.services.base_service import BaseService

router = APIRouter()


@router.get("/account/{service_name}/{id}")
async def get_channel(service_name: str, id: str):
    if service_name not in services:
        raise HTTPException(
            status_code=404, detail=f"Service '{service_name}' not supported. Supported services: {', '.join(services.keys())}"
        )

    service: BaseService = services[service_name]
    test = service.get_account_info(id)

    return {"hi": test}
