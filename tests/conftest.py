import os
import pytest


@pytest.fixture(scope="session", autouse=True)
def enable_md2beauty_debug():
    os.environ["MD2BEAUTY_DEBUG"] = "1"
    yield
    # do not unset to allow post-session hooks to still report with debug