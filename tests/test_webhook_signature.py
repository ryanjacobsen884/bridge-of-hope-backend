import pytest

from app.payments.test_provider import TestProvider


def test_valid_signature_accepted():
    provider = TestProvider()
    assert provider.verify_webhook(headers={"x-test-signature": "test-signature"}, raw_body=b"{}") is True


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"x-test-signature": "wrong"},
        {"x-test-signature": ""},
    ],
)
def test_invalid_signature_rejected(headers):
    provider = TestProvider()
    assert provider.verify_webhook(headers=headers, raw_body=b"{}") is False
