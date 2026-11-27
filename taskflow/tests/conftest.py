import pytest

from app import create_app


def make_app(tmp_path, csrf=False):
    return create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": csrf,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(tmp_path / "test.db"),
            "SECRET_KEY": "test-secret",
        }
    )


@pytest.fixture()
def app(tmp_path):
    return make_app(tmp_path)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def other_client(app):
    """A second browser session with its own cookie jar."""
    return app.test_client()


@pytest.fixture()
def csrf_client(tmp_path):
    return make_app(tmp_path, csrf=True).test_client()
