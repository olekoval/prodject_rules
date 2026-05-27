import secrets
from pathlib import Path
from flask import Flask, render_template, request
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
df_documents = pd.read_excel(data_path, sheet_name="documents")

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


def get_rule_details(rule_id):
    """
    Повертає активну версію правила та повну хронологію змін
    з описом документів-підстав для кожної версії.
    """
    rows = df_versions[df_versions['rule_id'] == rule_id].copy()
    if rows.empty:
        return None, []

    # Об'єднуємо версії з документами
    merged = rows.merge(df_documents, left_on='document_id', right_on='id', how='left')
    merged = merged.sort_values('effective_from', ascending=False)

    active_version = None
    history = []

    for _, row in merged.iterrows():
        # Формуємо інформацію про документ-підставу
        doc_number = row.get('doc_number')
        doc_date = row.get('doc_date')
        doc_type = row.get('doc_type', '')
        doc_title = row.get('title', '')
        file_path = row.get('file_path')

        doc_date_str = str(doc_date)[:10] if pd.notna(doc_date) else ''
        doc_number_str = str(int(doc_number)) if pd.notna(doc_number) else ''
        has_file = pd.notna(file_path) and str(file_path).strip() not in ('', 'nan')

        document = {
            'doc_type': doc_type if pd.notna(doc_type) else '',
            'doc_number': doc_number_str,
            'doc_date': doc_date_str,
            'title': doc_title if pd.notna(doc_title) else '',
            'file_path': str(file_path) if has_file else None,
            'has_file': has_file,
        }

        change_desc = row.get('change_description')
        entry = {
            'status': row['status'],
            'effective_from': str(row['effective_from'])[:10],
            'effective_to': str(row['effective_to'])[:10] if pd.notna(row.get('effective_to')) else None,
            'version_text': row['version_text'],
            'change_description': str(change_desc) if pd.notna(change_desc) else None,
            'document': document,
            'is_active': row['status'] == 'Активне',
        }
        history.append(entry)

        if active_version is None and row['status'] == 'Активне':
            active_version = entry

    return active_version, history


@app.route('/', methods=['GET'])
def index():
    service_cod = request.args.get('service', '')
    class_cod = request.args.get('class', '')
    open_rule_id = request.args.get('open_rule')

    classes = get_classes(service_cod) if service_cod else []
    rules = get_rules(service_cod, class_cod) if service_cod and class_cod else []

    version = None
    history = []
    if open_rule_id:
        version, history = get_rule_details(open_rule_id)

    return render_template(
        'select_service.html',
        services=services,
        service_cod=service_cod,
        classes=classes,
        class_cod=class_cod,
        rules=rules,
        open_rule_id=open_rule_id,
        version=version,
        history=history,
    )


if __name__ == "__main__":
    app.run(debug=True)
