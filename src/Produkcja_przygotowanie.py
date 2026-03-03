import xmlrpc.client
import os
import shutil

class Connector:
    # inicjije połaczenie z Odoo
    # pobiera: url, db, username, password
    def __init__(self, url='url', db='db',
                 username='user', password=None):
        self.url = url
        self.db = db
        self.username = username
        self.password = password or ""
        self.common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)
        self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)
        self.uid = None

    # loguje użytkownika Odoo
    # pobiera: password
    # zwraca: int(uid)
    def connect(self, password):
        self.password = password
        uid = self.common.authenticate(self.db, self.username, self.password, {})
        if not uid:
            uid = self.common.login(self.db, self.username, self.password)
        if not uid:
            raise RuntimeError("Auth failed")
        self.uid = uid
        return uid

BASE_PROD = "scieżka_docelowa_dla_zleceń"

FIELDS = [
    "id",
    "name",
    "state",
    "product_id",
    "origin",
    "partner_id",
    "routing_id",
]

# normalizuje tekst porównawczy
# pobiera: text(str)
# zwaraca: str
def normalize(text):
    return (
        text.lower()
        .replace("ó", "o")
        .replace("ł", "l")
        .replace("ś", "s")
        .replace("ć", "c")
        .replace("ń", "n")
        .replace("ą", "a")
        .replace("ę", "e")
        .replace("ż", "z")
        .replace("ź", "z")
        .replace("&", "")
        .replace("+", "")
        .replace("/", " ")
        .strip()
    )

# usuwa znaki specialne
# pobiera: name(str)
# zwraca: str
def clean_service_name(name):
    if not name:
        return name
    return (
        name.replace("\xa0", " ")
            .strip()
    )

# wczytuje hasło z pliku
def load_password():
    path = "plik_na_hasło"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except:
        return ""

# formatuje pole Odoo
def fmt(v):
    if isinstance(v, list) and len(v) == 2:
        return f"{v[1]} (ID: {v[0]})"
    return v

# sprawdza czy produkcja zawiera odroczenie
# pobiera: prod_id
# zwraca bool
def has_deferred_activity(conn, prod_id):
    domain = [
        ("res_model", "=", "mrp.production"),
        ("res_id", "=", prod_id),
        ("summary", "=", "Odroczenie"),
    ]
    ids = conn.models.execute_kw(conn.db, conn.uid, conn.password,
                                 "mail.activity", "search", [domain])
    return len(ids) > 0

# pobiera zlecenia produkcji, które mają odpowiednie filtry
# zwraca: list(dict) 
def get_all_productions(conn):
    domain = [
        ("state", "=", "confirmed"),
        ("product_id.name", "not ilike", "helpdesk"),
        ("product_id.name", "not ilike", "TD"),
    ]
    ids = conn.models.execute_kw(conn.db, conn.uid, conn.password,
                                "mrp.production", "search", [domain])
    if not ids:
        return []

    records = conn.models.execute_kw(conn.db, conn.uid, conn.password,
                                "mrp.production", "read", [ids], {"fields": FIELDS})

    filtered = []
    for r in records:
        if not has_deferred_activity(conn, r["id"]):
            filtered.append(r)

    return filtered

# pobiera zlecenia produkcji(workordery) dla przygotowania
#zwraca: list(dict)
def get_preparation_workorders(conn):
    domain = [
        ("name", "=", "Przygotowanie produkcji"),
        ("state", "=", "ready"),
    ]

    ids = conn.models.execute_kw(conn.db, conn.uid, conn.password,
                                "mrp.workorder", "search", [domain])

    if not ids:
        return []

    workorders = conn.models.execute_kw(conn.db, conn.uid, conn.password,
                                        "mrp.workorder", "read", [ids],
                                        {"fields": ["id", "name", "production_id", "state", "sale_id"]})

    result = []
    for w in workorders:
        prod_id = w["production_id"][0]

        prod = conn.models.execute_kw(conn.db, conn.uid, conn.password,
                                      "mrp.production", "read", [[prod_id]],
                                      {"fields": FIELDS})

        if not prod:
            continue

        p = prod[0]

        if w["sale_id"]:
            origin_value = w["sale_id"][1]
        else:
            origin_value = p["origin"]

        mapped = {
            "id": w["id"],
            "production_id": w["production_id"],
            "name": p["name"],
            "state": w["state"],
            "product_id": p["product_id"],
            "origin": origin_value,
            "partner_id": p["partner_id"],
            "routing_id": p["routing_id"],
        }

        result.append(mapped)

    return result

# znajduje powiązane zlecenia
# zwraca: list(str) 
def find_linked_orders(conn, origin, selected_whmo, selected_partner_id):
    domain = [
        ("origin", "=", origin),
        ("name", "!=", selected_whmo)
    ]
    ids = conn.models.execute_kw(
        conn.db, conn.uid, conn.password,
        "mrp.production", "search", [domain]
    )
    if not ids:
        return []

    records = conn.models.execute_kw(
        conn.db, conn.uid, conn.password,
        "mrp.production", "read", [ids],
        {"fields": ["name", "partner_id", "routing_id"]}
    )

    linked = []

    selected_service = ""
    if selected_whmo:
        selected_prod = conn.models.execute_kw(
            conn.db, conn.uid, conn.password,
            "mrp.production", "search_read",
            [[("name", "=", selected_whmo)]],
            {"fields": ["routing_id"]}
        )
        if selected_prod:
            selected_service = selected_prod[0]["routing_id"][1].lower()

    if "rozliczenie roczne" not in selected_service:
        return []

    for r in records:
        other_partner = r["partner_id"][0]

        if other_partner == selected_partner_id:
            continue

        if not are_partners_related(conn, selected_partner_id, other_partner):
            continue

        other_service = r["routing_id"][1].lower()
        if "rozliczenie roczne" not in other_service:
            continue

        linked.append(r["name"])

    return linked

# tworzy nazwę folderu
# pobiera: str
# zwarac: str
def build_folder_name(whmo, linked=None):
    if linked:
        return f"{whmo} -> {linked}"
    return whmo

# tworzy folder zlecenia
def create_order_folder(folder_name):
    path = os.path.join(BASE_PROD, folder_name)
    os.makedirs(path, exist_ok=True)
    return path

# ustala właściwego klienta
# pobiera: partner_id
# zwraca: str
def get_real_client_name(conn, partner_id):

    partner = conn.models.execute_kw(
        conn.db, conn.uid, conn.password,
        "res.partner", "read", [[partner_id]],
        {"fields": ["name", "company_type"]}
    )[0]

    if partner["company_type"] == "person":
        return partner["name"]

    relations = conn.models.execute_kw(
        conn.db,
        conn.uid,
        conn.password,
        "res.partner.relation",
        "search_read",
        [[
            "|",
            ("left_partner_id", "=", partner_id),
            ("right_partner_id", "=", partner_id)
        ]],
        {"fields": ["type_id", "left_partner_id", "right_partner_id"]}
    )

    for rel in relations:
        rel_type = rel.get("type_id", ["", ""])[1].lower()

        if rel_type != "firma":
            continue

        left = rel.get("left_partner_id")
        right = rel.get("right_partner_id")

        if left and left[0] == partner_id and right:
            return right[1]

        if right and right[0] == partner_id and left:
            return left[1]

    return partner["name"]

# wybiera nazwę klienta
# pobiera: workorder_partner_id, production_partner_id
# zwraca: str
def get_client_name(conn, workorder_partner_id, production_partner_id):
    if workorder_partner_id:
        partner = conn.models.execute_kw(
            conn.db, conn.uid, conn.password,
            "res.partner", "read", [[workorder_partner_id]],
            {"fields": ["name"]}
        )[0]
        return partner["name"]

    return get_real_client_name(conn, production_partner_id)

# kopiuje strukturę katalogów
def copy_structure(possible_names, target_folder, client_name):
    base = "scieżka_do_struktur"

    found_service = None

    for root, dirs, files in os.walk(base):
        for d in dirs:
            for name in possible_names:
                if normalize(d) == normalize(name):
                    found_service = os.path.join(root, d)
                    break
            if found_service:
                break
        if found_service:
            break

    if not found_service:
        for root, dirs, files in os.walk(base):
            for d in dirs:
                for name in possible_names:
                    if normalize(name) in normalize(d):
                        found_service = os.path.join(root, d)
                        break
                if found_service:
                    break
            if found_service:
                break

    if not found_service:
        print(f"Nie znaleziono folderu usługi: {possible_names}")
        return

    structure_folder = None
    STRUCTURE_KEYWORDS = [
        "struktura katalogow",
        "struktura katalogów",
        "struktura katalogu",
    ]

    for root, dirs, files in os.walk(found_service):
        for d in dirs:
            nd = normalize(d)
            if any(keyword in nd for keyword in STRUCTURE_KEYWORDS):
                structure_folder = os.path.join(root, d)
                break
        if structure_folder:
            break

    if not structure_folder:
        print(f"Brak folderu struktury w: {found_service}")
        return

    try:
        shutil.copytree(structure_folder, target_folder, dirs_exist_ok=True)
        print("Skopiowano strukturę katalogów.")
    except Exception as e:
        print("Błąd podczas kopiowania struktury:", e)

    if client_name:
        for item in os.listdir(target_folder):
            if normalize(item) == "imie nazwisko":
                os.rename(
                    os.path.join(target_folder, item),
                    os.path.join(target_folder, client_name)
                )
                print(f"Zmieniono nazwę folderu '{item}' na '{client_name}'")
                break

# dopisuje WHMO do SO
# pobiera: origin, whmo
# zwraca: bool
def append_whmo_to_sale_line(conn, origin, whmo):
    if not origin or not origin.startswith("SO"):
        return False

    sale_ids = conn.models.execute_kw(
        conn.db, conn.uid, conn.password,
        "sale.order", "search", [[("name", "=", origin)]]
    )
    if not sale_ids:
        return False

    sale_id = sale_ids[0]

    lines = conn.models.execute_kw(
        conn.db, conn.uid, conn.password,
        "sale.order.line", "search_read",
        [[("order_id", "=", sale_id)]],
        {"fields": ["name", "product_id"]}
    )

    for line in lines:
        if line["product_id"] and line["product_id"][0] == selected["product_id"][0]:
            current_name = line["name"]

            if whmo in current_name:
                return True

            new_name = f"{current_name}\n- {whmo}"

            conn.models.execute_kw(
                conn.db, conn.uid, conn.password,
                "sale.order.line", "write",
                [[line["id"]], {"name": new_name}]
            )
            return True

    return False

# sprawdza relacje partnerów do zoliczenia rocznego
# zwraca: bool
def are_partners_related(conn, partner_a, partner_b):
    relations = conn.models.execute_kw(
        conn.db, conn.uid, conn.password,
        "res.partner.relation", "search_read",
        [[
            "|",
            ("left_partner_id", "in", [partner_a, partner_b]),
            ("right_partner_id", "in", [partner_a, partner_b])
        ]],
        {"fields": ["type_id", "left_partner_id", "right_partner_id"]}
    )

    for rel in relations:
        rel_type = rel["type_id"][1].lower()

        if rel_type in ("partner fiskalny", "małżonek"):
            left = rel["left_partner_id"][0]
            right = rel["right_partner_id"][0]

            if {left, right} == {partner_a, partner_b}:
                return True

    return False

# sprawdza czy WHMO zostało dopisane w SO
# pobiera: origin, whmo
# zwraca: bool
def was_whmo_added(conn, origin, whmo):
    sale_ids = conn.models.execute_kw(
        conn.db, conn.uid, conn.password,
        "sale.order", "search", [[("name", "=", origin)]]
    )
    if not sale_ids:
        return False

    lines = conn.models.execute_kw(
        conn.db, conn.uid, conn.password,
        "sale.order.line", "search_read",
        [[("order_id", "=", sale_ids[0])]],
        {"fields": ["name"]}
    )

    return any(whmo in l["name"] for l in lines)

# sprawdza czy zostało wszystko wykonane następnie kończy workorder
# pobiera: production_id, origin, whmo, target_folder
# zwraca bool
def finish_preparation_workorder(conn, production_id, origin, whmo, target_folder):
    if not os.path.exists(target_folder):
        print("Folder nie został utworzony  nie można zakończyć workorderu.")
        return False

    if len(os.listdir(target_folder)) == 0:
        print("Folder jest pusty  struktura nie została skopiowana.")
        return False

    if not was_whmo_added(conn, origin, whmo):
        print("WHMO nie zostało dopisane  nie można zakończyć workorderu.")
        return False

    workorders = conn.models.execute_kw(
        conn.db, conn.uid, conn.password,
        "mrp.workorder", "search_read",
        [[("production_id", "=", production_id)]],
        {"fields": ["id", "name", "state"]}
    )

    if not workorders:
        print("Brak workorderów.")
        return False

    for w in workorders:
        if w["name"].lower() == "przygotowanie produkcji":
            if w["state"] == "done":
                print("Workorder 'Przygotowanie produkcji' już jest DONE.")
                return True

            conn.models.execute_kw(
                conn.db, conn.uid, conn.password,
                "mrp.workorder", "button_finish",
                [[w["id"]]]
            )
            print("Ustawiono 'Przygotowanie produkcji' na DONE.")
            return True

    print("Nie znaleziono workorderu 'Przygotowanie produkcji'.")
    return False

# dodaje wpis z szabolu
# pobiera: template_name, production_id, as_note
# zwraca: bool
def post_message_from_template(conn, template_name, production_id, partner_id, as_note=False):
    template_ids = conn.models.execute_kw(
        conn.db, conn.uid, conn.password,
        "mail.template", "search",
        [[("name", "=", template_name)]]
    )
    if not template_ids:
        print("Nie znaleziono szablonu.")
        return False

    template_id = template_ids[0]

    email_values = conn.models.execute_kw(
        conn.db, conn.uid, conn.password,
        "mail.template", "generate_email",
        [template_id, production_id]
    ) or {}

    subject = (email_values.get("subject") or "")
    body = (email_values.get("body_html") or email_values.get("body") or "<p></p>")

    subtype_id = conn.models.execute_kw(
        conn.db, conn.uid, conn.password,
        "ir.model.data", "xmlid_to_res_id",
        ["mail.mt_comment"]
    )

    msg_id = conn.models.execute_kw(
        conn.db, conn.uid, conn.password,
        "mrp.production", "message_post",
        [[production_id]],
        {
            "subject": subject,
            "body": body,
            "message_type": "comment",
            "subtype_id": subtype_id,
            "partner_ids": [(4, partner_id)],
            "notify": True,
        }
    )
    print(f"Wpis w chatter dodany. message_id={msg_id}")
    return True

# wyświetla listę zleceń (do zmiany)
# pobiera: records (list), workorders (list)
def show_all(records, workorders):
    print("\nZLECENIA PRODUKCJI:\n")

    all_records = records + workorders

    for r in all_records:
        print(f"{r['name']} (ID: {r['id']})")
        for f in FIELDS:
            print(f"  {f:15} - {fmt(r.get(f))}")
        print("----------------------------------")

    print("\nWpisz: stworz dla zlecenia WHMOxxxxx\n")

if __name__ == "__main__":
    conn = Connector()
    pwd = load_password()
    conn.connect(password=pwd)

    records = get_all_productions(conn)
    workorders = get_preparation_workorders(conn)

    if not records and not workorders:
        print("Brak zleceń.")
        exit()

    show_all(records, workorders)

    while True:
        cmd = input("> ").strip().lower()

        if cmd.startswith("stworz dla zlecenia"):
            parts = cmd.split()
            if len(parts) != 4:
                print("Użyj: stworz dla zlecenia WHMOxxxxx")
                continue

            whmo = parts[3].upper()

            selected = None
            for r in records + workorders:
                if r["name"] == whmo:
                    selected = r
                    break

            if not selected:
                print("Nie znaleziono zlecenia.")
                continue

            if selected["state"] == "confirmed":
                conn.models.execute_kw(
                    conn.db, conn.uid, conn.password,
                    "mrp.production", "button_plan",
                    [[selected["id"]]]
                )
                print("Utworzono zlecenie operacji")

                refreshed = conn.models.execute_kw(
                    conn.db, conn.uid, conn.password,
                    "mrp.production", "read",
                    [[selected["id"]]],
                    {"fields": FIELDS}
                )[0]
                selected = refreshed

            linked_orders = find_linked_orders(conn, selected["origin"], whmo, selected["partner_id"][0])
            linked = linked_orders[0] if linked_orders else None

            folder_name = build_folder_name(whmo, linked)

            folder_path = create_order_folder(folder_name)

            print(f"\nUtworzono folder: {folder_path}")
            raw_service_name = selected["routing_id"][1]
            service_name = clean_service_name(raw_service_name)
            possible_names = [service_name]
            workorder_partner_id = selected.get("partner_id", [None])[0]
            production_partner_id = selected["partner_id"][0]
            
            client_name = get_client_name(conn, workorder_partner_id, production_partner_id)
            print("Możliwe nazwy usługi:", possible_names)
            print("Klient:", client_name)

            copy_structure(possible_names, folder_path, client_name)

            append_whmo_to_sale_line(conn, selected["origin"], whmo)

            if "production_id" in selected and selected["production_id"]:
                production_id = selected["production_id"][0]
            else:
                production_id = selected["id"]

            success = finish_preparation_workorder(
                conn,
                production_id,
                selected["origin"],
                whmo,
                folder_path
            )
            if not success:
                break

            partner_id = selected["partner_id"][0]

            post_message_from_template(
                conn,
                "Produkcja - Zlecenie w toku (maszynowe)",
                production_id,
                partner_id
            )
            break

        elif cmd in ("exit", "quit", "q"):
            break
        else:
            print("Użyj: stworz dla zlecenia WHMOxxxxx lub exit")
# Autor: Wiktor Barczyk