import uuid

from app.services.tokens import issue_manage_token, verify_manage_token

SECRET = "test-secret-key-not-for-real-use"


def test_manage_token_round_trip():
    donor_id = uuid.uuid4()
    token = issue_manage_token(SECRET, donor_id)
    assert verify_manage_token(SECRET, token) == donor_id


def test_manage_token_rejects_tampering():
    donor_id = uuid.uuid4()
    token = issue_manage_token(SECRET, donor_id)
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    assert verify_manage_token(SECRET, tampered) is None


def test_manage_token_rejects_wrong_secret():
    donor_id = uuid.uuid4()
    token = issue_manage_token(SECRET, donor_id)
    assert verify_manage_token("a-different-secret", token) is None
