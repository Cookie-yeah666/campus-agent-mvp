"""文档分块器。

优先按章节切分；章节过长时按句子边界二次切分，块间保留
``overlap`` 字符的重叠，避免切断句子或丢失上下文。
"""

from __future__ import annotations

import re

from app.models.domain import KnowledgeChunk, KnowledgeDocument

_SENTENCE_RE = re.compile(r"[^。！？；\n]+[。！？；]?")


def _split_long_text(text: str, max_chars: int, overlap: int) -> list[str]:
    """把长文本按句子边界切成不超过 ``max_chars`` 的片段。"""
    if len(text) <= max_chars:
        return [text]

    sentences = [sentence.strip() for sentence in _SENTENCE_RE.findall(text) if sentence.strip()]
    if not sentences:
        sentences = [text]

    pieces: list[str] = []
    current: list[str] = []
    current_length = 0
    for sentence in sentences:
        if current and current_length + len(sentence) > max_chars:
            piece = "".join(current)
            pieces.append(piece)
            tail = piece[-overlap:] if overlap > 0 else ""
            current = [tail, sentence] if tail else [sentence]
            current_length = len(tail) + len(sentence)
        else:
            current.append(sentence)
            current_length += len(sentence)
    if current:
        pieces.append("".join(current))
    return [piece.strip() for piece in pieces if piece.strip()]


def chunk_document(
    document: KnowledgeDocument,
    *,
    min_chars: int,
    max_chars: int,
    overlap: int,
) -> list[KnowledgeChunk]:
    """把一篇文档切成带元数据的分块。

    Args:
        document: 知识库文档。
        min_chars: 目标最小块长度（仅用于提示，不强制合并章节）。
        max_chars: 单块最大字符数。
        overlap: 长章节二次切分时的重叠字符数。

    Returns:
        分块列表，``chunk_index`` 在文档内从 0 递增。
    """
    del min_chars  # 章节本身可能短于目标值，保持章节边界优先
    chunks: list[KnowledgeChunk] = []
    for section in document.sections:
        body = "\n".join(paragraph.strip() for paragraph in section.paragraphs if paragraph.strip())
        if not body:
            continue
        for piece in _split_long_text(body, max_chars=max_chars, overlap=overlap):
            index = len(chunks)
            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"{document.id}-{index:02d}",
                    doc_id=document.id,
                    doc_title=document.title,
                    chapter=section.heading,
                    doc_number=document.doc_number,
                    category=document.category,
                    chunk_index=index,
                    content=piece,
                )
            )
    return chunks
