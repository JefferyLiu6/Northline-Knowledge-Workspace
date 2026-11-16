from tortoise import fields
from tortoise.models import Model


class QaApp(Model):
    """An application = a set of knowledge bases + a retrieval strategy + a conversation model + a system Prompt.

    After administrators configure it, users can ask questions against it on the user side.
    Q&A application and knowledge base association table. An application can be linked to multiple knowledge bases.
    """

    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=255)
    # Encoding for sharing the link, and this application is found by the user
    app_code = fields.CharField(max_length=64, unique=True)
    description = fields.CharField(max_length=1000, null=True)
    avatar = fields.CharField(max_length=500, null=True)
    chat_model_id = fields.IntField(null=True)
    retrieval_strategy_id = fields.IntField(null=True)
    prompt_code = fields.CharField(max_length=100, null=True)
    # Turn off the straight link from Chapter 15-19 and open the LangGraph status map from Chapter 22
    agent_enabled = fields.CharField(max_length=10, default="No")
    # The number of historical messages brought into the model, too much to support the context slows down.
    max_history = fields.IntField(default=6)
    # A spin-off when you can't retrieve the information.
    empty_answer = fields.CharField(max_length=500, null=True)
    share_enabled = fields.CharField(max_length=10, default="No")
    status = fields.CharField(max_length=20, default="Active")
    create_user_id = fields.IntField(null=True)
    create_time = fields.DatetimeField(auto_now_add=True)
    update_time = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "qa_app"


class QaAppKb(Model):
    """Conversational session table. A continuous series of multi-turn conversations is a session."""

    id = fields.IntField(primary_key=True)
    app_id = fields.IntField()
    kb_id = fields.IntField()
    create_time = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "qa_app_kb"
        unique_together = ("app_id", "kb_id")


class ChatSession(Model):
    """Conversational message table. Each user question and each assistant response is a record."""

    id = fields.IntField(primary_key=True)
    session_no = fields.CharField(max_length=64, unique=True)
    app_id = fields.IntField()
    # The shared page is empty while anonymously accessing
    user_id = fields.IntField(null=True)
    # Take the first question as a title, show the list page
    title = fields.CharField(max_length=255, null=True)
    message_count = fields.IntField(default=0)
    source = fields.CharField(max_length=30, default="Admin portal")
    create_time = fields.DatetimeField(auto_now_add=True)
    update_time = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "chat_session"


class ChatMessage(Model):
    """Message reference source table."""

    id = fields.IntField(primary_key=True)
    session_id = fields.IntField()
    # Ask / answer
    role = fields.CharField(max_length=20)
    content = fields.TextField(null=True)
    # The problem of actually searching it opens up the question of rewrite or decomposition, which is different from the original one, so that we can check back.
    rewritten_query = fields.CharField(max_length=1000, null=True)
    # The search strategy for this question-and-answer session is a snapshot of which switches were turned on.
    strategy_snapshot = fields.TextField(null=True)
    agent_run_id = fields.IntField(null=True)
    prompt_tokens = fields.IntField(null=True)
    completion_tokens = fields.IntField(null=True)
    # Length indicates that the output has been cut.
    finish_reason = fields.CharField(max_length=50, null=True)
    error_message = fields.CharField(max_length=500, null=True)
    cost_millis = fields.BigIntField(null=True)
    create_time = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "chat_message"


class MessageReference(Model):
    """The content stored is a snapshot, because fragments may be modified or deleted later,

    But the answer the user saw at that time was generated based on the version of the content at that time.
    Message feedback table. Clicking down will be stored as test cases in Chapter 27.
    """

    id = fields.IntField(primary_key=True)
    message_id = fields.IntField()
    chunk_id = fields.IntField()
    document_id = fields.IntField(null=True)
    chunk_content = fields.TextField(null=True)
    score = fields.DecimalField(max_digits=10, decimal_places=6, null=True)
    rank_no = fields.IntField(null=True)
    retrieval_source = fields.CharField(max_length=64, null=True)
    create_time = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "message_reference"


class MessageFeedback(Model):
    """AI model configuration table."""

    id = fields.IntField(primary_key=True)
    message_id = fields.IntField()
    user_id = fields.IntField(null=True)
    feedback_type = fields.CharField(max_length=20)
    reason = fields.CharField(max_length=500, null=True)
    # Whether the assessment has been applied to avoid repeated sedimentation of the same article
    converted = fields.CharField(max_length=10, default="No")
    create_time = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "message_feedback"
