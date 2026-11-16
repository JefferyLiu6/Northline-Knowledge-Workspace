from tortoise import fields
from tortoise.models import Model


class KnowledgeBase(Model):
    """Knowledge Base Table. Primary classification of enterprise documents. A knowledge base contains multiple documents."""

    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=255)
    description = fields.CharField(max_length=1000, null=True)
    # The bound vector model is configured with an ID, locked after a store. The vectors already in the library are derived from this model.
    # Models must be re-quantified in full, otherwise new questions and old vectors do not have the same semantic space
    embedding_model_id = fields.IntField(null=True)
    # Default Slicing Policy ID, which determines how to slice when uploading a document
    chunk_strategy_id = fields.IntField(null=True)
    # The number of documents and segments are redundant statistical columns maintained by additions to and deletions from the document and segment,
    # List pages read the two numbers directly, without using each calculation.
    document_count = fields.IntField(default=0)
    chunk_count = fields.IntField(default=0)
    status = fields.CharField(max_length=20, default="Active")
    create_user_id = fields.IntField(null=True)
    create_time = fields.DatetimeField(auto_now_add=True)
    update_time = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "knowledge_base"


class KnowledgeDocument(Model):
    """Knowledge Document Table. The original files uploaded by users. One document belongs to one knowledge base."""

    id = fields.IntField(primary_key=True)
    # ID of the knowledge base to which it belongs, before deleting the knowledge base, requires that all documents below it be deleted
    kb_id = fields.IntField()
    name = fields.CharField(max_length=255)
    # Disk filename, access to original file /files/download/{file_name}
    file_name = fields.CharField(max_length=500, null=True)
    # File access address to fill back by /files/upload
    file_url = fields.CharField(max_length=500, null=True)
    # File type extrapolated from file suffix to determine which solver chapter 07 will use
    file_type = fields.CharField(max_length=30, null=True)
    file_size = fields.BigIntField(default=0)
    # Parsing state, chapter 07 flowes as document is parsed
    parse_status = fields.CharField(max_length=30, default="Pending parsing")
    parse_error = fields.CharField(max_length=500, null=True)
    # Parsed plain text, chapter 09 severs segments by it
    parsed_text = fields.TextField(null=True)
    # Whether the table was extracted from a parsing process, whether or not an OCR has been passed. The list page is used to mark the complexity of this document
    has_table = fields.CharField(max_length=10, default="No")
    has_ocr = fields.CharField(max_length=10, default="No")
    char_count = fields.IntField(default=0)
    chunk_count = fields.IntField(default=0)
    # Flow to Quantified Status, Chapter 12 when writing vectors
    vector_status = fields.CharField(max_length=30, default="Pending embedding")
    upload_user_id = fields.IntField(null=True)
    create_time = fields.DatetimeField(auto_now_add=True)
    update_time = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "knowledge_document"


class ChunkStrategy(Model):
    """Splitting Strategy Table. One row is a set of splitting parameters. The knowledge base splits documents according to this."""

    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=255)
    # Recursive blocks: cut by separator; male/son divisions: cut big pieces first and then small ones
    strategy_type = fields.CharField(max_length=30)
    chunk_size = fields.IntField(default=500)
    chunk_overlap = fields.IntField(default=50)
    # Only for fathers and sons, the length of a parent must be greater than that of a child
    parent_chunk_size = fields.IntField(null=True)
    # Separator List, comma-separated, sequentially attempted
    separators = fields.CharField(max_length=255, null=True)
    # The knowledge base uses the default policy when no strategy is specified, and only one "yes" is allowed in the whole table.
    is_default = fields.CharField(max_length=10, default="No")
    remark = fields.CharField(max_length=500, null=True)
    create_time = fields.DatetimeField(auto_now_add=True)
    update_time = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "chunk_strategy"


class RetrievalStrategy(Model):
    """Retrieval Strategy Table.

    One row is a complete set of retrieval parameters. The debug panel in Chapter 19 uses multiple rows for side-by-side comparison,
    and the Q&A application in Chapter 24 references one row as its retrieval method.
    """

    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=255)
    # Vector search: semantic matching, no precise character recognized
    vector_enabled = fields.CharField(max_length=10, default="Yes")
    vector_top_k = fields.IntField(default=5)
    # BM25 keyword search: character matching, non-synonym expression
    bm25_enabled = fields.CharField(max_length=10, default="No")
    bm25_top_k = fields.IntField(default=5)
    # RRF Integration Constants, smaller and more to the head
    rrf_k = fields.IntField(default=60)
    # Reorder access to Chapter 16
    rerank_enabled = fields.CharField(max_length=10, default="No")
    rerank_model_id = fields.IntField(null=True)
    rerank_top_n = fields.IntField(default=3)
    # Query rewrite in Chapter 17
    query_rewrite_enabled = fields.CharField(max_length=10, default="No")
    rewrite_type = fields.CharField(max_length=30, null=True)
    multi_query_count = fields.IntField(default=3)
    # Parent Backloading in Chapter 18
    parent_recall_enabled = fields.CharField(max_length=10, default="No")
    # The thresholds are separated by the number of fractions.
    # The range of the two values is one order of magnitude different and the same number is placed on both sides with a completely different meaning, so it has been split into two fields.
    # The final fraction on single-way recall is cosine similarities, take 0 to 1, below threshold determined as no answer
    vector_score_threshold = fields.DecimalField(max_digits=5, decimal_places=3, null=True)
    # The final fractions when reordered are associated with the re-allocation model, and there is a different order of magnitude and cosine similarities, with a separate threshold.
    rerank_score_threshold = fields.DecimalField(max_digits=5, decimal_places=3, null=True)
    metadata_filter = fields.CharField(max_length=1000, null=True)
    is_default = fields.CharField(max_length=10, default="No")
    remark = fields.CharField(max_length=500, null=True)
    create_time = fields.DatetimeField(auto_now_add=True)
    update_time = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "retrieval_strategy"


class KnowledgeChunk(Model):
    """Knowledge Chunk Table. The smallest retrieval unit after document splitting."""

    id = fields.IntField(primary_key=True)
    kb_id = fields.IntField()
    document_id = fields.IntField()
    # When the father and son split up, they point to the father and the rest is empty.
    parent_id = fields.IntField(null=True)
    chunk_index = fields.IntField(default=0)
    # Regular blocks are also involved in the generation; sub-blocks only participate in the retrieval, and the parent block is filled back only after a hit.
    chunk_type = fields.CharField(max_length=20, default="Standard chunk")
    content = fields.TextField()
    char_count = fields.IntField(default=0)
    # Extracted from the parsing text [page N] tag, which is used to give answers to users on page 1
    page_no = fields.IntField(null=True)
    title_path = fields.CharField(max_length=500, null=True)
    extra_meta = fields.TextField(null=True)
    vector_status = fields.CharField(max_length=30, default="Pending embedding")
    create_time = fields.DatetimeField(auto_now_add=True)
    update_time = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "knowledge_chunk"
