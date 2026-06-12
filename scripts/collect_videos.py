import requests
from bs4 import BeautifulSoup
import json
import os

BASE_URL = "https://stop-piramida.kz/videos"

CATEGORIES = [
    "lzheturizm",
    "lzhezarabotok",
    "stop-mfo",
    "dropperstvo",
    "lzhe-kredityi",
    "kriptoriski",
    "lzheyuristyi",
    "fishing",
    "lzheprodavczyi",
    "lzhexalyal",
    "telefonnoe-moshennichestvo",
    "roditelyam-na-zametku",
    "rabota-za-graniczej",
    "fejkovyie-vyiplatyi",
    "romanticheskoe-moshennichestvo",
    "riski-v-setevom-marketinge",
    "finansovyie-piramidyi",
]

OUT_DIR = "data/metadata"
os.makedirs(OUT_DIR, exist_ok=True)


def fetch_category(category: str):
    url = f"{BASE_URL}/{category}"
    print(f"[+] Parsing {url}")

    html = requests.get(url, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")

    results = []

    for card in soup.select(".videoBoxHover"):
        parent = card.parent

        desc_block = parent.select_one(".descVideo__text")
        description = desc_block.get_text(" ", strip=True) if desc_block else ""

        item = {
            "category": category,
            "title": card.get("data-v-title"),
            "vimeo": card.get("data-v-url"),
            "url": card.get("data-v-fullurl"),
            "description": description
        }

        results.append(item)

    return results


def save_jsonl(category: str, data: list):
    path = os.path.join(OUT_DIR, f"{category}.jsonl")

    with open(path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"[✓] Saved {len(data)} items -> {path}")


def main():
    all_count = 0

    for cat in CATEGORIES:
        try:
            data = fetch_category(cat)
            save_jsonl(cat, data)
            all_count += len(data)
        except Exception as e:
            print(f"[!] Error in {cat}: {e}")

    print(f"\nDONE. Total videos: {all_count}")


if __name__ == "__main__":
    main()