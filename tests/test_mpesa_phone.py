import pytest

from app.payments.mpesa_provider import normalize_phone


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("0712345678", "254712345678"),
        ("+254712345678", "254712345678"),
        ("254712345678", "254712345678"),
        ("0112345678", "254112345678"),
    ],
)
def test_normalize_phone_accepted_formats(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["12345", "not-a-phone", "+1-555-000-1111", ""])
def test_normalize_phone_rejects_invalid(raw):
    with pytest.raises(ValueError):
        normalize_phone(raw)
