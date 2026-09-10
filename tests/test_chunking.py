import pytest

from app.services.chunking import split_text


def test_empty_text_returns_no_chunks():
    assert split_text("") == []
    assert split_text("   \n\n  ") == []


def test_short_text_single_chunk():
    assert split_text("你好，世界") == ["你好，世界"]


def test_paragraph_packing():
    chunks = split_text("aaaa\n\nbbbb", chunk_size=10, overlap=0)
    assert chunks == ["aaaa\n\nbbbb"]


def test_paragraph_split_when_too_long():
    chunks = split_text("aaaa\n\nbbbb", chunk_size=4, overlap=0)
    assert chunks == ["aaaa", "bbbb"]


def test_long_paragraph_window_split():
    chunks = split_text("x" * 1200, chunk_size=500, overlap=0)
    assert len(chunks) == 3
    assert sum(len(c) for c in chunks) == 1200


def test_overlap_carries_tail_into_next_chunk():
    text = "A" * 600 + "\n\n" + "B" * 10
    chunks = split_text(text, chunk_size=500, overlap=20)
    assert chunks[0] == "A" * 500
    assert chunks[1] == "A" * 120          # 硬切余量 100A + 前块尾部 20A
    assert chunks[2] == "A" * 20 + "B" * 10  # 前块尾部 20A + 新段 10B


def test_chinese_text_chunks():
    text = "知识库问答系统。" * 100 + "\n\n" + "第二段内容。" * 50
    chunks = split_text(text, chunk_size=100, overlap=10)
    assert len(chunks) > 1
    assert any("知识库问答系统" in c for c in chunks)
    assert any("第二段内容" in c for c in chunks)


def test_invalid_params():
    with pytest.raises(ValueError):
        split_text("x", chunk_size=0)
    with pytest.raises(ValueError):
        split_text("x", chunk_size=10, overlap=10)
    with pytest.raises(ValueError):
        split_text("x", chunk_size=10, overlap=-1)
