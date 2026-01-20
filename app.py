from flask import Flask, render_template, request, redirect, url_for, send_file, session
import json
from datetime import datetime
from pathlib import Path
from io import BytesIO

import qrcode
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "change-this-to-any-random-string"

ADMIN_PASSWORD = "9900"  # change this

# -------------------------
# Language (EN/FI)
# -------------------------

TRANSLATIONS = {
    "en": {
        "home": "Home",
        "menu": "Menu",
        "reservation": "Reservation",
        "order": "Order",
        "admin": "Admin",
        "admin_title": "Reservations",
        "admin_subtitle": "Staff view — newest first",
        "delete": "Delete",
        "logout": "Logout",
    },
    "fi": {
        "home": "Koti",
        "menu": "Menu",
        "reservation": "Varaus",
        "order": "Tilaus",
        "admin": "Ylläpito",
        "name": "Nimi",
        "date": "Päivä",
        "people": "Henkilöä",
        "notes": "Lisätiedot",
        "phone": "Puhelin",
        "select_people": "Valitse henkilömäärä...",
        "reservation_title": "Pöytävaraus",
        "reservation_subtitle": "Varaa pöytä helposti. Ei käyttäjätiliä.",
        "reservation_success_title": "Varaus vahvistettu",
        "reservation_success_text": "Pöytäsi on varattu onnistuneesti.",
        "reservation_saved": "Varauksesi on tallennettu.",
        "time": "Aika",
        "admin_title": "Varaukset",
        "admin_subtitle": "Henkilökunnan näkymä — uusimmat ensin",
        "logout": "Kirjaudu ulos",
        "delete": "Poista",
        "no_reservations": "Ei varauksia vielä.",
    },
}

def get_lang():
    lang = request.args.get("lang", "").lower()
    return lang if lang in ("fi", "en") else "fi"

def t(key: str):
    return TRANSLATIONS.get(get_lang(), TRANSLATIONS["fi"]).get(key, key)

@app.context_processor
def inject_lang():
    return {"t": t, "lang": get_lang()}

# -------------------------
# Data files
# -------------------------

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

RESERVATIONS_FILE = DATA_DIR / "reservations.json"
ORDERS_FILE = DATA_DIR / "orders.json"
MENU_FILE = DATA_DIR / "menu.json"

MENU_UPLOAD_DIR = Path("static/images/menu")
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# -------------------------
# Helpers
# -------------------------

def load_json(path):
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").strip()
    return json.loads(text) if text else []

def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def load_reservations():
    return load_json(RESERVATIONS_FILE)

def save_reservations(items):
    save_json(RESERVATIONS_FILE, items)

def load_orders():
    return load_json(ORDERS_FILE)

def save_orders(items):
    save_json(ORDERS_FILE, items)

def load_menu():
    return load_json(MENU_FILE)

def save_menu(items):
    save_json(MENU_FILE, items)

def save_uploaded_image(file_storage):
    if not file_storage or not file_storage.filename:
        return ""
    filename = secure_filename(file_storage.filename)
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        raise ValueError("Unsupported image type")
    MENU_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    unique = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
    file_storage.save(str(MENU_UPLOAD_DIR / unique))
    return unique

def make_qr(url: str):
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# -------------------------
# Public routes
# -------------------------

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/menu")
def menu():
    items = sorted(load_menu(), key=lambda x: (x.get("category",""), x.get("name","")))
    return render_template("menu.html", items=items)

@app.route("/reservation", methods=["GET", "POST"])
def reservation():
    if request.method == "POST":
        data = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "name": request.form.get("name",""),
            "phone": request.form.get("phone",""),
            "date": request.form.get("date",""),
            "time": request.form.get("time",""),
            "people": request.form.get("people",""),
            "notes": request.form.get("notes",""),
        }
        items = load_reservations()
        items.append(data)
        save_reservations(items)
        return render_template("reservation_success.html", reservation=data)
    return render_template("reservation.html")

@app.route("/order", methods=["GET","POST"])
def order():
    if request.method == "POST":
        data = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "name": request.form.get("name",""),
            "table": request.form.get("table",""),
            "items": request.form.get("items",""),
            "notes": request.form.get("notes",""),
            "status": "new",
        }
        orders = load_orders()
        orders.append(data)
        save_orders(orders)
        return render_template("order_success.html", order=data)
    return render_template("order.html")

# -------------------------
# Admin auth
# -------------------------

@app.route("/admin-login", methods=["GET","POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin"))
        error = "Wrong password"
    return render_template("admin_login.html", error=error)

@app.route("/admin-logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))

# -------------------------
# Admin pages
# -------------------------

@app.route("/admin", methods=["GET","POST"])
def admin():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    items = sorted(load_reservations(), key=lambda x: x.get("id",""), reverse=True)

    if request.method == "POST":
        delete_id = request.form.get("delete_id")
        if delete_id:
            items = [r for r in items if r["id"] != delete_id]
            save_reservations(items)
            return redirect(url_for("admin", lang=get_lang()))

    return render_template("admin.html", reservations=items)

@app.route("/admin/orders", methods=["GET","POST"])
def admin_orders():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    orders = load_orders()
    if request.method == "POST":
        delete_id = request.form.get("delete_id")
        orders = [o for o in orders if o["id"] != delete_id]
        save_orders(orders)
        return redirect(url_for("admin_orders"))

    orders = sorted(orders, key=lambda x: x.get("id",""), reverse=True)
    return render_template("admin_orders.html", orders=orders)

@app.route("/admin/menu", methods=["GET","POST"])
def admin_menu():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    error = None
        # delete menu item
    delete_id = request.form.get("delete_id")
    if delete_id:
        items = load_menu()
        items = [i for i in items if str(i.get("id")) != str(delete_id)]
        save_menu(items)
        return redirect(url_for("admin_menu"))

    if request.method == "POST":
        try:
            price = float(request.form.get("price","").replace(",","."))

            item = {
                "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                "name": request.form.get("name",""),
                "category": request.form.get("category",""),
                "description": request.form.get("description",""),
                "price": price,
                "image": save_uploaded_image(request.files.get("image")),
                "available": True,
            }

            items = load_menu()
            items.append(item)
            save_menu(items)
            return redirect(url_for("admin_menu"))

        except Exception as e:
            error = str(e)

    items = sorted(load_menu(), key=lambda x: x.get("id",""), reverse=True)
    return render_template("admin_menu.html", items=items, error=error)

# -------------------------
# QR
# -------------------------

@app.route("/qr")
def qr_page():
    return render_template("qr.html")

@app.route("/qr/menu")
def qr_menu():
    return send_file(make_qr(request.url_root.rstrip("/") + "/menu"), mimetype="image/png")

@app.route("/qr/reservation")
def qr_reservation():
    return send_file(make_qr(request.url_root.rstrip("/") + "/reservation"), mimetype="image/png")

@app.route("/qr/order")
def qr_order():
    return send_file(make_qr(request.url_root.rstrip("/") + "/order"), mimetype="image/png")

# -------------------------

if __name__ == "__main__":
    app.run(debug=True)
