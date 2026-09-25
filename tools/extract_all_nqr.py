import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time

# -----------------------------
# SETTINGS
# -----------------------------

EXCEL_FILE = "Qualifications.xlsx"

START_ID = 1280
END_ID = 1300

BASE_URL = "https://www.nqr.gov.in/qualifications/"

# -----------------------------
# 1. LOAD OUR NQR EXCEL
# -----------------------------

# Real headers are on Excel row 3
df = pd.read_excel(EXCEL_FILE, header=2)

print("Qualifications loaded:", len(df))

# Remove spaces and convert codes to strings
df["Code"] = df["Code"].astype(str).str.strip()

wanted_codes = set(df["Code"])

print("Unique codes:", len(wanted_codes))

# Create quick lookup:
# code -> Excel qualification information
# Find duplicate qualification codes
duplicates = df[df["Code"].duplicated(keep=False)]

print("\nDuplicate codes found:")
print(duplicates[["Title", "Code", "Sector Name", "Level"]].to_string(index=False))

# Lookup that supports multiple rows for the same code
excel_lookup = {
    code: group.to_dict("records")
    for code, group in df.groupby("Code")
}


# -----------------------------
# 2. HTTP SESSION
# -----------------------------

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/153.0 Safari/537.36"
    )
})


# -----------------------------
# 3. STORAGE
# -----------------------------

mapping_results = []
eligibility_results = []


# -----------------------------
# 4. VISIT NQR PAGES
# -----------------------------

for nqr_id in range(START_ID, END_ID + 1):

    url = BASE_URL + str(nqr_id)

    try:

        response = session.get(url, timeout=20)

        print(f"\nChecking {nqr_id} → {response.status_code}")

        if response.status_code != 200:
            continue

        soup = BeautifulSoup(response.text, "html.parser")

        text = soup.get_text(" ", strip=True)


        # -----------------------------
        # Extract qualification codes
        # -----------------------------

        page_codes = re.findall(
            r'\b\d{4}/[A-Za-z0-9&._()-]+/[A-Za-z0-9&._()-]+/[A-Za-z0-9&._()-]+\b',
            text
        )

        page_codes = list(dict.fromkeys(page_codes))


        # -----------------------------
        # Match against our Excel
        # -----------------------------

        matched_codes = [
            code for code in page_codes
            if code in wanted_codes
        ]


        if not matched_codes:
            print("No Excel match")
            time.sleep(0.5)
            continue


        print("MATCH:", matched_codes)


        # -----------------------------
        # Save mapping
        # -----------------------------

        for code in matched_codes:

            for info in excel_lookup[code]:

                mapping_results.append({
                    "nqr_id": nqr_id,
                    "code": code,
                    "title": info.get("Title"),
                    "sector": info.get("Sector Name"),
                    "nsqf_level": info.get("Level"),
                    "url": url
    })


        # -----------------------------
        # Find eligibility table
        # -----------------------------

        for table in soup.find_all("table"):

            headers = [
                th.get_text(" ", strip=True)
                for th in table.find_all("th")
            ]

            required = {
                "Criteria 1",
                "Criteria 2",
                "Experience",
                "Training Qualification"
            }

            if required.issubset(set(headers)):

                rows = table.find_all("tr")[1:]

                for code in matched_codes:

                    route_number = 1

                    for row in rows:

                        cells = [
                            cell.get_text(" ", strip=True)
                            for cell in row.find_all(["td", "th"])
                        ]

                        if len(cells) >= 4:

                            eligibility_results.append({
                                "nqr_id": nqr_id,
                                "code": code,
                                "route": route_number,
                                "criteria_1": cells[0],
                                "criteria_2": cells[1],
                                "experience": cells[2],
                                "training_qualification": cells[3]
                            })

                            route_number += 1

                break


        time.sleep(0.5)


    except Exception as e:

        print("ERROR:", nqr_id, e)


# -----------------------------
# 5. SAVE RESULTS
# -----------------------------

mapping_df = pd.DataFrame(mapping_results)

eligibility_df = pd.DataFrame(eligibility_results)


mapping_df.to_csv(
    "qualification_mapping.csv",
    index=False
)

eligibility_df.to_csv(
    "eligibility_routes.csv",
    index=False
)


print("\n==============================")
print("FINISHED")
print("==============================")

print("Qualifications matched:", len(mapping_df))

print("Eligibility routes:", len(eligibility_df))

print("\nCreated:")
print("qualification_mapping.csv")
print("eligibility_routes.csv")