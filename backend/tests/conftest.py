import os
import uuid
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.database import Base


@pytest.fixture
def postgres():
    url = os.getenv('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('Set TEST_POSTGRES_URL to a disposable localhost test database')
    parsed = make_url(url)
    assert parsed.host in {'localhost', '127.0.0.1'} and parsed.database in {'integrity', 'test_engine'}, 'Only a disposable local database is allowed'
    schema = 'test_' + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text('CREATE SCHEMA ' + schema))
    engine = create_engine(url, connect_args={'options': '-csearch_path=' + schema})
    Base.metadata.create_all(engine)
    try:
        yield engine, admin
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text('DROP SCHEMA ' + schema + ' CASCADE'))
        admin.dispose()

