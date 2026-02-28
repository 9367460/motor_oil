"""
Парсер каталога racinglubes.fr — ПОЛНЫЙ с вариантами объёма
- Все категории, все страницы пагинации
- Объёмы через AJAX (каждый вариант = отдельная карточка товара)
- Перевод через словарь (без Google Translate — быстро)
- Дедупликация по product_id + attr_value_id
"""
import json, os, re, time, warnings
warnings.filterwarnings("ignore")

import cloudscraper
from bs4 import BeautifulSoup
import requests as _req

scraper = cloudscraper.create_scraper()
BASE_URL    = "https://www.racinglubes.fr"
CBR_API     = "https://www.cbr-xml-daily.ru/daily_json.js"
AJAX_URL    = f"{BASE_URL}/index.php?controller=product&ajax=1&action=refresh"

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUT_DIR     = os.path.join(SCRIPT_DIR, "..", "site", "data")
CONTENT_DIR = os.path.join(SCRIPT_DIR, "..", "site", "content", "products")

# ── Словарь: французские термины → русские ───────────────────────────────────
FR_TO_RU = [
    ("Huile Moteur Compétition",               "Моторное масло Спорт"),
    ("Huile moteur compétition",               "Моторное масло Спорт"),
    ("Huile Moteur Véhicules Anciens",         "Моторное масло Классика"),
    ("Huile Moteur Diesel",                    "Моторное масло Дизель"),
    ("Huile Moteur",                           "Моторное масло"),
    ("Huile moteur",                           "Моторное масло"),
    ("Huile Boite de Vitesse",                 "Масло КПП"),
    ("Huile Boîte de Vitesse",                 "Масло КПП"),
    ("Huile boite de vitesse",                 "Масло КПП"),
    ("Huile boîte de vitesse",                 "Масло КПП"),
    ("Huile de Pont",                          "Масло для моста"),
    ("Huile Direction Assistée",               "Масло ГУР"),
    ("Huile de Transmission Automatique",      "Масло АКПП"),
    ("Huile de transmission automatique",      "Масло АКПП"),
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
    ("Additif de Refroidissement",             "Охлаждающая присадка"),
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
    ("Super dégrippant",                       "Суперразблокиратор"),
    ("Dégrippant",                             "Разблокиратор"),
    ("Graisse",                                "Смазка"),
    ("Lubrifiant",                             "Смазочный материал"),
    ("Nettoyant freins",                       "Очиститель тормозов"),
    ("Filtre à huile",                         "Масляный фильтр"),
    ("Filtre",                                 "Фильтр"),
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
    "Liquide de Refroidissement Compétition":          "Охл. жидкость Спорт",
    "Liquide de Refroidissement Véhicules Anciens":    "Охл. жидкость Классика",
    "Lave Glace et Dégivrant":                         "Омыватель и размораживатель",
    "Lave-Glace et Dégivrant":                         "Омыватель и размораживатель",
    "Dégripant / Graissage / Dégraissant":             "Смазки и очистители",
    "Dégraissant / Nettoyant":                         "Обезжириватель / Очиститель",
    "Dégrippant - Graissage - Dégraissant":            "Обезжириватель / Очиститель",
    "Dégrippant":                                      "Жидкость WD",
    "Pâte à Joint et Mastic":                          "Герметики и мастики",
    "Colles et Fixe-écrous":                           "Клеи и фиксаторы",
    "Colles et Fixe Ecrous":                           "Клеи и фиксаторы",
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
    "Filtration":                                      "Масляные фильтры",
    "Filtres à Huile":                                 "Масляные фильтры",
    "Produit Atelier":                                 "Продукты для сервиса",
    "Huiles pour transmissions automatiques":          "Масло АКПП",
    "Huiles pour transmissions manuelles":             "Масло МКПП",
    "Gazole":                                          "Дизельные присадки",
    "Liquide Hydraulique":                             "Гидравлическая жидкость",
    "Liquide de direction assistée":                   "Жидкость ГУР",
    "Graisse / Lubrifiant":                            "Смазки",
}

# Перевод объёмов
def _n(m, g=1): return m.group(g).replace(',', '.')

VOLUME_RU = [
    # Bidon (канистра)
    (r'bidon de (\d+(?:[.,]\d+)?)\s*ml',   lambda m: f"{_n(m)}мл"),
    (r'bidon de (\d+(?:[.,]\d+)?)\s*l\b',  lambda m: f"{_n(m)}L"),
    # Fût / Tonnelet (бочка)
    (r'tonnelet(?:\s+de)?\s+(\d+(?:[.,]\d+)?)\s*kg', lambda m: f"Бочонок {_n(m)} кг"),
    (r'tonnelet(?:\s+de)?\s+(\d+(?:[.,]\d+)?)\s*l\b', lambda m: f"{_n(m)}L"),
    (r'fût de (\d+(?:[.,]\d+)?)\s*kg',     lambda m: f"Бочка {_n(m)} кг"),
    (r'fût de (\d+(?:[.,]\d+)?)\s*l\b',    lambda m: f"{_n(m)}L"),
    # Seau (ведро)
    (r'seau de (\d+(?:[.,]\d+)?)\s*kg',    lambda m: f"Ведро {_n(m)} кг"),
    (r'seau de (\d+(?:[.,]\d+)?)\s*l\b',   lambda m: f"Ведро {_n(m)} л"),
    # Aérosol
    (r'aérosol de (\d+(?:[.,]\d+)?)\s*ml', lambda m: f"Аэрозоль {_n(m)} мл"),
    (r'aérosol de (\d+(?:[.,]\d+)?)\s*l\b',lambda m: f"Аэрозоль {_n(m)} л"),
    # Cartouche (картридж)
    (r'cartouche(?: classic| [àa] visser)?(?: de)? (\d+(?:[.,]\d+)?)\s*g\b', lambda m: f"Картридж {_n(m)} г"),
    (r'cartouche(?: de)? (\d+(?:[.,]\d+)?)\s*ml', lambda m: f"Картридж {_n(m)} мл"),
    (r'cartouche(?: de)? (\d+(?:[.,]\d+)?)\s*g\b', lambda m: f"Картридж {_n(m)} г"),
    # Flacon (флакон)
    (r'flacon de (\d+(?:[.,]\d+)?)\s*g\b', lambda m: f"Флакон {_n(m)} г"),
    (r'flacon de (\d+(?:[.,]\d+)?)\s*ml',  lambda m: f"Флакон {_n(m)} мл"),
    (r'flacon de (\d+(?:[.,]\d+)?)\s*l\b', lambda m: f"Флакон {_n(m)} л"),
    # Tube
    (r'tube(?: de)? (\d+(?:[.,]\d+)?)\s*g\b',  lambda m: f"Туба {_n(m)} г"),
    (r'tube(?: de)? (\d+(?:[.,]\d+)?)\s*ml',   lambda m: f"Туба {_n(m)} мл"),
    (r'tube(?: de)? (\d+(?:[.,]\d+)?)\s*l\b',  lambda m: f"Туба {_n(m)} л"),
    # Pot / Récipient (банка / ёмкость)
    (r'pot(?: de)? (\d+(?:[.,]\d+)?)\s*kg',    lambda m: f"Банка {_n(m)} кг"),
    (r'pot(?: de)? (\d+(?:[.,]\d+)?)\s*g\b',   lambda m: f"Банка {_n(m)} г"),
    (r'récipient de (\d+(?:[.,]\d+)?)\s*ml',   lambda m: f"Ёмкость {_n(m)} мл"),
    # Seringue (шприц)
    (r'seringue de (\d+)\s*x\s*(\d+(?:[.,]\d+)?)\s*ml', lambda m: f"Шприц {m.group(1)}×{_n(m,2)} мл"),
    (r'seringue de (\d+(?:[.,]\d+)?)\s*g\b',   lambda m: f"Шприц {_n(m)} г"),
    (r'seringue de (\d+(?:[.,]\d+)?)\s*ml',    lambda m: f"Шприц {_n(m)} мл"),
    # Spray / Pulvérisateur (спрей / распылитель)
    (r'spray(?: de)? (\d+(?:[.,]\d+)?)\s*ml',  lambda m: f"Спрей {_n(m)} мл"),
    (r'pulvérisateur de (\d+(?:[.,]\d+)?)\s*ml', lambda m: f"Распылитель {_n(m)} мл"),
    # Stick
    (r'stick de (\d+(?:[.,]\d+)?)\s*g\b',      lambda m: f"Стик {_n(m)} г"),
    # Pack / Rouleau
    (r'pack de (\d+)\s*rouleaux?',              lambda m: f"Уп. {m.group(1)} рул."),
    (r'rouleau de (\d+(?:[.,]\d+)?)\s*m\b',    lambda m: f"Рулон {_n(m)} м"),
    # Kit avec quantité
    (r'kit de (\d+(?:[.,]\d+)?)\s*g\b',        lambda m: f"Комплект {_n(m)} г"),
    # Generic: numbers + unit
    (r'(\d+(?:[.,]\d+)?)\s*litres?',            lambda m: f"{_n(m)}L"),
    (r'(\d+(?:[.,]\d+)?)\s*l\b',               lambda m: f"{_n(m)}L"),
    (r'(\d+(?:[.,]\d+)?)\s*ml\b',              lambda m: f"{_n(m)}мл"),
    (r'(\d+(?:[.,]\d+)?)\s*g\b',               lambda m: f"{_n(m)} г"),
    (r'(\d+(?:[.,]\d+)?)\s*kg\b',              lambda m: f"{_n(m)} кг"),
    (r'(\d+(?:[.,]\d+)?)\s*m\b',               lambda m: f"{_n(m)} м"),
]

# Color/type labels that are NOT volumes — translate to Russian for display
VARIANT_COLORS_RU = {
    'vert': 'Зелёный', 'noir': 'Чёрный', 'rose': 'Розовый',
    'rouge': 'Красный', 'bleu': 'Синий', 'blanc': 'Белый',
    'camao': 'Камуфляж', 'military tan': 'Military Tan',
    'patriotic': 'Patriotic', 'v-twin': 'V-Twin',
}

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


def parse_volume_label(label):
    """'Bidon de 5 L' → '5L', 'Aérosol de 250 ml' → 'Аэрозоль 250 мл', 'Vert' → 'Зелёный'"""
    low = label.lower().strip()
    for pattern, fn in VOLUME_RU:
        m = re.search(pattern, low)
        if m:
            return fn(m)
    # Color/type labels
    if low in VARIANT_COLORS_RU:
        return VARIANT_COLORS_RU[low]
    return label


def extract_viscosity(title):
    m = re.search(r'\b(\d+W\d+)\b', title, re.IGNORECASE)
    return m.group(1).upper() if m else ""


def get_cbr_rate():
    r = _req.get(CBR_API, timeout=15)
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
    """Получает все URL товаров из категории с пагинацией."""
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
        time.sleep(0.3)
    return urls


def fetch_combo_price_and_sku(id_product, id_pa_default, group_id, attr_val):
    """AJAX запрос для получения цены и SKU конкретного объёма."""
    data = {
        'id_product': id_product,
        'id_product_attribute': id_pa_default,
        f'group[{group_id}]': attr_val,
        'qty': '1',
    }
    try:
        r = scraper.post(AJAX_URL, data=data, timeout=15)
        if r.status_code == 200:
            resp = r.json()
            html = resp.get('product_prices', '') + resp.get('product_cover_thumbnails', '') + resp.get('product_reference', '')
            # Price: content="XX.XX"
            pm = re.search(r'content=["\']([0-9.]+)["\']', html)
            price = float(pm.group(1)) if pm else None
            # SKU
            sm = re.search(r'product-reference-value[^>]*>\s*([^<\s]+)\s*<', html)
            sku = sm.group(1).strip() if sm else None
            return price, sku
    except Exception:
        pass
    return None, None


def parse_product_variants(url, rate):
    """
    Парсит страницу товара и возвращает СПИСОК вариантов (один на каждый объём).
    Если вариантов нет — список из одного элемента.
    """
    try:
        r = scraper.get(url, timeout=30)
        if r.status_code != 200:
            return []
    except Exception as e:
        print(f"  Ошибка: {e}", flush=True)
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    ld = get_json_ld(soup, "Product")
    if not ld:
        return []

    title_fr  = ld.get("name", "").strip()
    desc_fr   = re.sub(r"<[^>]+>", " ", ld.get("description", "")).strip()[:400]
    cat_fr    = ld.get("category", "").strip()
    brand     = (ld.get("brand") or {}).get("name", "")

    img = ld.get("image", "")
    if isinstance(img, list):
        img = img[0] if img else ""
    img = img.replace("home_default", "large_default")

    default_price_eur = 0.0
    try:
        default_price_eur = float((ld.get("offers") or {}).get("price", 0))
    except (ValueError, TypeError):
        pass

    default_sku = str(ld.get("sku", "")).strip()

    if not title_fr or default_price_eur <= 0:
        return []

    title_ru = translate_title(title_fr)
    cat_ru   = translate_category(cat_fr)

    viscosity = extract_viscosity(title_fr)

    pid_match  = re.search(r"/(\d+)-", url)
    product_id = pid_match.group(1) if pid_match else default_sku
    cat_slug   = slugify(cat_fr) if cat_fr else "products"

    # Собираем изображения
    images = [img]
    for itag in soup.select(".product-images img"):
        src = itag.get("src", "").replace("medium_default", "large_default")
        if src and src not in images:
            images.append(src)
    images = images[:4]

    # ── Ищем варианты объёма ──────────────────────────────────────────────────
    id_product_inp = soup.select_one('input#idp, input[name="idp"]')
    id_pa_inp      = soup.select_one('input#idpa, input[name="idpa"]')
    id_product_val = id_product_inp['value'] if id_product_inp else product_id
    id_pa_default  = id_pa_inp['value'] if id_pa_inp else None

    volume_variants = []  # [(attr_val, label, is_default)]
    group_id = None

    for ul in soup.select("ul.variant-radio-pc"):
        gid_m = re.search(r'id="group_(\d+)"', str(ul))
        if not gid_m:
            continue
        group_id = gid_m.group(1)
        for radio in ul.select('input[type=radio]'):
            attr_val = radio.get('value', '').strip()
            label    = radio.get('title', '').strip()
            is_def   = radio.has_attr('checked')
            if attr_val and label:
                volume_variants.append((attr_val, label, is_def))
        break  # берём только первую группу атрибутов (Conditionnement)

    results = []

    if not volume_variants:
        # Нет вариантов объёма — один товар
        slug = f"{product_id}-{slugify(title_ru)}"[:90]
        results.append({
            "id":           product_id,
            "combo_key":    product_id,
            "slug":         slug,
            "title":        title_ru,
            "title_fr":     title_fr,
            "sku":          default_sku,
            "brand":        brand,
            "category":     cat_ru,
            "cat_slug":     cat_slug,
            "viscosity":    viscosity,
            "volume":       "",
            "description":  desc_fr,
            "price_eur":    default_price_eur,
            "price_rub":    compute_price_rub(default_price_eur, rate),
            "image":        img,
            "images":       images,
            "url_supplier": url,
        })
        return results

    # Есть варианты — создаём отдельный товар для каждого объёма
    for attr_val, label, is_default in volume_variants:
        vol_str = parse_volume_label(label)  # "1L", "5L", "209L"

        if is_default:
            price_eur = default_price_eur
            sku       = default_sku
        else:
            # AJAX запрос
            price_eur, sku = fetch_combo_price_and_sku(
                id_product_val, id_pa_default, group_id, attr_val
            )
            if price_eur is None:
                price_eur = default_price_eur  # fallback
            if not sku:
                sku = f"{default_sku}-{attr_val}"
            time.sleep(0.15)

        title_with_vol = f"{title_ru} {vol_str}"
        slug = f"{product_id}-{attr_val}-{slugify(title_ru)}-{slugify(vol_str)}"[:90]

        results.append({
            "id":           product_id,
            "combo_key":    f"{product_id}-{attr_val}",
            "slug":         slug,
            "title":        title_with_vol,
            "title_fr":     f"{title_fr} {label}",
            "sku":          sku,
            "brand":        brand,
            "category":     cat_ru,
            "cat_slug":     cat_slug,
            "viscosity":    viscosity,
            "volume":       vol_str,
            "description":  desc_fr,
            "price_eur":    price_eur,
            "price_rub":    compute_price_rub(price_eur, rate),
            "image":        img,
            "images":       images,
            "url_supplier": url,
        })

    return results


def write_page(prod):
    slug  = prod["slug"]
    path  = os.path.join(CONTENT_DIR, f"{slug}.md")
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
    print("Парсер racinglubes.fr — ПОЛНЫЙ КАТАЛОГ + ОБЪЁМЫ")
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
    seen_combos  = set()  # combo_key = product_id + attr_val
    seen_pids    = set()  # product IDs (для дедупликации по базовому ID)
    cats_out     = {}
    n = 0

    for ci, cat_url in enumerate(ALL_CATEGORY_URLS):
        cat_label = cat_url.split("/")[-1]
        print(f"\n  [{ci+1}/{len(ALL_CATEGORY_URLS)}] {cat_label}", flush=True)

        prod_urls = get_product_urls(cat_url)
        # Фильтруем: только те product_id, которые мы ещё не обрабатывали
        new_urls = []
        for u in prod_urls:
            pm = re.search(r"/(\d+)-", u)
            pid = pm.group(1) if pm else None
            if pid and pid not in seen_pids:
                new_urls.append(u)
        print(f"  Всего URL: {len(prod_urls)}, новых: {len(new_urls)}", flush=True)

        for url in new_urls:
            pm = re.search(r"/(\d+)-", url)
            pid = pm.group(1) if pm else None
            if pid:
                seen_pids.add(pid)

            variants = parse_product_variants(url, rate)
            for prod in variants:
                ck = prod["combo_key"]
                if ck in seen_combos:
                    continue
                seen_combos.add(ck)
                all_products.append(prod)
                write_page(prod)
                n += 1

                cat_ru = prod["category"]
                cs     = prod["cat_slug"]
                if cs not in cats_out:
                    cats_out[cs] = {"name": cat_ru, "slug": cs, "count": 0}
                cats_out[cs]["count"] += 1

                vis = f" [{prod['viscosity']}]" if prod["viscosity"] else ""
                vol = f" {prod['volume']}" if prod["volume"] else ""
                print(f"  [{n}] {prod['title'][:50]}{vis}{vol} {prod['price_rub']:.0f}₽", flush=True)

            time.sleep(0.2)

    print(f"\n[3] Сохранение...", flush=True)

    with open(os.path.join(OUT_DIR, "products.json"), "w", encoding="utf-8") as f:
        json.dump(all_products, f, ensure_ascii=False, indent=2)

    with open(os.path.join(OUT_DIR, "categories.json"), "w", encoding="utf-8") as f:
        json.dump(list(cats_out.values()), f, ensure_ascii=False, indent=2)

    brands = sorted({p["brand"] for p in all_products if p["brand"]})

    def vis_key(x):
        m = re.search(r'^(\d+)', x)
        return int(m.group()) if m else 999

    def vol_key(x):
        m = re.search(r'([\d.]+)', x)
        return float(m.group()) if m else 0

    viscosities = sorted({p["viscosity"] for p in all_products if p["viscosity"]}, key=vis_key)
    volumes     = sorted({p["volume"]    for p in all_products if p["volume"]},    key=vol_key)

    with open(os.path.join(OUT_DIR, "filters.json"), "w", encoding="utf-8") as f:
        json.dump({"brands": brands, "viscosities": viscosities, "volumes": volumes},
                  f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"ИТОГО: {n} товаров (с вариантами объёма)")
    print(f"Категорий:  {len(cats_out)}")
    print(f"Брендов:    {len(brands)}")
    print(f"Вязкостей:  {len(viscosities)}")
    print(f"Объёмов:    {len(volumes)} вариантов: {volumes[:10]}")
    print(f"{'='*60}", flush=True)


if __name__ == "__main__":
    main()
