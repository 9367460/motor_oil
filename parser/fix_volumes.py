"""
Постобработка: переводит французские метки объёма в .md файлах на русский язык.
Также регенерирует products.json и filters.json с обновлёнными объёмами.
"""
import json, os, re, sys

# Add parser dir to path to reuse scrape.py's parse_volume_label
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrape import parse_volume_label, slugify

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR  = os.path.join(SCRIPT_DIR, "..", "site", "content", "products")
DATA_DIR     = os.path.join(SCRIPT_DIR, "..", "site", "data")

def fix_md_file(path):
    """Read .md file, translate volume field, update title if needed, write back."""
    with open(path, encoding="utf-8") as f:
        content = f.read()

    # Extract old volume
    m = re.search(r'^volume:\s*"([^"]*)"', content, re.MULTILINE)
    if not m:
        return None, None  # no volume field

    old_vol = m.group(1)
    new_vol = parse_volume_label(old_vol)

    if old_vol == new_vol:
        return old_vol, None  # no change needed

    # Replace volume field
    content = re.sub(
        r'^(volume:\s*)"[^"]*"',
        f'\\g<1>"{new_vol}"',
        content, flags=re.MULTILINE
    )

    # Update title: replace old volume suffix with new
    # title usually ends with " <old_vol>" → " <new_vol>"
    if old_vol and old_vol != new_vol:
        content = content.replace(f' {old_vol}"', f' {new_vol}"', 1)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return old_vol, new_vol


def main():
    changed = 0
    skipped = 0
    translations = {}

    md_files = [f for f in os.listdir(CONTENT_DIR) if f.endswith(".md") and f != "_index.md"]
    print(f"Processing {len(md_files)} files...")

    for fname in sorted(md_files):
        path = os.path.join(CONTENT_DIR, fname)
        old_vol, new_vol = fix_md_file(path)
        if new_vol is not None:
            changed += 1
            translations[old_vol] = new_vol
            if changed <= 20:
                print(f"  {old_vol!r} → {new_vol!r}")
        else:
            skipped += 1

    print(f"\nChanged: {changed}, Skipped: {skipped}")
    if translations:
        print("\nTranslations applied:")
        for k, v in sorted(translations.items()):
            print(f"  {k!r} → {v!r}")

    # Regenerate products.json and filters.json from updated .md files
    print("\nRegenerating data files...")
    regenerate_data(md_files)


def regenerate_data(md_files):
    """Read all .md files and regenerate products.json and filters.json."""
    products = []
    brands_set = set()
    visc_set   = set()
    vol_set    = set()
    cats_out   = {}

    FRONT_RE = re.compile(r'^---\n(.*?)\n---', re.DOTALL)

    for fname in sorted(md_files):
        path = os.path.join(CONTENT_DIR, fname)
        with open(path, encoding="utf-8") as f:
            content = f.read()

        m = FRONT_RE.match(content)
        if not m:
            continue
        front = m.group(1)

        def get_field(name):
            r = re.search(rf'^{name}:\s*"?([^"\n]*)"?', front, re.MULTILINE)
            return r.group(1).strip() if r else ""

        def get_float(name):
            r = re.search(rf'^{name}:\s*([0-9.]+)', front, re.MULTILINE)
            return float(r.group(1)) if r else 0.0

        def get_list(name):
            r = re.search(rf'^{name}:\s*\[([^\]]*)\]', front, re.MULTILINE)
            if not r:
                return []
            return [x.strip().strip('"').strip("'") for x in r.group(1).split(",") if x.strip()]

        slug      = fname[:-3]
        title     = get_field("title")
        sku       = get_field("sku")
        brand     = get_field("brand")
        category  = get_field("category")
        cat_slug  = get_field("cat_slug")
        viscosity = get_field("viscosity")
        volume    = get_field("volume")
        price_eur = get_float("price_eur")
        price_rub = get_float("price_rub")
        image     = get_field("image")
        images    = get_list("images")
        url_sup   = get_field("url_supplier")

        prod = {
            "slug": slug, "title": title, "sku": sku,
            "brand": brand, "category": category, "cat_slug": cat_slug,
            "viscosity": viscosity, "volume": volume,
            "price_eur": price_eur, "price_rub": price_rub,
            "image": image, "images": images, "url_supplier": url_sup,
        }
        products.append(prod)

        if brand:    brands_set.add(brand)
        if viscosity: visc_set.add(viscosity)
        if volume:   vol_set.add(volume)
        if category and cat_slug:
            if cat_slug not in cats_out:
                cats_out[cat_slug] = {"name": category, "slug": cat_slug, "count": 0}
            cats_out[cat_slug]["count"] += 1

    # Write products.json
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "products.json"), "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    # Write categories.json
    with open(os.path.join(DATA_DIR, "categories.json"), "w", encoding="utf-8") as f:
        json.dump(list(cats_out.values()), f, ensure_ascii=False, indent=2)

    # Write filters.json — volumes: only real volume/size strings
    def is_real_volume(v):
        """True if the string represents a real quantity/size."""
        return bool(re.search(
            r'\d+\s*(?:L|мл|г|кг|м\b|мл|ml|kg|g\b|л\b)',
            v, re.IGNORECASE
        ))

    real_volumes = sorted([v for v in vol_set if is_real_volume(v)])

    filters = {
        "brands":      sorted(brands_set),
        "viscosities": sorted(visc_set),
        "volumes":     real_volumes,
    }
    with open(os.path.join(DATA_DIR, "filters.json"), "w", encoding="utf-8") as f:
        json.dump(filters, f, ensure_ascii=False, indent=2)

    print(f"  products.json: {len(products)} items")
    print(f"  categories.json: {len(cats_out)} categories")
    print(f"  filters.json: {len(brands_set)} brands, {len(visc_set)} viscosities, {len(real_volumes)} volumes")
    print(f"  Volumes sample: {real_volumes[:15]}")


if __name__ == "__main__":
    main()
