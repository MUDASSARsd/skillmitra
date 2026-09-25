import requests
from bs4 import BeautifulSoup
import pandas as pd

url = "https://www.nqr.gov.in/qualifications/12190"

response = requests.get(url, timeout=20)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

eligibility_rows = []

# Search every table instead of assuming table 0
for table in soup.find_all("table"):

    headers = [
        cell.get_text(" ", strip=True)
        for cell in table.find_all("th")
    ]

    # Check whether this is the eligibility table
    if (
        "Criteria 1" in headers
        and "Criteria 2" in headers
        and "Experience" in headers
        and "Training Qualification" in headers
    ):

        print("Eligibility table found!")

        for tr in table.find_all("tr")[1:]:

            cells = [
                cell.get_text(" ", strip=True)
                for cell in tr.find_all(["td", "th"])
            ]

            if len(cells) >= 4:
                eligibility_rows.append({
                    "nqr_id": 12190,
                    "criteria_1": cells[0],
                    "criteria_2": cells[1],
                    "experience": cells[2],
                    "training_qualification": cells[3]
                })

        break


# Convert to dataframe
df = pd.DataFrame(eligibility_rows)

print("\nExtracted eligibility:")
print(df)

# Save
df.to_csv("eligibility.csv", index=False)

print("\nSaved successfully as eligibility.csv")