#  Scraper-online

Automated scraper for **uk.representclo.com** that collects product data —
name, sizes, current price, original price, and image URL — and exports
everything into an Excel report ready to import into Google Sheets.

**No photos are downloaded.** Only the image URL is captured; Google
Sheets renders the actual photo using the `=IMAGE()` formula after import.

---

## What It Does

1. Crawls product listing pages on the Represent storefront.
2. Visits every product page and extracts:
   - Product name
   - Product image URL (cleaned of any malformed proxy prefix)
   - Available sizes
   - Current price (after discount) **per size**
   - Original price (before discount) **per size**
   - Stock availability **per size**
3. Builds a single Excel file matching the Google Sheets import template.

---

## Project Structure

```
represent_scraper_project/
├── collectors/
│   └── product_collector.py   # Discovers product URLs from category/listing pages
├── extractors/
│   └── size_extractor.py      # Extracts name, image URL, currency, sizes & pricing
├── reporting/
│   └── excel_builder.py       # Builds the final .xlsx with formulas
├── logs/                      # One log file per catalog run
├── outputs/                   # One .xlsx/.csv per catalog run
├── config.py                  # Base URL, catalog naming, request settings
├── main.py                    # Entry point — runs the full pipeline
├── requirements.txt
└── README.md
```

---

## Output Table Format

The Excel file matches this exact column layout, ready to paste into
Google Sheets:

| Column | Header                            | Content                                             |
|--------|------------------------------------|------------------------------------------------------|
| A      | Фото продукта                      | `=IMAGE(H{row})` — renders the photo from column H   |
| B      | Ссылка на продукт                  | Product page URL                                     |
| C      | Имя                                 | Product name                                          |
| D      | Размер                              | Size label                                            |
| E      | Наличие                            | `TRUE` / `FALSE` — in stock for this size             |
| F      | Цена                                | Current price (after discount)                        |
| G      | Цена без скидки                    | Original price (before discount)                      |
| H      | image_url                          | Raw image URL (feeds the `=IMAGE()` formula)          |
| I      | Цена с учетом скидки (экономия)    | `=VALUE(SUBSTITUTE(G;".";","))-VALUE(SUBSTITUTE(F;".";","))` — savings amount |

Each row = one product + one size combination (long format), matching
your existing template exactly.

---

## How Size & Price Extraction Works

Represent's product pages are built on Shopify. The visible page text
(e.g. "Select Size", "In Stock") is unreliable to scrape directly.
Instead, `size_extractor.py` reads the hidden Shopify variant `<select>`
element, where each `<option>` carries the real data as HTML attributes:

| Attribute                     | Meaning                            |
|--------------------------------|--------------------------------------|
| `data-option-1`                | Size label (e.g. `XXL`)             |
| `data-variant-price`           | Current price, in pence/cents       |
| `data-variant-price-compare`   | Price before discount, in pence     |
| `disabled`                     | Present when the size is out of stock |
| `value`                        | Shopify variant ID                   |

A size is considered **available** if its `<option>` does **not** have
a `disabled` attribute.

### Image URL cleanup

The site occasionally serves `og:image` wrapped by a Speedsize proxy with
a malformed double-protocol prefix:

```
http:https://sfycdn.speedsize.com/.../uk.representclo.com/cdn/shop/files/....jpg
```

`_clean_image_url()` strips the bad prefix automatically, producing a
directly usable URL for the `=IMAGE()` formula.

---

## Setup

```bash
pip install -r requirements.txt
```

---

## Usage

### Default run
```bash
python main.py
```
Scrapes `config.COLLECTION_URLS` (default: `/collections/all`), names the
output `"catalog - <today's date>.xlsx"`.

### Custom catalog name
```bash
python main.py https://uk.representclo.com/collections/all --name "Чудокаталог"
```
Produces: `outputs/Чудокаталог - <today's date>.xlsx`

### Custom catalog name + custom date
```bash
python main.py https://uk.representclo.com/collections/all --name "Чудокаталог" --date 01.01.1991
```
Produces: `outputs/Чудокаталог - 01.01.1991.xlsx`

### Scrape a specific category
```bash
python main.py https://uk.representclo.com/collections/shorts --name "Shorts"
```

### Scrape multiple categories into one report
```bash
python main.py https://uk.representclo.com/collections/247 https://uk.representclo.com/collections/hoodies --name "Mixed"
```

Any argument starting with `http://` or `https://` is treated as a
collection/category URL. If none is given, `config.COLLECTION_URLS` is used.

---

## Output Files

Each run produces:
```
outputs/<Catalog Name> - <DD.MM.YYYY>.xlsx
outputs/<Catalog Name> - <DD.MM.YYYY>.csv
logs/<Catalog Name> - <DD.MM.YYYY>.log
```

Different catalog names or dates never overwrite each other's output.

---

## Importing into Google Sheets

1. Open Google Sheets → File → Import → Upload the `.xlsx` file.
2. Choose "Insert new sheet" (or replace, depending on your workflow).
3. The `=IMAGE()` and savings formulas in columns A and I will recalculate
   automatically once imported, rendering photos directly from column H's URLs.

---

## Known Warnings

```
[WARNING] No sizes found for <url>
```
Means the product page had no Shopify variant `<select>` element at all
(rare — usually a broken or discontinued listing). This is different
from a product being sold out; sold-out sizes are still captured
correctly with `available=False`.

---

## Notes & Limitations

- Respect the site's `robots.txt` and terms of service before scraping.
- The scraper is built specifically for Represent's Shopify template.
  If the site changes its HTML structure, `size_extractor.py` may need
  updating (specifically the `<select class="product-select-data">` lookup).
- Currency is read from `og:price:currency` and defaults to `GBP` if missing.
- No images are downloaded to disk — only URLs are captured.


---

## Задание сайта для парсинга через TARGET.txt

Вместо передачи ссылки каждый раз через командную строку, теперь можно
просто прописать целевой URL (или несколько) в файле `TARGET.txt` в
корне проекта:

```
# TARGET.txt — одна ссылка на строку, строки с # игнорируются
https://uk.representclo.com/collections/all
```

Приоритет источника ссылки (от высшего к низшему):
1. Аргумент командной строки (`python main.py <url>`)
2. `TARGET.txt`
3. `config.COLLECTION_URLS` (запасной вариант в коде)

Это удобно для автоматического запуска (например, через GitHub Actions по
расписанию) — просто редактируешь `TARGET.txt`, коммитишь, и следующий
прогон по расписанию сам подхватит новую ссылку без изменения кода.

---

## Автоматический ежедневный запуск через GitHub Actions

В проект добавлен файл `.github/workflows/daily-scrape.yml`, который
запускает скрапер **каждый день в 05:00 по лондонскому времени**
(Europe/London — GitHub Actions сам учитывает переход на летнее/зимнее
время, дополнительно ничего пересчитывать не нужно).

### Как это работает

1. GitHub по расписанию запускает виртуальную машину.
2. Устанавливает Python и зависимости из `requirements.txt`.
3. Запускает `python main.py --name "Чудокаталог"`, который берёт ссылку
   из `TARGET.txt`.
4. Готовый `.xlsx`/`.csv` сохраняется как:
   - **Artifact** — доступен для скачивания на вкладке Actions → конкретный run → Artifacts (хранится 30 дней);
   - **Коммит в репозиторий** — файл автоматически коммитится в папку `outputs/` того же репозитория, так что его видно прямо в файловой структуре на GitHub без скачивания.

### Как настроить у себя

1. Создай приватный (или публичный) репозиторий на GitHub.
2. Залей туда всю папку `represent_scraper_project/` целиком, включая
   `.github/workflows/daily-scrape.yml`.
3. Ничего дополнительно настраивать не нужно — `GITHUB_TOKEN` для коммита
   выдаётся автоматически самим GitHub Actions.
4. Расписание уже стоит на 05:00 Europe/London. Чтобы поменять время,
   отредактируй строку `cron: "0 5 * * *"` в workflow-файле (формат:
   минута час * * *, время указывается в часовом поясе из поля `timezone`).

### Проверка вручную

Workflow можно запустить и вручную, не дожидаясь расписания — на вкладке
**Actions** репозитория выбери **Daily Represent Scraper** → **Run workflow**.

### Важно про длительность

Полный прогон занимает ~38 минут (2255 секунд по замеру пользователя) —
это заложено в `timeout-minutes: 90` в workflow-файле с запасом. Менять
не нужно, если общее время скрапинга не вырастет значительно.
