"""Document parsing.

Read the uploaded original files into plain text for chapter 09 to divide into knowledge segments.

Treatment of all types of treatment:

    PDF takes the text layer page by page; tables on the same page are extracted from pdflumber into Markdown tables;
              Scanner when no text layer is available for the entire page. Go OCR recognition
    WORD reads paragraphs and converts tables into Markdown tables
    EXCEL Converts each sheet into a Markdown table
    MarkdoWN read as it is
    TXT Read As

The returned ParseResult with two tags in addition to the text: does this document have a table, has gone past OCR,
They will be filled back in the fields of knowledge_documents and has_ocr.
"""

from dataclasses import dataclass, field


@dataclass
class ParseResult:
    """A parsed output."""

    # Parsed_text
    text: str = ""
    # Whether the table was extracted from a file
    has_table: bool = False
    # Is there a whole page gone? OCR.
    has_ocr: bool = False
    # Text snippets of each page or sheet, in order of sequence, are text
    segments: list[str] = field(default_factory=list)


# Wrapping lines in cells disrupt the structure of the Markdown table and replace them with spaces
def _clean_cell(value) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("|", "/").strip()


def _rows_to_markdown(rows: list[list]) -> str:
    """Converts the two-dimensional array of cells to a Markdown table.

    Turned to Markdown instead of a tab, because it was cut and quantified.
    Models see that separate forms recognize the line, and answer questions like "How long is the warranty period for a model?"
    """
    cleaned = [[_clean_cell(cell) for cell in row] for row in rows if row]
    if not cleaned:
        return ""
    header = cleaned[0]
    lines = ["| " + " | ".join(header) + " |"]
    # Markdown Table must have this line separated, otherwise the table structure cannot be rendered
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
    for row in cleaned[1:]:
        # Fill short lines to prevent a row of cells from being smaller than the top of the table and leading to an error in the column
        padded = row + [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(padded[: len(header)]) + " |")
    return "\n".join(lines)


def _ocr_page(page) -> str:
    """Do OCR for PDF pages that do not have a text layer.

    The page is re-identified with a bitmap of two times the resolution, which is too low to be clearly changed.
    Rapidocr is pure CPU reasoning, not required to display a card.
    """
    import pymupdf
    from rapidocr_onnxruntime import RapidOCR

    matrix = pymupdf.Matrix(2, 2)
    pixmap = page.get_pixmap(matrix=matrix)
    image_bytes = pixmap.tobytes("png")
    ocr = RapidOCR()
    result, _ = ocr(image_bytes)
    if not result:
        return ""
    # RapidOCR returns each [coordinate box, text, confidence] with only text
    return "\n".join(item[1] for item in result)


def _parse_pdf(file_path: str) -> ParseResult:
    import pdfplumber
    import pymupdf

    outcome = ParseResult()
    document = pymupdf.open(file_path)
    # pdflumber takes tables, pymupdf takes the text layer and two libraries read the same file
    with pdfplumber.open(file_path) as plumber_pdf:
        for index, page in enumerate(document):
            parts = []
            page_text = page.get_text().strip()
            if page_text:
                parts.append(page_text)
            else:
                # No text can be found on the entire page, which indicates that this page is a scanned picture and handed to OCR.
                ocr_text = _ocr_page(page)
                if ocr_text:
                    outcome.has_ocr = True
                    parts.append(ocr_text)
            # The table is taken separately. The table in the text layer is a scattered character by pdfplummer
            if index < len(plumber_pdf.pages):
                for table in plumber_pdf.pages[index].extract_tables() or []:
                    markdown = _rows_to_markdown(table)
                    if markdown:
                        outcome.has_table = True
                        parts.append(markdown)
            if parts:
                # Page_no of chapter 09 when it is cut,
                # The answer to the question-and-answer is from page one.
                outcome.segments.append(f"[Page {index + 1}]\n" + "\n\n".join(parts))
    document.close()
    outcome.text = "\n\n".join(outcome.segments)
    return outcome


def _parse_word(file_path: str) -> ParseResult:
    from docx import Document

    outcome = ParseResult()
    document = Document(file_path)
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            outcome.segments.append(text)
    for table in document.tables:
        rows = [[cell.text for cell in row.cells] for row in table.rows]
        markdown = _rows_to_markdown(rows)
        if markdown:
            outcome.has_table = True
            outcome.segments.append(markdown)
    outcome.text = "\n\n".join(outcome.segments)
    return outcome


def _parse_excel(file_path: str) -> ParseResult:
    from openpyxl import load_workbook

    outcome = ParseResult()
    # Data_only=True allows formula cells to return the result rather than the formula itself
    workbook = load_workbook(file_path, data_only=True)
    for sheet in workbook.worksheets:
        rows = [list(row) for row in sheet.iter_rows(values_only=True)]
        # The whole line was thrown out. Excel always had a lot of empty lines.
        rows = [row for row in rows if any(cell is not None and str(cell).strip() for cell in row)]
        markdown = _rows_to_markdown(rows)
        if markdown:
            outcome.has_table = True
            # Take the sheet name. You can distinguish between multiple tables in a file.
            outcome.segments.append(f"[Sheet: {sheet.title}]\n{markdown}")
    workbook.close()
    outcome.text = "\n\n".join(outcome.segments)
    return outcome


def _parse_plain_text(file_path: str) -> ParseResult:
    outcome = ParseResult()
    # Errors=ignore skips individual cipher characters and does not allow a bad byte to cause the entire parse failure
    with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
        text = handle.read().strip()
    if text:
        outcome.segments.append(text)
    outcome.text = text
    return outcome


# File_type extrapolated from chapter 06 by file suffix and distributed here to the corresponding resolution function by type
PARSERS = {
    "PDF": _parse_pdf,
    "WORD": _parse_word,
    "EXCEL": _parse_excel,
    "MARKDOWN": _parse_plain_text,
    "TXT": _parse_plain_text,
}


def parse(file_path: str, file_type: str) -> ParseResult:
    """Parsing files by file type returns text and two tags."""
    parser = PARSERS.get(file_type)
    if parser is None:
        raise ValueError(f"No Corresponding {file_type} Parser Type")
    return parser(file_path)
