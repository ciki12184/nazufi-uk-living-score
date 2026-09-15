import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from bulk_common import request

OFSTED_LANDING = "https://www.gov.uk/government/statistical-data-sets/monthly-management-information-ofsteds-school-inspections-outcomes"
HMLR_LANDING = "https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads"
ONS_LATEST = "https://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/privaterentandhousepricesuk/latest"

def discover_latest_ofsted_csv():
    html = request(OFSTED_LANDING, timeout=60).text
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        href = urljoin(OFSTED_LANDING, a["href"])
        low = text.lower()
        if (
            "latest inspections as at" in low
            and href.lower().endswith(".csv")
        ):
            candidates.append((text, href))
    if not candidates:
        raise RuntimeError("Could not discover Ofsted latest-inspections CSV")
    # GOV.UK lists newest releases first. Do not guess a date from the filename.
    return {"label": candidates[0][0], "url": candidates[0][1]}

def discover_hmlr_current_month_csv():
    html = request(HMLR_LANDING, timeout=60).text
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split()).lower()
        href = urljoin(HMLR_LANDING, a["href"])
        if "current month as a csv file" in text:
            return {"label": a.get_text(" ", strip=True), "url": href}
    # HM Land Registry also uses a stable current-month endpoint.
    stable = "https://price-paid-data.publicdata.landregistry.gov.uk/pp-monthly-update-new-version.csv"
    return {"label": "HM Land Registry current month CSV", "url": stable}

def discover_ons_release_metadata():
    html = request(ONS_LATEST, timeout=60).text
    soup = BeautifulSoup(html, "html.parser")
    title = soup.find("h1")
    page_text = " ".join(soup.get_text(" ", strip=True).split())
    released = None
    m = re.search(r"Release date:\s*([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})", page_text, re.I)
    if m:
        released = m.group(1)
    return {
        "title": title.get_text(" ", strip=True) if title else "ONS latest housing release",
        "released": released,
        "url": ONS_LATEST,
    }

if __name__ == "__main__":
    print("Ofsted:", discover_latest_ofsted_csv())
    print("HMLR:", discover_hmlr_current_month_csv())
    print("ONS:", discover_ons_release_metadata())


ONS_RENT_DATASET = "https://www.ons.gov.uk/economy/inflationandpriceindices/datasets/priceindexofprivaterentsukmonthlypricestatistics"

def discover_latest_ons_rent_xlsx():
    html = request(ONS_RENT_DATASET, timeout=60).text
    soup = BeautifulSoup(html, "html.parser")
    # The dataset page lists newest edition first.
    edition_heading = soup.find(["h2","h3"], string=re.compile(r"edition of this dataset", re.I))
    if edition_heading:
        node = edition_heading.find_next("a", href=True)
        if node and "xlsx" in node.get_text(" ", strip=True).lower():
            return {
                "label": edition_heading.get_text(" ", strip=True),
                "url": urljoin(ONS_RENT_DATASET, node["href"])
            }
    for a in soup.find_all("a", href=True):
        if "xlsx" in a.get_text(" ", strip=True).lower():
            return {
                "label": "Latest ONS PIPR workbook",
                "url": urljoin(ONS_RENT_DATASET, a["href"])
            }
    raise RuntimeError("Could not discover latest ONS PIPR XLSX")
