from coding_agent.rate_limit import TokenRateLimiter

def test_reserves_tokens_within_budget() -> None:
    limiter = TokenRateLimiter(10)
    limiter.reserve(4)
    limiter.reserve(6)
    assert sum(tokens for _, tokens in limiter.entries) == 10

def test_rejects_request_larger_than_minute_budget() -> None:
    limiter = TokenRateLimiter(10)
    try:
        limiter.reserve(11)
    except ValueError as error:
        assert "MISTRAL_TPM" in str(error)
    else:
        raise AssertionError("Expected an oversized request to be rejected")
