import ssl
import certifi
from django.core.mail.backends.smtp import EmailBackend as DjangoEmailBackend

class SSLEmailBackend(DjangoEmailBackend):
    def _get_connection(self):
        connection = super()._get_connection()
        if self.use_tls:
            # Use certifi's certificate bundle
            connection.starttls(context=ssl.create_default_context(cafile=certifi.where()))
        return connection