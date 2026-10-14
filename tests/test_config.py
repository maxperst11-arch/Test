from magic_boot.config import Settings


def make(users: str) -> Settings:
    return Settings(_env_file=None, telegram_bot_token="x", allowed_users=users)


def test_empty_whitelist_allows_everyone():
    assert make("").is_allowed(42, None)


def test_whitelist_by_id_and_username():
    settings = make("123, @Axi_718")
    assert settings.is_allowed(123, None)
    assert settings.is_allowed(5, "axi_718")
    assert not settings.is_allowed(5, "stranger")
    assert not settings.is_allowed(5, None)
