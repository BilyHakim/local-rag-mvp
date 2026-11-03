"""Bounded public HTTP reads with DNS pinning, including every redirect hop."""
import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit, urljoin
import httpx


async def public_target(url: str):
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Gunakan URL HTTP/HTTPS publik tanpa kredensial")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in {80, 443}:
        raise ValueError("Hanya port 80/443 yang didukung")
    addresses = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, port, type=socket.SOCK_STREAM)
    ips = list(dict.fromkeys(item[4][0] for item in addresses))
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError("Alamat lokal/private tidak dapat diakses")
    return parsed, ips[0]


async def fetch_public(url: str, *, max_bytes=2_000_000):
    async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=8), trust_env=False) as client:
        for _ in range(5):
            parsed, ip = await public_target(url)
            # Connect to the validated IP, preserve hostname for HTTP Host and TLS SNI.
            target = httpx.URL(url).copy_with(host=ip, fragment=None)
            host = parsed.netloc.encode("idna").decode()
            async with client.stream("GET", target,
                                     headers={"Host": host, "User-Agent": "CompanyWorkspaceAudit/1.0", "Accept": "text/html,application/xml,text/plain,image/*"},
                                     extensions={"sni_hostname": parsed.hostname.encode("idna").decode()}) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("Redirect tanpa tujuan")
                    url = urljoin(url, location)
                    continue
                blocks, total = [], 0
                async for block in response.aiter_bytes():
                    total += len(block)
                    if total > max_bytes:
                        raise ValueError("Respons melebihi batas ukuran")
                    blocks.append(block)
                return {"url": url, "status": response.status_code, "headers": dict(response.headers), "body": b"".join(blocks)}
    raise ValueError("Terlalu banyak redirect")
