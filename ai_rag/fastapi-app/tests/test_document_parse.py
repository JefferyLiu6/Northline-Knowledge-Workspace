"""Document parsing interface test.

Covers three failed paths with temporary files: TXT, Excel, PDF and missing and empty documents.
Scanner OCR requires a real scan, which is manually verified on the page.
"""

import os

import pytest

from service.file_service import UPLOAD_DIR

KB_NAME = "Testing the library -- module test"


@pytest.fixture()
def kb_id(client, admin_headers):
    """Build a temporary knowledge base, which will be cleared with the documents under the library."""
    client.post(
        "/knowledgeBase/add",
        json={"name": KB_NAME, "status": "Active"},
        headers=admin_headers,
    )
    page = client.get(
        "/knowledgeBase/selectPage",
        params={"name": KB_NAME, "page_num": 1, "page_size": 10},
        headers=admin_headers,
    ).json()
    created = [item for item in page["data"]["list"] if item["name"] == KB_NAME][0]

    yield created["id"]

    docs = client.get(
        "/knowledgeDocument/selectPage",
        params={"kb_id": created["id"], "page_num": 1, "page_size": 50},
        headers=admin_headers,
    ).json()
    doc_ids = [item["id"] for item in docs["data"]["list"]]
    if doc_ids:
        client.request(
            "DELETE", "/knowledgeDocument/deleteBatch", json=doc_ids, headers=admin_headers
        )
    client.delete(f"/knowledgeBase/delete/{created['id']}", headers=admin_headers)


@pytest.fixture()
def temp_files():
    """Record the files in the file directory for this test, run and delete."""
    created = []
    yield created
    for name in created:
        path = os.path.join(UPLOAD_DIR, name)
        if os.path.exists(path):
            os.remove(path)


def _write_text_file(temp_files, file_name, content):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_DIR, file_name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    temp_files.append(file_name)
    return path


def _add_doc(client, admin_headers, kb_id, file_name):
    client.post(
        "/knowledgeDocument/add",
        json={
            "kb_id": kb_id,
            "name": file_name,
            "file_name": file_name,
            "file_url": f"http://127.0.0.1:9090/files/download/{file_name}",
            "file_size": 100,
        },
        headers=admin_headers,
    )
    page = client.get(
        "/knowledgeDocument/selectPage",
        params={"kb_id": kb_id, "name": file_name, "page_num": 1, "page_size": 10},
        headers=admin_headers,
    ).json()
    return page["data"]["list"][0]["id"]


def test_parse_txt_writes_text_and_char_count(client, admin_headers, kb_id, temp_files):
    """After the TXT parsing is completed, write text and characters. The state becomes parsed."""
    content = "The GTE-3000 model has a 24-month duration. \n will be charged in turn after the expiration period."
    _write_text_file(temp_files, "Description of quality assurance.txt", content)
    doc_id = _add_doc(client, admin_headers, kb_id, "Description of quality assurance.txt")

    assert client.post(f"/knowledgeDocument/parse/{doc_id}", headers=admin_headers).json()["code"] == "200"

    detail = client.get(f"/knowledgeDocument/parsedText/{doc_id}", headers=admin_headers).json()
    assert detail["data"]["parse_status"] == "Parsed"
    assert "GTE-3000" in detail["data"]["parsed_text"]
    assert detail["data"]["char_count"] == len(content)
    # No form, no table. OCR.
    assert detail["data"]["has_table"] == "No"
    assert detail["data"]["has_ocr"] == "No"


def test_parse_excel_converts_sheet_to_markdown_table(client, admin_headers, kb_id, temp_files):
    """Excel, converts each sheet to a Markdown table and marks it with a table tag."""
    from openpyxl import Workbook

    file_name = "Warranty Comparison.xlsx"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_DIR, file_name)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Warranty period"
    sheet.append(["Model", "Warranty period", "Remarks"])
    sheet.append(["GTE-3000", "24 months", "Mainboard"])
    workbook.save(path)
    workbook.close()
    temp_files.append(file_name)

    doc_id = _add_doc(client, admin_headers, kb_id, file_name)
    client.post(f"/knowledgeDocument/parse/{doc_id}", headers=admin_headers)

    detail = client.get(f"/knowledgeDocument/parsedText/{doc_id}", headers=admin_headers).json()
    text = detail["data"]["parsed_text"]
    assert detail["data"]["parse_status"] == "Parsed"
    assert detail["data"]["has_table"] == "Yes"
    # Sheet name in text, different when you have more tables in a file
    assert "[Sheet: Warranty period]" in text
    # Turned to Markdown form. Models recognize the lineup.
    assert "| --- | --- | --- |" in text
    assert "| GTE-3000 | 24 months | Mainboard |" in text


def test_parse_pdf_keeps_page_number(client, admin_headers, kb_id, temp_files):
    """PDF parsing results by page block, the first paragraph indicates a page number."""
    import pymupdf

    file_name = "Product description.pdf"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_DIR, file_name)
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 100), "Warranty period is 24 months.")
    document.save(path)
    document.close()
    temp_files.append(file_name)

    doc_id = _add_doc(client, admin_headers, kb_id, file_name)
    client.post(f"/knowledgeDocument/parse/{doc_id}", headers=admin_headers)

    detail = client.get(f"/knowledgeDocument/parsedText/{doc_id}", headers=admin_headers).json()
    assert detail["data"]["parse_status"] == "Parsed"
    assert "[Page 1]" in detail["data"]["parsed_text"]
    assert "24 months" in detail["data"]["parsed_text"]
    # You don't leave without a text layer, OCR.
    assert detail["data"]["has_ocr"] == "No"


def test_parse_missing_file_is_rejected(client, admin_headers, kb_id, temp_files):
    """When the original file is not on disk, the interface stops directly and does not create a task."""
    path = _write_text_file(temp_files, "Missing document.txt", "temporary")
    doc_id = _add_doc(client, admin_headers, kb_id, "Missing document.txt")
    os.remove(path)

    body = client.post(f"/knowledgeDocument/parse/{doc_id}", headers=admin_headers).json()
    assert body["code"] == "500"
    assert body["msg"] == "File does not exist"


def test_parse_empty_file_marks_failed(client, admin_headers, kb_id, temp_files):
    """An empty file does not parsing content, the state is marked as a resolution failure and causes are recorded."""
    _write_text_file(temp_files, "Empty file.txt", "   ")
    doc_id = _add_doc(client, admin_headers, kb_id, "Empty file.txt")

    client.post(f"/knowledgeDocument/parse/{doc_id}", headers=admin_headers)

    detail = client.get(f"/knowledgeDocument/parsedText/{doc_id}", headers=admin_headers).json()
    assert detail["data"]["parse_status"] == "Parsing failed"
    assert detail["data"]["parse_error"] == "No text was parsed, please confirm the file content is not empty"


def test_parse_records_task(client, admin_headers, kb_id, temp_files):
    """Each analysis leaves a record of the task, and when successful, the status is completed."""
    _write_text_file(temp_files, "Mission log test.txt", "A paragraph to verify the text of the task record.")
    doc_id = _add_doc(client, admin_headers, kb_id, "Mission log test.txt")

    client.post(f"/knowledgeDocument/parse/{doc_id}", headers=admin_headers)

    tasks = client.get(f"/knowledgeDocument/tasks/{doc_id}", headers=admin_headers).json()
    assert tasks["code"] == "200"
    latest = tasks["data"][0]
    assert latest["task_type"] == "Document parsing"
    assert latest["task_status"] == "Completed"
    assert latest["success_count"] == 1
    assert latest["total_count"] == 1
    assert latest["cost_millis"] is not None
