"""Rate limiting keyed on the real visitor IP.

DRF's default `get_ident` trusts the whole X-Forwarded-For header, which any client can forge:
sending a different fake IP with each request would sidestep the login limit. Here the IP comes
only from a header that the hosting proxy overwrites (settings.CLIENT_IP_HEADER, for example
Cloudflare's CF-Connecting-IP on Render), or else from the socket address.
"""

import ipaddress

from django.conf import settings
from rest_framework.throttling import ScopedRateThrottle


def client_ip(request) -> str:
    header = settings.CLIENT_IP_HEADER
    value = (request.META.get(header, "") if header else "") or request.META.get("REMOTE_ADDR", "")
    value = value.split(",")[0].strip()
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return "unknown"


class ClientIPScopedThrottle(ScopedRateThrottle):
    def get_ident(self, request):
        return client_ip(request)
