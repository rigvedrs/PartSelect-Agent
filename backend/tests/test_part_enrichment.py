from app.agent.tools.part_enrichment import needs_enrichment


def test_needs_enrichment_missing_price():
    assert needs_enrichment({"ps_number": "PS1", "name": "Filter", "price": None}) is True


def test_needs_enrichment_zero_price():
    assert needs_enrichment({"ps_number": "PS1", "name": "Filter", "price": 0}) is True


def test_needs_enrichment_ok():
    assert needs_enrichment({"ps_number": "PS1", "name": "Filter", "price": 12.99}) is False
