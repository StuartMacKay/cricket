from django.apps import AppConfig


class Config(AppConfig):
    name = "audits"

    def ready(self):
        from django.db.backends.signals import connection_created

        def enable_wal(sender, connection, **kwargs):
            if connection.vendor == "sqlite":
                connection.cursor().execute("PRAGMA journal_mode=WAL;")

        connection_created.connect(enable_wal)
