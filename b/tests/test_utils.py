from coding_agent.utils import normalize_email

def test_normalize_email():
    assert normalize_email(" User@Example.com ") == "user@Example.com"
    assert normalize_email("TEST.User@Domain.com") == "test.user@Domain.com"
    assert normalize_email("  ") == ""
    assert normalize_email("noat") == "noat"
    assert normalize_email("") == ""
