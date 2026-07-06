from component_loader import load_component_module

redact = load_component_module("redact")


def test_redact_for_log_masks_sensitive_mapping_values():
    payload = {
        "password": "super-secret-password",
        "authorization": "Bearer ey.fake.token",
        "accountNumber": "123456789",
        "serviceLocationNumber": "987654321",
        "meterNumber": "555444333",
        "userId": "person@example.com",
        "utility": "ELECTRIC",
    }

    result = redact.redact_for_log(payload)

    assert "super-secret-password" not in result
    assert "ey.fake.token" not in result
    assert "123456789" not in result
    assert "987654321" not in result
    assert "555444333" not in result
    assert "person@example.com" not in result
    assert "ELECTRIC" in result
    assert "***REDACTED***" in result


def test_redact_for_log_masks_sensitive_text_patterns():
    result = redact.redact_for_log(
        "Bearer abc.def.ghi for person@example.com account 123456789"
    )

    assert "abc.def.ghi" not in result
    assert "person@example.com" not in result
    assert "123456789" not in result
    assert "Bearer ***REDACTED***" in result
    assert "***REDACTED_EMAIL***" in result
    assert "***REDACTED_NUMBER***" in result


def test_redact_value_leaves_harmless_values_readable():
    payload = {"industries": ["ELECTRIC"], "status": "COMPLETE"}

    assert redact.redact_value(payload) == payload
