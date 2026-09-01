"""Reddit credential loader must stay fail-soft and file-first.

``_load_env`` is the only path that turns a cwd `.env` into praw credentials.
A parser that drops keys, treats comments as values, or lets process env
override a committed `.env` silently changes Node 6 from praw to the
rate-limited JSON feed (or the other way around).
"""

from __future__ import annotations

from gesh_core import sentiment_connector as sc


def test_load_env_reads_reddit_keys_from_dotenv(tmp_path, monkeypatch) -> None:
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "# comment should be ignored",
                "REDDIT_CLIENT_ID=file-id",
                "REDDIT_CLIENT_SECRET=file-secret",
                "REDDIT_USER_AGENT=gesh-financial/test",
                "UNRELATED=nope",
                "",
            ]
        )
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("REDDIT_USER_AGENT", raising=False)

    keys = sc._load_env()
    assert keys == {
        "REDDIT_CLIENT_ID": "file-id",
        "REDDIT_CLIENT_SECRET": "file-secret",
        "REDDIT_USER_AGENT": "gesh-financial/test",
    }
    assert "UNRELATED" not in keys


def test_load_env_file_wins_over_process_env(tmp_path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("REDDIT_CLIENT_ID=from-file\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REDDIT_CLIENT_ID", "from-process")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "process-secret")
    monkeypatch.delenv("REDDIT_USER_AGENT", raising=False)

    keys = sc._load_env()
    assert keys["REDDIT_CLIENT_ID"] == "from-file"
    assert keys["REDDIT_CLIENT_SECRET"] == "process-secret"
    assert "REDDIT_USER_AGENT" not in keys


def test_load_env_without_dotenv_uses_process_env(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REDDIT_CLIENT_ID", "env-id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "env-secret")
    monkeypatch.setenv("REDDIT_USER_AGENT", "env-ua")

    keys = sc._load_env()
    assert keys["REDDIT_CLIENT_ID"] == "env-id"
    assert keys["REDDIT_CLIENT_SECRET"] == "env-secret"
    assert keys["REDDIT_USER_AGENT"] == "env-ua"
