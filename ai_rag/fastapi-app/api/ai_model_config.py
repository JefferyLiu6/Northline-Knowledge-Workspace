"""AI model configuration interface."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from common.result import Result
from common.auth import require_admin
from models import User
from service import ai_model_config_service

router = APIRouter(prefix="/aiModelConfig")


class AiModelConfigPayload(BaseModel):
    # Pydantic by default uses the field name at the beginning of mdel_ as a prefix to keep, warning that it will not be possible to use it.
    # Model_type and model_name of this table are business fields, turn off this protection here
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int | None = None
    name: str | None = None
    model_type: str | None = None
    provider: str | None = None
    protocol: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model_name: str | None = None
    dimension: int | None = None
    enabled: str | None = None
    remark: str | None = None


@router.post("/add")
async def add(payload: AiModelConfigPayload, _: User = Depends(require_admin)):
    await ai_model_config_service.add(payload.model_dump(exclude_unset=True))
    return Result.success()


@router.put("/update")
async def update(payload: AiModelConfigPayload, _: User = Depends(require_admin)):
    await ai_model_config_service.update(payload.id, payload.model_dump(exclude_unset=True))
    return Result.success()


@router.delete("/delete/{config_id}")
async def delete(config_id: int, _: User = Depends(require_admin)):
    await ai_model_config_service.delete(config_id)
    return Result.success()


@router.post("/test/{config_id}")
async def test(config_id: int, _: User = Depends(require_admin)):
    """Connectivity test, using the configuration in the library to call the model once."""
    return Result.success(await ai_model_config_service.test_connection(config_id))


@router.get("/selectAll")
async def select_all(model_type: str = "", _: User = Depends(require_admin)):
    return Result.success(await ai_model_config_service.select_all(model_type))


@router.get("/selectPage")
async def select_page(
    name: str = "",
    model_type: str = "",
    page_num: int = 1,
    page_size: int = 10,
    _: User = Depends(require_admin),
):
    return Result.success(
        await ai_model_config_service.select_page(name, model_type, page_num, page_size)
    )
