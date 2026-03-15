import pytest
from pydantic import ValidationError
from src.short_url.schemas import URLCreate


def test_url_create_alias_success():
    data = {
        "long_url": "https://example.com",
        "custom_alias": "Valid-Alias_123"
    }
    schema = URLCreate(**data)
    assert schema.custom_alias == "Valid-Alias_123"


@pytest.mark.parametrize("bad_alias", [
    "alias with spaces",
    "alias!",
    "алиас_кириллицей",
    "alias@aaa",
    "some.dot"
])
def test_url_create_alias_error(bad_alias):
    data = {
        "long_url": "https://example.com",
        "custom_alias": bad_alias
    }
    with pytest.raises(ValidationError) as exc_info:
        URLCreate(**data)
    assert "Ожидается ^[a-zA-Z0-9_-]+$" in str(exc_info.value)


def test_url_create_empty_alias_ok():
    schema = URLCreate(long_url="https://example.com")
    assert schema.custom_alias is None
