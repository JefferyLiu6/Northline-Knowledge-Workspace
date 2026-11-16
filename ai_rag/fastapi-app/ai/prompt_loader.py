"""Prompt loading.

all prompts sent to the model are read from the prompt_template table, no prompts are hard-coded in the code.
perform three checks when retrieving the template: existence, activation, and non-empty content, if any condition is not met, an explicit prompt is issued,
do not use hard-coded prompts as a fallback—this would make administrators think that changing the template takes effect, but in reality, the code's version is still being used.
"""

import re

from common.exception_handler import CustomException
from models import PromptTemplate

# Prompt variables use the form {variable_name}.
VARIABLE_PATTERN = re.compile(r"\{(\w+)\}")


async def load(code: str) -> str:
    """retrieve the template content by encoding."""
    template = await PromptTemplate.get_or_none(code=code)
    if template is None:
        raise CustomException(f"Cannot Find Prompt Template with Code {code} , Please Add It in Prompt Template First")
    if template.enabled != "Yes":
        raise CustomException(f"Prompt Template {code} Is Disabled, Please Enable First")
    if not template.content or not template.content.strip():
        raise CustomException(f"Prompt Template {code} Content Is Empty, Please Fill It First")
    return template.content


async def render(code: str, **values) -> str:
    """retrieve the template and fill in the variables.

    variables appearing in the template but not passed will be blocked, preventing placeholders like {context} from being sent to the model as-is.
    """
    content = await load(code)
    required = set(VARIABLE_PATTERN.findall(content))
    missing = required - set(values.keys())
    if missing:
        raise CustomException(f"Prompt Template {code} is missing the following variables: {', '.join(sorted(missing))}")
    # Replace only the variables actually used in the template, multiple values ignored
    result = content
    for name in required:
        result = result.replace("{" + name + "}", str(values[name]))
    return result


def extract_variables(content: str | None) -> str:
    """extract the variable list from the template content, separated by commas, and automatically refill it into the variables column upon saving."""
    if not content:
        return ""
    # Subject. Fromkeys, keep the order of appearance while it's heavy, and displaying the same sequence as in the template on the page
    names = list(dict.fromkeys(VARIABLE_PATTERN.findall(content)))
    return ",".join(names)
