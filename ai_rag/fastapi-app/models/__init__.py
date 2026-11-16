"""Original scaffolding puts all models in a single models.py file, but this project has many tables, so it is split into files by business domain:

user.py       Users and system foundation

    knowledge.py  Knowledge base, documents, fragments, retrieval strategies
    config.py     Model configuration, Prompt templates, tool registration
    process.py    Document processing tasks, debug records, tool call logs
    Subsequent chapters will introduce new tables and place them in the corresponding files by domain, and import them here, so that Tortoise can scan them.

Q&A application table.
"""

from models.chat import (
    ChatMessage,
    ChatSession,
    MessageFeedback,
    MessageReference,
    QaApp,
    QaAppKb,
)
from models.config import AiModelConfig, FunctionTool, PromptTemplate
from models.evaluation import (
    EvalCase,
    EvalCaseResult,
    EvalDataset,
    EvalReport,
    EvalTask,
)
from models.knowledge import (
    ChunkStrategy,
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeDocument,
    RetrievalStrategy,
)
from models.process import (
    AgentRun,
    AgentStep,
    DocumentProcessTask,
    RetrievalDebugRecord,
    ToolCallLog,
)
from models.user import User

__all__ = [
    "User",
    "KnowledgeBase",
    "KnowledgeDocument",
    "ChunkStrategy",
    "KnowledgeChunk",
    "RetrievalStrategy",
    "DocumentProcessTask",
    "AgentRun",
    "AgentStep",
    "RetrievalDebugRecord",
    "ToolCallLog",
    "AiModelConfig",
    "PromptTemplate",
    "FunctionTool",
    "QaApp",
    "QaAppKb",
    "ChatSession",
    "ChatMessage",
    "MessageReference",
    "MessageFeedback",
    "EvalDataset",
    "EvalCase",
    "EvalTask",
    "EvalCaseResult",
    "EvalReport",
]
