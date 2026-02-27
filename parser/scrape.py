"""
Парсер каталога racinglubes.fr — ПОЛНЫЙ
- Все категории, все страницы пагинации
- Перевод на русский (словарь + Google Translate для описаний)
- Метаданные для фильтров: вязкость, объём, бренд
- Дедупликация по ID товара
"""
import json, os, re, time, warnings
warnings.filterwarnings("ignore")

import cloudscraper
from bs4 import BeautifulSoup
try:
    from deep_translator import GoogleTranslator
    TRANSLATE_AVAIL = True
except ImportError:
    TRANSLATE_AVAIL = False

scraper = cloudscraper.create_scraper()
BASE_URL = "https://www.racinglubes.fr"
CBR_API  = "https://www.cbr-xml-daily.ru/daily_json.js"

OUT_DIR     = os.path.join(os.path.dirname(__file__), "..", "site", "data")
CONTENT_DIR = os.path.join(os.path.dirname(__file__), "..", "site", "content", "products")

# ── Словарь: французские термины → русские ───────────────────────────────────
FR_TO_RU = [
    # Полные фразы — сначала (порядок важен)
    ("Huile Moteur Compétition",               "Моторное масло Спорт"),
    ("Huile moteur compétition",               "Моторное масло Спорт"),
    ("Huile Moteur Véhicules Anciens",         "Моторное масло Классика"),
    ("Huile Moteur",                           "Моторное масло"),
    ("Huile moteur",                           "Моторное масло"),
    ("Huile Boite de Vitesse",                 "Масло КПП"),
    ("Huile Boîte de Vitesse",                 "Масло КПП"),
    ("Huile boite de vitesse",                 "Масло КПП"),
    ("Huile boîte de vitesse",                 "Масло КПП"),
    ("Huile de Pont",                          "Масло для моста"),
    ("Huile Direction Assistée",               "Масло ГУР"),
    ("Liquide de Frein",                       "Тормозная жидкость"),
    ("Liquide de frein",                       "Тормозная жидкость"),
    ("Liquide de Refroidissement",             "Охлаждающая жидкость"),
    ("Liquide de refroidissement",             "Охлаждающая жидкость"),
    ("Lave-Glace",                             "Омыватель стёкол"),
    ("Lave-glace",                             "Омыватель стёкол"),
    ("Stop Fuite Radiateur",                   "Стоп-течь радиатора"),
    ("Stop Fuite Direction Assistée",          "Стоп-течь ГУР"),
    ("Stop Fuite Boite Manuelle",              "Стоп-течь КПП"),
    ("Stop Fumée",                             "Стоп-дым"),
    ("Stop Fuite",                             "Стоп-течь"),
    ("Anti Usure Boîte de Vitesses",           "Антиизнос КПП"),
    ("Anti-Usure Moteur",                      "Антиизнос мотора"),
    ("Anti-Usure",                             "Антиизнос"),
    ("Nettoyant Prévidange",                   "Промывка перед заменой масла"),
    ("Nettoyant Injecteurs Essence",           "Очиститель инжекторов"),
    ("Nettoyant Carburateur Essence Spray",    "Очиститель карбюратора"),
    ("Nettoyant Radiateur",                    "Очиститель радиатора"),
    ("Nettoyant",                              "Очиститель"),
    ("Poussoirs Hydrauliques",                 "Гидравлические толкатели"),
    ("Maxi Compression",                       "Максимальная компрессия"),
    ("Full Metal",                             "Full Metal"),
    ("Traitement Carburant Essence",           "Присадка к бензину"),
    ("Pass Contrôle Technique Essence",        "Прохождение техосмотра бензин"),
    ("Pass Contrôle Technique Diesel",         "Прохождение техосмотра дизель"),
    ("Substitut de Plomb",                     "Заменитель свинца"),
    ("Additif Carburant",                      "Присадка к топливу"),
    ("Additif",                                "Присадка"),
    ("B2 Traitement Huile",                    "Присадка к маслу B2"),
    ("Race Oil",                               "Гоночное масло"),
    ("High Performance",                       "Высокопроизводительное"),
    ("Premium Fuel Economy",                   "Premium Fuel Economy"),
    ("Racing",                                 "Racing"),
    ("Full Synthetic",                         "Полностью синтетическое"),
    ("Synthèse",                               "Синтетика"),
    ("Semi-synthèse",                          "Полусинтетика"),
    ("Synthétique",                            "Синтетическое"),
    ("Minérale",                               "Минеральное"),
    ("Essence",                                "Бензин"),
]

CATEGORY_RU = {
    "Huile Moteur":                                    "Моторное масло",
    "Huile Boite de Vitesse et Pont":                  "Масло КПП и мост",
    "Huile Boîte de Vitesse et Pont":                  "Масло КПП и мост",
    "Freinage - Direction assistée":                   "Тормоза и ГУР",
    "Freinage - Direction Assistée":                   "Тормоза и ГУР",
    "Freinage - Direction assistée compétition":       "Тормоза и ГУР Спорт",
    "Freinage - Direction Assistée Véhicules Anciens": "Тормоза и ГУР Классика",
    "Additifs":                                        "Присадки",
    "Additifs Compétition":                            "Присадки Спорт",
    "Additifs Véhicules Anciens":                      "Присадки Классика",
    "AdBlue":                                          "AdBlue (мочевина)",
    "Liquide de Refroidissement":                      "Охлаждающая жидкость",
    "Liquide de refroidissement -":                    "Охлаждающая жидкость",
    "Liquide de Refroidissement Compétition":          "Охл. жидкость Спорт",
    "Liquide de Refroidissement Véhicules Anciens":    "Охл. жидкость Классика",
    "Lave Glace et Dégivrant":                         "Омыватель и размораживатель",
    "Lave-Glace et Dégivrant":                         "Омыватель и размораживатель",
    "Dégripant / Graissage / Dégraissant":             "Смазки и очистители",
    "Dégraissant / Nettoyant":                         "Обезжириватель / Очиститель",
    "Pâte à Joint et Mastic":                          "Герметики и мастики",
    "Colles et Fixe-écrous":                           "Клеи и фиксаторы",
    "Matériel de Garage et Outillage":                 "Инструменты для гаража",
    "Huile moteur compétition":                        "Моторное масло Спорт",
    "Huile Moteur Compétition":                        "Моторное масло Спорт",
    "Huile boite de vitesse compétition":              "Масло КПП Спорт",
    "Huile Boite de Vitesse Compétition":              "Масло КПП Спорт",
    "Huile Boite Vitesse Compétition":                 "Масло КПП Спорт",
    "Huile Moteur Véhicules Anciens":                  "Моторное масло Классика",
    "Huile Boîte de Vitesse Véhicules Anciens":        "Масло КПП Классика",
    "Huile Moteur Diesel":                             "Моторное масло Дизель",
    "Huile":                                           "Масло",
    "Radiateur et Système de Refroidissement":         "Радиатор и охлаждение",
    "Home mobil™":                                     "Масло Mobil",
    "Essence":                                         "Присадки бензин",
    "Filtration":                                      "Фильтрация",
    "Produit Atelier":                                 "Продукты для сервиса",
}

# Все главные категории сайта
ALL_CATEGORY_URLS = [
    "https://www.racinglubes.fr/29-huile-moteur",
    "https://www.racinglubes.fr/14-huile-boite-de-vitesse-et-pont",
    "https://www.racinglubes.fr/15-freinage-direction-assistee",
    "https://www.racinglubes.fr/155-additifs",
    "https://www.racinglubes.fr/563-adblue",
    "https://www.racinglubes.fr/80-liquide-de-refroidissement-",
    "https://www.racinglubes.fr/58-lave-glace-et-degivrant",
    "https://www.racinglubes.fr/60-degrippant-graissage-degraissant",
    "https://www.racinglubes.fr/61-pate-a-joint-et-mastic",
    "https://www.racinglubes.fr/228-colles-et-fixe-ecrous",
    "https://www.racinglubes.fr/569-filtration",
    "https://www.racinglubes.fr/76-materiel-de-garage-et-outillage-",
    "https://www.racinglubes.fr/465-produit-atelier",
    "https://www.racinglubes.fr/24-huile-moteur-competition",
    "https://www.racinglubes.fr/26-huile-boite-vitesse-competition",
    "https://www.racinglubes.fr/27-freinage-direction-assistee-competition",
    "https://www.racinglubes.fr/342-liquide-de-refroidissement-competition",
    "https://www.racinglubes.fr/387-additifs-competition",
    "https://www.racinglubes.fr/200-huile-moteur-vehicules-anciens",
    "https://www.racinglubes.fr/201-huile-boite-de-vitesse-vehicules-anciens",
    "https://www.racinglubes.fr/374-freinage-direction-assistee-vehicules-anciens",
    "https://www.racinglubes.fr/377-liquide-de-refroidissement-vehicules-anciens",
    "https://www.racinglubes.fr/378-additifs-vehicules-anciens",
]


def translate_title(title_fr):
    result = title_fr
    for fr, ru in FR_TO_RU:
        result = result.replace(fr, ru)
    return result


def translate_category(cat_fr):
    return CATEGORY_RU.get(cat_fr, cat_fr)


def translate_desc(text_fr):
    if not TRANSLATE_AVAIL or not text_fr or len(text_fr.strip()) < 10:
        return text_fr
    try:
        return GoogleTranslator(source="fr", target="ru").translate(text_fr[:900]) or text_fr
    except Exception:
        return text_fr


def extract_viscosity(title):
    m = re.search(r'\b(\d+W\d+)\b', title, re.IGNORECASE)
    return m.group(1).upper() if m else ""


def extract_volume(title):
    m = re.search(r'\b(\d+(?:[.,]\d+)?)\s*(?:L|litre|litres)\b', title, re.IGNORECASE)
    if m:
        return f"{m.group(1).replace(',','.')}L"
    return ""


def get_cbr_rate():
    r = scraper.get(CBR_API, timeout=15)
    r.raise_for_status()
    return r.json()["Valute"]["EUR"]["Value"]


def compute_price_rub(eur, rate):
    return round(eur * rate * 4 + 5, 2)


def slugify(text):
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_]+", "-", text).strip("-")


def get_json_ld(soup, ld_type):
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(script.string)
            if isinstance(d, dict) and d.get("@type") == ld_type:
                return d
        except Exception:
            pass
    return None


def get_product_urls(cat_url):
    """Получает все URL товаров из категории, обходя пагинацию."""
    urls = []
    page = 1
    while True:
        url = f"{cat_url}?p={page}" if page > 1 else cat_url
        try:
            r = scraper.get(url, timeout=30)
            if r.status_code != 200:
                break
        except Exception as e:
            print(f"  Ошибка {url}: {e}", flush=True)
            break

        soup = BeautifulSoup(r.text, "html.parser")
        arts = soup.select("article.product-miniature")
        if not arts:
            break

        for art in arts:
            a = art.select_one("a.product-thumbnail")
            if a and a.get("href"):
                href = a["href"].split("#")[0]
                if not href.endswith(".html"):
                    href += ".html"
                if href not in urls:
                    urls.append(href)

        if not soup.select_one("a[rel=next], .pagination .next a"):
            break
        page += 1
        time.sleep(0.25)
    return urls


def parse_product(url, rate):
    try:
        r = scraper.get(url, timeout=30)
        if r.status_code != 200:
            return None
    except Exception as e:
        print(f"  Ошибка: {e}", flush=True)
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    ld = get_json_ld(soup, "Product")
    if not ld:
        return None

    title_fr  = ld.get("name", "").strip()
    sku       = str(ld.get("sku", "")).strip()
    desc_fr   = re.sub(r"<[^>]+>", " ", ld.get("description", "")).strip()
    cat_fr    = ld.get("category", "").strip()
    brand     = (ld.get("brand") or {}).get("name", "")

    img = ld.get("image", "")
    if isinstance(img, list):
        img = img[0] if img else ""
    img = img.replace("home_default", "large_default")

    price_eur = 0.0
    try:
        price_eur = float((ld.get("offers") or {}).get("price", 0))
    except (ValueError, TypeError):
        pass

    if not title_fr or price_eur <= 0:
        return None

    title_ru = translate_title(title_fr)
    cat_ru   = translate_category(cat_fr)
    desc_ru  = translate_desc(desc_fr)

    viscosity = extract_viscosity(title_fr)
    volume    = extract_volume(title_fr)

    images = [img]
    for itag in soup.select(".product-images img"):
        src = itag.get("src", "").replace("medium_default", "large_default")
        if src and src not in images:
            images.append(src)

    pid_match  = re.search(r"/(\d+)-", url)
    product_id = pid_match.group(1) if pid_match else sku
    slug       = f"{product_id}-{slugify(title_ru)}"[:80]
    cat_slug   = slugify(cat_fr) if cat_fr else "products"
    price_rub  = compute_price_rub(price_eur, rate)

    return {
        "id":          product_id,
        "slug":        slug,
        "title":       title_ru,
        "title_fr":    title_fr,
        "sku":         sku,
        "brand":       brand,
        "category":    cat_ru,
        "cat_slug":    cat_slug,
        "viscosity":   viscosity,
        "volume":      volume,
        "description": desc_ru,
        "price_eur":   price_eur,
        "price_rub":   price_rub,
        "image":       img,
        "images":      images[:4],
        "url_supplier": url,
    }


def write_page(prod):
    slug = prod["slug"]
    path = os.path.join(CONTENT_DIR, f"{slug}.md")
    title = prod["title"].replace('"', '\\"')
    cat   = prod["category"].replace('"', '\\"')
    brand = prod["brand"].replace('"', '\\"')

    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(f'title: "{title}"\n')
        f.write(f'title_fr: "{prod["title_fr"]}"\n')
        f.write(f'sku: "{prod["sku"]}"\n')
        f.write(f'brand: "{brand}"\n')
        f.write(f'category: "{cat}"\n')
        f.write(f'cat_slug: "{prod["cat_slug"]}"\n')
        f.write(f'viscosity: "{prod["viscosity"]}"\n')
        f.write(f'volume: "{prod["volume"]}"\n')
        f.write(f'price_eur: {prod["price_eur"]}\n')
        f.write(f'price_rub: {prod["price_rub"]}\n')
        f.write(f'image: "{prod["image"]}"\n')
        imgs_yaml = "\n".join(f'  - "{i}"' for i in prod["images"])
        f.write(f'images:\n{imgs_yaml}\n')
        f.write("draft: false\n---\n\n")
        f.write(prod["description"])


def main():
    print("=" * 60)
    print("Парсер racinglubes.fr — ПОЛНЫЙ КАТАЛОГ")
    print("=" * 60, flush=True)

    print("\n[1] Курс EUR/RUB...")
    rate = get_cbr_rate()
    print(f"    EUR = {rate:.4f} RUB", flush=True)

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(CONTENT_DIR, exist_ok=True)

    # Очистить старые страницы товаров
    removed = 0
    for fname in os.listdir(CONTENT_DIR):
        if fname.endswith(".md") and fname != "_index.md":
            os.remove(os.path.join(CONTENT_DIR, fname))
            removed += 1
    print(f"    Удалено старых страниц: {removed}", flush=True)

    print(f"\n[2] Парсинг {len(ALL_CATEGORY_URLS)} категорий...", flush=True)

    all_products = []
    seen_ids     = set()
    cats_out     = {}
    n = 0

    for ci, cat_url in enumerate(ALL_CATEGORY_URLS):
        cat_label = cat_url.split("/")[-1]
        print(f"\n  [{ci+1}/{len(ALL_CATEGORY_URLS)}] {cat_label}", flush=True)

        prod_urls = get_product_urls(cat_url)
        new_urls  = [u for u in prod_urls
                     if (m := re.search(r"/(\d+)-", u)) and m.group(1) not in seen_ids]
        print(f"  Всего URL: {len(prod_urls)}, новых: {len(new_urls)}", flush=True)

        for url in new_urls:
            pid_m = re.search(r"/(\d+)-", url)
            pid   = pid_m.group(1) if pid_m else None
            if pid and pid in seen_ids:
                continue

            prod = parse_product(url, rate)
            if prod:
                seen_ids.add(prod["id"])
                all_products.append(prod)
                write_page(prod)
                n += 1
                cat_ru = prod["category"]
                cs     = prod["cat_slug"]
                if cs not in cats_out:
                    cats_out[cs] = {"name": cat_ru, "slug": cs, "count": 0}
                cats_out[cs]["count"] += 1
                vis = f" [{prod['viscosity']}]" if prod["viscosity"] else ""
                print(f"  [{n}] {prod['title'][:55]}{vis} {prod['price_rub']:.0f}₽", flush=True)
            elif pid:
                seen_ids.add(pid)

            time.sleep(0.2)

    print(f"\n[3] Сохранение...", flush=True)

    with open(os.path.join(OUT_DIR, "products.json"), "w", encoding="utf-8") as f:
        json.dump(all_products, f, ensure_ascii=False, indent=2)

    with open(os.path.join(OUT_DIR, "categories.json"), "w", encoding="utf-8") as f:
        json.dump(list(cats_out.values()), f, ensure_ascii=False, indent=2)

    brands     = sorted({p["brand"] for p in all_products if p["brand"]})
    viscosities = sorted({p["viscosity"] for p in all_products if p["viscosity"]},
                          key=lambda x: (int(re.search(r'^(\d+)', x).group()), x))
    volumes    = sorted({p["volume"] for p in all_products if p["volume"]},
                         key=lambda x: float(re.search(r'[\d.]+', x).group()))

    with open(os.path.join(OUT_DIR, "filters.json"), "w", encoding="utf-8") as f:
        json.dump({"brands": brands, "viscosities": viscosities, "volumes": volumes},
                  f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"ИТОГО: {n} товаров")
    print(f"Категорий:  {len(cats_out)}")
    print(f"Брендов:    {len(brands)}")
    print(f"Вязкостей:  {len(viscosities)}")
    print(f"{'='*60}", flush=True)


if __name__ == "__main__":
    main()
