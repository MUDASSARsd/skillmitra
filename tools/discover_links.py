import requests
from bs4 import BeautifulSoup
import re

url = "https://www.nqr.gov.in/qualifications-search"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/153.0 Safari/537.36"
    )
}

response = requests.get(url, headers=headers, timeout=20)

print("Status:", response.status_code)

soup = BeautifulSoup(response.text, "html.parser")

qualification_links = {}

for a in soup.find_all("a", href=True):

    href = a["href"]

    # Find links like /qualifications/1284
    match = re.search(r"/qualifications/(\d+)", href)

    if match:
        nqr_id = match.group(1)

        if href.startswith("/"):
            full_url = "https://www.nqr.gov.in" + href
        else:
            full_url = href

        title = a.get_text(" ", strip=True)

        qualification_links[nqr_id] = {
            "title": title,
            "url": full_url
        }


print("\nQualification links found:", len(qualification_links))

print("\nFIRST RESULTS")
print("=" * 70)

for nqr_id, info in list(qualification_links.items())[:20]:
    print(
        "ID:", nqr_id,
        "| Title:", info["title"],
        "| URL:", info["url"]
    )