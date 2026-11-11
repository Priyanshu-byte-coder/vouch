from app.pipeline.ingest import is_arxiv_id, normalize_arxiv_id


def test_valid_ids():
    for s in ["2602.23452", "2602.23452v2", "1706.03762", "https://arxiv.org/abs/2604.26835", "arXiv:2604.26835",
              "https://arxiv.org/pdf/2604.26835v1.pdf", "hep-th/9901001", "math.GT/0309136"]:
        assert is_arxiv_id(normalize_arxiv_id(s)), s


def test_invalid_ids():
    for s in ["hello", "", "2602", "10.1038/nature14539", "https://example.com/2602.23452", "2602.23452 extra"]:
        assert not is_arxiv_id(normalize_arxiv_id(s)), s
