import json
import os
import re
import requests
from bs4 import BeautifulSoup

# API ссылка Центрального банка РФ для получения курса валют
CBR_API = "https://www.cbr-xml-daily.ru/daily_json.js"


def get_cbr_rate(currency="EUR"):
    """Возвращает курс валюты к рублю по данным ЦБ.
    По умолчанию берётся курс евро.
    """
    r = requests.get(CBR_API)
    r.raise_for_status()
    data = r.json()
    return data["Valute"][currency]["Value"]


def parse_product(url):
    """Парсит страницу товара, возвращает словарь с полями.
    Эта функция требует адаптации под реальную структуру сайта.
    """
    r = requests.get(url)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.select_one("h1.product-title").text.strip()
    sku = soup.select_one(".product-sku").text.strip()
    descr = soup.select_one(".product-description").get_text("\n", strip=True)
    price_str = soup.select_one(".price").text
    price = float(re.sub(r"[^\d,\.]", "", price_str).replace(",", "."))
    img = soup.select_one(".product-image img")["src"]
    return dict(
        title=title,
        sku=sku,
        descr=descr,
        supplier_price=price,
        image_url=img,
    )


def crawl_catalog(start_url):
    """Обходит каталог, собирает список товаров."""
    products = []
    to_visit = [start_url]
    visited = set()
    while to_visit:
        url = to_visit.pop()
        if url in visited:
            continue
        visited.add(url)
        r = requests.get(url)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # ссылки на товары
        for a in soup.select("a.product-link"):
            products.append(parse_product(a["href"]))
        # пагинация
        for a in soup.select("a.next"):
            to_visit.append(a["href"])
    return products


def compute_price(sup_price, rate):
    """Пересчёт цены по формуле поставщик + 300% * курс + 5 руб."""
    return sup_price + sup_price * 3 * rate + 5


if __name__ == "__main__":
    rate = get_cbr_rate("EUR")
    items = crawl_catalog("https://www.racinglubes.fr/catalogue")
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "site", "data"), exist_ok=True)
    output_file = os.path.join(os.path.dirname(__file__), "..", "site", "data", "products.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump([{
            **it,
            "price_rub": f"{compute_price(it['supplier_price'], rate):.2f}"
        } for it in items], f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(items)} products to {output_file}")
