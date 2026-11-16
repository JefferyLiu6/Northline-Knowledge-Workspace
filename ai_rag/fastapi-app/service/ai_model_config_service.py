"""Business logic for AI model configuration management."""

from typing import List

from ai import model_factory
from common.exception_handler import CustomException
from common.result import PageInfo
from models import AiModelConfig, KnowledgeBase

MODEL_TYPES = {model_factory.CHAT, model_factory.EMBEDDING, model_factory.RERANK}
PROTOCOLS = {"OpenAI compatible", "Native DashScope", model_factory.OLLAMA_RERANK}


def config_dict(config: AiModelConfig, mask_key: bool = True) -> dict:
    return {
        "id": config.id,
        "name": config.name,
        "model_type": config.model_type,
        "provider": config.provider,
        "protocol": config.protocol,
        "base_url": config.base_url,
        # List page displays only the header end of the key and avoids the entire set of keys appearing on the page and browser cache
        "api_key": _mask(config.api_key) if mask_key else config.api_key,
        "model_name": config.model_name,
        "dimension": config.dimension,
        "enabled": config.enabled,
        "remark": config.remark,
        "create_time": config.create_time,
        "update_time": config.update_time,
    }


def _mask(api_key: str | None) -> str:
    """Sensitive key desensitization, retaining only the first 4 and last 4 digits."""
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return api_key[:4] + "*" * 8 + api_key[-4:]


def _validate(payload: dict) -> None:
    if not payload.get("name"):
        raise CustomException("Please enter the configuration name")
    if payload.get("model_type") not in MODEL_TYPES:
        raise CustomException("Model type parameter error")
    if payload.get("protocol") not in PROTOCOLS:
        raise CustomException("Interface protocol parameter error")
    if payload["protocol"] == model_factory.OLLAMA_RERANK and payload["model_type"] != model_factory.RERANK:
        raise CustomException("Ollama chat reranking requires the Reranking model type")
    if not payload.get("base_url"):
        raise CustomException("Please enter the interface address")
    if not payload.get("model_name"):
        raise CustomException("Please enter the model name")
    # Vector(N) for vector dimensions to determine PGVecor table, and vector models must be filled in
    if payload.get("model_type") == model_factory.EMBEDDING and not payload.get("dimension"):
        raise CustomException("Vector models must specify the vector dimension")


async def _clear_other_enabled(model_type: str, keep_id: int | None = None) -> None:
    """Only one enabled configuration is allowed under the same type; disable the others."""
    query = AiModelConfig.filter(model_type=model_type, enabled="Yes")
    if keep_id is not None:
        query = query.exclude(id=keep_id)
    await query.update(enabled="No")


async def add(payload: dict) -> None:
    _validate(payload)
    if await AiModelConfig.get_or_none(name=payload["name"]):
        raise CustomException("Duplicate configuration name")
    enabled = payload.get("enabled") or "No"
    if enabled == "Yes":
        await _clear_other_enabled(payload["model_type"])
    await AiModelConfig.create(
        name=payload["name"],
        model_type=payload["model_type"],
        provider=payload.get("provider"),
        protocol=payload["protocol"],
        base_url=payload["base_url"],
        api_key=payload.get("api_key"),
        model_name=payload["model_name"],
        # Only vector models need dimensions, other types of space stored
        dimension=payload.get("dimension") if payload["model_type"] == model_factory.EMBEDDING else None,
        enabled=enabled,
        remark=payload.get("remark"),
    )


async def update(config_id: int | None, payload: dict) -> None:
    if config_id is None:
        raise CustomException("Configuration ID cannot be empty")
    config = await AiModelConfig.get_or_none(id=config_id)
    if config is None:
        raise CustomException("No model configuration found")
    _validate(payload)
    if await KnowledgeBase.filter(embedding_model_id=config_id).exists():
        if any(payload.get(key) != getattr(config, key) for key in ("model_type", "model_name", "base_url", "dimension", "protocol")):
            raise CustomException("Clear bound knowledge base embeddings before changing the embedding model")
    if await AiModelConfig.filter(name=payload["name"]).exclude(id=config_id).exists():
        raise CustomException("Duplicate configuration name")
    enabled = payload.get("enabled") or "No"
    if enabled == "Yes":
        await _clear_other_enabled(payload["model_type"], keep_id=config_id)
    api_key = payload.get("api_key")
    update_data = {
        "name": payload["name"],
        "model_type": payload["model_type"],
        "provider": payload.get("provider"),
        "protocol": payload["protocol"],
        "base_url": payload["base_url"],
        "model_name": payload["model_name"],
        "dimension": payload.get("dimension") if payload["model_type"] == model_factory.EMBEDDING else None,
        "enabled": enabled,
        "remark": payload.get("remark"),
    }
    # The key on the page is off-the-shelf, and you cannot overwrite the real key without re-entering it.
    if api_key and "*" not in api_key:
        update_data["api_key"] = api_key
    await AiModelConfig.filter(id=config_id).update(**update_data)


async def delete(config_id: int) -> None:
    config = await AiModelConfig.get_or_none(id=config_id)
    if config is None:
        raise CustomException("No model configuration found")
    # Enabled configurations are being asked questions and answered and used to quantify the link, deleting them would make the function directly unavailable
    if config.enabled == "Yes":
        raise CustomException("Enabled configurations cannot be deleted; please enable another configuration of the same type first")
    if await KnowledgeBase.filter(embedding_model_id=config_id).exists():
        raise CustomException("Clear bound knowledge base embeddings before deleting this model")
    await AiModelConfig.filter(id=config_id).delete()


async def test_connection(config_id: int) -> str:
    """Connectivity test, use the saved configuration in the database to call the model once."""
    config = await AiModelConfig.get_or_none(id=config_id)
    if config is None:
        raise CustomException("No model configuration found")
    return await model_factory.test_connection(config)


async def select_all(model_type: str = "") -> List[dict]:
    query = AiModelConfig.all()
    if model_type:
        query = query.filter(model_type=model_type)
    configs = await query.order_by("model_type", "-enabled", "id")
    return [config_dict(config) for config in configs]


async def select_page(name: str = "", model_type: str = "", page_num: int = 1, page_size: int = 10) -> PageInfo:
    query = AiModelConfig.filter(name__contains=name)
    if model_type:
        query = query.filter(model_type=model_type)
    configs = await query.order_by("model_type", "id").offset((page_num - 1) * page_size).limit(page_size)
    total = await query.count()
    return PageInfo(total=total, list=[config_dict(config) for config in configs])
