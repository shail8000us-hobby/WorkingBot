import os


def test_env_parsing_defaults():
    os.environ.pop("EXECUTE_ORDERS", None)
    os.environ.pop("DELTA_DRY_ORDERS", None)
    # Just verify this module can import and read env without exploding
    import importlib

    importlib.import_module("bot.run")
