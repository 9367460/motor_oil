"""
Обновление цен в рублях по текущему курсу ЦБ РФ.
Читает существующие .md файлы товаров и пересчитывает price_rub.
Не перезаписывает контент — только обновляет поле price_rub.
Также регенерирует products.json с актуальными ценами.
"""
import json, os, re, requests, warnings
warnings.filterwarnings("ignore")

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUT_DIR     = os.path.join(SCRIPT_DIR, "..", "site", "data")
CONTENT_DIR = os.path.join(SCRIPT_DIR, "..", "site", "content", "products")
CBR_API     = "https://www.cbr-xml-daily.ru/daily_json.js"


def get_rate():
    try:
        r = requests.get(CBR_API, timeout=10)
        rate = r.json()["Valute"]["EUR"]["Value"]
        print(f"EUR = {rate} RUB", flush=True)
        return rate
    except Exception as e:
        print(f"CBR error: {e}, using 91.30", flush=True)
        return 91.30


def calc_price(price_eur, rate):
    # price_eur × 3 (наценка 200%) × (курс ЦБ + 5)
    return round(price_eur * 3 * (rate + 5), 2)


def get_field(fm, name):
    m = re.search(rf'^{name}: "?([^"\n]*)"?', fm, re.MULTILINE)
    return m.group(1).strip('"') if m else ''


def get_float(fm, name):
    m = re.search(rf'^{name}: ([0-9.]+)', fm, re.MULTILINE)
    return float(m.group(1)) if m else 0.0


def main():
    rate = get_rate()
    products = []
    categories = {}
    brands = set()
    viscosities = set()

    md_files = [f for f in os.listdir(CONTENT_DIR)
                if f.endswith('.md') and f != '_index.md']
    print(f"Updating prices for {len(md_files)} products...", flush=True)

    updated = 0
    for fname in sorted(md_files):
        fpath = os.path.join(CONTENT_DIR, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()

        fm_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
        if not fm_match:
            continue
        fm = fm_match.group(1)

        price_eur = get_float(fm, 'price_eur')
        old_price_rub = get_float(fm, 'price_rub')

        if price_eur > 0:
            new_price_rub = calc_price(price_eur, rate)
            if abs(new_price_rub - old_price_rub) > 0.01:
                content = re.sub(
                    r'^price_rub: [0-9.]+',
                    f'price_rub: {new_price_rub}',
                    content,
                    flags=re.MULTILINE
                )
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write(content)
                updated += 1
        else:
            new_price_rub = old_price_rub

        # Collect data for JSON
        title = get_field(fm, 'title')
        sku = get_field(fm, 'sku')
        brand = get_field(fm, 'brand')
        category = get_field(fm, 'category')
        cat_slug = get_field(fm, 'cat_slug')
        viscosity = get_field(fm, 'viscosity')
        volume = get_field(fm, 'volume')
        image = get_field(fm, 'image')
        title_fr = get_field(fm, 'title_fr')

        body_match = re.search(r'^---\n.*?\n---\n\n?(.*)', content, re.DOTALL)
        desc = body_match.group(1).strip() if body_match else ''

        products.append({
            "slug": fname.replace('.md', ''),
            "title": title,
            "title_fr": title_fr,
            "sku": sku,
            "brand": brand,
            "category": category,
            "cat_slug": cat_slug,
            "viscosity": viscosity,
            "volume": volume,
            "price_eur": price_eur,
            "price_rub": new_price_rub,
            "image": image,
            "description": desc[:200] + "..." if len(desc) > 200 else desc
        })

        if category:
            if category not in categories:
                categories[category] = {"name": category, "slug": cat_slug, "count": 0}
            categories[category]["count"] += 1
        if brand:
            brands.add(brand)
        if viscosity:
            viscosities.add(viscosity)

    print(f"Updated {updated} prices, {len(products)} total products", flush=True)

    # Save data files
    products.sort(key=lambda x: x['slug'])
    categories_list = sorted(categories.values(), key=lambda x: x['name'])

    def viscosity_key(v):
        m = re.match(r'^(\d+)W(\d+)$', v)
        return (int(m.group(1)), int(m.group(2))) if m else (999, 999)

    with open(os.path.join(OUT_DIR, 'products.json'), 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    with open(os.path.join(OUT_DIR, 'categories.json'), 'w', encoding='utf-8') as f:
        json.dump(categories_list, f, ensure_ascii=False, indent=2)

    with open(os.path.join(OUT_DIR, 'filters.json'), 'w', encoding='utf-8') as f:
        json.dump({
            "brands": sorted(brands),
            "viscosities": sorted(viscosities, key=viscosity_key),
            "volumes": []
        }, f, ensure_ascii=False, indent=2)

    print("Saved products.json, categories.json, filters.json", flush=True)


if __name__ == '__main__':
    main()
