"""All code related to large models, retrieval, Agent, and evaluation in this project is placed in this package,

Not allowed to scatter in api/ or service/, the purpose is to make the AI chain readable and replaceable separately.
Module planning introduced step by step by chapter:

model_factory.py   Read configuration from ai_model_config table, build dialogue/vector/re-ranking models

    prompt_loader.py   Read Prompt from prompt_template table, perform existence and enable validation
    loader.py          Document loading and parsing (PDF tables, scanned OCR)
    splitter.py        Text splitting strategy (recursive / semantic / parent-child)
    retriever.py       Vector retrieval, BM25, RRF fusion, re-ranking, query rewrite
    graph.py           LangGraph arranged Agentic RAG state diagram
    tools.py           Function calling tool implementation, corresponding to function_tool table
    evaluator.py       RAGAS evaluation execution and metric aggregation
    RAG effect evaluation.
"""
