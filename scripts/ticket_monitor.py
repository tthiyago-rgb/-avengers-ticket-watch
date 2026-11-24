#!/usr/bin/env python3
"""Conservative, read-only inspection of public ticket pages."""

from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import re
import sys

SOURCES = (
    "https://www.district.in/movies/seven-screen-s-cinemas-kilambakkam-chennai-CD1102122",
    "https://www.district.in/movies/avengers-doomsday-movie-tickets-in-chennai-MV176735",
    "https://ticketnew.com/movies/chennai/",
)
TITLE = re.compile(r"\bAvengers\s*:?\s*Doomsday\b", re.I)
DATE = re.compile(
    r"\b(?:17\s+December\s+2026|December\s+17,?\s+2026|17\s+Dec(?:ember)?\.?\s+2026|17[./-]12[./-]2026|2026-12-17)\b",
    re.I,
)
VENUE = re.compile(r"Seven\s+Screen[’']?s?\s+Cinemas?", re.I)
LANGUAGE = re.compile(r"\bEnglish\b", re.I)


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden_depth = 0
        self.parts = []
        self.hidden = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "svg", "template"):
            self.hidden_depth += 1
        elif tag in ("br", "p", "div", "li", "td", "tr", "h1", "h2", "h3") and not self.hidden_depth:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "svg", "template") and self.hidden_depth:
            self.hidden_depth -= 1
        elif tag in ("p", "div", "li", "td", "tr", "h1", "h2", "h3") and not self.hidden_depth:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.hidden_depth:
            self.hidden.append(data)
        else:
            self.parts.append(data)


def evidence(label, pattern, text):
    matches = list(pattern.finditer(text))
    if not matches:
        print(f"  {label}: not explicitly found")
        return False
    excerpts = []
    for match in matches[:2]:
        excerpt = re.sub(r"\s+", " ", text[max(0, match.start()-65):match.end()+85]).strip()
        excerpts.append(excerpt[:220])
    print(f"  {label}: found — " + " | ".join(excerpts))
    return True


def inspect(url):
    print(f"\nSource: {url}")
    request = Request(url, headers={"User-Agent": "AvengersTicketMonitor/1.0 (public page inspection)"})
    try:
        with urlopen(request, timeout=20) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            raw = response.read(2_000_001)
    except HTTPError as error:
        if error.code in (401, 403, 429):
            print(f"  Status: UNVERIFIED — HTTP {error.code}; access is restricted or rate limited.")
        else:
            print(f"  Status: CHECK FAILED — HTTP {error.code}.")
        return
    except (URLError, TimeoutError, OSError) as error:
        print(f"  Status: CHECK FAILED — request failed: {error}.")
        return

    if status >= 500:
        print(f"  Status: CHECK FAILED — HTTP {status}.")
        return
    if status >= 400:
        print(f"  Status: UNVERIFIED — HTTP {status}; page could not be inspected.")
        return
    if len(raw) > 2_000_000:
        print("  Status: UNVERIFIED — response exceeded the 2 MB inspection limit.")
        return
    if "html" not in content_type.lower():
        print(f"  Status: UNVERIFIED — response is not an HTML page ({content_type or 'unknown type'}).")
        return

    parser = VisibleText()
    try:
        parser.feed(raw.decode("utf-8", errors="replace"))
    except Exception as error:
        print(f"  Status: UNVERIFIED — could not parse page content: {error}.")
        return
    text = re.sub(r"[ \t\r]+", " ", "".join(parser.parts))
    folded = text.lower()
    if any(term in folded for term in ("captcha", "verify you are human", "access denied", "enable javascript", "javascript is required")):
        print("  Status: UNVERIFIED — page indicates a challenge, access restriction, or JavaScript requirement.")
        return
    if not text.strip():
        print("  Status: UNVERIFIED — no inspectable visible page text (possibly JavaScript-rendered).")
        return

    print(f"  HTTP: {status}; inspected visible HTML text ({len(text)} characters).")
    title_found = evidence("Movie", TITLE, text)
    date_found = evidence("Date", DATE, text)
    evidence("Venue", VENUE, text)
    evidence("Language", LANGUAGE, text)
    times = re.findall(r"\b(?:6(?::\d{2})?\s*(?:p\.?m\.?|PM)|18:\d{2})\b", text, re.I)
    print("  Showtime after 6:00 PM IST: " + (", ".join(dict.fromkeys(times[:5])) if times else "no matching time explicitly found"))

    if title_found and date_found:
        print("  Status: UNVERIFIED — movie and date text are present, but page content does not prove a matching show has two bookable seats.")
    else:
        print("  Status: NOT LISTED — exact movie and date were not both found in this page's visible content; this is not proof of site-wide unavailability.")


if __name__ == "__main__":
    print("Avengers: Doomsday — 17 December 2026 — Seven Screen’s Cinemas, Kilambakkam, Chennai")
    print("Request: 2 English tickets; showtime after 6:00 PM IST. Read-only public-page checks; no booking or notifications.")
    for source in SOURCES:
        inspect(source)
    print("\nAVAILABLE is never inferred from a movie listing; confirm seats through the official booking interface.")
