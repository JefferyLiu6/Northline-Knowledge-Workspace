"""AI model configuration is tested for interface with Prompt templates.

API Key, which only covers failed paths when not filled in.
The successful path after the key is filled out is manually verified on the page.
"""

CONFIG_NAME = "Test model configuration -- module test exclusively"
TEMPLATE_CODE = "TEST_TEMPLATE_UNIT"


def _cleanup_config(client, admin_headers):
    page = client.get(
        "/aiModelConfig/selectPage",
        params={"name": CONFIG_NAME, "page_num": 1, "page_size": 10},
        headers=admin_headers,
    ).json()
    for item in page["data"]["list"]:
        if item["name"] == CONFIG_NAME:
            client.delete(f"/aiModelConfig/delete/{item['id']}", headers=admin_headers)


def _find_config(client, admin_headers):
    page = client.get(
        "/aiModelConfig/selectPage",
        params={"name": CONFIG_NAME, "page_num": 1, "page_size": 10},
        headers=admin_headers,
    ).json()
    for item in page["data"]["list"]:
        if item["name"] == CONFIG_NAME:
            return item
    return None


def _cleanup_template(client, admin_headers):
    page = client.get(
        "/promptTemplate/selectAll", headers=admin_headers
    ).json()
    for item in page["data"]:
        if item["code"] == TEMPLATE_CODE:
            client.delete(f"/promptTemplate/delete/{item['id']}", headers=admin_headers)


def test_seed_configs_use_local_ollama(client, admin_headers):
    """The seeded chat and embedding models are ready for local Ollama."""
    body = client.get("/aiModelConfig/selectAll", headers=admin_headers).json()
    models = {item["model_type"]: item for item in body["data"] if item["enabled"] == "Yes"}
    for model_type, model_name in (
        ("Chat model", "llama3.1:8b"),
        ("Embedding model", "mxbai-embed-large:latest"),
    ):
        config = models[model_type]
        assert config["enabled"] == "Yes"
        assert config["protocol"] == "OpenAI compatible"
        assert config["base_url"] == "http://127.0.0.1:11434/v1"
        assert config["model_name"] == model_name
    assert models["Embedding model"]["dimension"] == 1024
    assert models["Reranking model"]["protocol"] == "Ollama chat reranking"
    assert models["Reranking model"]["model_name"] == "llama3.1:8b"


def test_api_key_is_masked_in_list(client, admin_headers):
    """The key returned by the list interface is non-sensitive and does not send a whole series of keys to the front end."""
    _cleanup_config(client, admin_headers)
    client.post(
        "/aiModelConfig/add",
        json={
            "name": CONFIG_NAME,
            "model_type": "Chat model",
            "protocol": "OpenAI compatible",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "sk-abcdefghijklmnop",
            "model_name": "qwen-plus",
        },
        headers=admin_headers,
    )
    created = _find_config(client, admin_headers)
    assert created["api_key"] == "sk-a" + "*" * 8 + "mnop"

    _cleanup_config(client, admin_headers)


def test_embedding_requires_dimension(client, admin_headers):
    """Vector models must fill dimensions."""
    body = client.post(
        "/aiModelConfig/add",
        json={
            "name": CONFIG_NAME,
            "model_type": "Embedding model",
            "protocol": "OpenAI compatible",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model_name": "text-embedding-v4",
        },
        headers=admin_headers,
    ).json()
    assert body["code"] == "500"
    assert body["msg"] == "Vector models must specify the vector dimension"


def test_only_one_enabled_per_model_type(client, admin_headers):
    """Only one enabler is allowed under the same type, and a new enabler will stop the original."""
    _cleanup_config(client, admin_headers)
    before = client.get("/aiModelConfig/selectAll", params={"model_type": "Chat model"}, headers=admin_headers).json()
    old_enabled = [item for item in before["data"] if item["enabled"] == "Yes"][0]

    client.post(
        "/aiModelConfig/add",
        json={
            "name": CONFIG_NAME,
            "model_type": "Chat model",
            "protocol": "OpenAI compatible",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "sk-test",
            "model_name": "qwen-max",
            "enabled": "Yes",
        },
        headers=admin_headers,
    )
    after = client.get("/aiModelConfig/selectAll", params={"model_type": "Chat model"}, headers=admin_headers).json()
    enabled = [item for item in after["data"] if item["enabled"] == "Yes"]
    assert len(enabled) == 1
    assert enabled[0]["name"] == CONFIG_NAME

    # Restore: restart the original one and delete the test configuration
    client.put(
        "/aiModelConfig/update",
        json={
            "id": old_enabled["id"],
            "name": old_enabled["name"],
            "model_type": old_enabled["model_type"],
            "protocol": old_enabled["protocol"],
            "base_url": old_enabled["base_url"],
            "model_name": old_enabled["model_name"],
            "enabled": "Yes",
        },
        headers=admin_headers,
    )
    _cleanup_config(client, admin_headers)


def test_enabled_config_cannot_be_deleted(client, admin_headers):
    """Cannot delete the configuration that is being enabled."""
    configs = client.get("/aiModelConfig/selectAll", headers=admin_headers).json()
    enabled = [item for item in configs["data"] if item["enabled"] == "Yes"][0]

    body = client.delete(f"/aiModelConfig/delete/{enabled['id']}", headers=admin_headers).json()
    assert body["code"] == "500"
    assert body["msg"] == "Enabled configurations cannot be deleted; please enable another configuration of the same type first"


def test_masked_key_does_not_overwrite_real_key(client, admin_headers):
    """The key is not changed when editing, and desensitivity does not overwrite the real key."""
    _cleanup_config(client, admin_headers)
    client.post(
        "/aiModelConfig/add",
        json={
            "name": CONFIG_NAME,
            "model_type": "Chat model",
            "protocol": "OpenAI compatible",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "sk-abcdefghijklmnop",
            "model_name": "qwen-plus",
        },
        headers=admin_headers,
    )
    created = _find_config(client, admin_headers)

    # Send back the non-sensitivity string from the list. The simulation user changed only another field.
    client.put(
        "/aiModelConfig/update",
        json={
            "id": created["id"],
            "name": CONFIG_NAME,
            "model_type": "Chat model",
            "protocol": "OpenAI compatible",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": created["api_key"],
            "model_name": "qwen-max",
        },
        headers=admin_headers,
    )
    after = _find_config(client, admin_headers)
    # The key is not covered by the sensitisation string.
    assert after["api_key"] == "sk-a" + "*" * 8 + "mnop"
    assert after["model_name"] == "qwen-max"

    _cleanup_config(client, admin_headers)


def test_test_connection_without_key_is_rejected(client, admin_headers):
    """API Key is not filled in to give a human face."""
    _cleanup_config(client, admin_headers)
    client.post(
        "/aiModelConfig/add",
        json={
            "name": CONFIG_NAME,
            "model_type": "Chat model",
            "protocol": "OpenAI compatible",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model_name": "qwen-plus",
        },
        headers=admin_headers,
    )
    created = _find_config(client, admin_headers)

    body = client.post(f"/aiModelConfig/test/{created['id']}", headers=admin_headers).json()
    assert body["code"] == "500"
    assert body["msg"] == "please fill in the API Key first"

    _cleanup_config(client, admin_headers)


def test_seed_prompt_templates_exist(client, admin_headers):
    """Five Prompt templates are preset in the initialization data."""
    body = client.get("/promptTemplate/selectAll", headers=admin_headers).json()
    codes = {item["code"] for item in body["data"]}
    assert {"RAG_ANSWER", "QUERY_REWRITE", "CONTEXT_GRADE", "HALLUCINATION_CHECK", "EVAL_CASE_GEN"} <= codes


def test_variables_are_extracted_from_content(client, admin_headers):
    """Automatically extracts a list of variables from the template contents when saving."""
    _cleanup_template(client, admin_headers)
    client.post(
        "/promptTemplate/add",
        json={
            "code": TEMPLATE_CODE,
            "name": "Unit Test Template",
            "scene": "Answer generation",
            "content": "Sources: {context}\nQuestion: {question}\nRepeat question: {question}",
        },
        headers=admin_headers,
    )
    body = client.get("/promptTemplate/selectAll", headers=admin_headers).json()
    created = [item for item in body["data"] if item["code"] == TEMPLATE_CODE][0]
    # Repeated variables are recorded only once, in the same order as the template.
    assert created["variables"] == "context,question"

    _cleanup_template(client, admin_headers)


def test_preview_renders_variables(client, admin_headers):
    """Previews the variable values into a template and returns the text that is actually sent to the model."""
    _cleanup_template(client, admin_headers)
    client.post(
        "/promptTemplate/add",
        json={
            "code": TEMPLATE_CODE,
            "name": "Unit Test Template",
            "content": "Sources: {context}\nQuestion: {question}",
        },
        headers=admin_headers,
    )
    body = client.get("/promptTemplate/selectAll", headers=admin_headers).json()
    created = [item for item in body["data"] if item["code"] == TEMPLATE_CODE][0]

    preview = client.post(
        "/promptTemplate/preview",
        json={"id": created["id"], "values": {"context": "Quality assurance 24 months", "question": "How long is the warranty"}},
        headers=admin_headers,
    ).json()
    assert preview["code"] == "200"
    assert preview["data"] == "Sources: Quality assurance 24 months\nQuestion: How long is the warranty"

    _cleanup_template(client, admin_headers)


def test_preview_missing_variable_is_rejected(client, admin_headers):
    """The variable is not filled out at full time to specify which is missing."""
    _cleanup_template(client, admin_headers)
    client.post(
        "/promptTemplate/add",
        json={
            "code": TEMPLATE_CODE,
            "name": "Unit Test Template",
            "content": "Sources: {context}\nQuestion: {question}",
        },
        headers=admin_headers,
    )
    body = client.get("/promptTemplate/selectAll", headers=admin_headers).json()
    created = [item for item in body["data"] if item["code"] == TEMPLATE_CODE][0]

    preview = client.post(
        "/promptTemplate/preview",
        json={"id": created["id"], "values": {"context": "Quality assurance 24 months"}},
        headers=admin_headers,
    ).json()
    assert preview["code"] == "500"
    assert preview["msg"] == f"Prompt Template {TEMPLATE_CODE} is missing the following variables: question"

    _cleanup_template(client, admin_headers)


def test_duplicated_template_code_is_rejected(client, admin_headers):
    """Template encoding does not allow repetition."""
    _cleanup_template(client, admin_headers)
    payload = {
        "code": TEMPLATE_CODE,
        "name": "Unit Test Template",
        "content": "Content {context}",
    }
    client.post("/promptTemplate/add", json=payload, headers=admin_headers)
    body = client.post("/promptTemplate/add", json=payload, headers=admin_headers).json()
    assert body["code"] == "500"
    assert body["msg"] == "Template Encoding Repeated"

    _cleanup_template(client, admin_headers)
