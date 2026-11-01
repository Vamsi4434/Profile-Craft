from profile_craft.security import hash_password, is_hashed, verify_password


def test_hash_round_trip():
    h = hash_password("correct horse")
    assert is_hashed(h)
    assert "correct horse" not in h
    assert verify_password("correct horse", h)
    assert not verify_password("wrong", h)


def test_hashes_are_salted():
    assert hash_password("same") != hash_password("same")


def test_garbage_hash_does_not_verify():
    assert not verify_password("x", "plaintext")
    assert not verify_password("x", None)
