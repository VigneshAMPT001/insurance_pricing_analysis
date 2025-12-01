from bs4 import BeautifulSoup
from pathlib import Path
from icic_bs4_scraper import extract_premium_summary, extract_idv_values


if __name__ == "__main__":
    html_file = Path(__file__).parent / "icici_prem.html"

    with open(html_file, "r", encoding="utf-8") as f:
        html_content = f.read()

    print(f">>> Scraping HTML from: {html_file}")
    soup = BeautifulSoup(html_content, "html.parser")

    data = extract_premium_summary(soup)

    print(data)
