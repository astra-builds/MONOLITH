"""Temp-DB fixture so tests don't mutate the dev DB."""
import os
import tempfile

# Set MONOLITH_DB before any app modules are imported so DB_PATH binds to the temp file.
_fd, _path = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["MONOLITH_DB"] = _path

import pytest  # noqa: E402

@pytest.fixture(scope="session", autouse=True)
def cleanup_temp_db():
    yield
    try:
        os.unlink(_path)
    except OSError:
        pass
