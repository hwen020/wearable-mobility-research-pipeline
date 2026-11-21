from alembic import context
from app.db import engine


def migrate(connection):
    if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is None:
    with engine.begin() as connection:
        migrate(connection)
else:
    migrate(connection)
