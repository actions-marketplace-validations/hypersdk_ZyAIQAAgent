from langchain_core.documents import Document

from knowledge.retrieval import expand_queries, rerank


def test_expand_queries_adds_product_aliases() -> None:
    queries = expand_queries(
        "How do I block internet access?",
        product="PacketWolf",
    )
    assert len(queries) >= 2
    assert any("cilium" in query.lower() for query in queries)


def test_reranker_prefers_matching_content() -> None:
    matching = Document(
        page_content="Use a default deny egress network policy and allow DNS.",
        metadata={"product": "PacketWolf", "updated_at": "2026-07-30"},
    )
    unrelated = Document(
        page_content="Convert a VMware disk to qcow2.",
        metadata={"product": "HyperSDK", "updated_at": "2026-07-30"},
    )
    ranked = rerank(
        "PacketWolf default deny egress DNS",
        [(unrelated, 0.5), (matching, 0.5)],
        product="PacketWolf",
        limit=2,
    )
    assert ranked[0].document is matching
