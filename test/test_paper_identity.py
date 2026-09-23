from src.paper_identity import canonical_id, lookup_path, register


def test_canonical_id_unifies_arxiv_abs_and_doi():
    abs_url = "https://arxiv.org/abs/2608.03392"
    doi_url = "https://doi.org/10.48550/arxiv.2608.03392"
    assert canonical_id(abs_url, "Self-Evolving Coding Agents") == "arxiv:2608.03392"
    assert canonical_id(doi_url, "Self-Evolving Coding Agents") == "arxiv:2608.03392"


def test_canonical_id_uses_title_for_zenodo_duplicates():
    a = canonical_id("https://doi.org/10.5281/zenodo.21097270", "Self-Evolving World Models for LLM Agent Planning")
    b = canonical_id("https://doi.org/10.5281/zenodo.21097471", "Self-Evolving World Models for LLM Agent Planning")
    assert a == b
    assert a.startswith("title:")


def test_lookup_path_finds_registered_id(tmp_path):
    paper = tmp_path / "raw" / "paper"
    paper.mkdir(parents=True)
    path = paper / "self-evolving-coding-agents.md"
    path.write_text("x", encoding="utf-8")
    sidecar = tmp_path / "identity.json"
    register("arxiv:2608.03392", str(path), "https://arxiv.org/abs/2608.03392", path=sidecar)
    found = lookup_path(
        "https://doi.org/10.48550/arxiv.2608.03392",
        "Self-Evolving Coding Agents",
        raw_dir=paper,
        identity_path=sidecar,
    )
    assert found == path
