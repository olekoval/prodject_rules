"""
data_utils.py
=============
Завантаження даних з Excel та всі функції бізнес-логіки.
Імпортується у main.py — роути Flask не знають про pandas/Excel.
"""

import re
from pathlib import Path

import pandas as pd

# ── Шлях до бази даних ──────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "database.xlsx"

# ── Завантаження листів Excel ────────────────────────────────────────────────
df_dicts    = pd.read_excel(DATA_PATH, sheet_name="dicts")
df_rules    = pd.read_excel(DATA_PATH, sheet_name="rules")
df_versions = pd.read_excel(DATA_PATH, sheet_name="rule_versions")
df_documents= pd.read_excel(DATA_PATH, sheet_name="documents")

# ── Побудова основного денормалізованого датафрейму правил ──────────────────
# Приєднуємо назви сервісів і класів через таблицю dicts
dff = (
    df_rules
    .merge(df_dicts, left_on="rule_service", right_on="cod")
    .merge(df_dicts, left_on="rule_clas",    right_on="cod")
)
dff = dff.rename(columns={"name_x": "name_servise", "name_y": "name_clas"})

# Приєднуємо текстову назву самого правила (тип "Правило" у dicts)
df_rule_names = (
    df_dicts[df_dicts["type"] == "Правило"][["cod", "name"]]
    .rename(columns={"cod": "rule_code", "name": "rule_text"})
)
dff = dff.merge(df_rule_names, on="rule_code", how="left")

# Залишаємо тільки потрібні колонки
dff = dff[["id", "packet_number", "rule_service", "name_servise",
           "rule_clas", "name_clas", "rule_code", "rule_text"]]

# ── Список сервісів для навігації ────────────────────────────────────────────
services = (
    df_dicts[df_dicts["type"] == "Сервіс"][["cod", "name"]]
    .to_dict("records")
)

# ── Регулярний вираз для токенізації кодів у тексті версії ──────────────────
# Знаходить будь-який токен ≥4 символів з літер, цифр, дефісу, що містить цифру
CODE_PATTERN = re.compile(r"\b(?=.*\d)[A-Za-z0-9-]{4,}\b")


# ────────────────────────────────────────────────────────────────────────────
# Функції для головної сторінки (навігація сервіс → клас → правило)
# ────────────────────────────────────────────────────────────────────────────

def get_classes(service_cod: str) -> list[dict]:
    """Повертає список унікальних класів для вказаного сервісу.

    Args:
        service_cod: Код сервісу з колонки `rule_service`.

    Returns:
        Список словників із даними класів (ключі 'cod' та 'name'). 
        Якщо `service_cod` не існує в базі, повертає порожній список `[]`.
    """
    return (
        dff[dff["rule_service"] == service_cod][["rule_clas", "name_clas"]]
        .drop_duplicates()
        .rename(columns={"rule_clas": "cod", "name_clas": "name"})
        .to_dict("records") # якщо dff буде поржній поверне порожній список []
    )


def get_rules(service_cod: str, class_cod: str) -> list[dict]:
    """Повертає список правил для вибраного сервісу та класу."""
    mask = (dff["rule_service"] == service_cod) & (dff["rule_clas"] == class_cod)
    return (
        dff[mask][["id", "rule_code", "rule_text", "packet_number"]]
        .drop_duplicates()
        .to_dict("records")
    )


def get_rule_details(rule_id: str) -> tuple[dict | None, list[dict]]:
    """
    Повертає (активна_версія, хронологія) для правила за його id.
    Активна версія — перший запис зі статусом 'Активне' після сортування
    за датою спадно. Хронологія містить усі версії.
    """
    rows = df_versions[df_versions["rule_id"] == rule_id].copy()
    if rows.empty:
        return None, []

    # Приєднуємо документи-підстави до кожної версії
    merged = rows.merge(df_documents, left_on="document_id", right_on="id", how="left")
    merged = merged.sort_values("effective_from", ascending=False)

    active_version = None
    history = []

    for _, row in merged.iterrows():
        doc_number  = row.get("doc_number")
        doc_date    = row.get("doc_date")
        doc_type    = row.get("doc_type", "")
        doc_title   = row.get("title", "")
        file_path   = row.get("file_path")

        # Безпечне перетворення дати і номера документа
        doc_date_str   = str(doc_date)[:10]      if pd.notna(doc_date)   else ""
        doc_number_str = str(int(doc_number))    if pd.notna(doc_number) else ""
        has_file = pd.notna(file_path) and str(file_path).strip() not in ("", "nan")

        document = {
            "doc_type":   doc_type  if pd.notna(doc_type)  else "",
            "doc_number": doc_number_str,
            "doc_date":   doc_date_str,
            "title":      doc_title if pd.notna(doc_title) else "",
            "file_path":  str(file_path) if has_file else None,
            "has_file":   has_file,
        }

        change_desc = row.get("change_description")
        entry = {
            "status":             row["status"],
            "effective_from":     str(row["effective_from"])[:10],
            "effective_to":       str(row["effective_to"])[:10] if pd.notna(row.get("effective_to")) else None,
            "version_text":       row["version_text"],
            "change_description": str(change_desc) if pd.notna(change_desc) else None,
            "document":           document,
            "is_active":          row["status"] == "Активне",
        }
        history.append(entry)

        # Перша активна версія (за датою спадно) — поточна
        if active_version is None and row["status"] == "Активне":
            active_version = entry

    return active_version, history


# ────────────────────────────────────────────────────────────────────────────
# Функція пошуку правил за кодом
# ────────────────────────────────────────────────────────────────────────────

def search_rules_by_code(query: str) -> list[dict]:
    """
    Шукає правила, у версіях яких (version_text) є токен що точно збігається
    з рядком query (без урахування регістру).

    Алгоритм:
    1. Витягуємо всі токени з version_text кожної версії за CODE_PATTERN.
    2. Якщо query (case-insensitive) є серед токенів — правило потрапляє
       до результатів.
    3. Шукаємо по ВСІХ версіях правила (не лише активних).
    4. Дублікати правил (rule_id) усуваємо — одне правило показується раз.

    Повертає список dict з ключами: id, rule_code, rule_text,
    name_servise, name_clas — для відображення у списку результатів.
    """
    if not query or len(query) < 4:
        return []

    # Нормалізуємо запит користувача:
    # 1. Знімаємо пробіли на початку і в кінці
    # 2. Знімаємо пробіли навколо дефісу (напр. "10331 - 7" → "10331-7")
    query = re.sub(r'\s*-\s*', '-', query).strip()
    query_lower = query.lower()

    # Збираємо rule_id правил де знайдено збіг
    matched_rule_ids = set()
    for _, row in df_versions.iterrows():
        text = str(row.get("version_text", ""))
        # Нормалізуємо текст з бази так само — прибираємо пробіли навколо дефісів
        # щоб некоректний ввід у Excel не заважав пошуку
        text = re.sub(r'\s*-\s*', '-', text)
        tokens = CODE_PATTERN.findall(text)
        # Точний збіг без урахування регістру
        if any(t.lower() == query_lower for t in tokens):
            matched_rule_ids.add(row["rule_id"])

    if not matched_rule_ids:
        return []

    # Повертаємо дані про правила з dff (містить назви сервісу та класу)
    result = (
        dff[dff["id"].isin(matched_rule_ids)]
        [["id", "rule_code", "rule_text", "name_servise", "name_clas"]]
        .drop_duplicates(subset=["id"])
        .to_dict("records")
    )
    return result
