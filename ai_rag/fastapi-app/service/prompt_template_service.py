"""Prompt template manages business logic."""

from typing import List

from ai import prompt_loader
from common.exception_handler import CustomException
from common.result import PageInfo
from models import PromptTemplate


def template_dict(template: PromptTemplate) -> dict:
    return {
        "id": template.id,
        "code": template.code,
        "name": template.name,
        "scene": template.scene,
        "content": template.content,
        "variables": template.variables,
        "enabled": template.enabled,
        "remark": template.remark,
        "create_time": template.create_time,
        "update_time": template.update_time,
    }


def _validate(payload: dict) -> None:
    if not payload.get("code"):
        raise CustomException("Please enter the template encoding.")
    if not payload.get("name"):
        raise CustomException("Please enter a template name")
    content = payload.get("content")
    if not content or not content.strip():
        raise CustomException("Please enter the template contents")


async def add(payload: dict) -> None:
    _validate(payload)
    # The code press code to take the template. Repeated encoding makes it uncertain which one is taken.
    if await PromptTemplate.get_or_none(code=payload["code"]):
        raise CustomException("Template Encoding Repeated")
    await PromptTemplate.create(
        code=payload["code"],
        name=payload["name"],
        scene=payload.get("scene"),
        content=payload["content"],
        # The list of variables is automatically extracted from the content, so managers are not allowed to maintain it manually and avoid actual mismatches
        variables=prompt_loader.extract_variables(payload["content"]),
        enabled=payload.get("enabled") or "Yes",
        remark=payload.get("remark"),
    )


async def update(template_id: int | None, payload: dict) -> None:
    if template_id is None:
        raise CustomException("Template ID cannot be empty")
    template = await PromptTemplate.get_or_none(id=template_id)
    if template is None:
        raise CustomException("Prompt template not found")
    _validate(payload)
    if await PromptTemplate.filter(code=payload["code"]).exclude(id=template_id).exists():
        raise CustomException("Template Encoding Repeated")
    await PromptTemplate.filter(id=template_id).update(
        code=payload["code"],
        name=payload["name"],
        scene=payload.get("scene"),
        content=payload["content"],
        # The variable may have changed with the content, and then we'll do it again.
        variables=prompt_loader.extract_variables(payload["content"]),
        enabled=payload.get("enabled") or "Yes",
        remark=payload.get("remark"),
    )


async def delete(template_id: int) -> None:
    template = await PromptTemplate.get_or_none(id=template_id)
    if template is None:
        raise CustomException("Prompt template not found")
    await PromptTemplate.filter(id=template_id).delete()


async def preview(template_id: int, values: dict) -> str:
    """Rewrite the template using the entered variable value to see what is actually sent to the model."""
    template = await PromptTemplate.get_or_none(id=template_id)
    if template is None:
        raise CustomException("Prompt template not found")
    return await prompt_loader.render(template.code, **values)


async def select_all() -> List[dict]:
    templates = await PromptTemplate.all().order_by("id")
    return [template_dict(item) for item in templates]


async def select_page(keyword: str = "", scene: str = "", page_num: int = 1, page_size: int = 10) -> PageInfo:
    # Keyword matches a name, and the last input box on the page is enough.
    query = PromptTemplate.filter(name__contains=keyword)
    if scene:
        query = query.filter(scene=scene)
    templates = await query.order_by("id").offset((page_num - 1) * page_size).limit(page_size)
    total = await query.count()
    return PageInfo(total=total, list=[template_dict(item) for item in templates])
