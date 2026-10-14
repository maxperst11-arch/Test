from magic_boot.config import Settings


def make(ids: str) -> Settings:
    return Settings(_env_file=None, telegram_bot_token="x", allowed_user_ids=ids)


def test_empty_whitelist_allows_everyone():
    assert make("").is_allowed(42)


def test_whitelist_parsing_and_check():
    settings = make("1, 2,3")
    assert settings.allowed_user_ids == [1, 2, 3]
    assert settings.is_allowed(2)
    assert not settings.is_allowed(4)
