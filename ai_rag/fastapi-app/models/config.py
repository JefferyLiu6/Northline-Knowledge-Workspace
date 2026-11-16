from tortoise import fields
from tortoise.models import Model


class AiModelConfig(Model):
    """Stored configuration for chat, embeddings, and reranking.

    Local deployments use Ollama. The protocol selects the appropriate client.
    """

    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=255)
    # Dialogue Model / Vector Model / Reorder Model
    model_type = fields.CharField(max_length=50)
    provider = fields.CharField(max_length=100, null=True)
    # Interface protocol used by the model client
    protocol = fields.CharField(max_length=50, default="OpenAI compatible")
    base_url = fields.CharField(max_length=500, null=True)
    api_key = fields.CharField(max_length=500, null=True)
    model_name = fields.CharField(max_length=255, null=True)
    # Only vector models need to match the dimensions of PGVector's table
    dimension = fields.IntField(null=True)
    # Only one enabler is allowed under the same type, code is "type + enabled" configuration
    enabled = fields.CharField(max_length=10, default="Yes")
    remark = fields.CharField(max_length=500, null=True)
    create_time = fields.DatetimeField(auto_now_add=True)
    update_time = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "ai_model_config"


class PromptTemplate(Model):
    """Prompt Template Table.

    All prompts sent to the model are stored here. Changing the prompt does not require changing the code or restarting the service.
    Code retrieves the prompt by code. If it is not found or disabled, it directly reports an error. No hard-coded prompts are used as fallback.
    """

    id = fields.IntField(primary_key=True)
    # Template Encoding. The code uses it to take the template, which is the only one in the whole table.
    code = fields.CharField(max_length=100, unique=True)
    name = fields.CharField(max_length=255)
    scene = fields.CharField(max_length=100, null=True)
    # Template contents, with large brackets, for example {context}, {question}
    content = fields.TextField()
    # List of variables, comma separated, show the manager what variables are required for this template
    variables = fields.CharField(max_length=500, null=True)
    enabled = fields.CharField(max_length=10, default="Yes")
    remark = fields.CharField(max_length=500, null=True)
    create_time = fields.DatetimeField(auto_now_add=True)
    update_time = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "prompt_template"


class FunctionTool(Model):
    """Function Tool Registry.

    The tools available to the Agent are determined by this table, not by how many tools are registered in the code.
    The enabled field is a true switch: after disabling, the Agent will not be able to access this tool on its next execution.
    """

    id = fields.IntField(primary_key=True)
    # Must match the name of ai/tools. py to achieve the function, which is not matched by an unusable tool
    tool_code = fields.CharField(max_length=100, unique=True)
    tool_name = fields.CharField(max_length=255)
    # This description will be sent to the model as it is, which will determine when this tool should be adjusted.
    description = fields.CharField(max_length=1000, null=True)
    input_schema = fields.TextField(null=True)
    enabled = fields.CharField(max_length=10, default="Yes")
    sort = fields.IntField(default=0)
    create_time = fields.DatetimeField(auto_now_add=True)
    update_time = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "function_tool"
