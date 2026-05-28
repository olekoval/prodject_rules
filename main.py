"""
main.py
=======
Flask-додаток: визначення роутів.
Вся бізнес-логіка та дані — у data_utils.py.
"""

import secrets
from flask import Flask, render_template, request

from data_utils import (
    services,
    get_classes,
    get_rules,
    get_rule_details,
    search_rules_by_code,
)

app = Flask(__name__,
            template_folder="web_app/templates",
            static_folder="web_app/static")

app.config["SECRET_KEY"] = secrets.token_hex(24)


@app.route("/", methods=["GET"])
def index():
    """Головна сторінка: навігація сервіс → клас → правило → деталі."""
    service_cod  = request.args.get("service", "")
    class_cod    = request.args.get("class", "")
    open_rule_id = request.args.get("open_rule")

    classes = get_classes(service_cod) if service_cod else []
    rules   = get_rules(service_cod, class_cod) if service_cod and class_cod else []

    # Деталі правила завантажуються лише якщо є open_rule у параметрах
    version, history = (None, [])
    if open_rule_id:
        version, history = get_rule_details(open_rule_id)

    return render_template(
        "select_service.html",
        services=services,
        service_cod=service_cod,
        classes=classes,
        class_cod=class_cod,
        rules=rules,
        open_rule_id=open_rule_id,
        version=version,
        history=history,
    )


@app.route("/search", methods=["GET"])
def search():
    """
    Сторінка пошуку правил за кодом спостереження/інтервенції.
    GET-параметр: q — рядок пошуку (мінімум 4 символи).
    """
    query = request.args.get("q", "").strip()

    # Виконуємо пошук лише якщо введено ≥4 символів
    results      = search_rules_by_code(query) if len(query) >= 4 else []
    open_rule_id = request.args.get("open_rule")

    # Деталі обраного правила зі списку результатів
    version, history = (None, [])
    if open_rule_id:
        version, history = get_rule_details(open_rule_id)

    return render_template(
        "search.html",
        query=query,
        results=results,
        open_rule_id=open_rule_id,
        version=version,
        history=history,
    )


if __name__ == "__main__":
    app.run(debug=True)
