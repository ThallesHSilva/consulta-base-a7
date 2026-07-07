from __future__ import annotations

import csv
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import smtplib
import time
import textwrap
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from email.message import EmailMessage
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / ".cache"
DB_PATH = CACHE_DIR / "consulta_base.sqlite3"
AUTH_DB_PATH = CACHE_DIR / "auth.sqlite3"
STATIC_DIR = ROOT / "static"
SEARCH_LIMIT = 500
SESSION_COOKIE = "consulta_base_session"
SESSION_DURATION_HOURS = 12
PASSWORD_RESET_MINUTES = 30
PASSWORD_RESET_WINDOW_SECONDS = 15 * 60
PASSWORD_RESET_EMAIL_LIMIT = 3
PASSWORD_RESET_IP_LIMIT = 10
PASSWORD_HASH_ITERATIONS = 260_000
AUTH_STATUSES = {"PENDENTE_APROVACAO", "ATIVO", "BLOQUEADO", "CANCELADO"}
AUTH_PROFILES = {"ADMIN", "USUARIO"}
GENERIC_RESET_MESSAGE = (
    "Se o e-mail estiver cadastrado, enviaremos as instruções para redefinição de senha."
)
DB_TIMEOUT_SECONDS = 30
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "").strip().lower() in {
    "1",
    "true",
    "sim",
    "yes",
    "on",
}

DATA_FILES = [
    {
        "key": "mapa_parque",
        "label": "MAPA PARQUE",
        "path": DATA_DIR / "MAPA PARQUE.csv",
        "cnpj_columns": ["NR_CNPJ"],
        "cliente_columns": ["NM_CLIENTE"],
    },
    {
        "key": "parque_movel",
        "label": "PARQUE MOVEL",
        "path": DATA_DIR / "PARQUE MOVEL.csv",
        "cnpj_columns": ["CNPJ_CLIENTE"],
        "cliente_columns": ["CLIENTE", "NM_CLIENTE"],
    },
    {
        "key": "parque_fixa",
        "label": "PARQUE FIXA",
        "path": DATA_DIR / "PARQUE FIXA.csv",
        "cnpj_columns": ["DOCUMENTO"],
        "cliente_columns": ["NM_CLIENTE", "CLIENTE"],
    },
]

APP_STATE: dict[str, Any] = {
    "ready": False,
    "missing_files": [],
    "sources": [],
    "message": "Base ainda nao inicializada.",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(value: datetime | None = None) -> str:
    return (value or utc_now()).isoformat(timespec="seconds")


def normalize_email(value: Any) -> str:
    return clean_cell(value).lower()


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    return (
        f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}$"
        f"{salt.hex()}${digest.hex()}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_hex, digest_hex = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, TypeError):
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


def validate_password_strength(password: str) -> str:
    if len(password) < 8:
        return "A senha deve ter no mínimo 8 caracteres."
    if not re.search(r"[A-Za-zÀ-ÿ]", password):
        return "A senha deve conter ao menos uma letra."
    if not re.search(r"\d", password):
        return "A senha deve conter ao menos um número."
    return ""


def public_user(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "nome_completo": row["nome_completo"],
        "email": row["email"],
        "perfil": row["perfil"],
        "status": row["status"],
        "data_criacao": row["data_criacao"],
        "data_aprovacao": row["data_aprovacao"],
        "aprovado_por": row["aprovado_por"],
        "data_bloqueio": row["data_bloqueio"],
        "data_cancelamento": row["data_cancelamento"],
        "ultimo_login": row["ultimo_login"],
    }


def relative_display(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def clean_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\x00", "").strip()


def cnpj_digits(value: Any) -> str:
    raw = clean_cell(value)
    if not raw:
        return ""

    compact = raw.replace(" ", "")
    if re.fullmatch(r"[-+]?\d+(?:[,.]\d+)?[eE][-+]?\d+", compact):
        try:
            number = Decimal(compact.replace(",", "."))
            if number == number.to_integral_value():
                return f"{int(number):d}"
        except (InvalidOperation, ValueError):
            pass

    return re.sub(r"\D", "", raw)


def cnpj_key(value: Any) -> str:
    digits = cnpj_digits(value)
    return digits.lstrip("0") or ("0" if digits else "")


def first_value(row: dict[str, str], columns: list[str]) -> str:
    for column in columns:
        value = clean_cell(row.get(column))
        if value:
            return value
    return ""


def parse_decimal(value: Any) -> Decimal:
    raw = clean_cell(value)
    if not raw:
        return Decimal("0")

    normalized = re.sub(r"[^\d,.\-]", "", raw)
    if not normalized:
        return Decimal("0")

    if "," in normalized and "." in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    elif "," in normalized:
        normalized = normalized.replace(",", ".")

    try:
        return Decimal(normalized)
    except InvalidOperation:
        return Decimal("0")


def decimal_to_json_number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def decimal_to_brl(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.01"))
    integer_part, decimal_part = f"{quantized:.2f}".split(".")
    grouped = f"{int(integer_part):,}".replace(",", ".")
    return f"R$ {grouped},{decimal_part}"


def number_to_brl(value: Any) -> str:
    try:
        return decimal_to_brl(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        return "-"


def number_to_gb(value: Any) -> str:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return "-"
    if number == number.to_integral_value():
        return f"{int(number)} GB"
    return f"{str(number).replace('.', ',')} GB"


def extract_brl_value(value: Any) -> str:
    raw = clean_cell(value)
    if not raw:
        return ""

    match = re.search(r"R\$\s*([0-9][0-9.,]*)", raw, flags=re.IGNORECASE)
    if not match:
        return ""

    amount_text = match.group(1)
    if "," not in amount_text and "." in amount_text:
        parts = amount_text.split(".")
        if all(len(part) == 3 for part in parts[1:]):
            amount_text = "".join(parts)

    amount = parse_decimal(amount_text)
    if amount <= 0:
        return ""
    return decimal_to_brl(amount)


def is_dados_product(value: Any) -> bool:
    return clean_cell(value).upper() == "DADOS"


def broadband_unique_key(payload: dict[str, Any], row_number: int | None = None) -> str:
    designator = clean_cell(payload.get("DESIGNADOR"))
    if designator:
        return designator.upper()
    return f"__row_{row_number}" if row_number is not None else ""


def m_range_key(value: Any) -> str:
    number = parse_decimal(value)
    if number < 0:
        return ""
    if number <= 16:
        return "m0_m16"
    if number == 17:
        return "m17"
    return "above_m17"


def detect_encoding(path: Path) -> str:
    sample = path.read_bytes()[:65536]
    try:
        sample.decode("utf-8-sig")
        return "utf-8-sig"
    except UnicodeDecodeError:
        return "cp1252"


def sanitize_headers(headers: list[str]) -> list[str]:
    result: list[str] = []
    seen: dict[str, int] = {}
    for index, header in enumerate(headers, start=1):
        name = clean_cell(header) or f"COLUNA_{index}"
        count = seen.get(name, 0) + 1
        seen[name] = count
        if count > 1:
            name = f"{name}_{count}"
        result.append(name)
    return result


def iter_csv_rows(path: Path):
    encoding = detect_encoding(path)
    with path.open("r", encoding=encoding, errors="replace", newline="") as file:
        reader = csv.reader(file, delimiter=";")
        try:
            headers = sanitize_headers(next(reader))
        except StopIteration:
            return

        for row_number, row in enumerate(reader, start=2):
            if not any(clean_cell(cell) for cell in row):
                continue

            record: dict[str, str] = {}
            for index, value in enumerate(row):
                if index < len(headers):
                    key = headers[index]
                else:
                    key = f"EXTRA_{index - len(headers) + 1}"
                record[key] = clean_cell(value)
            yield row_number, record


def file_signature() -> list[dict[str, Any]]:
    signature = []
    for data_file in DATA_FILES:
        path = data_file["path"]
        stat = path.stat()
        signature.append(
            {
                "path": relative_display(path),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
        )
    return signature


def missing_files() -> list[str]:
    return [
        relative_display(data_file["path"])
        for data_file in DATA_FILES
        if not data_file["path"].is_file()
    ]


def database_is_current() -> bool:
    if not DB_PATH.is_file():
        return False
    try:
        with sqlite3.connect(DB_PATH, timeout=DB_TIMEOUT_SECONDS) as conn:
            row = conn.execute(
                "SELECT value FROM metadata WHERE key = 'file_signature'"
            ).fetchone()
            if not row:
                return False
            return json.loads(row[0]) == file_signature()
    except (sqlite3.Error, json.JSONDecodeError, OSError):
        return False


@contextmanager
def open_auth_db() -> Iterator[sqlite3.Connection]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(AUTH_DB_PATH, timeout=DB_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {DB_TIMEOUT_SECONDS * 1000}")
    try:
        yield conn
    finally:
        conn.close()


def initialize_auth_database() -> None:
    with open_auth_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_completo TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                senha_hash TEXT NOT NULL,
                perfil TEXT NOT NULL,
                status TEXT NOT NULL,
                data_criacao TEXT NOT NULL,
                data_aprovacao TEXT,
                aprovado_por INTEGER,
                data_bloqueio TEXT,
                data_cancelamento TEXT,
                ultimo_login TEXT,
                FOREIGN KEY (aprovado_por) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                data_criacao TEXT NOT NULL,
                data_expiracao TEXT NOT NULL,
                ultimo_uso TEXT,
                ip TEXT,
                user_agent TEXT,
                ativo INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                data_criacao TEXT NOT NULL,
                data_expiracao TEXT NOT NULL,
                data_utilizacao TEXT,
                utilizado INTEGER NOT NULL DEFAULT 0,
                ip_solicitacao TEXT,
                user_agent TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS password_reset_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                ip_solicitacao TEXT,
                user_agent TEXT,
                data_criacao TEXT NOT NULL,
                aceito INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                cnpj_key TEXT NOT NULL,
                cnpj_display TEXT NOT NULL,
                company_name TEXT,
                data_consulta TEXT NOT NULL,
                total INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
            CREATE INDEX IF NOT EXISTS idx_sessions_hash ON sessions(token_hash);
            CREATE INDEX IF NOT EXISTS idx_reset_hash ON password_reset_tokens(token_hash);
            CREATE INDEX IF NOT EXISTS idx_reset_requests_email ON password_reset_requests(email, data_criacao);
            CREATE INDEX IF NOT EXISTS idx_reset_requests_ip ON password_reset_requests(ip_solicitacao, data_criacao);
            CREATE INDEX IF NOT EXISTS idx_search_history_user_date
                ON search_history(user_id, data_consulta);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_search_history_user_cnpj
                ON search_history(user_id, cnpj_key);
            """
        )
        ensure_initial_admin(conn)


def ensure_initial_admin(conn: sqlite3.Connection) -> None:
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if total_users:
        return

    email = normalize_email(os.environ.get("ADMIN_EMAIL") or "admin@a7connect.local")
    password = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(18)
    now = utc_iso()
    conn.execute(
        """
        INSERT INTO users (
            nome_completo, email, senha_hash, perfil, status, data_criacao,
            data_aprovacao, aprovado_por
        ) VALUES (?, ?, ?, 'ADMIN', 'ATIVO', ?, ?, NULL)
        """,
        ("Administrador A7 Connect", email, hash_password(password), now, now),
    )
    conn.commit()

    if not os.environ.get("ADMIN_PASSWORD"):
        credentials_path = CACHE_DIR / "admin_credentials.txt"
        credentials_path.write_text(
            "\n".join(
                [
                    "Credenciais iniciais do administrador A7 Connect",
                    "Altere a senha após o primeiro acesso.",
                    f"E-mail: {email}",
                    f"Senha: {password}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        print(
            "Administrador inicial criado. "
            f"Credenciais em {relative_display(credentials_path)}"
        )


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS records;
        DROP TABLE IF EXISTS sources;
        DROP TABLE IF EXISTS metadata;

        CREATE TABLE records (
            id INTEGER PRIMARY KEY,
            source_key TEXT NOT NULL,
            source_label TEXT NOT NULL,
            row_number INTEGER NOT NULL,
            cnpj_key TEXT NOT NULL,
            cnpj_digits TEXT NOT NULL,
            cnpj_original TEXT NOT NULL,
            cliente TEXT,
            payload_json TEXT NOT NULL
        );

        CREATE TABLE sources (
            source_key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            file_name TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            indexed_count INTEGER NOT NULL,
            size INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL
        );

        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )


def rebuild_database() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = DB_PATH.with_suffix(".tmp")
    if temp_path.exists():
        temp_path.unlink()

    conn = sqlite3.connect(temp_path, timeout=DB_TIMEOUT_SECONDS)
    try:
        conn.execute("PRAGMA journal_mode = OFF")
        conn.execute("PRAGMA synchronous = OFF")
        create_schema(conn)

        for data_file in DATA_FILES:
            source_key = data_file["key"]
            source_label = data_file["label"]
            path = data_file["path"]
            row_count = 0
            indexed_count = 0
            batch: list[tuple[str, str, int, str, str, str, str, str]] = []

            for row_number, record in iter_csv_rows(path):
                row_count += 1
                original_cnpj = first_value(record, data_file["cnpj_columns"])
                digits = cnpj_digits(original_cnpj)
                key = cnpj_key(original_cnpj)
                if not key:
                    continue

                indexed_count += 1
                cliente = first_value(record, data_file["cliente_columns"])
                payload = {k: v for k, v in record.items() if clean_cell(v)}
                batch.append(
                    (
                        source_key,
                        source_label,
                        row_number,
                        key,
                        digits,
                        original_cnpj,
                        cliente,
                        json.dumps(payload, ensure_ascii=False),
                    )
                )

                if len(batch) >= 5000:
                    conn.executemany(
                        """
                        INSERT INTO records (
                            source_key, source_label, row_number, cnpj_key,
                            cnpj_digits, cnpj_original, cliente, payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        batch,
                    )
                    batch.clear()

            if batch:
                conn.executemany(
                    """
                    INSERT INTO records (
                        source_key, source_label, row_number, cnpj_key,
                        cnpj_digits, cnpj_original, cliente, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    batch,
                )

            stat = path.stat()
            conn.execute(
                """
                INSERT INTO sources (
                    source_key, label, file_name, row_count, indexed_count,
                    size, mtime_ns
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_key,
                    source_label,
                    relative_display(path),
                    row_count,
                    indexed_count,
                    stat.st_size,
                    stat.st_mtime_ns,
                ),
            )

        conn.execute("CREATE INDEX idx_records_cnpj ON records(cnpj_key)")
        conn.execute(
            "CREATE INDEX idx_records_source_cnpj ON records(source_key, cnpj_key)"
        )
        conn.execute(
            "INSERT INTO metadata (key, value) VALUES ('file_signature', ?)",
            (json.dumps(file_signature(), ensure_ascii=False, sort_keys=True),),
        )
        conn.commit()
    finally:
        conn.close()

    os.replace(temp_path, DB_PATH)


def load_sources() -> list[dict[str, Any]]:
    with sqlite3.connect(DB_PATH, timeout=DB_TIMEOUT_SECONDS) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT source_key, label, file_name, row_count, indexed_count, size
            FROM sources
            ORDER BY label
            """
        ).fetchall()
        return [dict(row) for row in rows]


def load_cnpj_metrics(conn: sqlite3.Connection, key: str) -> dict[str, int]:
    mobile_lines = conn.execute(
        """
        SELECT COUNT(*)
        FROM records
        WHERE source_key = 'parque_movel'
          AND cnpj_key = ?
        """,
        (key,),
    ).fetchone()[0]

    fixed_rows = conn.execute(
        """
        SELECT row_number, payload_json
        FROM records
        WHERE source_key = 'parque_fixa'
          AND cnpj_key = ?
        """,
        (key,),
    ).fetchall()
    broadband_designators: set[str] = set()
    for row in fixed_rows:
        payload = json.loads(row["payload_json"])
        if is_dados_product(payload.get("DS_TIPO_PRODUTO")):
            broadband_designators.add(broadband_unique_key(payload, row["row_number"]))

    return {
        "mobile_lines": mobile_lines,
        "broadband_lines": len(broadband_designators),
    }


def load_company_name(conn: sqlite3.Connection, key: str) -> str:
    row = conn.execute(
        """
        SELECT cliente
        FROM records
        WHERE cnpj_key = ?
          AND cliente IS NOT NULL
          AND TRIM(cliente) <> ''
        ORDER BY
          CASE source_key
            WHEN 'mapa_parque' THEN 0
            WHEN 'parque_fixa' THEN 1
            WHEN 'parque_movel' THEN 2
            ELSE 3
          END,
          row_number
        LIMIT 1
        """,
        (key,),
    ).fetchone()
    return clean_cell(row["cliente"]) if row else ""


def load_client_profile(conn: sqlite3.Connection, key: str) -> dict[str, str]:
    rows = conn.execute(
        """
        SELECT payload_json
        FROM records
        WHERE source_key = 'mapa_parque'
          AND cnpj_key = ?
        ORDER BY row_number
        """,
        (key,),
    ).fetchall()

    status = ""
    portfolio = ""
    for row in rows:
        payload = json.loads(row["payload_json"])
        if not status:
            status = clean_cell(payload.get("SITUACAO_RECEITA"))
        if not portfolio:
            portfolio = clean_cell(payload.get("ADABASMOVEL"))
        if status and portfolio:
            break

    return {
        "status": status,
        "portfolio": portfolio,
    }


def load_device_credit(conn: sqlite3.Connection, key: str) -> str:
    rows = conn.execute(
        """
        SELECT payload_json
        FROM records
        WHERE source_key = 'mapa_parque'
          AND cnpj_key = ?
        ORDER BY row_number
        """,
        (key,),
    ).fetchall()

    for row in rows:
        payload = json.loads(row["payload_json"])
        credit = extract_brl_value(payload.get("APARELHOS"))
        if credit:
            return credit

    return "Sem crédito liberado"


def load_broadband_availability(conn: sqlite3.Connection, key: str) -> str:
    rows = conn.execute(
        """
        SELECT payload_json
        FROM records
        WHERE source_key = 'mapa_parque'
          AND cnpj_key = ?
        ORDER BY row_number
        """,
        (key,),
    ).fetchall()

    for row in rows:
        payload = json.loads(row["payload_json"])
        availability = clean_cell(payload.get("DS_DISPONIBILIDADE"))
        if availability:
            return availability

    return "Sem informação de disponibilidade"


def load_mobile_info(conn: sqlite3.Connection, key: str) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT payload_json
        FROM records
        WHERE source_key = 'parque_movel'
          AND cnpj_key = ?
        ORDER BY row_number
        """,
        (key,),
    ).fetchall()

    due_dates: list[str] = []
    invoice_amount = Decimal("0")
    contracted_internet = Decimal("0")
    m_ranges = {
        "m0_m16": 0,
        "m17": 0,
        "above_m17": 0,
    }

    for row in rows:
        payload = json.loads(row["payload_json"])
        due_date = clean_cell(payload.get("DT_VENC_FAT"))
        if due_date and due_date not in due_dates:
            due_dates.append(due_date)

        invoice_amount += parse_decimal(payload.get("FAT_MEDIO_03_MESES"))
        contracted_internet += parse_decimal(payload.get("QTD_GB_CONTRATADO_DADOS"))

        bucket = m_range_key(payload.get("M"))
        if bucket:
            m_ranges[bucket] += 1

    return {
        "invoice_due": ", ".join(due_dates),
        "invoice_amount": decimal_to_json_number(invoice_amount),
        "contracted_internet_gb": decimal_to_json_number(contracted_internet),
        "m_ranges": [
            {"label": "M0 A M16", "count": m_ranges["m0_m16"]},
            {"label": "M17", "count": m_ranges["m17"]},
            {"label": "ACIMA DE M17", "count": m_ranges["above_m17"]},
        ],
    }


def load_mobile_info_empty() -> dict[str, Any]:
    return {
        "invoice_due": "",
        "invoice_amount": 0,
        "contracted_internet_gb": 0,
        "m_ranges": [
            {"label": "M0 A M16", "count": 0},
            {"label": "M17", "count": 0},
            {"label": "ACIMA DE M17", "count": 0},
        ],
    }


def load_mobile_detail(conn: sqlite3.Connection, key: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT row_number, payload_json
        FROM records
        WHERE source_key = 'parque_movel'
          AND cnpj_key = ?
        ORDER BY row_number
        """,
        (key,),
    ).fetchall()

    detail = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        detail.append(
            {
                "row_number": row["row_number"],
                "line": clean_cell(payload.get("NR_TELEFONE")),
                "plan": clean_cell(payload.get("PLANO")),
                "m": clean_cell(payload.get("M")),
                "average_billing": decimal_to_json_number(
                    parse_decimal(payload.get("FAT_MEDIO_03_MESES"))
                ),
            }
        )
    return detail


def load_broadband_detail(conn: sqlite3.Connection, key: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT row_number, payload_json
        FROM records
        WHERE source_key = 'parque_fixa'
          AND cnpj_key = ?
        ORDER BY row_number
        """,
        (key,),
    ).fetchall()

    accounts: dict[str, dict[str, Any]] = {}
    for row in rows:
        payload = json.loads(row["payload_json"])
        account_number = clean_cell(payload.get("CONTA_COBRANCA")) or "Sem conta"
        product = clean_cell(payload.get("DS_PRODUTO")) or "Sem produto"
        designator = clean_cell(payload.get("DESIGNADOR"))
        billing = parse_decimal(payload.get("VL_FAT_BRUTO"))

        account = accounts.setdefault(
            account_number,
            {
                "account": account_number,
                "total_billing_decimal": Decimal("0"),
                "products": {},
            },
        )

        product_key = designator or f"__row_{row['row_number']}"
        product_row = account["products"].setdefault(
            product_key,
            {
                "designator": designator,
                "product_names": [],
                "billing_decimal": Decimal("0"),
            },
        )
        if product not in product_row["product_names"]:
            product_row["product_names"].append(product)

        product_row["billing_decimal"] += billing

    detail = []
    for account in accounts.values():
        products = []
        total_billing = Decimal("0")
        for product in account["products"].values():
            total_billing += product["billing_decimal"]
            products.append(
                {
                    "designator": product["designator"],
                    "product": " / ".join(product["product_names"]),
                    "billing": decimal_to_json_number(product["billing_decimal"]),
                }
            )

        detail.append(
            {
                "account": account["account"],
                "total_billing": decimal_to_json_number(total_billing),
                "products": products,
            }
        )
    return detail


def query_detail(value: str, detail_type: str) -> dict[str, Any]:
    key = cnpj_key(value)
    if not key:
        return {
            "query": value,
            "normalized": "",
            "type": detail_type,
            "company_name": "",
            "items": [],
            "message": "Informe um CNPJ valido.",
        }

    with sqlite3.connect(DB_PATH, timeout=DB_TIMEOUT_SECONDS) as conn:
        conn.row_factory = sqlite3.Row
        company_name = load_company_name(conn, key)
        if detail_type == "mobile":
            items = load_mobile_detail(conn, key)
        elif detail_type == "broadband":
            items = load_broadband_detail(conn, key)
        else:
            return {
                "query": value,
                "normalized": key,
                "type": detail_type,
                "company_name": company_name,
                "items": [],
                "message": "Tipo de detalhamento invalido.",
            }

    return {
        "query": value,
        "normalized": key,
        "type": detail_type,
        "company_name": company_name,
        "items": items,
    }


def initialize_data(force_rebuild: bool = False) -> dict[str, Any]:
    missing = missing_files()
    if missing:
        names = ", ".join(missing)
        prefix = "Arquivo ausente" if len(missing) == 1 else "Arquivos ausentes"
        return {
            "ready": False,
            "missing_files": missing,
            "sources": [],
            "message": f"{prefix}: {names}",
        }

    if force_rebuild or not database_is_current():
        rebuild_database()

    sources = load_sources()
    return {
        "ready": True,
        "missing_files": [],
        "sources": sources,
        "message": "Base carregada com sucesso.",
    }


def refresh_data(force_rebuild: bool = True) -> dict[str, Any]:
    global APP_STATE
    APP_STATE = initialize_data(force_rebuild=force_rebuild)
    return APP_STATE


def query_cnpj(value: str) -> dict[str, Any]:
    key = cnpj_key(value)
    if not key:
        return {
            "query": value,
            "total": 0,
            "company_name": "",
            "client_status": "",
            "client_portfolio": "",
            "device_credit": "",
            "broadband_availability": "",
            "mobile_info": load_mobile_info_empty(),
            "limited": False,
            "results": [],
            "message": "Informe um CNPJ valido.",
        }

    with sqlite3.connect(DB_PATH, timeout=DB_TIMEOUT_SECONDS) as conn:
        conn.row_factory = sqlite3.Row
        metrics = load_cnpj_metrics(conn, key)
        company_name = load_company_name(conn, key)
        client_profile = load_client_profile(conn, key)
        device_credit = load_device_credit(conn, key)
        broadband_availability = load_broadband_availability(conn, key)
        mobile_info = load_mobile_info(conn, key)
        total = conn.execute(
            "SELECT COUNT(*) FROM records WHERE cnpj_key = ?",
            (key,),
        ).fetchone()[0]
        rows = conn.execute(
            """
            SELECT source_key, source_label, row_number, cnpj_digits,
                   cnpj_original, cliente, payload_json
            FROM records
            WHERE cnpj_key = ?
            ORDER BY source_label, row_number
            LIMIT ?
            """,
            (key, SEARCH_LIMIT + 1),
        ).fetchall()

    limited = len(rows) > SEARCH_LIMIT
    rows = rows[:SEARCH_LIMIT]
    results = []
    for row in rows:
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        results.append(result)

    return {
        "query": value,
        "normalized": key,
        "total": total,
        "shown": len(results),
        "limited": limited,
        "message": "CNPJ não localizado." if total == 0 else "",
        "company_name": company_name,
        "client_status": client_profile["status"],
        "client_portfolio": client_profile["portfolio"],
        "device_credit": device_credit,
        "broadband_availability": broadband_availability,
        "mobile_info": mobile_info,
        "metrics": metrics,
        "results": results,
    }


def pdf_text(value: Any) -> str:
    text = clean_cell(value)
    text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return text


def build_simple_pdf(lines: list[str], title: str = "Consulta Base A7 Connect") -> bytes:
    page_width = 595
    page_height = 842
    x = 48
    y = 790
    line_height = 15
    content_lines = ["BT", "/F1 11 Tf", f"{x} {y} Td"]
    first_line = True

    for raw_line in lines:
        wrapped = textwrap.wrap(clean_cell(raw_line), width=92) or [""]
        for line in wrapped:
            if first_line:
                content_lines.append(f"({pdf_text(line)}) Tj")
                first_line = False
            else:
                content_lines.append(f"0 -{line_height} Td")
                content_lines.append(f"({pdf_text(line)}) Tj")
        if raw_line == "":
            content_lines.append(f"0 -{line_height} Td")
    content_lines.append("ET")

    stream = "\n".join(content_lines).encode("cp1252", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
            f"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ).encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info << /Title ({pdf_text(title)}) >> >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("cp1252", errors="replace")
    )
    return bytes(output)


def build_cnpj_pdf(value: str) -> tuple[HTTPStatus, bytes | dict[str, Any], str]:
    data = query_cnpj(value)
    if not data.get("total"):
        return HTTPStatus.NOT_FOUND, {"ok": False, "message": data.get("message") or "CNPJ não localizado."}, ""

    metrics = data.get("metrics") or {}
    mobile_info = data.get("mobile_info") or {}
    ranges = mobile_info.get("m_ranges") or []
    range_lines = [
        f"{item.get('label', '-')}: {item.get('count', 0)}"
        for item in ranges
    ]

    lines = [
        "A7 Connect - Consulta Base",
        f"Gerado em: {utc_now().astimezone().strftime('%d/%m/%Y %H:%M')}",
        "",
        "Cliente",
        f"Razão social: {data.get('company_name') or '-'}",
        f"CNPJ: {data.get('query') or data.get('normalized') or '-'}",
        f"Status: {data.get('client_status') or '-'}",
        f"Carteira: {data.get('client_portfolio') or '-'}",
        f"Crédito de aparelho: {data.get('device_credit') or '-'}",
        f"Disponibilidade de BL: {data.get('broadband_availability') or '-'}",
        "",
        "Indicadores",
        f"Linhas móveis: {metrics.get('mobile_lines', 0)}",
        f"Banda larga: {metrics.get('broadband_lines', 0)}",
        f"Faturamento Móvel: {number_to_brl(mobile_info.get('invoice_amount'))}",
        f"Internet Móvel: {number_to_gb(mobile_info.get('contracted_internet_gb'))}",
        "",
        "Informações da móvel",
        f"Vencimento da fatura: {mobile_info.get('invoice_due') or '-'}",
        f"Valor da fatura: {number_to_brl(mobile_info.get('invoice_amount'))}",
        f"Internet contratada: {number_to_gb(mobile_info.get('contracted_internet_gb'))}",
        "",
        "Distribuição por fidelização",
        *range_lines,
    ]
    filename_digits = cnpj_digits(value) or "consulta"
    filename = f"consulta-cnpj-{filename_digits}.pdf"
    return HTTPStatus.OK, build_simple_pdf(lines, "Consulta por CNPJ"), filename


def fetch_user_by_email(conn: sqlite3.Connection, email: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM users WHERE email = ?",
        (normalize_email(email),),
    ).fetchone()


def fetch_user_by_id(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def create_pending_user(data: dict[str, Any]) -> tuple[bool, str]:
    name = clean_cell(data.get("nome_completo"))
    email = normalize_email(data.get("email"))
    password = str(data.get("senha") or "")
    confirmation = str(data.get("senha_confirmacao") or "")

    if not name:
        return False, "Informe o nome completo."
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return False, "Informe um e-mail válido."
    if password != confirmation:
        return False, "A confirmação de senha não confere."

    password_error = validate_password_strength(password)
    if password_error:
        return False, password_error

    try:
        with open_auth_db() as conn:
            conn.execute(
                """
                INSERT INTO users (
                    nome_completo, email, senha_hash, perfil, status, data_criacao
                ) VALUES (?, ?, ?, 'USUARIO', 'PENDENTE_APROVACAO', ?)
                """,
                (name, email, hash_password(password), utc_iso()),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        return False, "Este e-mail já está cadastrado."

    return (
        True,
        "Cadastro realizado com sucesso. Aguarde a aprovação do administrador para acessar o sistema.",
    )


def create_session(
    conn: sqlite3.Connection,
    user_id: int,
    ip: str,
    user_agent: str,
) -> str:
    token = secrets.token_urlsafe(32)
    now = utc_now()
    expiration = now + timedelta(hours=SESSION_DURATION_HOURS)
    conn.execute(
        """
        INSERT INTO sessions (
            user_id, token_hash, data_criacao, data_expiracao,
            ultimo_uso, ip, user_agent, ativo
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            user_id,
            hash_token(token),
            utc_iso(now),
            utc_iso(expiration),
            utc_iso(now),
            ip,
            user_agent,
        ),
    )
    conn.execute(
        "UPDATE users SET ultimo_login = ? WHERE id = ?",
        (utc_iso(now), user_id),
    )
    conn.commit()
    return token


def authenticate_user(
    email: str,
    password: str,
    ip: str,
    user_agent: str,
) -> tuple[HTTPStatus, dict[str, Any], str | None]:
    with open_auth_db() as conn:
        user = fetch_user_by_email(conn, email)
        if not user or not verify_password(password, user["senha_hash"]):
            return HTTPStatus.UNAUTHORIZED, {"ok": False, "message": "E-mail ou senha inválidos."}, None

        status = user["status"]
        if status == "PENDENTE_APROVACAO":
            return (
                HTTPStatus.FORBIDDEN,
                {
                    "ok": False,
                    "message": "Seu cadastro ainda está aguardando aprovação do administrador.",
                },
                None,
            )
        if status == "BLOQUEADO":
            return (
                HTTPStatus.FORBIDDEN,
                {
                    "ok": False,
                    "message": "Seu acesso está temporariamente bloqueado. Entre em contato com o administrador.",
                },
                None,
            )
        if status == "CANCELADO":
            return (
                HTTPStatus.FORBIDDEN,
                {
                    "ok": False,
                    "message": "Seu cadastro foi cancelado. Entre em contato com o administrador.",
                },
                None,
            )
        if status != "ATIVO":
            return HTTPStatus.FORBIDDEN, {"ok": False, "message": "Usuário sem acesso ao sistema."}, None

        session_token = create_session(conn, user["id"], ip, user_agent)
        response = {
            "ok": True,
            "message": "Login realizado com sucesso.",
            "redirect": "/app",
            "user": public_user(user),
        }
        return HTTPStatus.OK, response, session_token


def lookup_session_user(token: str) -> dict[str, Any] | None:
    if not token:
        return None

    now = utc_iso()
    with open_auth_db() as conn:
        row = conn.execute(
            """
            SELECT u.*, s.id AS session_id
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ?
              AND s.ativo = 1
              AND s.data_expiracao > ?
            """,
            (hash_token(token), now),
        ).fetchone()
        if not row:
            return None
        if row["status"] != "ATIVO":
            conn.execute(
                "UPDATE sessions SET ativo = 0 WHERE id = ?",
                (row["session_id"],),
            )
            conn.commit()
            return None
        conn.execute(
            "UPDATE sessions SET ultimo_uso = ? WHERE id = ?",
            (now, row["session_id"]),
        )
        conn.commit()
        return {
            "id": row["id"],
            "nome_completo": row["nome_completo"],
            "email": row["email"],
            "perfil": row["perfil"],
            "status": row["status"],
        }


def logout_session(token: str) -> None:
    if not token:
        return
    with open_auth_db() as conn:
        conn.execute(
            "UPDATE sessions SET ativo = 0 WHERE token_hash = ?",
            (hash_token(token),),
        )
        conn.commit()


def list_users(search: str = "", status: str = "") -> list[dict[str, Any]]:
    query = "SELECT * FROM users WHERE 1 = 1"
    params: list[Any] = []
    search_value = clean_cell(search)
    status_value = clean_cell(status).upper()

    if search_value:
        query += " AND (nome_completo LIKE ? OR email LIKE ?)"
        like = f"%{search_value}%"
        params.extend([like, like])
    if status_value in AUTH_STATUSES:
        query += " AND status = ?"
        params.append(status_value)

    query += " ORDER BY data_criacao DESC, id DESC"
    with open_auth_db() as conn:
        rows = conn.execute(query, params).fetchall()
        return [public_user(row) for row in rows]


def save_search_history(
    user_id: int,
    query_value: str,
    result: dict[str, Any],
) -> None:
    key = cnpj_key(query_value)
    if not key:
        return

    display = clean_cell(result.get("query")) or clean_cell(query_value) or key
    company_name = clean_cell(result.get("company_name"))
    try:
        total = int(result.get("total") or 0)
    except (TypeError, ValueError):
        total = 0

    with open_auth_db() as conn:
        conn.execute(
            """
            INSERT INTO search_history (
                user_id, cnpj_key, cnpj_display, company_name, data_consulta, total
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, cnpj_key) DO UPDATE SET
                cnpj_display = excluded.cnpj_display,
                company_name = excluded.company_name,
                data_consulta = excluded.data_consulta,
                total = excluded.total
            """,
            (user_id, key, display, company_name, utc_iso(), total),
        )
        conn.execute(
            """
            DELETE FROM search_history
            WHERE user_id = ?
              AND id NOT IN (
                  SELECT id
                  FROM search_history
                  WHERE user_id = ?
                  ORDER BY data_consulta DESC, id DESC
                  LIMIT 15
              )
            """,
            (user_id, user_id),
        )
        conn.commit()


def list_search_history(user_id: int) -> list[dict[str, Any]]:
    with open_auth_db() as conn:
        rows = conn.execute(
            """
            SELECT cnpj_key, cnpj_display, company_name, data_consulta, total
            FROM search_history
            WHERE user_id = ?
            ORDER BY data_consulta DESC, id DESC
            LIMIT 15
            """,
            (user_id,),
        ).fetchall()

    return [
        {
            "cnpj_key": row["cnpj_key"],
            "cnpj": row["cnpj_display"],
            "company_name": row["company_name"] or "",
            "data_consulta": row["data_consulta"],
            "total": row["total"],
            "found": row["total"] > 0,
        }
        for row in rows
    ]


def update_user_status(
    admin_user: dict[str, Any],
    user_id: int,
    action: str,
) -> tuple[HTTPStatus, dict[str, Any]]:
    normalized_action = clean_cell(action).lower()
    now = utc_iso()

    with open_auth_db() as conn:
        user = fetch_user_by_id(conn, user_id)
        if not user:
            return HTTPStatus.NOT_FOUND, {"ok": False, "message": "Usuário não encontrado."}
        if user["id"] == admin_user["id"] and normalized_action in {"bloquear", "cancelar"}:
            return (
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "message": "Não é possível bloquear ou cancelar seu próprio usuário."},
            )

        if normalized_action == "aprovar":
            if user["status"] != "PENDENTE_APROVACAO":
                return (
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "message": "Somente usuários pendentes podem ser aprovados."},
                )
            conn.execute(
                """
                UPDATE users
                SET status = 'ATIVO',
                    data_aprovacao = COALESCE(data_aprovacao, ?),
                    aprovado_por = COALESCE(aprovado_por, ?),
                    data_bloqueio = NULL,
                    data_cancelamento = NULL
                WHERE id = ?
                """,
                (now, admin_user["id"], user_id),
            )
            message = "Cadastro aprovado com sucesso."
        elif normalized_action == "bloquear":
            if user["status"] == "CANCELADO":
                return (
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "message": "Usuários cancelados não podem ser bloqueados."},
                )
            conn.execute(
                """
                UPDATE users
                SET status = 'BLOQUEADO',
                    data_bloqueio = ?,
                    data_cancelamento = NULL
                WHERE id = ?
                """,
                (now, user_id),
            )
            conn.execute("UPDATE sessions SET ativo = 0 WHERE user_id = ?", (user_id,))
            message = "Usuário bloqueado com sucesso."
        elif normalized_action == "reativar":
            conn.execute(
                """
                UPDATE users
                SET status = 'ATIVO',
                    data_bloqueio = NULL,
                    data_cancelamento = NULL,
                    data_aprovacao = COALESCE(data_aprovacao, ?),
                    aprovado_por = COALESCE(aprovado_por, ?)
                WHERE id = ?
                  AND status = 'BLOQUEADO'
                """,
                (now, admin_user["id"], user_id),
            )
            if conn.total_changes == 0:
                return (
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "message": "Somente usuários bloqueados podem ser reativados."},
                )
            message = "Usuário reativado com sucesso."
        elif normalized_action == "cancelar":
            conn.execute(
                """
                UPDATE users
                SET status = 'CANCELADO',
                    data_cancelamento = ?
                WHERE id = ?
                """,
                (now, user_id),
            )
            conn.execute("UPDATE sessions SET ativo = 0 WHERE user_id = ?", (user_id,))
            message = "Cadastro cancelado com sucesso."
        else:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "message": "Ação inválida."}

        conn.commit()
        return HTTPStatus.OK, {"ok": True, "message": message}


def is_reset_rate_limited(conn: sqlite3.Connection, email: str, ip: str) -> bool:
    cutoff = utc_iso(utc_now() - timedelta(seconds=PASSWORD_RESET_WINDOW_SECONDS))
    email_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM password_reset_requests
        WHERE email = ?
          AND data_criacao >= ?
        """,
        (email, cutoff),
    ).fetchone()[0]
    ip_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM password_reset_requests
        WHERE ip_solicitacao = ?
          AND data_criacao >= ?
        """,
        (ip, cutoff),
    ).fetchone()[0]
    return email_count >= PASSWORD_RESET_EMAIL_LIMIT or ip_count >= PASSWORD_RESET_IP_LIMIT


def build_reset_email_body(reset_link: str) -> str:
    return "\n".join(
        [
            "Olá, recebemos uma solicitação para redefinir sua senha.",
            "",
            "Clique no link abaixo para criar uma nova senha:",
            "",
            reset_link,
            "",
            "Este link é válido por 30 minutos.",
            "",
            "Caso você não tenha solicitado essa alteração, ignore este e-mail.",
        ]
    )


def send_password_reset_email(email: str, reset_link: str) -> None:
    subject = "Redefinição de senha - A7 Connect"
    body = build_reset_email_body(reset_link)
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_from = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER") or "no-reply@a7connect.local"

    if smtp_host:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = smtp_from
        message["To"] = email
        message.set_content(body)

        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = os.environ.get("SMTP_USER")
        smtp_password = os.environ.get("SMTP_PASSWORD")
        use_tls = os.environ.get("SMTP_TLS", "1") != "0"
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
            if use_tls:
                smtp.starttls()
            if smtp_user and smtp_password:
                smtp.login(smtp_user, smtp_password)
            smtp.send_message(message)
        return

    outbox_dir = CACHE_DIR / "password_reset_outbox"
    outbox_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{int(time.time())}-{secrets.token_hex(4)}.txt"
    (outbox_dir / file_name).write_text(
        "\n".join([f"Para: {email}", f"Assunto: {subject}", "", body]),
        encoding="utf-8",
    )


def request_password_reset(
    email: str,
    ip: str,
    user_agent: str,
    base_url: str,
) -> dict[str, Any]:
    normalized_email = normalize_email(email)
    with open_auth_db() as conn:
        limited = is_reset_rate_limited(conn, normalized_email, ip)
        conn.execute(
            """
            INSERT INTO password_reset_requests (
                email, ip_solicitacao, user_agent, data_criacao, aceito
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (normalized_email, ip, user_agent, utc_iso(), 0 if limited else 1),
        )

        if not limited:
            user = fetch_user_by_email(conn, normalized_email)
            if user and user["status"] != "CANCELADO":
                conn.execute(
                    """
                    UPDATE password_reset_tokens
                    SET utilizado = 1,
                        data_utilizacao = COALESCE(data_utilizacao, ?)
                    WHERE user_id = ?
                      AND utilizado = 0
                    """,
                    (utc_iso(), user["id"]),
                )
                raw_token = secrets.token_urlsafe(36)
                now = utc_now()
                expires_at = now + timedelta(minutes=PASSWORD_RESET_MINUTES)
                conn.execute(
                    """
                    INSERT INTO password_reset_tokens (
                        user_id, token_hash, data_criacao, data_expiracao,
                        utilizado, ip_solicitacao, user_agent
                    ) VALUES (?, ?, ?, ?, 0, ?, ?)
                    """,
                    (
                        user["id"],
                        hash_token(raw_token),
                        utc_iso(now),
                        utc_iso(expires_at),
                        ip,
                        user_agent,
                    ),
                )
                conn.commit()
                reset_link = f"{base_url}/redefinir-senha?token={raw_token}"
                try:
                    send_password_reset_email(normalized_email, reset_link)
                except Exception as error:
                    print(f"Falha ao enviar e-mail de recuperação: {error}")
                return {"ok": True, "message": GENERIC_RESET_MESSAGE}

        conn.commit()
    return {"ok": True, "message": GENERIC_RESET_MESSAGE}


def reset_password(data: dict[str, Any]) -> tuple[HTTPStatus, dict[str, Any]]:
    token = clean_cell(data.get("token"))
    password = str(data.get("senha") or "")
    confirmation = str(data.get("senha_confirmacao") or "")

    if not token:
        return HTTPStatus.BAD_REQUEST, {"ok": False, "message": "Token inválido ou expirado."}
    if password != confirmation:
        return HTTPStatus.BAD_REQUEST, {"ok": False, "message": "A confirmação de senha não confere."}
    password_error = validate_password_strength(password)
    if password_error:
        return HTTPStatus.BAD_REQUEST, {"ok": False, "message": password_error}

    with open_auth_db() as conn:
        row = conn.execute(
            """
            SELECT prt.*, u.status
            FROM password_reset_tokens prt
            JOIN users u ON u.id = prt.user_id
            WHERE prt.token_hash = ?
              AND prt.utilizado = 0
              AND prt.data_expiracao > ?
            """,
            (hash_token(token), utc_iso()),
        ).fetchone()
        if not row or row["status"] == "CANCELADO":
            return HTTPStatus.BAD_REQUEST, {"ok": False, "message": "Token inválido ou expirado."}

        now = utc_iso()
        conn.execute(
            "UPDATE users SET senha_hash = ? WHERE id = ?",
            (hash_password(password), row["user_id"]),
        )
        conn.execute(
            """
            UPDATE password_reset_tokens
            SET utilizado = 1,
                data_utilizacao = ?
            WHERE user_id = ?
              AND utilizado = 0
            """,
            (now, row["user_id"]),
        )
        conn.execute("UPDATE sessions SET ativo = 0 WHERE user_id = ?", (row["user_id"],))
        conn.commit()

    return (
        HTTPStatus.OK,
        {"ok": True, "message": "Senha redefinida com sucesso. Faça login novamente."},
    )


class ConsultaHandler(SimpleHTTPRequestHandler):
    def get_cookie_value(self, name: str) -> str:
        cookie_header = self.headers.get("Cookie", "")
        if not cookie_header:
            return ""
        cookie = SimpleCookie()
        cookie.load(cookie_header)
        morsel = cookie.get(name)
        return morsel.value if morsel else ""

    def get_current_user(self) -> dict[str, Any] | None:
        return lookup_session_user(self.get_cookie_value(SESSION_COOKIE))

    def client_ip(self) -> str:
        forwarded = self.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
        return self.client_address[0]

    def user_agent(self) -> str:
        return self.headers.get("User-Agent", "")[:500]

    def base_url(self) -> str:
        if PUBLIC_BASE_URL:
            return PUBLIC_BASE_URL
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or "127.0.0.1:8000"
        proto = self.headers.get("X-Forwarded-Proto") or "http"
        proto = proto.split(",", 1)[0].strip()
        return f"{proto}://{host}".rstrip("/")

    def read_json_body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            data = {}
        return data if isinstance(data, dict) else {}

    def redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def set_session_cookie(self, token: str) -> None:
        max_age = SESSION_DURATION_HOURS * 60 * 60
        secure = "; Secure" if SESSION_COOKIE_SECURE else ""
        self.send_header(
            "Set-Cookie",
            (
                f"{SESSION_COOKIE}={token}; HttpOnly; SameSite=Lax; "
                f"Path=/; Max-Age={max_age}{secure}"
            ),
        )

    def clear_session_cookie(self) -> None:
        secure = "; Secure" if SESSION_COOKIE_SECURE else ""
        self.send_header(
            "Set-Cookie",
            f"{SESSION_COOKIE}=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0{secure}",
        )

    def send_auth_json(
        self,
        data: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
        session_token: str | None = None,
        clear_session: bool = False,
    ) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if session_token:
            self.set_session_cookie(session_token)
        if clear_session:
            self.clear_session_cookie()
        self.end_headers()
        self.wfile.write(body)

    def require_page_user(self, admin: bool = False) -> dict[str, Any] | None:
        user = self.get_current_user()
        if not user:
            self.redirect("/login")
            return None
        if admin and user["perfil"] != "ADMIN":
            self.send_error(HTTPStatus.FORBIDDEN)
            return None
        return user

    def require_api_user(self, admin: bool = False) -> dict[str, Any] | None:
        user = self.get_current_user()
        if not user:
            self.send_json(
                {"ok": False, "message": "Sessão expirada. Faça login novamente."},
                status=HTTPStatus.UNAUTHORIZED,
            )
            return None
        if admin and user["perfil"] != "ADMIN":
            self.send_json(
                {"ok": False, "message": "Acesso restrito ao administrador."},
                status=HTTPStatus.FORBIDDEN,
            )
            return None
        return user

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            target = "/app"
            if parsed.query:
                target = f"{target}?{parsed.query}"
            self.redirect(target if self.get_current_user() else "/login")
            return

        if parsed.path == "/app":
            if not self.require_page_user():
                return
            self.serve_static_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return

        if parsed.path == "/detail.html":
            if not self.require_page_user():
                return
            self.serve_static_file(STATIC_DIR / "detail.html", "text/html; charset=utf-8")
            return

        if parsed.path == "/historico":
            if not self.require_page_user():
                return
            self.serve_static_file(STATIC_DIR / "historico.html", "text/html; charset=utf-8")
            return

        if parsed.path == "/login":
            if self.get_current_user():
                self.redirect("/app")
                return
            self.serve_static_file(STATIC_DIR / "login.html", "text/html; charset=utf-8")
            return

        if parsed.path == "/cadastro":
            self.serve_static_file(STATIC_DIR / "cadastro.html", "text/html; charset=utf-8")
            return

        if parsed.path == "/aguardando-aprovacao":
            self.serve_static_file(STATIC_DIR / "aguardando-aprovacao.html", "text/html; charset=utf-8")
            return

        if parsed.path == "/esqueci-senha":
            self.serve_static_file(STATIC_DIR / "esqueci-senha.html", "text/html; charset=utf-8")
            return

        if parsed.path == "/redefinir-senha":
            self.serve_static_file(STATIC_DIR / "redefinir-senha.html", "text/html; charset=utf-8")
            return

        if parsed.path == "/admin/usuarios":
            if not self.require_page_user(admin=True):
                return
            self.serve_static_file(STATIC_DIR / "admin-users.html", "text/html; charset=utf-8")
            return

        if parsed.path == "/api/auth/me":
            user = self.get_current_user()
            if not user:
                self.send_json({"ok": False, "user": None}, status=HTTPStatus.UNAUTHORIZED)
                return
            self.send_json({"ok": True, "user": user})
            return

        if parsed.path == "/api/admin/users":
            if not self.require_api_user(admin=True):
                return
            params = parse_qs(parsed.query)
            self.send_json(
                {
                    "ok": True,
                    "users": list_users(
                        params.get("search", [""])[0],
                        params.get("status", [""])[0],
                    ),
                }
            )
            return

        if parsed.path == "/api/status":
            if not self.require_api_user():
                return
            self.send_json(APP_STATE)
            return

        if parsed.path == "/api/history":
            user = self.require_api_user()
            if not user:
                return
            self.send_json({"ok": True, "items": list_search_history(user["id"])})
            return

        if parsed.path == "/api/search":
            user = self.require_api_user()
            if not user:
                return
            if not APP_STATE.get("ready"):
                self.send_json(APP_STATE, status=HTTPStatus.SERVICE_UNAVAILABLE)
                return

            params = parse_qs(parsed.query)
            cnpj = params.get("cnpj", [""])[0]
            result = query_cnpj(cnpj)
            save_search_history(user["id"], cnpj, result)
            self.send_json(result)
            return

        if parsed.path == "/api/detail":
            if not self.require_api_user():
                return
            if not APP_STATE.get("ready"):
                self.send_json(APP_STATE, status=HTTPStatus.SERVICE_UNAVAILABLE)
                return

            params = parse_qs(parsed.query)
            cnpj = params.get("cnpj", [""])[0]
            detail_type = params.get("type", [""])[0]
            self.send_json(query_detail(cnpj, detail_type))
            return

        if parsed.path == "/api/export/pdf":
            if not self.require_api_user():
                return
            if not APP_STATE.get("ready"):
                self.send_json(APP_STATE, status=HTTPStatus.SERVICE_UNAVAILABLE)
                return

            params = parse_qs(parsed.query)
            cnpj = params.get("cnpj", [""])[0]
            status, payload, filename = build_cnpj_pdf(cnpj)
            if isinstance(payload, dict):
                self.send_json(payload, status=status)
                return
            self.send_pdf(payload, filename)
            return

        if parsed.path.startswith("/static/"):
            target = (ROOT / parsed.path.lstrip("/")).resolve()
            if not target.is_relative_to(STATIC_DIR):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_type = {
                ".css": "text/css; charset=utf-8",
                ".js": "application/javascript; charset=utf-8",
                ".html": "text/html; charset=utf-8",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
                ".svg": "image/svg+xml",
                ".ico": "image/x-icon",
            }.get(target.suffix.lower(), "application/octet-stream")
            self.serve_static_file(target, content_type)
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        data = self.read_json_body()

        if parsed.path == "/api/auth/login":
            status, response, session_token = authenticate_user(
                normalize_email(data.get("email")),
                str(data.get("senha") or ""),
                self.client_ip(),
                self.user_agent(),
            )
            self.send_auth_json(response, status=status, session_token=session_token)
            return

        if parsed.path == "/api/auth/register":
            ok, message = create_pending_user(data)
            self.send_json(
                {"ok": ok, "message": message},
                status=HTTPStatus.CREATED if ok else HTTPStatus.BAD_REQUEST,
            )
            return

        if parsed.path == "/api/auth/logout":
            logout_session(self.get_cookie_value(SESSION_COOKIE))
            self.send_auth_json(
                {"ok": True, "message": "Logout realizado com sucesso."},
                clear_session=True,
            )
            return

        if parsed.path == "/api/auth/password/forgot":
            response = request_password_reset(
                normalize_email(data.get("email")),
                self.client_ip(),
                self.user_agent(),
                self.base_url(),
            )
            self.send_json(response)
            return

        if parsed.path == "/api/auth/password/reset":
            status, response = reset_password(data)
            self.send_json(response, status=status)
            return

        if parsed.path == "/api/data/refresh":
            if not self.require_api_user():
                return
            state = refresh_data(force_rebuild=bool(data.get("force")))
            response_status = HTTPStatus.OK if state.get("ready") else HTTPStatus.SERVICE_UNAVAILABLE
            self.send_json(
                {
                    "ok": bool(state.get("ready")),
                    "ready": bool(state.get("ready")),
                    "message": state.get("message", ""),
                    "missing_files": state.get("missing_files", []),
                    "sources": state.get("sources", []),
                },
                status=response_status,
            )
            return

        if parsed.path == "/api/admin/users/action":
            admin_user = self.require_api_user(admin=True)
            if not admin_user:
                return
            try:
                user_id = int(data.get("user_id"))
            except (TypeError, ValueError):
                self.send_json(
                    {"ok": False, "message": "Usuário inválido."},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            status, response = update_user_status(
                admin_user,
                user_id,
                str(data.get("action") or ""),
            )
            self.send_json(response, status=status)
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def send_json(self, data: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_pdf(self, body: bytes, filename: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def serve_static_file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        message = format % args
        message = re.sub(r"(token=)[^&\s]+", r"\1[redacted]", message)
        print(f"{self.address_string()} - {message}")


def run() -> None:
    global APP_STATE

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))

    initialize_auth_database()

    print("Inicializando base local...")
    APP_STATE = initialize_data()
    if APP_STATE["ready"]:
        total = sum(source["indexed_count"] for source in APP_STATE["sources"])
        print(f"Base pronta: {total} registros indexados.")
    else:
        print(APP_STATE["message"])

    server = ThreadingHTTPServer((host, port), ConsultaHandler)
    print(f"Acesse: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")


if __name__ == "__main__":
    run()
