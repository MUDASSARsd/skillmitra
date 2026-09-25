import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://www.nqr.gov.in"

session = requests.Session()

# Browser-like headers
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    )
})

# --------------------------------------------------
# STEP 1: Open NQR first
# This gives us cookies + CSRF token
# --------------------------------------------------

page = session.get(
    BASE_URL + "/qualifications-search",
    timeout=20
)

print("Initial page status:", page.status_code)

soup = BeautifulSoup(page.text, "html.parser")

token_input = soup.find("input", {"name": "_token"})

if token_input is None:
    print("Could not find CSRF token.")
    exit()

token = token_input.get("value")

print("Token found:", token[:10] + "...")

# --------------------------------------------------
# STEP 2: Search
# --------------------------------------------------

params = {
    "_token": token,
    "qualificationTitle": "Line Patrolling Man",
    "awardingbody": "",
    "nsqflevel": "",
    "NationalHrs": "10000",
    "NationalHrsMin": "100"
}

response = session.get(
    BASE_URL + "/advance-search",
    params=params,
    timeout=20,
    headers={
        "Referer": BASE_URL + "/qualifications-search"
    }
)

print("\nSearch status:", response.status_code)
print("Search URL:", response.url)

# --------------------------------------------------
# STEP 3: Extract qualification links
# --------------------------------------------------

soup = BeautifulSoup(response.text, "html.parser")

found = []

for link in soup.find_all("a", href=True):

    href = link["href"]

    if "/qualifications/" in href:

        title = link.get_text(" ", strip=True)

        full_url = urljoin(BASE_URL, href)

        item = (title, full_url)

        if item not in found:
            found.append(item)

print("\nRESULTS")
print("=" * 60)

if not found:
    print("No qualification links found.")

else:
    for title, url in found:

        print("Title:", title)
        print("URL:", url)

        # Extract numeric NQR ID
        nqr_id = url.rstrip("/").split("/")[-1]

        print("NQR ID:", nqr_id)
        print("-" * 60)