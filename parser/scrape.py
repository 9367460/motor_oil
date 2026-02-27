"""
Парсер каталога racinglubes.fr
Использует JSON-LD structured data для получения данных о товарах.
Пересчитывает цены: цена_поставщика * курс_ЦБ * 4 + 5 руб
"""
import json
import os
import re
import time
import cloudscraper
from bs4 import BeautifulSoup

scraper = cloudscraper.create_scraper()
BASE_URL = "https://www.racinglubes.fr"
CBR_API = "https://www.cbr-xml-daily.ru/daily_json.js"

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "site", "data")
CONTENT_DIR = os.path.join(os.path.dirname(__file__), "..", "site", "content", "products")


def get_cbr_rate(currency="EUR"):
    r = scraper.get(CBR_API)
    r.raise_for_status()
    return r.json()["Valute"][currency]["Value"]


def compute_price_rub(price_eur, rate):
    """цена поставщика в EUR * курс ЦБ * 4 + 5 рублей"""
    return round(price_eur * rate * 4 + 5, 2)


def slugify(text):
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_]+", "-", text).strip("-")


def get_json_ld(soup, ld_type):
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and data.get("@type") == ld_type:
                return data
        except Exception:
            pass
    return None


def get_category_product_urls(cat_url):
    """Возвращает все URL товаров из категории, обходя пагинацию."""
    urls = []
    page = 1
    while True:
        url = f"{cat_url}?p={page}" if page > 1 else cat_url
        try:
            r = scraper.get(url)
            r.raise_for_status()
        except Exception as e:
            print(f"  Error fetching {url}: {e}")
            break
        soup = BeautifulSoup(r.text, "html.parser")
        products = soup.select("article.product-miniature")
        if not products:
            break
        for art in products:
            a = art.select_one("a.product-thumbnail, .product-title a")
            if a and a.get("href"):
                href = a["href"].split("#")[0]
                if href not in urls:
                    urls.append(href)
        # Check if next page exists
        next_link = soup.select_one("a[rel=next], .pagination .next a, a[aria-label=Next]")
        if not next_link:
            break
        page += 1
        time.sleep(0.3)
    return urls


def parse_product(url, rate):
    """Парсит страницу товара через JSON-LD, возвращает словарь или None."""
    try:
        r = scraper.get(url)
        r.raise_for_status()
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    # --- JSON-LD structured data ---
    product_ld = get_json_ld(soup, "Product")
    if not product_ld:
        return None

    title = product_ld.get("name", "").strip()
    sku = str(product_ld.get("sku", "")).strip()
    description = re.sub(r"<[^>]+>", " ", product_ld.get("description", "")).strip()
    category = product_ld.get("category", "").strip()
    brand = ""
    brand_obj = product_ld.get("brand")
    if isinstance(brand_obj, dict):
        brand = brand_obj.get("name", "")

    # Image — prefer large_default
    img = product_ld.get("image", "")
    if isinstance(img, list):
        img = img[0] if img else ""
    img = img.replace("home_default", "large_default")

    # Price from offers
    price_eur = 0.0
    offers = product_ld.get("offers", {})
    if isinstance(offers, dict):
        try:
            price_eur = float(offers.get("price", 0))
        except (ValueError, TypeError):
            pass

    if not title or price_eur <= 0:
        return None

    # Clean URL for slug: extract numeric ID from path
    slug_match = re.search(r"/(\d+)-", url)
    product_id = slug_match.group(1) if slug_match else sku
    slug = f"{product_id}-{slugify(title)}"[:80]

    # Category slug for URL prefix
    cat_slug = slugify(category) if category else "products"

    # All images from page
    images = [img]
    for img_tag in soup.select(".product-images img, #product-images-large img"):
        src = img_tag.get("src", "")
        if src and src not in images:
            images.append(src.replace("medium_default", "large_default"))

    price_rub = compute_price_rub(price_eur, rate)

    return {
        "id": product_id,
        "slug": slug,
        "title": title,
        "sku": sku,
        "brand": brand,
        "category": category,
        "cat_slug": cat_slug,
        "description": description,
        "price_eur": price_eur,
        "price_rub": price_rub,
        "image": img,
        "images": images[:4],
        "url_supplier": url,
    }


def get_leaf_categories():
    """Возвращает список URL листовых категорий (с товарами)."""
    r = scraper.get(BASE_URL)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    cats = []
    seen = set()
    # Category links from navigation: /ID-slug pattern (no file extension)
    for a in soup.find_all("a", href=re.compile(r"racinglubes\.fr/\d+-[a-z]")):
        href = a["href"].split("#")[0]
        if href in seen:
            continue
        # Skip parent categories (they have sub-categories) — we'll filter below
        cat_id = re.search(r"/(\d+)-", href)
        if cat_id and href not in seen:
            seen.add(href)
            name = a.get_text(strip=True)
            cats.append({"url": href, "name": name})

    return cats


def main():
    print("Получаю курс EUR/RUB от ЦБ РФ...")
    rate = get_cbr_rate("EUR")
    print(f"Курс EUR: {rate:.4f} RUB")

    print("Получаю список категорий...")
    categories = get_leaf_categories()
    print(f"Найдено категорий: {len(categories)}")

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(CONTENT_DIR, exist_ok=True)

    all_products = []
    seen_urls = set()

    for i, cat in enumerate(categories):
        cat_name = cat["name"]
        cat_url = cat["url"]
        print(f"\n[{i+1}/{len(categories)}] Категория: {cat_name}")
        prod_urls = get_category_product_urls(cat_url)
        print(f"  Найдено товаров: {len(prod_urls)}")

        for j, url in enumerate(prod_urls):
            # Normalize URL: strip anchors and add .html if needed
            url_clean = url.split("#")[0]
            if not url_clean.endswith(".html"):
                url_clean = url_clean + ".html"
            if url_clean in seen_urls:
                continue
            seen_urls.add(url_clean)

            print(f"  [{j+1}/{len(prod_urls)}] {url_clean[-60:]}", end=" ... ", flush=True)
            prod = parse_product(url_clean, rate)
            if prod:
                all_products.append(prod)
                write_content_page(prod)
                print(f"OK — {prod['price_rub']:.0f} руб")
            else:
                print("skip")
            time.sleep(0.2)

    # Save products.json
    out_file = os.path.join(OUT_DIR, "products.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_products, f, ensure_ascii=False, indent=2)

    # Save categories list
    cats_out = {}
    for p in all_products:
        cat = p["category"]
        slug = p["cat_slug"]
        if slug not in cats_out:
            cats_out[slug] = {"name": cat, "slug": slug, "count": 0}
        cats_out[slug]["count"] += 1
    with open(os.path.join(OUT_DIR, "categories.json"), "w", encoding="utf-8") as f:
        json.dump(list(cats_out.values()), f, ensure_ascii=False, indent=2)

    print(f"\nГотово! Всего товаров: {len(all_products)}")
    print(f"Данные: {out_file}")
    print(f"Страницы: {CONTENT_DIR}")


def write_content_page(prod):
    """Создаёт markdown-страницу товара для Hugo."""
    slug = prod["slug"]
    page_path = os.path.join(CONTENT_DIR, f"{slug}.md")
    title = prod["title"].replace('"', '\\"')
    with open(page_path, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(f'title: "{title}"\n')
        f.write(f'sku: "{prod["sku"]}"\n')
        f.write(f'brand: "{prod["brand"]}"\n')
        f.write(f'category: "{prod["category"]}"\n')
        f.write(f'cat_slug: "{prod["cat_slug"]}"\n')
        f.write(f'price_eur: {prod["price_eur"]}\n')
        f.write(f'price_rub: {prod["price_rub"]}\n')
        f.write(f'image: "{prod["image"]}"\n')
        images_yaml = "\n".join(f'  - "{img}"' for img in prod["images"])
        f.write(f'images:\n{images_yaml}\n')
        f.write(f'supplier_url: "{prod["url_supplier"]}"\n')
        f.write(f'draft: false\n')
        f.write("---\n\n")
        f.write(prod["description"])


if __name__ == "__main__":
    main()
