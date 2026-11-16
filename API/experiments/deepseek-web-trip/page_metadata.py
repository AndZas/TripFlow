"""Read image and geo metadata from the public page for an option."""

from html.parser import HTMLParser
from http.client import HTTPException, HTTPSConnection
from ipaddress import ip_address
import json
import re
import socket
import ssl
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen


TLS = ssl.create_default_context()
IGNORED_WORDS = {"отель", "гостиница", "hotel", "музей", "museum", "государственный", "современного",
                 "искусства", "file", "boutique"}


class Head(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.images = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "meta":
            name = attributes.get("property") or attributes.get("name") or attributes.get("itemprop")
            if name and (value := attributes.get("content")):
                self.meta.setdefault(name.lower(), value.strip())
        elif tag == "img" and (alt := attributes.get("alt")) and (src := attributes.get("data-src") or attributes.get("src")):
            self.images.append((alt, src))


def same_subject(name, page_title):
    words = lambda value: set(re.findall(r"[^\W\d_]{4,}", value.casefold())) - IGNORED_WORDS
    wanted, found = words(name), words(page_title)
    matches = {word for word in wanted if any(word == other or len(word) >= 6 and word[:6] == other[:6]
                                            for other in found)}
    return bool(matches) and (len(matches) >= 2 or len(wanted) <= 2)


def read_head(url):
    parts = urlsplit(url)
    if parts.port not in (None, 443):
        return {}
    host = parts.hostname.encode("idna").decode()
    connection = HTTPSConnection(host, timeout=5, context=TLS)
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        address = next((addr[0] for *_, addr in addresses if ip_address(addr[0]).is_global
                        and not ip_address(addr[0]).is_multicast), None)
        if not address:
            return {}
        # TLS still verifies the original hostname. The remote destination stays on the checked IP.
        with socket.create_connection((address, 443), timeout=5) as tcp:
            connection.sock = TLS.wrap_socket(tcp, server_hostname=host)
            path = parts.path or "/"
            if parts.query:
                path += "?" + parts.query
            connection.request("GET", path, headers={"Accept": "text/html", "User-Agent": "TripFlow/1.0"})
            with connection.getresponse() as response:
                content_type = response.getheader("Content-Type", "")
                if response.status != 200 or "text/html" not in content_type.lower():
                    return {}
                data = response.read(196_608)
        head = Head()
        charset = re.search(r"charset=([\w-]+)", content_type, re.I)
        head.feed(data.decode(charset[1] if charset else "utf-8", "replace"))
        return {**head.meta, "images": head.images}
    except (OSError, HTTPException, ValueError, LookupError):
        return {}
    finally:
        connection.close()


def metadata_for(card):
    source = card["identity"]
    meta = read_head(source["url"])
    title = meta.get("og:title") or meta.get("twitter:title") or source["title"]
    if not same_subject(card["name"], title):
        return None, None
    image = meta.get("og:image:secure_url") or meta.get("og:image") or meta.get("twitter:image") or meta.get("image")
    if not image:
        image = next((src for alt, src in meta.get("images", []) if same_subject(card["name"], alt)), None)
    coords = None
    if position := meta.get("geo.position"):
        match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*[,;]\s*(-?\d+(?:\.\d+)?)\s*", position)
        if match and -90 <= (lat := float(match[1])) <= 90 and -180 <= (lon := float(match[2])) <= 180:
            coords = {**source, "lat": lat, "lon": lon, "quote": position}
    return urljoin(source["url"], image) if image else None, coords


def commons_photo(name, destination):
    params = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
              "gsrsearch": f"{name} {destination} filetype:bitmap", "gsrlimit": 6,
              "prop": "imageinfo", "iiprop": "url", "iiurlwidth": 640}
    url = "https://commons.wikimedia.org/w/api.php?" + urlencode(params)
    request = Request(url, headers={"User-Agent": "TripFlow/1.0 travel prototype"})
    try:
        with urlopen(request, timeout=7) as response:
            result = json.load(response)
        pages = result.get("query", {}).get("pages", {}).values()
        for page in sorted(pages, key=lambda item: item.get("index", 99)):
            title = page["title"]
            if (same_subject(name, title) and re.search(r"\.(?:jpe?g|webp|png)$", title, re.I)
                    and not re.search(r"logo|stamp|portfolio|логотип|монета|марка|портрет", title, re.I)):
                info = page["imageinfo"][0]
                return info.get("thumburl"), info.get("descriptionurl")
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        pass
    return None, None
