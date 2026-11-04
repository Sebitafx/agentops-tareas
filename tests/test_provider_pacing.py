import pytest

from harness import provider_http as transport


def test_groq_calls_are_paced_without_retry(monkeypatch):
    monkeypatch.setenv("GROQ_MIN_INTERVAL_SECONDS", "65")
    monkeypatch.setattr(transport, "_last_groq_started", None)
    times = iter([100.0, 110.0, 165.0])
    sleeps = []
    monkeypatch.setattr(transport.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(transport.time, "sleep", sleeps.append)
    transport.pace_groq()
    transport.pace_groq()
    assert sleeps == [55.0]


@pytest.mark.parametrize("value", ["invalid", "-1", "121"])
def test_invalid_pacing_is_rejected(monkeypatch, value):
    monkeypatch.setenv("GROQ_MIN_INTERVAL_SECONDS", value)
    with pytest.raises(transport.CheckError, match="INVALID_PROVIDER_PACING"):
        transport.pace_groq()
