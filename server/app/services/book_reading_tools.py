import json
import posixpath
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4
from xml.etree import ElementTree as ET

from agents import function_tool
from pypdf import PdfReader

from app.core.config import settings
from app.models.book import Book as BookModel
from app.prompt import get_prompt
from app.schemas import chat as chat_schemas
from app.services import provider_rules

BOOK_CONTEXT_MESSAGE_ROLE = "book_context"
BOOK_TOOL_GET_PAGE_CONTENT = "get_page_content"
BOOK_TOOL_GET_SELECTED_CONTENT = "get_selected_content"
BOOK_TOOL_GREP_SEARCH = "grep_book_search"
BOOK_TOOL_GET_TOC = "get_book_toc"

SEARCH_EXCERPT_RADIUS = 90
SEARCH_MAX_RESULTS = 5


@dataclass
class BookReadingRequestContext:
    book_id: int
    page_context: Optional[chat_schemas.PageContextPayload] = None
    selected_quote: Optional[chat_schemas.SelectedQuotePayload] = None


def _normalize_text(value: Optional[str]) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _normalize_excerpt_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _serialize_json(value: Dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False)


def _resolve_book_file_path(book: BookModel) -> Optional[Path]:
    raw_path = _normalize_text(getattr(book, "file_path", None))
    if not raw_path:
        return None
    normalized = raw_path.replace("\\", "/").lstrip("/")
    if not normalized:
        return None
    return Path(settings.DATA_DIR) / normalized


def _detect_book_format(book: BookModel) -> str:
    file_name = _normalize_text(getattr(book, "file_name", None))
    file_path = _normalize_text(getattr(book, "file_path", None))
    ext = Path(file_name or file_path).suffix.lower()
    if ext == ".epub":
        return "epub"
    if ext == ".pdf":
        return "pdf"
    if ext == ".txt":
        return "txt"
    if ext in {".mobi", ".azw", ".azw3"}:
        return "mobi"
    return ext.lstrip(".") or "unknown"


def _safe_toc_path(items: Optional[Iterable[str]]) -> List[str]:
    return [
        item.strip()
        for item in (items or [])
        if isinstance(item, str) and item.strip()
    ]


def _page_snapshot_payload(
    book: BookModel,
    page_context: chat_schemas.PageContextPayload,
) -> Dict[str, Any]:
    content = _normalize_text(page_context.excerpt) or _normalize_text(page_context.text)
    payload: Dict[str, Any] = {
        "book_title": _normalize_text(getattr(book, "title", None)) or "未知书名",
        "book_author": _normalize_text(getattr(book, "author", None)) or "未知作者",
        "locator": _normalize_text(page_context.locator) or "当前位置",
        "toc_path": _safe_toc_path(page_context.toc_path),
        "source_type": _normalize_text(page_context.source_type) or "unknown",
        "truncated": bool(page_context.truncated),
        "supported": bool(page_context.supported and content),
        "content": content,
    }
    if not payload["supported"]:
        payload["note"] = _normalize_text(page_context.reason) or "当前页正文为空或暂不可提取"
    return payload


def _selected_quote_payload(
    selected_quote: chat_schemas.SelectedQuotePayload,
) -> Dict[str, Any]:
    content = _normalize_text(selected_quote.excerpt) or _normalize_text(selected_quote.text)
    if content:
        return {
            "status": "selected",
            "locator": _normalize_text(selected_quote.locator) or "当前位置",
            "toc_path": _safe_toc_path(selected_quote.toc_path),
            "source_type": _normalize_text(selected_quote.source_type) or "unknown",
            "truncated": bool(selected_quote.truncated),
            "content": content,
        }
    return {
        "status": "cleared",
        "content": "",
        "note": get_prompt("chat/book_reading_tool_response_selected_cleared.txt").strip(),
    }


def _build_mock_tool_call_item(
    tool_name: str,
    llm_config: Any,
    model_name: Optional[str],
) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "type": "function_call",
        "call_id": f"{tool_name}_{uuid4().hex}",
        "name": tool_name,
        "arguments": "{}",
    }
    if llm_config and provider_rules.needs_gemini_thought_signature(llm_config, model_name):
        item["provider_data"] = {"thought_signature": "skip_thought_signature_validator"}
    return item


def build_book_context_mock_history_items(
    book: BookModel,
    page_context: Optional[chat_schemas.PageContextPayload],
    selected_quote: Optional[chat_schemas.SelectedQuotePayload],
    *,
    llm_config: Any = None,
    model_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    if page_context is not None:
        call_item = _build_mock_tool_call_item(
            BOOK_TOOL_GET_PAGE_CONTENT,
            llm_config=llm_config,
            model_name=model_name,
        )
        items.append(call_item)
        items.append(
            {
                "type": "function_call_output",
                "call_id": call_item["call_id"],
                "output": _serialize_json(_page_snapshot_payload(book, page_context)),
            }
        )

    if selected_quote is not None:
        call_item = _build_mock_tool_call_item(
            BOOK_TOOL_GET_SELECTED_CONTENT,
            llm_config=llm_config,
            model_name=model_name,
        )
        items.append(call_item)
        items.append(
            {
                "type": "function_call_output",
                "call_id": call_item["call_id"],
                "output": _serialize_json(_selected_quote_payload(selected_quote)),
            }
        )

    return items


def build_book_reading_tools(
    book: BookModel,
    request_context: Optional[BookReadingRequestContext],
) -> List[Any]:
    description_get_page_content = get_prompt("chat/book_reading_tool_desc_get_page_content.txt").strip()
    description_get_selected_content = get_prompt("chat/book_reading_tool_desc_get_selected_content.txt").strip()
    description_grep_book_search = get_prompt("chat/book_reading_tool_desc_grep_book_search.txt").strip()
    description_get_book_toc = get_prompt("chat/book_reading_tool_desc_get_book_toc.txt").strip()

    page_context = request_context.page_context if request_context and request_context.book_id == book.id else None
    selected_quote = request_context.selected_quote if request_context and request_context.book_id == book.id else None

    page_unchanged_note = get_prompt("chat/book_reading_tool_response_page_unchanged.txt").strip()
    selected_unchanged_note = get_prompt("chat/book_reading_tool_response_selected_unchanged.txt").strip()
    search_unsupported_note = get_prompt("chat/book_reading_tool_response_search_unsupported.txt").strip()
    toc_unsupported_note = get_prompt("chat/book_reading_tool_response_toc_unsupported.txt").strip()

    toc_cache: Optional[Dict[str, Any]] = None
    search_cache: Optional[Tuple[List[Dict[str, Any]], Optional[str]]] = None

    def _get_toc_payload() -> Dict[str, Any]:
        nonlocal toc_cache
        if toc_cache is None:
            toc_cache = _load_book_toc_payload(book, unsupported_note=toc_unsupported_note)
        return toc_cache

    def _get_search_sections() -> Tuple[List[Dict[str, Any]], Optional[str]]:
        nonlocal search_cache
        if search_cache is None:
            search_cache = _load_book_search_sections(book, unsupported_note=search_unsupported_note)
        return search_cache

    @function_tool(
        name_override=BOOK_TOOL_GET_PAGE_CONTENT,
        description_override=description_get_page_content,
    )
    async def get_page_content() -> Dict[str, Any]:
        if page_context is None:
            return {
                "status": "unchanged",
                "note": page_unchanged_note,
            }
        return _page_snapshot_payload(book, page_context)

    @function_tool(
        name_override=BOOK_TOOL_GET_SELECTED_CONTENT,
        description_override=description_get_selected_content,
    )
    async def get_selected_content() -> Dict[str, Any]:
        if selected_quote is None:
            return {
                "status": "unchanged",
                "note": selected_unchanged_note,
            }
        return _selected_quote_payload(selected_quote)

    @function_tool(
        name_override=BOOK_TOOL_GET_TOC,
        description_override=description_get_book_toc,
    )
    async def get_book_toc() -> Dict[str, Any]:
        return _get_toc_payload()

    @function_tool(
        name_override=BOOK_TOOL_GREP_SEARCH,
        description_override=description_grep_book_search,
    )
    async def grep_book_search(query: str) -> Dict[str, Any]:
        normalized_query = _normalize_text(query)
        if not normalized_query:
            return {
                "query": "",
                "matches": [],
                "total_matches": 0,
            }

        sections, unsupported_note = _get_search_sections()
        if unsupported_note:
            return {
                "query": normalized_query,
                "matches": [],
                "total_matches": 0,
                "note": unsupported_note,
            }

        lowered_query = normalized_query.casefold()
        matches: List[Dict[str, Any]] = []
        for section in sections:
            text = section.get("text", "")
            if not text:
                continue
            index = text.casefold().find(lowered_query)
            if index < 0:
                continue
            excerpt = _build_search_excerpt(text, index, len(normalized_query))
            matches.append(
                {
                    "locator": section.get("locator") or "当前位置",
                    "toc_path": section.get("toc_path") or [],
                    "excerpt": excerpt,
                }
            )
            if len(matches) >= SEARCH_MAX_RESULTS:
                break

        return {
            "query": normalized_query,
            "matches": matches,
            "total_matches": len(matches),
        }

    return [get_page_content, get_selected_content, grep_book_search, get_book_toc]


def _build_search_excerpt(text: str, match_index: int, query_length: int) -> str:
    start = max(0, match_index - SEARCH_EXCERPT_RADIUS)
    end = min(len(text), match_index + query_length + SEARCH_EXCERPT_RADIUS)
    excerpt = text[start:end].strip()
    if start > 0:
        excerpt = f"...{excerpt}"
    if end < len(text):
        excerpt = f"{excerpt}..."
    return excerpt


def _load_book_toc_payload(book: BookModel, *, unsupported_note: str) -> Dict[str, Any]:
    file_path = _resolve_book_file_path(book)
    if not file_path or not file_path.exists():
        return {
            "book_title": _normalize_text(getattr(book, "title", None)) or "未知书名",
            "toc": [],
            "note": unsupported_note,
        }

    format_type = _detect_book_format(book)
    try:
        if format_type == "epub":
            toc = _load_epub_toc(file_path)
        elif format_type == "pdf":
            toc = _load_pdf_toc(file_path)
        elif format_type == "txt":
            toc = [
                {
                    "label": _normalize_text(getattr(book, "title", None)) or "全文",
                    "locator": "全文",
                    "children": [],
                }
            ]
        else:
            toc = []
    except Exception:
        toc = []

    payload: Dict[str, Any] = {
        "book_title": _normalize_text(getattr(book, "title", None)) or "未知书名",
        "toc": toc,
    }
    if not toc:
        payload["note"] = unsupported_note
    return payload


def _load_book_search_sections(
    book: BookModel,
    *,
    unsupported_note: str,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    file_path = _resolve_book_file_path(book)
    if not file_path or not file_path.exists():
        return [], unsupported_note

    format_type = _detect_book_format(book)
    try:
        if format_type == "epub":
            return _load_epub_search_sections(file_path, book), None
        if format_type == "pdf":
            return _load_pdf_search_sections(file_path), None
        if format_type == "txt":
            return _load_txt_search_sections(file_path, book), None
    except Exception:
        return [], unsupported_note

    return [], unsupported_note


def _read_epub_package_root(
    archive: zipfile.ZipFile,
) -> Tuple[str, ET.Element]:
    container_xml = archive.read("META-INF/container.xml")
    container_root = ET.fromstring(container_xml)
    rootfile = container_root.find(".//{*}rootfile")
    if rootfile is None:
        raise ValueError("EPUB rootfile missing")
    opf_path = rootfile.attrib.get("full-path")
    if not opf_path:
        raise ValueError("EPUB OPF path missing")
    package_root = ET.fromstring(archive.read(opf_path))
    return opf_path, package_root


def _load_epub_toc(file_path: Path) -> List[Dict[str, Any]]:
    with zipfile.ZipFile(file_path) as archive:
        opf_path, package_root = _read_epub_package_root(archive)
        toc_entries, _ = _extract_epub_toc_entries(archive, opf_path, package_root)
        return toc_entries


def _load_epub_search_sections(file_path: Path, book: BookModel) -> List[Dict[str, Any]]:
    with zipfile.ZipFile(file_path) as archive:
        opf_path, package_root = _read_epub_package_root(archive)
        _, href_to_toc_path = _extract_epub_toc_entries(archive, opf_path, package_root)
        manifest = {
            item.attrib.get("id"): item.attrib.get("href")
            for item in package_root.findall(".//{*}manifest/{*}item")
            if item.attrib.get("id") and item.attrib.get("href")
        }
        sections: List[Dict[str, Any]] = []
        for itemref in package_root.findall(".//{*}spine/{*}itemref"):
            idref = itemref.attrib.get("idref")
            href = manifest.get(idref or "")
            if not href:
                continue
            archive_path = _normalize_epub_archive_path(opf_path, href)
            try:
                raw = archive.read(archive_path)
            except KeyError:
                continue

            text = _extract_xml_text(raw)
            if not text:
                continue

            toc_path = href_to_toc_path.get(_strip_fragment(archive_path)) or [
                _normalize_text(getattr(book, "title", None)) or "正文"
            ]
            sections.append(
                {
                    "locator": " > ".join(toc_path) or "当前位置",
                    "toc_path": toc_path,
                    "text": text,
                }
            )
        return sections


def _extract_epub_toc_entries(
    archive: zipfile.ZipFile,
    opf_path: str,
    package_root: ET.Element,
) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    manifest = {
        item.attrib.get("id"): item
        for item in package_root.findall(".//{*}manifest/{*}item")
        if item.attrib.get("id")
    }

    nav_item = next(
        (
            item
            for item in manifest.values()
            if "nav" in (item.attrib.get("properties", "") or "").lower()
        ),
        None,
    )
    if nav_item is not None:
        href = nav_item.attrib.get("href")
        if href:
            toc_entries = _parse_epub_nav_document(
                archive,
                _normalize_epub_archive_path(opf_path, href),
            )
            return toc_entries, _flatten_toc_href_paths(toc_entries)

    spine = package_root.find(".//{*}spine")
    toc_id = spine.attrib.get("toc") if spine is not None else None
    ncx_item = manifest.get(toc_id or "")
    if ncx_item is not None:
        href = ncx_item.attrib.get("href")
        if href:
            toc_entries = _parse_epub_ncx_document(
                archive,
                _normalize_epub_archive_path(opf_path, href),
            )
            return toc_entries, _flatten_toc_href_paths(toc_entries)

    return [], {}


def _parse_epub_nav_document(
    archive: zipfile.ZipFile,
    archive_path: str,
) -> List[Dict[str, Any]]:
    root = ET.fromstring(archive.read(archive_path))
    toc_nav = None
    for node in root.iter():
        if not str(node.tag).endswith("nav"):
            continue
        attr_text = " ".join(str(value) for value in node.attrib.values())
        if "toc" in attr_text:
            toc_nav = node
            break
    if toc_nav is None:
        return []

    ol_node = next((child for child in toc_nav if str(child.tag).endswith("ol")), None)
    if ol_node is None:
        return []
    return _parse_epub_nav_ol(ol_node, archive_path)


def _parse_epub_nav_ol(ol_node: ET.Element, base_archive_path: str) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for li_node in ol_node:
        if not str(li_node.tag).endswith("li"):
            continue
        label = ""
        href = None
        children_node = None
        for child in li_node:
            if str(child.tag).endswith("a"):
                label = _normalize_excerpt_text("".join(child.itertext()))
                href = child.attrib.get("href")
            elif str(child.tag).endswith("span") and not label:
                label = _normalize_excerpt_text("".join(child.itertext()))
            elif str(child.tag).endswith("ol"):
                children_node = child
        entry: Dict[str, Any] = {
            "label": label or "未命名章节",
            "href": (
                _strip_fragment(_normalize_epub_archive_path(base_archive_path, href))
                if href
                else None
            ),
            "locator": label or "未命名章节",
            "children": _parse_epub_nav_ol(children_node, base_archive_path) if children_node is not None else [],
        }
        entries.append(entry)
    return entries


def _parse_epub_ncx_document(
    archive: zipfile.ZipFile,
    archive_path: str,
) -> List[Dict[str, Any]]:
    root = ET.fromstring(archive.read(archive_path))
    nav_map = root.find(".//{*}navMap")
    if nav_map is None:
        return []
    return _parse_epub_ncx_nav_points(nav_map, archive_path)


def _parse_epub_ncx_nav_points(
    node: ET.Element,
    base_archive_path: str,
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for nav_point in node:
        if not str(nav_point.tag).endswith("navPoint"):
            continue
        label_node = nav_point.find("./{*}navLabel/{*}text")
        label = _normalize_excerpt_text(label_node.text or "") if label_node is not None else ""
        content = nav_point.find("./{*}content")
        href = content.attrib.get("src") if content is not None else None
        entry = {
            "label": label or "未命名章节",
            "href": (
                _strip_fragment(_normalize_epub_archive_path(base_archive_path, href))
                if href
                else None
            ),
            "locator": label or "未命名章节",
            "children": _parse_epub_ncx_nav_points(nav_point, base_archive_path),
        }
        entries.append(entry)
    return entries


def _flatten_toc_href_paths(
    items: List[Dict[str, Any]],
    trail: Optional[List[str]] = None,
    result: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, List[str]]:
    if result is None:
        result = {}
    trail = trail or []
    for item in items:
        label = _normalize_text(item.get("label")) or "未命名章节"
        current_trail = [*trail, label]
        href = _strip_fragment(_normalize_text(item.get("href")))
        if href:
            result[href] = current_trail
        _flatten_toc_href_paths(item.get("children") or [], current_trail, result)
    return result


def _normalize_epub_archive_path(opf_path: str, href: str) -> str:
    opf_dir = posixpath.dirname(opf_path)
    normalized = posixpath.normpath(posixpath.join(opf_dir, href))
    return normalized.lstrip("./")


def _strip_fragment(href: str) -> str:
    return href.split("#", 1)[0]


def _extract_xml_text(raw: bytes) -> str:
    try:
        root = ET.fromstring(raw)
        text = "".join(root.itertext())
    except ET.ParseError:
        text = re.sub(r"<[^>]+>", " ", raw.decode("utf-8", errors="ignore"))
    return _normalize_excerpt_text(text)


def _load_pdf_toc(file_path: Path) -> List[Dict[str, Any]]:
    reader = PdfReader(str(file_path))
    outline = getattr(reader, "outline", None) or getattr(reader, "outlines", None)
    if not outline:
        return []
    return _parse_pdf_outline_items(reader, outline)


def _parse_pdf_outline_items(
    reader: PdfReader,
    items: Any,
) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []
    result: List[Dict[str, Any]] = []
    index = 0
    while index < len(items):
        item = items[index]
        children_items = items[index + 1] if index + 1 < len(items) and isinstance(items[index + 1], list) else None
        if children_items is not None:
            index += 1

        if isinstance(item, list):
            result.extend(_parse_pdf_outline_items(reader, item))
        else:
            title = _normalize_excerpt_text(str(getattr(item, "title", None) or item))
            page_number = _resolve_pdf_outline_page(reader, item)
            result.append(
                {
                    "label": title or "未命名章节",
                    "locator": f"第 {page_number} 页" if page_number else None,
                    "page": page_number,
                    "children": _parse_pdf_outline_items(reader, children_items or []),
                }
            )
        index += 1
    return result


def _resolve_pdf_outline_page(reader: PdfReader, item: Any) -> Optional[int]:
    try:
        return reader.get_destination_page_number(item) + 1
    except Exception:
        return None


def _load_pdf_search_sections(file_path: Path) -> List[Dict[str, Any]]:
    reader = PdfReader(str(file_path))
    toc_entries = _load_pdf_toc(file_path)
    page_to_toc_path = _flatten_pdf_toc_page_map(toc_entries)
    sorted_pages = sorted(page_to_toc_path.keys())
    sections: List[Dict[str, Any]] = []
    for page_index, page in enumerate(reader.pages, start=1):
        text = _normalize_excerpt_text(page.extract_text() or "")
        if not text:
            continue
        toc_path = _find_nearest_pdf_toc_path(page_index, sorted_pages, page_to_toc_path)
        sections.append(
            {
                "locator": f"第 {page_index} 页",
                "toc_path": toc_path,
                "text": text,
            }
        )
    return sections


def _flatten_pdf_toc_page_map(
    items: List[Dict[str, Any]],
    trail: Optional[List[str]] = None,
    result: Optional[Dict[int, List[str]]] = None,
) -> Dict[int, List[str]]:
    if result is None:
        result = {}
    trail = trail or []
    for item in items:
        label = _normalize_text(item.get("label")) or "未命名章节"
        current_trail = [*trail, label]
        page = item.get("page")
        if isinstance(page, int) and page > 0 and page not in result:
            result[page] = current_trail
        _flatten_pdf_toc_page_map(item.get("children") or [], current_trail, result)
    return result


def _find_nearest_pdf_toc_path(
    page_number: int,
    sorted_pages: List[int],
    page_to_toc_path: Dict[int, List[str]],
) -> List[str]:
    nearest_path: List[str] = []
    for candidate in sorted_pages:
        if candidate > page_number:
            break
        nearest_path = page_to_toc_path.get(candidate, nearest_path)
    return nearest_path


def _load_txt_search_sections(file_path: Path, book: BookModel) -> List[Dict[str, Any]]:
    text = _normalize_excerpt_text(file_path.read_text(encoding="utf-8", errors="ignore"))
    if not text:
        return []
    toc_path = [_normalize_text(getattr(book, "title", None)) or "全文"]
    return [
        {
            "locator": "全文",
            "toc_path": toc_path,
            "text": text,
        }
    ]
