"""文本切块：段落优先打包，块间保留重叠以维持上下文。"""

import re

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")


def _window_split(text: str, chunk_size: int) -> list[str]:
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def split_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """把长文本切成检索友好的片段列表。

    - 优先以空行（段落）为自然边界，贪心打包段落到不超过 chunk_size 的块；
    - 单段超长时按字符窗口硬切；
    - 相邻块之间保留 overlap 个字符的首尾衔接。
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须为正数")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap 必须处于 [0, chunk_size) 区间")

    text = text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT.split(text) if p.strip()]

    blocks: list[str] = []
    buffer = ""
    for para in paragraphs:
        if len(para) > chunk_size:
            if buffer:
                blocks.append(buffer)
                buffer = ""
            blocks.extend(_window_split(para, chunk_size))
            continue
        candidate = f"{buffer}\n\n{para}" if buffer else para
        if len(candidate) <= chunk_size:
            buffer = candidate
        else:
            blocks.append(buffer)
            buffer = para
    if buffer:
        blocks.append(buffer)

    if overlap == 0 or len(blocks) <= 1:
        return blocks

    merged = [blocks[0]]
    for prev, cur in zip(blocks, blocks[1:], strict=False):
        tail = prev[-overlap:]
        merged.append(f"{tail}{cur}")
    return merged
