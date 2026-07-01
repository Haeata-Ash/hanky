import hanky.hanky as hanky_module
from hanky.config import Config
from hanky.hanky import HankyPipeline


def test_provided_config_object_is_used():
    cfg = Config(ANKI_DB_PATH="/custom/collection.anki2", ALLOW_DUPLICATES=True)

    app = HankyPipeline(cfg)

    assert app.config is cfg
    assert app.config.ANKI_DB_PATH == "/custom/collection.anki2"
    assert app.config.ALLOW_DUPLICATES is True


def test_no_config_falls_back_to_default_config(monkeypatch, tmp_path):
    monkeypatch.setattr(
        hanky_module, "_DEFAULT_CONFIG_PATH", tmp_path / "no_such_config.toml"
    )

    app = HankyPipeline()

    assert app.config == Config()


def test_provided_config_takes_precedence_over_default_file(monkeypatch, tmp_path):
    toml = tmp_path / "hanky.toml"
    toml.write_text("ALLOW_DUPLICATES = true\n")
    monkeypatch.setattr(hanky_module, "_DEFAULT_CONFIG_PATH", toml)

    cfg = Config(ALLOW_DUPLICATES=False)
    app = HankyPipeline(cfg)

    # an explicitly supplied config must win, the default file is never read
    assert app.config is cfg
    assert app.config.ALLOW_DUPLICATES is False


def test_config_property_is_cached(monkeypatch, tmp_path):
    monkeypatch.setattr(
        hanky_module, "_DEFAULT_CONFIG_PATH", tmp_path / "no_such_config.toml"
    )

    app = HankyPipeline()

    assert app.config is app.config


def test_default_config_file_is_loaded_when_present(monkeypatch, tmp_path):
    toml = tmp_path / "hanky.toml"
    toml.write_text('ANKI_DB_PATH = "/from/file.anki2"\nALLOW_DUPLICATES = true\n')
    monkeypatch.setattr(hanky_module, "_DEFAULT_CONFIG_PATH", toml)

    app = HankyPipeline()

    assert app.config.ANKI_DB_PATH == "/from/file.anki2"
    assert app.config.ALLOW_DUPLICATES is True
