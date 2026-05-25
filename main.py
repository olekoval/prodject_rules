import secrets
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__,
            template_folder='web_app/templates',
            static_folder='web_app/static')

app.config['SECRET_KEY'] = secrets.token_hex(24)

data_path = BASE_DIR / "data" / "database.xlsx"

df_dicts = pd.read_excel(data_path, sheet_name="dicts")
df_rules = pd.read_excel(data_path, sheet_name="rules")
df_versions = pd.read_excel(data_path, sheet_name="rule_versions")

dff = (df_rules
       .merge(df_dicts, left_on='rule_service', right_on='cod')
       .merge(df_dicts, left_on='rule_clas', right_on='cod'))
dff = dff.rename(columns={'name_x': 'name_servise', 'name_y': 'name_clas'})

df_rule_names = (df_dicts[df_dicts['type'] == 'Правило'][['cod', 'name']]
                 .rename(columns={'cod': 'rule_code', 'name': 'rule_text'}))
dff = dff.merge(df_rule_names, on='rule_code', how='left')
dff = dff[['id', 'packet_number', 'rule_service', 'name_servise',
           'rule_clas', 'name_clas', 'rule_code', 'rule_text']]

services = df_dicts[df_dicts['type'] == 'Сервіс'][['cod', 'name']].to_dict('records')


def get_classes(service_cod):
    return (dff[dff['rule_service'] == service_cod][['rule_clas', 'name_clas']]
            .drop_duplicates()
            .rename(columns={'rule_clas': 'cod', 'name_clas': 'name'})
            .to_dict('records'))


def get_rules(service_cod, class_cod):
    return (dff[(dff['rule_service'] == service_cod) & (dff['rule_clas'] == class_cod)]
            [['id', 'rule_code', 'rule_text', 'packet_number']]
            .drop_duplicates()
            .to_dict('records'))


def get_version(rule_id):
    rows = df_versions[(df_versions['rule_id'] == rule_id) & (df_versions['status'] == 'Активне')]
    if rows.empty:
        return None
    row = rows.sort_values('effective_from', ascending=False).iloc[0]
    return {
        'version_text': row['version_text'],
        'status': row['status'],
        'effective_from': str(row['effective_from'])[:10],
    }


@app.route('/', methods=['GET'])
def index():
    # Отримуємо параметри фільтрації та відкриття правила прямо з URL (Query string)
    service_cod = request.args.get('service', '')
    class_cod = request.args.get('class', '')
    open_rule_id = request.args.get('open_rule')

    # Каскадна вибірка даних: класи завантажуються лише якщо обрано сервіс,
    # а правила — якщо обрано і сервіс, і клас.
    classes = get_classes(service_cod) if service_cod else []
    rules = get_rules(service_cod, class_cod) if service_cod and class_cod else []

    # Якщо користувач клікнув "Переглянути текст", шукаємо версію цього правила
    version = None
    if open_rule_id:
        version = get_version(open_rule_id)

    # Рендеримо сторінку, передаючи туди всі відфільтровані дані
    return render_template(
        'select_service.html',
        services=services,
        service_cod=service_cod,
        classes=classes,
        class_cod=class_cod,
        rules=rules,
        open_rule_id=open_rule_id,
        version=version,
    )


if __name__ == "__main__":
    app.run(debug=True)
