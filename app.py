from __future__ import annotations

import json
import os
import random
import secrets
import statistics
import csv
import io
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, abort, flash, jsonify, make_response, redirect, render_template, request, session, url_for
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


app = Flask(__name__)
Path(app.instance_path).mkdir(parents=True, exist_ok=True)
secret_key_file = Path(app.instance_path) / ".secret_key"
app.secret_key = os.environ.get("FLASK_SECRET_KEY")
if not app.secret_key:
    if not secret_key_file.exists():
        secret_key_file.write_text(secrets.token_hex(32), encoding="utf-8")
    app.secret_key = secret_key_file.read_text(encoding="utf-8").strip()

database_url = os.environ.get("DATABASE_URL", "sqlite:///users.db")
if database_url.startswith("postgres://"):
    database_url = "postgresql://" + database_url.removeprefix("postgres://")

app.config.update(
    SQLALCHEMY_DATABASE_URI=database_url,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    MAX_CONTENT_LENGTH=12 * 1024 * 1024,
    UPLOAD_FOLDER=str(Path(app.root_path) / "static" / "uploads"),
    MAIL_SERVER=os.environ.get("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_PORT=int(os.environ.get("MAIL_PORT", "587")),
    MAIL_USE_TLS=os.environ.get("MAIL_USE_TLS", "true").lower() == "true",
    MAIL_USERNAME=os.environ.get("MAIL_USERNAME"),
    MAIL_PASSWORD=os.environ.get("MAIL_PASSWORD"),
    MAIL_DEFAULT_SENDER=os.environ.get("MAIL_USERNAME") or "noreply@agritrust.local",
    APP_DEBUG=os.environ.get("FLASK_DEBUG", "1").lower() in {"1", "true", "yes"},
)
Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

db = SQLAlchemy(app)
mail = Mail(app)
ALLOWED_UPLOAD_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "pdf"}
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
LISTING_KINDS = {"produce", "residue", "supply", "machine", "transport"}


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    otp_verified = db.Column(db.Boolean, default=False, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)


class MarketplaceListing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(32), nullable=False, index=True)
    payload = db.Column(db.Text, nullable=False)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    receipt = db.Column(db.String(20), unique=True, nullable=False)
    items = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(32), nullable=False, default="Requested")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class RentalRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class TransactionRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    receipt = db.Column(db.String(32), nullable=False, index=True)
    product_name = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(48), nullable=False, index=True)
    region = db.Column(db.String(100), nullable=False, default="Not recorded")
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Float, nullable=False, default=0)
    status = db.Column(db.String(32), nullable=False, default="Requested", index=True)
    transaction_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    is_sample = db.Column(db.Boolean, nullable=False, default=False, index=True)


_SAMPLE_PRODUCTS = [
    ("Produce", "Wheat", 2680), ("Produce", "Rice", 3150),
    ("Produce", "Tomatoes", 1850), ("Produce", "Onions", 2240),
    ("Produce", "Cotton", 6900), ("Produce", "Sugarcane", 340),
    ("Residue", "Wheat Straw", 520), ("Residue", "Rice Husk", 360),
    ("Residue", "Corn Stover", 430), ("Residue", "Sugarcane Bagasse", 610),
    ("Farm supplies", "Wheat Seeds", 1450), ("Farm supplies", "Organic Fertilizer", 780),
    ("Farm supplies", "Drip Irrigation Kit", 4250), ("Farm supplies", "Sprayer", 1950),
    ("Machinery", "Tractor Rental", 500), ("Machinery", "Harvester Rental", 820),
    ("Transport", "Farm Produce Haulage", 2300), ("Transport", "Cold Storage Truck", 3900),
]
_SAMPLE_REGIONS = ["Punjab", "Haryana", "Uttar Pradesh", "Maharashtra", "Madhya Pradesh", "Rajasthan", "Gujarat", "Karnataka", "Bihar", "Telangana"]


def _make_sample_transactions(now: datetime | None = None) -> list[TransactionRecord]:
    """Create a stable 150-record demo dataset spanning the last 12 months."""
    rng = random.Random(20261126)
    now = now or datetime.utcnow()
    records = []
    for index in range(1, 151):
        category, product, base_price = rng.choice(_SAMPLE_PRODUCTS)
        quantity = rng.randint(1, 28) if category in {"Produce", "Machinery", "Transport"} else rng.randint(3, 85)
        unit_price = round(base_price * rng.uniform(0.82, 1.18), 2)
        status = rng.choices(["Completed", "Requested", "Cancelled"], weights=[78, 17, 5], k=1)[0]
        records.append(TransactionRecord(
            receipt=f"DEMO-{index:04d}",
            product_name=product,
            category=category,
            region=rng.choice(_SAMPLE_REGIONS),
            quantity=quantity,
            unit_price=unit_price,
            status=status,
            transaction_date=now - timedelta(days=rng.randrange(365), hours=rng.randrange(24)),
            is_sample=True,
        ))
    return records


with app.app_context():
    db.create_all()
    if not MarketplaceListing.query.filter_by(kind="machine").first():
        for machine in (
            {"name": "Tractor", "rate": 500, "description": "Standard farming tractor for plowing and hauling."},
            {"name": "Harvester", "rate": 800, "description": "Crop harvester suitable for wheat and rice."},
            {"name": "Rotavator", "rate": 300, "description": "Machine for soil tilling and preparation."},
        ):
            db.session.add(MarketplaceListing(kind="machine", payload=json.dumps(machine)))
    if not TransactionRecord.query.filter_by(is_sample=True).first():
        db.session.add_all(_make_sample_transactions())
    db.session.commit()


def _entry_dict(entry: MarketplaceListing) -> dict:
    data = json.loads(entry.payload)
    data["id"] = entry.id
    data["kind"] = entry.kind
    return data


def _entries(kind: str) -> list[dict]:
    rows = MarketplaceListing.query.filter_by(kind=kind).order_by(MarketplaceListing.id.desc()).all()
    return [_entry_dict(row) for row in rows]


def _save_entry(kind: str, data: dict, entry_id: int | None = None) -> dict | None:
    if kind not in LISTING_KINDS:
        abort(404)
    entry = MarketplaceListing.query.filter_by(id=entry_id, kind=kind).first() if entry_id else None
    if entry_id and entry is None:
        return None
    if entry is None:
        entry = MarketplaceListing(kind=kind, payload="{}")
        db.session.add(entry)
    entry.payload = json.dumps(data, ensure_ascii=False)
    db.session.commit()
    return _entry_dict(entry)


def _upload(file_storage, allowed: set[str] | None = None) -> str | None:
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    extension = Path(filename).suffix.lower().lstrip(".")
    if not filename or extension not in (allowed or ALLOWED_UPLOAD_EXTENSIONS):
        abort(400, description="Unsupported upload file type.")
    stored_name = f"{secrets.token_hex(8)}{Path(filename).suffix.lower()}"
    file_storage.save(Path(app.config["UPLOAD_FOLDER"]) / stored_name)
    return stored_name


def _listing_json(data: dict) -> dict:
    result = dict(data)
    if result.get("image"):
        result["image_url"] = url_for("static", filename=f"uploads/{result['image']}")
    if result.get("images"):
        result["image_urls"] = [url_for("static", filename=f"uploads/{name}") for name in result["images"]]
    return result


def _read_json_file(filename: str) -> list[dict]:
    path = Path(app.root_path) / "static" / filename
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def _transaction_category(value: str) -> str:
    category = value.strip().lower()
    if "residue" in category or "straw" in category or "husk" in category:
        return "Residue"
    if "supply" in category or "seed" in category or "fertiliz" in category or "spray" in category:
        return "Farm supplies"
    if "machin" in category or "tractor" in category or "harvest" in category:
        return "Machinery"
    if "transport" in category or "haulage" in category:
        return "Transport"
    return "Produce"


def _analytics_data(period: str) -> dict:
    now = datetime.utcnow()
    day_ranges = {"30d": 30, "90d": 90, "12m": 365}
    start = now - timedelta(days=day_ranges[period]) if period in day_ranges else None
    query = TransactionRecord.query
    if start:
        query = query.filter(TransactionRecord.transaction_date >= start)
    records = query.order_by(TransactionRecord.transaction_date.desc(), TransactionRecord.id.desc()).all()

    orders: dict[str, dict] = {}
    category_data: dict[str, dict] = defaultdict(lambda: {"value": 0.0, "orders": set()})
    product_data: dict[str, dict] = defaultdict(lambda: {"value": 0.0, "orders": set(), "category": ""})
    region_data: dict[str, dict] = defaultdict(lambda: {"value": 0.0, "orders": set()})
    monthly_values: dict[str, float] = defaultdict(float)
    completed_value = pending_value = cancelled_value = 0.0

    for record in records:
        value = record.quantity * record.unit_price
        status = record.status.strip().lower()
        order = orders.setdefault(record.receipt, {
            "status": record.status,
            "value": 0.0,
            "is_sample": record.is_sample,
            "date": record.transaction_date,
        })
        order["value"] += value
        if status == "completed":
            completed_value += value
            category_data[record.category]["value"] += value
            category_data[record.category]["orders"].add(record.receipt)
            product_data[record.product_name]["value"] += value
            product_data[record.product_name]["orders"].add(record.receipt)
            product_data[record.product_name]["category"] = record.category
            region_data[record.region]["value"] += value
            region_data[record.region]["orders"].add(record.receipt)
            monthly_values[record.transaction_date.strftime("%Y-%m")] += value
        elif status in {"requested", "pending"}:
            pending_value += value
        elif status in {"cancelled", "canceled"}:
            cancelled_value += value

    completed_orders = [order for order in orders.values() if order["status"].strip().lower() == "completed"]
    pending_orders = [order for order in orders.values() if order["status"].strip().lower() in {"requested", "pending"}]
    cancelled_orders = [order for order in orders.values() if order["status"].strip().lower() in {"cancelled", "canceled"}]
    completed_order_values = [order["value"] for order in completed_orders]

    if period == "all" and records:
        first_month = min(record.transaction_date for record in records).replace(day=1)
    else:
        first_month = (start or now - timedelta(days=365)).replace(day=1)
    last_month = now.replace(day=1)
    month_keys = []
    cursor = first_month
    while cursor <= last_month:
        month_keys.append(cursor.strftime("%Y-%m"))
        cursor = cursor.replace(year=cursor.year + (cursor.month == 12), month=(cursor.month % 12) + 1)
    max_month_value = max((monthly_values[key] for key in month_keys), default=0)
    trend = [{
        "label": datetime.strptime(key, "%Y-%m").strftime("%b %y"),
        "value": round(monthly_values[key], 2),
        "height": round(monthly_values[key] / max_month_value * 100) if max_month_value else 0,
    } for key in month_keys]

    categories = [{"name": name, "value": round(data["value"], 2), "orders": len(data["orders"])}
                  for name, data in sorted(category_data.items(), key=lambda item: item[1]["value"], reverse=True)]
    max_category_value = max((item["value"] for item in categories), default=0)
    for item in categories:
        item["share"] = round(item["value"] / max_category_value * 100) if max_category_value else 0
    top_products = [{"name": name, "category": data["category"], "value": round(data["value"], 2), "orders": len(data["orders"])}
                    for name, data in sorted(product_data.items(), key=lambda item: item[1]["value"], reverse=True)[:6]]
    regions = [{"name": name, "value": round(data["value"], 2), "orders": len(data["orders"])}
               for name, data in sorted(region_data.items(), key=lambda item: item[1]["value"], reverse=True)[:8]]

    sample_receipts = {receipt for receipt, order in orders.items() if order["is_sample"]}
    live_receipts = set(orders) - sample_receipts
    return {
        "records": records,
        "period": period,
        "stats": {
            "transactions": len(orders),
            "completed": len(completed_orders),
            "pending": len(pending_orders),
            "cancelled": len(cancelled_orders),
            "completed_value": round(completed_value, 2),
            "pending_value": round(pending_value, 2),
            "cancelled_value": round(cancelled_value, 2),
            "average_order": round(statistics.mean(completed_order_values), 2) if completed_order_values else 0,
            "median_order": round(statistics.median(completed_order_values), 2) if completed_order_values else 0,
            "sample_transactions": len(sample_receipts),
            "live_transactions": len(live_receipts),
        },
        "trend": trend,
        "categories": categories,
        "top_products": top_products,
        "regions": regions,
        "latest": [{
            "receipt": record.receipt,
            "date": record.transaction_date,
            "product": record.product_name,
            "category": record.category,
            "region": record.region,
            "quantity": record.quantity,
            "value": round(record.quantity * record.unit_price, 2),
            "status": record.status,
            "is_sample": record.is_sample,
        } for record in records[:12]],
    }


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/set_language/<lang>")
def set_language(lang: str):
    if lang not in {"en", "hi"}:
        abort(404)
    response = make_response(redirect(request.referrer or url_for("home")))
    response.set_cookie("lang", lang, max_age=30 * 24 * 60 * 60, samesite="Lax")
    return response


@app.route("/landing")
def landing():
    return render_template("landing.html", username=session.get("user", "Guest"))


@app.route("/dash")
def dash():
    return render_template("dash.html")


@app.route("/dashuser")
def dashuser():
    return render_template("dashuser.html", username=session.get("user", "Guest"))


@app.route("/analytics")
def analytics():
    period = request.args.get("period", "12m")
    if period not in {"30d", "90d", "12m", "all"}:
        period = "12m"
    return render_template("analytics.html", **_analytics_data(period))


@app.route("/analytics/export.csv")
def analytics_export():
    period = request.args.get("period", "12m")
    if period not in {"30d", "90d", "12m", "all"}:
        period = "12m"
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["data_source", "receipt", "date_utc", "product", "category", "region", "quantity", "unit_price_inr", "order_value_inr", "status"])
    for record in _analytics_data(period)["records"]:
        writer.writerow([
            "sample" if record.is_sample else "live",
            record.receipt,
            record.transaction_date.isoformat(timespec="seconds"),
            record.product_name,
            record.category,
            record.region,
            record.quantity,
            f"{record.unit_price:.2f}",
            f"{record.quantity * record.unit_price:.2f}",
            record.status,
        ])
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename=agritrust-transactions-{period}.csv"
    return response


@app.route("/analytics/add", methods=["POST"])
def analytics_add():
    name = request.form.get("product_name", "").strip()
    region = request.form.get("region", "").strip()
    status = request.form.get("status", "Requested").strip().title()
    transaction_date = request.form.get("transaction_date", "").strip()
    try:
        quantity = int(request.form.get("quantity", ""))
        unit_price = round(float(request.form.get("unit_price", "")), 2)
        if not name or quantity < 1 or quantity > 1_000_000 or unit_price < 0 or unit_price > 100_000_000:
            raise ValueError
        if status not in {"Requested", "Completed", "Cancelled"}:
            raise ValueError
        created_at = datetime.strptime(transaction_date, "%Y-%m-%d") if transaction_date else datetime.utcnow()
    except (TypeError, ValueError):
        flash("Enter a product, positive quantity, valid price, and supported status.", "error")
        return redirect(url_for("analytics", period="all"))

    db.session.add(TransactionRecord(
        receipt=f"MAN-{secrets.token_hex(3).upper()}",
        product_name=name[:180],
        category=_transaction_category(request.form.get("category", "produce")),
        region=region[:100] or "Not recorded",
        quantity=quantity,
        unit_price=unit_price,
        status=status,
        transaction_date=created_at,
        is_sample=False,
    ))
    db.session.commit()
    flash("Transaction record saved. Analytics now includes your entry.", "success")
    return redirect(url_for("analytics", period="all"))


@app.route("/shop")
@app.route("/buy")
def shop():
    return render_template("shop.html", produce_listings=[_listing_json(entry) for entry in _entries("produce")])


@app.route("/buy-residues")
def buy_residues():
    return render_template("buy_residues.html", residue_listings=_entries("residue"))


@app.route("/rent")
def rent_machinery():
    return redirect(url_for("rent_machines"))


@app.route("/rent_machines")
def rent_machines():
    return render_template("rent_machines.html", machines=_entries("machine"))


@app.route("/buy_supplies")
def buy_supplies():
    return render_template(
        "buy_supplies.html",
        products=_read_json_file("supplies.json"),
        supply_listings=[_listing_json(entry) for entry in _entries("supply")],
    )


@app.route("/supplies")
def supplies():
    return render_template("supplies.html", supplies=_entries("supply"))


@app.route("/sell_transport")
def sell_transport():
    return render_template("sell_transport.html", transports=_entries("transport"))


@app.route("/sell", methods=["GET", "POST"])
def sell():
    if request.method == "GET":
        return render_template("sell.html", listings=_entries("produce"))

    fields = (
        "crop_type", "variety", "quantity", "min_order", "quality_grade", "moisture",
        "harvest_date", "price", "msp", "location", "farm_size", "soil_type", "state",
        "residue", "organic", "packaging", "delivery_date", "description",
    )
    data = {field: request.form.get(field, "").strip() for field in fields}
    required = (
        "crop_type", "variety", "quantity", "min_order", "quality_grade", "harvest_date",
        "price", "location", "state", "residue", "organic",
    )
    missing = [field for field in required if not data[field]]
    if missing:
        message = "Complete all required produce listing fields."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(success=False, error=message, missing=missing), 400
        flash(message, "error")
        return redirect(url_for("sell"))

    current_id = request.form.get("edit_id", type=int)
    existing = MarketplaceListing.query.filter_by(id=current_id, kind="produce").first() if current_id else None
    previous = json.loads(existing.payload) if existing else {}
    submitted_images = request.form.getlist("existing_images[]")
    kept_images = [Path(item.split("?")[0]).name for item in submitted_images]
    kept_images = [name for name in kept_images if (Path(app.config["UPLOAD_FOLDER"]) / name).is_file()]
    if not submitted_images:
        kept_images = list(previous.get("images", []))
    for image_file in request.files.getlist("images"):
        stored = _upload(image_file, IMAGE_EXTENSIONS)
        if stored:
            kept_images.append(stored)
    data["images"] = kept_images
    data["certificate"] = _upload(request.files.get("certificate")) or previous.get("certificate")
    data["govt_proof"] = _upload(request.files.get("govt_proof")) or previous.get("govt_proof")
    data["status"] = "Listed"
    listing = _save_entry("produce", data, current_id)
    if listing is None:
        return jsonify(success=False, error="Listing not found."), 404
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        payload = _listing_json(listing)
        payload["images"] = payload.get("image_urls", [])
        return jsonify(success=True, listing=payload)
    flash("Produce listing saved.", "success")
    return redirect(url_for("sell"))


@app.route("/api/listings/<kind>", methods=["GET", "POST"])
def api_listings(kind: str):
    if kind not in LISTING_KINDS:
        abort(404)
    if request.method == "GET":
        return jsonify([_listing_json(entry) for entry in _entries(kind)])

    data = request.get_json(silent=True) or request.form.to_dict()
    data.pop("kind", None)
    entry_id = None
    if data.get("id"):
        try:
            entry_id = int(data.pop("id"))
        except (TypeError, ValueError):
            return jsonify(success=False, error="Invalid listing id."), 400
    upload = request.files.get("image")
    allowed_uploads = ALLOWED_UPLOAD_EXTENSIONS if kind == "residue" else IMAGE_EXTENSIONS
    stored = _upload(upload, allowed_uploads) if upload else None
    if stored:
        data["image"] = stored
    elif entry_id:
        existing = MarketplaceListing.query.filter_by(id=entry_id, kind=kind).first()
        if existing:
            data["image"] = json.loads(existing.payload).get("image")
    required_name = "serviceName" if kind == "transport" else "name"
    if not str(data.get(required_name, "")).strip():
        return jsonify(success=False, error="A name is required."), 400
    saved = _save_entry(kind, data, entry_id)
    if saved is None:
        return jsonify(success=False, error="Listing not found."), 404
    return jsonify(success=True, listing=_listing_json(saved))


@app.route("/api/listings/<kind>/<int:entry_id>", methods=["DELETE"])
def api_delete_listing(kind: str, entry_id: int):
    if kind not in LISTING_KINDS:
        abort(404)
    entry = MarketplaceListing.query.filter_by(id=entry_id, kind=kind).first()
    if entry is None:
        return jsonify(success=False, error="Listing not found."), 404
    db.session.delete(entry)
    db.session.commit()
    return jsonify(success=True)


@app.route("/sell_residue", methods=["GET", "POST"])
def sell_residue():
    if request.method == "POST":
        return api_listings("residue")
    return render_template("sell_residue.html", residue_listings=_entries("residue"))


@app.route("/add_residue", methods=["POST"])
def add_residue():
    data = {
        "name": request.form.get("name") or request.form.get("residue_name", ""),
        "mobile": request.form.get("mobile", ""),
        "type": request.form.get("type", ""),
        "qty": request.form.get("qty") or request.form.get("quantity", ""),
        "location": request.form.get("location", ""),
        "desc": request.form.get("desc") or request.form.get("description", ""),
    }
    return jsonify(success=True, residue=_save_entry("residue", data))


@app.route("/add_machine", methods=["POST"])
def add_machine():
    data = request.form.to_dict()
    data["description"] = data.pop("desc", data.get("description", ""))
    stored = _upload(request.files.get("image"), IMAGE_EXTENSIONS)
    if stored:
        data["image"] = stored
    if not data.get("name"):
        return jsonify(success=False, error="Machine name is required."), 400
    saved = _save_entry("machine", data, request.form.get("id", type=int))
    if saved is None:
        return jsonify(success=False, error="Machine not found."), 404
    return jsonify(success=True, machine=_listing_json(saved))


@app.route("/rent_machine", methods=["POST"])
def rent_machine():
    data = request.get_json(silent=True) or {}
    try:
        machine_id = int(data.get("id"))
    except (TypeError, ValueError):
        return jsonify(success=False, message="Choose a valid machine."), 400
    machine = MarketplaceListing.query.filter_by(id=machine_id, kind="machine").first()
    if machine is None:
        return jsonify(success=False, message="Machine not found."), 404
    rental = RentalRequest(machine_id=machine_id)
    db.session.add(rental)
    machine_data = json.loads(machine.payload)
    try:
        rate = round(float(machine_data.get("rate", 0)), 2)
    except (TypeError, ValueError):
        rate = 0
    db.session.add(TransactionRecord(
        receipt=f"RENT-{secrets.token_hex(3).upper()}",
        product_name=f"{machine_data.get('name', 'Machine')} Rental"[:180],
        category="Machinery",
        region="Not recorded",
        quantity=1,
        unit_price=max(0, rate),
        status="Requested",
        is_sample=False,
    ))
    db.session.commit()
    return jsonify(success=True, message="Rent request received.", request_id=rental.id)


@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    data = request.get_json(silent=True) or {}
    try:
        product_id = int(data.get("id"))
        quantity = max(1, int(data.get("quantity", 1)))
    except (TypeError, ValueError):
        return jsonify(success=False, error="Choose a valid product and quantity."), 400
    cart = session.get("cart", {})
    cart[str(product_id)] = cart.get(str(product_id), 0) + quantity
    session["cart"] = cart
    return jsonify(success=True, cart=cart, item_count=sum(cart.values()))


@app.route("/checkout", methods=["POST"])
def checkout():
    data = request.get_json(silent=True) or {}
    items = data.get("items") or []
    if not isinstance(items, list) or not items:
        return jsonify(success=False, error="Your cart is empty."), 400
    clean_items = []
    try:
        for item in items:
            name = str(item.get("name", "")).strip()
            price = round(float(item.get("price", 0)), 2)
            quantity = int(item.get("qty", item.get("quantity", 1)))
            if not name or price < 0 or quantity < 1:
                raise ValueError
            clean_items.append({
                "name": name,
                "price": price,
                "quantity": quantity,
                "category": _transaction_category(str(item.get("category", "produce"))),
                "region": str(item.get("region", item.get("location", ""))).strip()[:100] or "Not recorded",
            })
    except (AttributeError, TypeError, ValueError):
        return jsonify(success=False, error="One or more cart items are invalid."), 400
    receipt = secrets.token_hex(4).upper()
    order = Order(receipt=receipt, items=json.dumps(clean_items, ensure_ascii=False))
    db.session.add(order)
    transaction_date = datetime.utcnow()
    for item in clean_items:
        db.session.add(TransactionRecord(
            receipt=receipt,
            product_name=item["name"][:180],
            category=item["category"],
            region=item["region"],
            quantity=item["quantity"],
            unit_price=item["price"],
            status=order.status,
            transaction_date=transaction_date,
            is_sample=False,
        ))
    db.session.commit()
    session["last_order"] = receipt
    receipts = session.get("order_receipts", [])
    session["order_receipts"] = (receipts + [receipt])[-20:]
    session.pop("cart", None)
    return jsonify(success=True, receipt=receipt, status=order.status)


@app.route("/orders")
def orders():
    receipts = session.get("order_receipts", [])
    orders_by_receipt = Order.query.filter(Order.receipt.in_(receipts)).order_by(Order.created_at.desc()).all() if receipts else []
    order_data = [
        {"receipt": order.receipt, "items": json.loads(order.items), "status": order.status, "created_at": order.created_at}
        for order in orders_by_receipt
    ]
    return render_template("orders.html", orders=order_data)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    if not name or not email:
        flash("Enter your name and email.", "error")
        return redirect(url_for("signup"))
    if User.query.filter_by(email=email).first():
        flash("That email is already registered. Please log in.", "error")
        return redirect(url_for("signup"))
    otp = f"{secrets.randbelow(900000) + 100000:06d}"
    session["pending_signup"] = {"name": name, "email": email}
    session["signup_otp"] = otp
    session["signup_otp_expiry"] = int((datetime.utcnow() + timedelta(minutes=10)).timestamp())
    if app.config["MAIL_USERNAME"] and app.config["MAIL_PASSWORD"]:
        try:
            message = Message(
                "Your AgriTrust verification code",
                recipients=[email],
                body=f"Your verification code is {otp}. It expires in 10 minutes.",
            )
            mail.send(message)
        except Exception:
            app.logger.exception("OTP email could not be sent")
            flash("Email delivery failed. Check the mail settings and try again.", "error")
            return redirect(url_for("signup"))
    elif app.config["APP_DEBUG"]:
        flash(f"Development OTP: {otp} (valid for 10 minutes)", "info")
    else:
        flash("Email signup is unavailable until mail settings are configured.", "error")
        return redirect(url_for("signup"))
    return redirect(url_for("verify_otp"))


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if not session.get("pending_signup") or not session.get("signup_otp"):
        return redirect(url_for("signup"))
    if request.method == "POST":
        if int(datetime.utcnow().timestamp()) > session.get("signup_otp_expiry", 0):
            session.pop("pending_signup", None)
            session.pop("signup_otp", None)
            session.pop("signup_otp_expiry", None)
            flash("That code expired. Please start signup again.", "error")
            return redirect(url_for("signup"))
        if secrets.compare_digest(session.get("signup_otp", ""), request.form.get("otp", "").strip()):
            session["verified_signup"] = session.pop("pending_signup")
            session.pop("signup_otp", None)
            session.pop("signup_otp_expiry", None)
            return redirect(url_for("set_credentials"))
        flash("Invalid verification code.", "error")
    return render_template("verify_otp.html")


@app.route("/set-credentials", methods=["GET", "POST"])
def set_credentials():
    pending = session.get("verified_signup")
    if not pending:
        return redirect(url_for("signup"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if len(username) < 3 or len(password) < 8:
            flash("Use a username of at least 3 characters and a password of at least 8 characters.", "error")
            return render_template("set_credentials.html")
        if User.query.filter(or_(User.username == username, User.email == pending["email"])).first():
            flash("That username or email is already registered.", "error")
            return redirect(url_for("signup"))
        user = User(
            name=pending["name"],
            email=pending["email"],
            username=username,
            password=generate_password_hash(password),
            otp_verified=True,
        )
        db.session.add(user)
        db.session.commit()
        session.pop("verified_signup", None)
        session["user"] = username
        flash("Account created. The marketplace is also available without logging in.", "success")
        return redirect(url_for("landing"))
    return render_template("set_credentials.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter(or_(User.username == identifier, User.email == identifier.lower())).first()
        if user and check_password_hash(user.password, password):
            session["user"] = user.username
            session.permanent = bool(request.form.get("remember"))
            flash(f"Welcome, {user.username}!", "success")
            return redirect(url_for("landing"))
        flash("Invalid username/email or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("You are now browsing as a guest.", "success")
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=app.config["APP_DEBUG"], use_reloader=False)

