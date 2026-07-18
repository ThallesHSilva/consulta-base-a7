import json
import os
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import app


class CnpjNormalizationTest(unittest.TestCase):
    def test_keeps_plain_digits(self):
        self.assertEqual(app.cnpj_digits("00.000.083/0001-19"), "00000083000119")

    def test_compact_key_removes_leading_zeroes(self):
        self.assertEqual(app.cnpj_key("00.000.083/0001-19"), "83000119")

    def test_expands_scientific_notation_with_comma_decimal(self):
        self.assertEqual(app.cnpj_digits("2,60684E+13"), "26068400000000")

    def test_blank_values_do_not_produce_key(self):
        self.assertEqual(app.cnpj_key(""), "")

    def test_display_adds_leading_zeroes_to_complete_fourteen_digits(self):
        self.assertEqual(
            app.format_cnpj_display("21.147.000/320"),
            "00.021.147/0003-20",
        )


class HeaderSanitizingTest(unittest.TestCase):
    def test_blank_and_duplicate_headers_are_unique(self):
        self.assertEqual(
            app.sanitize_headers(["A", "", "A", ""]),
            ["A", "COLUNA_2", "A_2", "COLUNA_4"],
        )


class ProductTypeTest(unittest.TestCase):
    def test_dados_product_is_case_and_space_insensitive(self):
        self.assertTrue(app.is_dados_product(" dados "))
        self.assertFalse(app.is_dados_product("VOZ"))

    def test_broadband_unique_key_uses_designator(self):
        first = {"DESIGNADOR": "ABC123"}
        duplicate = {"DESIGNADOR": " abc123 "}
        blank = {"DESIGNADOR": ""}
        self.assertEqual(app.broadband_unique_key(first, 10), "ABC123")
        self.assertEqual(app.broadband_unique_key(first, 10), app.broadband_unique_key(duplicate, 11))
        self.assertEqual(app.broadband_unique_key(blank, 12), "__row_12")


class FixedRecommendationTest(unittest.TestCase):
    def test_extracts_middle_recommendation_label(self):
        self.assertEqual(
            app.recommendation_label("M 14 - UPGRADE - SMALL"),
            "UPGRADE",
        )
        self.assertEqual(app.recommendation_label("Formato livre"), "Formato livre")

    def test_groups_offers_by_recommendation_and_adds_mobile_once(self):
        with closing(sqlite3.connect(":memory:")) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute(
                """
                CREATE TABLE records (
                    source_key TEXT,
                    cnpj_key TEXT,
                    row_number INTEGER,
                    payload_json TEXT
                )
                """
            )
            rows = [
                (
                    "parque_fixa",
                    "123",
                    2,
                    {
                        "CONTA_COBRANCA": "9001",
                        "DS_PRODUTO": "Banda Larga",
                        "DESIGNADOR": "BL-1",
                        "VL_FAT_BRUTO": "100",
                        "M": "13",
                        "ENDERECO": "Rua Exemplo, 100",
                    },
                ),
                (
                    "recomendacao_fixa",
                    "123",
                    2,
                    {
                        "CONTA_COBRANCA": "9001",
                        "RECOMENDACAO": "6",
                        "DS_TIPO_PRECO": "Voz + Dados (2P)",
                        "DS_RECOMENDACAO": "M 14 - UPGRADE - SMALL",
                        "PLANO": "Banda Larga 700 Mbps",
                        "VL_RECOMENDACAO": "99.99",
                        "VL_CONSUMO_MOVEL": "39.99",
                    },
                ),
                (
                    "recomendacao_fixa",
                    "123",
                    3,
                    {
                        "CONTA_COBRANCA": "9001",
                        "RECOMENDACAO": "6",
                        "DS_TIPO_PRECO": "Voz + Dados (2P)",
                        "DS_RECOMENDACAO": "M 14 - UPGRADE - SMALL",
                        "PLANO": "Ilimitado Brasil Empresas",
                        "VL_RECOMENDACAO": "30",
                        "VL_CONSUMO_MOVEL": "39.99",
                    },
                ),
            ]
            conn.executemany(
                "INSERT INTO records VALUES (?, ?, ?, ?)",
                [
                    (source, cnpj, number, json.dumps(payload))
                    for source, cnpj, number, payload in rows
                ],
            )

            detail = app.load_broadband_detail(conn, "123")

        self.assertEqual(len(detail), 1)
        self.assertEqual(detail[0]["m"], "13")
        self.assertEqual(detail[0]["address"], "Rua Exemplo, 100")
        self.assertEqual(len(detail[0]["offers"]), 1)
        offer = detail[0]["offers"][0]
        self.assertEqual(offer["recommendation"], "6")
        self.assertEqual(offer["offer"], "Voz + Dados (2P)")
        self.assertEqual(
            offer["plan"],
            "Banda Larga 700 Mbps + Ilimitado Brasil Empresas + Móvel",
        )
        self.assertEqual(offer["recommendation_label"], "UPGRADE")
        self.assertAlmostEqual(offer["value"], 169.98, places=2)

    def test_recommendation_sources_do_not_locate_client_by_themselves(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_db_path = app.DB_PATH
            app.DB_PATH = Path(temp_dir) / "consulta.sqlite3"
            try:
                with closing(sqlite3.connect(app.DB_PATH)) as conn:
                    conn.execute(
                        """
                        CREATE TABLE records (
                            id INTEGER PRIMARY KEY,
                            source_key TEXT NOT NULL,
                            source_label TEXT NOT NULL,
                            row_number INTEGER NOT NULL,
                            cnpj_key TEXT NOT NULL,
                            cnpj_digits TEXT NOT NULL,
                            cnpj_original TEXT NOT NULL,
                            line_key TEXT NOT NULL DEFAULT '',
                            cliente TEXT,
                            payload_json TEXT NOT NULL
                        )
                        """
                    )
                    conn.execute(
                        """
                        INSERT INTO records (
                            source_key, source_label, row_number, cnpj_key,
                            cnpj_digits, cnpj_original, cliente, payload_json
                        ) VALUES ('recomendacao_fixa', 'RECOMENDACAO FIXA', 2,
                                  '123', '123', '123', NULL, ?)
                        """,
                        (json.dumps({"CONTA_COBRANCA": "9001", "RECOMENDACAO": "1"}),),
                    )
                    conn.execute(
                        """
                        INSERT INTO records (
                            source_key, source_label, row_number, cnpj_key,
                            cnpj_digits, cnpj_original, line_key, cliente, payload_json
                        ) VALUES ('recomendacao_movel', 'RECOMENDACAO MOVEL', 2,
                                  '123', '123', '123', '62998256961', NULL, ?)
                        """,
                        (
                            json.dumps(
                                {
                                    "NR_LINHA": "62998256961",
                                    "PLANO_RECOMENDADO": "Plano A",
                                }
                            ),
                        ),
                    )

                result = app.query_cnpj("123")
            finally:
                app.DB_PATH = original_db_path

        self.assertEqual(result["total"], 0)
        self.assertEqual(result["results"], [])
        self.assertEqual(result["cnpj"], "00.000.000/0001-23")


class MobileInfoParsingTest(unittest.TestCase):
    def test_mobile_line_key_normalizes_country_code_and_excel_decimal(self):
        self.assertEqual(app.mobile_line_key("55 (62) 99825-6961"), "62998256961")
        self.assertEqual(app.mobile_line_key("62998256961.0"), "62998256961")

    def test_parse_decimal_accepts_brazilian_decimal(self):
        self.assertEqual(app.parse_decimal("1.234,56"), app.Decimal("1234.56"))
        self.assertEqual(app.parse_decimal("99,98"), app.Decimal("99.98"))

    def test_m_range_key_groups_expected_ranges(self):
        self.assertEqual(app.m_range_key("16"), "m0_m16")
        self.assertEqual(app.m_range_key("17"), "m17")
        self.assertEqual(app.m_range_key("18"), "above_m17")


class MobileRecommendationTest(unittest.TestCase):
    def test_attaches_two_recommended_plans_by_line(self):
        with closing(sqlite3.connect(":memory:")) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute(
                """
                CREATE TABLE records (
                    source_key TEXT,
                    cnpj_key TEXT,
                    row_number INTEGER,
                    line_key TEXT,
                    payload_json TEXT
                )
                """
            )
            conn.executemany(
                "INSERT INTO records VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        "parque_movel",
                        "123",
                        2,
                        "62998256961",
                        json.dumps(
                            {
                                "NR_TELEFONE": "62998256961",
                                "PLANO": "Smart Empresas 1GB",
                                "M": "10",
                                "FAT_MEDIO_03_MESES": "49.99",
                            }
                        ),
                    ),
                    (
                        "recomendacao_movel",
                        "999",
                        2,
                        "62998256961",
                        json.dumps(
                            {
                                "NR_LINHA": "62998256961",
                                "PLANO_RECOMENDADO": "Smart Empresas 3GB",
                                "PLANO_RECOMENDADO_UP": "Smart Empresas 6GB",
                            }
                        ),
                    ),
                ],
            )

            detail = app.load_mobile_detail(conn, "123")

        self.assertEqual(len(detail), 1)
        self.assertEqual(
            detail[0]["offers"],
            [
                {"offer": "Plano recomendado", "plan": "Smart Empresas 3GB"},
                {"offer": "Plano recomendado UP", "plan": "Smart Empresas 6GB"},
            ],
        )


class DeviceCreditTest(unittest.TestCase):
    def test_extracts_and_formats_brl_credit(self):
        self.assertEqual(
            app.extract_brl_value("capacidade de pagamento de R$16000"),
            "R$ 16.000,00",
        )
        self.assertEqual(
            app.extract_brl_value("capacidade de pagamento de R$16.000"),
            "R$ 16.000,00",
        )

    def test_blank_device_credit_returns_empty_value(self):
        self.assertEqual(app.extract_brl_value(""), "")
        self.assertEqual(app.extract_brl_value("sem informacao"), "")


class ClientProfileTest(unittest.TestCase):
    def test_loads_offer_fields_from_mapa_parque(self):
        with closing(sqlite3.connect(":memory:")) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute(
                """
                CREATE TABLE records (
                    source_key TEXT,
                    cnpj_key TEXT,
                    row_number INTEGER,
                    payload_json TEXT
                )
                """
            )
            conn.execute(
                "INSERT INTO records VALUES ('mapa_parque', '123', 2, ?)",
                (json.dumps({"POSSE": "Movel", "PRIMEIRA_OFERTA": "Oferta A"}),),
            )
            conn.execute(
                "INSERT INTO records VALUES ('mapa_parque', '123', 3, ?)",
                (
                    json.dumps(
                        {
                            "DIGITAL_1": "Microsoft 365",
                            "FIXA_BASICA": "Oferta Fixa Básica",
                            "VIVO_TECH": "Vivo Tech disponível",
                            "AVANCADOS": "Solução avançada",
                            "MOVEL": "Oferta móvel",
                            "VVN": "Oferta VVN",
                            "NM_CONTATO_SFA": "Maria Gestora",
                            "EMAIL_CONTATO_PRINCIPAL_SFA": "maria@example.com",
                            "CELULAR_CONTATO_PRINCIPAL_SFA": "11999990000",
                        }
                    ),
                ),
            )

            profile = app.load_client_profile(conn, "123")

        self.assertEqual(profile["posse"], "Movel")
        self.assertEqual(profile["primeira_oferta"], "Oferta A")
        self.assertEqual(profile["digital"], "Microsoft 365")
        self.assertEqual(profile["fixa_basica"], "Oferta Fixa Básica")
        self.assertEqual(profile["vivo_tech"], "Vivo Tech disponível")
        self.assertEqual(profile["avancada"], "Solução avançada")
        self.assertEqual(profile["movel"], "Oferta móvel")
        self.assertEqual(profile["vvn"], "Oferta VVN")
        self.assertEqual(profile["contact_manager"], "Maria Gestora")
        self.assertEqual(profile["contact_email"], "maria@example.com")
        self.assertEqual(profile["contact_mobile"], "11999990000")


class AuthSecurityTest(unittest.TestCase):
    def test_password_hash_is_not_plain_text_and_verifies(self):
        stored = app.hash_password("Senha1234")
        self.assertNotIn("Senha1234", stored)
        self.assertTrue(app.verify_password("Senha1234", stored))
        self.assertFalse(app.verify_password("SenhaErrada123", stored))

    def test_password_strength_requires_minimum_rules(self):
        self.assertEqual(
            app.validate_password_strength("curta1"),
            "A senha deve ter no mínimo 8 caracteres.",
        )
        self.assertEqual(
            app.validate_password_strength("senhasemnumero"),
            "A senha deve conter ao menos um número.",
        )
        self.assertEqual(app.validate_password_strength("Senha1234"), "")

    def test_initial_admin_uses_environment_configuration(self):
        original_auth_db_path = app.AUTH_DB_PATH
        original_cache_dir = app.CACHE_DIR
        original_values = {
            key: os.environ.get(key)
            for key in ("ADMIN_NAME", "ADMIN_EMAIL", "ADMIN_PASSWORD")
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                app.CACHE_DIR = Path(temp_dir)
                app.AUTH_DB_PATH = app.CACHE_DIR / "auth.sqlite3"
                os.environ["ADMIN_NAME"] = "Admin Teste"
                os.environ["ADMIN_EMAIL"] = "admin.teste@example.com"
                os.environ["ADMIN_PASSWORD"] = "SenhaAdmin123"
                app.initialize_auth_database()
                with app.open_auth_db() as conn:
                    admin = app.fetch_user_by_email(conn, "admin.teste@example.com")
                self.assertEqual(admin["nome_completo"], "Admin Teste")
                self.assertEqual(admin["perfil"], "ADMIN")
                self.assertTrue(admin["email_confirmado_em"])
                self.assertTrue(app.verify_password("SenhaAdmin123", admin["senha_hash"]))
                self.assertFalse((app.CACHE_DIR / "admin_credentials.txt").exists())
            finally:
                app.AUTH_DB_PATH = original_auth_db_path
                app.CACHE_DIR = original_cache_dir
                for key, value in original_values.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value


class EmailVerificationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_auth_db_path = app.AUTH_DB_PATH
        self.original_cache_dir = app.CACHE_DIR
        self.original_admin_password = os.environ.get("ADMIN_PASSWORD")
        self.original_smtp_host = os.environ.pop("SMTP_HOST", None)
        os.environ["ADMIN_PASSWORD"] = "Senha1234"
        app.CACHE_DIR = Path(self.temp_dir.name)
        app.AUTH_DB_PATH = app.CACHE_DIR / "auth.sqlite3"
        app.initialize_auth_database()

    def tearDown(self):
        app.AUTH_DB_PATH = self.original_auth_db_path
        app.CACHE_DIR = self.original_cache_dir
        if self.original_admin_password is None:
            os.environ.pop("ADMIN_PASSWORD", None)
        else:
            os.environ["ADMIN_PASSWORD"] = self.original_admin_password
        if self.original_smtp_host is not None:
            os.environ["SMTP_HOST"] = self.original_smtp_host
        self.temp_dir.cleanup()

    def register_user(self):
        return app.create_pending_user(
            {
                "nome_completo": "Maria Supervisora",
                "email": "maria@example.com",
                "senha": "Senha1234",
                "senha_confirmacao": "Senha1234",
            },
            "127.0.0.1",
            "tests",
            "http://127.0.0.1:8000",
        )

    def verification_token_from_outbox(self):
        files = list((app.CACHE_DIR / "email_verification_outbox").glob("*.txt"))
        self.assertTrue(files)
        newest = max(files, key=lambda path: path.stat().st_mtime_ns)
        content = newest.read_text(encoding="utf-8")
        match = re.search(r"confirmar-email\?token=([^\s]+)", content)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_email_must_be_confirmed_before_approval_and_login(self):
        ok, message = self.register_user()
        self.assertTrue(ok)
        self.assertIn("validação", message)

        with app.open_auth_db() as conn:
            user = app.fetch_user_by_email(conn, "maria@example.com")
            user_id = user["id"]
            self.assertIsNone(user["email_confirmado_em"])

        status, response, token = app.authenticate_user(
            "maria@example.com", "Senha1234", "127.0.0.1", "tests"
        )
        self.assertEqual(status, app.HTTPStatus.FORBIDDEN)
        self.assertEqual(response["code"], "EMAIL_NAO_CONFIRMADO")
        self.assertIsNone(token)

        status, response = app.update_user_status({"id": 1}, user_id, "aprovar")
        self.assertEqual(status, app.HTTPStatus.BAD_REQUEST)
        self.assertIn("confirmar", response["message"].lower())

        verification_token = self.verification_token_from_outbox()
        status, response = app.confirm_email(verification_token)
        self.assertEqual(status, app.HTTPStatus.OK)
        self.assertTrue(response["ok"])

        status, response = app.update_user_status({"id": 1}, user_id, "aprovar")
        self.assertEqual(status, app.HTTPStatus.OK)
        self.assertTrue(response["ok"])
        status, response, session_token = app.authenticate_user(
            "maria@example.com", "Senha1234", "127.0.0.1", "tests"
        )
        self.assertEqual(status, app.HTTPStatus.OK)
        self.assertTrue(session_token)

    def test_resend_invalidates_previous_verification_token(self):
        self.register_user()
        first_token = self.verification_token_from_outbox()
        response = app.request_email_verification(
            "maria@example.com", "127.0.0.1", "tests", "http://127.0.0.1:8000"
        )
        self.assertTrue(response["ok"])
        second_token = self.verification_token_from_outbox()
        self.assertNotEqual(first_token, second_token)

        status, _ = app.confirm_email(first_token)
        self.assertEqual(status, app.HTTPStatus.BAD_REQUEST)
        status, response = app.confirm_email(second_token)
        self.assertEqual(status, app.HTTPStatus.OK)
        self.assertTrue(response["ok"])


class SessionCookieTest(unittest.TestCase):
    def test_auto_secure_cookie_follows_request_proto(self):
        self.assertTrue(app.secure_cookie_enabled("auto", "https"))
        self.assertTrue(app.secure_cookie_enabled("", "https, http"))
        self.assertFalse(app.secure_cookie_enabled("auto", "http"))

    def test_explicit_secure_cookie_values(self):
        self.assertTrue(app.secure_cookie_enabled("1", "http"))
        self.assertTrue(app.secure_cookie_enabled("true", "http"))
        self.assertFalse(app.secure_cookie_enabled("0", "https"))

    def test_set_session_cookie_omits_secure_on_http_auto(self):
        original_mode = app.SESSION_COOKIE_SECURE_MODE
        app.SESSION_COOKIE_SECURE_MODE = "auto"
        handler = object.__new__(app.ConsultaHandler)
        handler.headers = {"X-Forwarded-Proto": "http"}
        sent_headers = []
        handler.send_header = lambda name, value: sent_headers.append((name, value))

        try:
            handler.set_session_cookie("abc")
        finally:
            app.SESSION_COOKIE_SECURE_MODE = original_mode

        cookie = next(value for name, value in sent_headers if name == "Set-Cookie")
        self.assertNotIn("; Secure", cookie)

    def test_set_session_cookie_adds_secure_on_https_auto(self):
        original_mode = app.SESSION_COOKIE_SECURE_MODE
        app.SESSION_COOKIE_SECURE_MODE = "auto"
        handler = object.__new__(app.ConsultaHandler)
        handler.headers = {"X-Forwarded-Proto": "https"}
        sent_headers = []
        handler.send_header = lambda name, value: sent_headers.append((name, value))

        try:
            handler.set_session_cookie("abc")
        finally:
            app.SESSION_COOKIE_SECURE_MODE = original_mode

        cookie = next(value for name, value in sent_headers if name == "Set-Cookie")
        self.assertIn("; Secure", cookie)


class PdfExportTest(unittest.TestCase):
    def test_simple_pdf_has_pdf_signature(self):
        pdf = app.build_simple_pdf(["Consulta Base", "Cliente: Teste"])
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertIn(b"%%EOF", pdf)

    def test_cnpj_pdf_uses_fourteen_digit_display(self):
        original_query_cnpj = app.query_cnpj
        app.query_cnpj = lambda value: {
            "total": 1,
            "cnpj": app.format_cnpj_display(value),
            "normalized": app.cnpj_key(value),
            "company_name": "Cliente Teste",
            "metrics": {},
            "mobile_info": {},
        }
        try:
            status, pdf, filename = app.build_cnpj_pdf("21.147.000/320")
        finally:
            app.query_cnpj = original_query_cnpj

        self.assertEqual(status, app.HTTPStatus.OK)
        self.assertIn(b"CNPJ: 00.021.147/0003-20", pdf)
        self.assertEqual(filename, "consulta-cnpj-00021147000320.pdf")


class DataUploadTest(unittest.TestCase):
    def test_empty_install_starts_without_bundled_bases(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original_root = app.ROOT
            original_data_dir = app.DATA_DIR
            original_data_files = app.DATA_FILES
            original_file_by_key = app.DATA_FILE_BY_KEY
            original_state = app.APP_STATE
            try:
                app.ROOT = root
                app.DATA_DIR = root / "data"
                app.DATA_FILES = [
                    {
                        "key": "base_a",
                        "label": "BASE A",
                        "path": app.DATA_DIR / "BASE A.csv",
                        "cnpj_columns": ["DOCUMENTO"],
                        "cliente_columns": [],
                    }
                ]
                app.DATA_FILE_BY_KEY = {item["key"]: item for item in app.DATA_FILES}
                state = app.initialize_data()
                data_dir_created = app.DATA_DIR.is_dir()
            finally:
                app.ROOT = original_root
                app.DATA_DIR = original_data_dir
                app.DATA_FILES = original_data_files
                app.DATA_FILE_BY_KEY = original_file_by_key
                app.APP_STATE = original_state

        self.assertFalse(state["ready"])
        self.assertEqual(state["missing_files"], ["data/BASE A.csv"])
        self.assertTrue(data_dir_created)

    def test_deferred_admin_upload_is_saved_while_other_required_base_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original_root = app.ROOT
            original_data_dir = app.DATA_DIR
            original_data_files = app.DATA_FILES
            original_file_by_key = app.DATA_FILE_BY_KEY
            original_state = app.APP_STATE
            try:
                app.ROOT = root
                app.DATA_DIR = root / "data"
                app.DATA_FILES = [
                    {
                        "key": "base_a",
                        "label": "BASE A",
                        "path": app.DATA_DIR / "BASE A.csv",
                        "cnpj_columns": ["DOCUMENTO"],
                        "cliente_columns": [],
                    },
                    {
                        "key": "base_b",
                        "label": "BASE B",
                        "path": app.DATA_DIR / "BASE B.csv",
                        "cnpj_columns": ["DOCUMENTO"],
                        "cliente_columns": [],
                    },
                ]
                app.DATA_FILE_BY_KEY = {item["key"]: item for item in app.DATA_FILES}
                status, response = app.save_uploaded_data_files(
                    [
                        {
                            "name": "base_a",
                            "filename": "BASE A.csv",
                            "content": b"DOCUMENTO;CLIENTE\n12;Cliente\n",
                        }
                    ],
                    refresh_after_upload=False,
                )
                file_saved = (app.DATA_DIR / "BASE A.csv").is_file()
            finally:
                app.ROOT = original_root
                app.DATA_DIR = original_data_dir
                app.DATA_FILES = original_data_files
                app.DATA_FILE_BY_KEY = original_file_by_key
                app.APP_STATE = original_state

        self.assertEqual(status, app.HTTPStatus.OK)
        self.assertTrue(response["ok"])
        self.assertFalse(response["ready"])
        self.assertIn("data/BASE B.csv", response["message"])
        self.assertTrue(file_saved)

    def test_validate_uploaded_csv_headers_accepts_expected_cnpj_column(self):
        headers = app.validate_uploaded_csv_headers(
            b"NR_CNPJ;NM_CLIENTE\n12;Cliente\n",
            app.DATA_FILE_BY_KEY["mapa_parque"],
        )
        self.assertIn("NR_CNPJ", headers)

    def test_validate_uploaded_csv_headers_rejects_wrong_file(self):
        with self.assertRaises(ValueError):
            app.validate_uploaded_csv_headers(
                b"DOCUMENTO;NM_CLIENTE\n12;Cliente\n",
                app.DATA_FILE_BY_KEY["parque_movel"],
            )

    def test_validate_recommendation_file_by_document_column(self):
        headers = app.validate_uploaded_csv_headers(
            b"DOCUMENTO;CONTA_COBRANCA;RECOMENDACAO\n12;9001;1\n",
            app.DATA_FILE_BY_KEY["recomendacao_fixa"],
        )
        self.assertIn("DOCUMENTO", headers)

    def test_validate_mobile_recommendation_file_by_document_column(self):
        headers = app.validate_uploaded_csv_headers(
            b"NR_DOCUMENTO;NR_LINHA;PLANO_RECOMENDADO;PLANO_RECOMENDADO_UP\n12;6299;Plano A;Plano B\n",
            app.DATA_FILE_BY_KEY["recomendacao_movel"],
        )
        self.assertIn("NR_DOCUMENTO", headers)

    def test_parse_multipart_form_extracts_named_csv_file(self):
        boundary = "----a7boundary"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="mapa_parque"; filename="MAPA PARQUE.csv"\r\n'
            "Content-Type: text/csv\r\n\r\n"
            "NR_CNPJ;NM_CLIENTE\r\n12;Cliente\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")
        parts = app.parse_multipart_form(f"multipart/form-data; boundary={boundary}", body)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]["name"], "mapa_parque")
        self.assertEqual(parts[0]["filename"], "MAPA PARQUE.csv")
        self.assertIn(b"NR_CNPJ", parts[0]["content"])


class SearchHistoryTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_auth_db_path = app.AUTH_DB_PATH
        self.original_admin_password = os.environ.get("ADMIN_PASSWORD")
        os.environ["ADMIN_PASSWORD"] = "Senha1234"
        app.AUTH_DB_PATH = Path(self.temp_dir.name) / "auth.sqlite3"
        app.initialize_auth_database()

    def tearDown(self):
        app.AUTH_DB_PATH = self.original_auth_db_path
        if self.original_admin_password is None:
            os.environ.pop("ADMIN_PASSWORD", None)
        else:
            os.environ["ADMIN_PASSWORD"] = self.original_admin_password
        self.temp_dir.cleanup()

    def create_active_user(
        self,
        name,
        email,
        team_id=None,
        profile="USUARIO",
        manager_id=None,
    ):
        with app.open_auth_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (
                    nome_completo, email, email_confirmado_em, senha_hash, perfil, status,
                    data_criacao, data_aprovacao, equipe_id, gestor_id
                ) VALUES (?, ?, ?, ?, ?, 'ATIVO', ?, ?, ?, ?)
                """,
                (
                    name,
                    email,
                    app.utc_iso(),
                    app.hash_password("Senha1234"),
                    profile,
                    app.utc_iso(),
                    app.utc_iso(),
                    team_id,
                    manager_id,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def test_history_keeps_only_latest_15_items(self):
        for index in range(16):
            cnpj = f"12.345.678/0001-{index:02d}"
            app.save_search_history(
                1,
                cnpj,
                {"query": cnpj, "total": 1, "company_name": f"Cliente {index}"},
            )

        items = app.list_search_history(1)
        self.assertEqual(len(items), 15)
        self.assertEqual(items[0]["cnpj"], "12.345.678/0001-15")
        self.assertNotIn("12.345.678/0001-00", [item["cnpj"] for item in items])

    def test_session_lasts_two_hours_and_new_login_invalidates_previous(self):
        with app.open_auth_db() as conn:
            first_token = app.create_session(conn, 1, "127.0.0.1", "device-one")
            first_session = conn.execute(
                "SELECT data_criacao, data_expiracao FROM sessions WHERE token_hash = ?",
                (app.hash_token(first_token),),
            ).fetchone()

        created_at = app.parse_iso_datetime(first_session["data_criacao"])
        expires_at = app.parse_iso_datetime(first_session["data_expiracao"])
        self.assertEqual(expires_at - created_at, app.timedelta(hours=2))
        self.assertIsNotNone(app.lookup_session_user(first_token))

        with app.open_auth_db() as conn:
            second_token = app.create_session(conn, 1, "10.0.0.2", "device-two")
            active_sessions = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE user_id = 1 AND ativo = 1"
            ).fetchone()[0]

        self.assertEqual(active_sessions, 1)
        self.assertIsNone(app.lookup_session_user(first_token))
        self.assertIsNotNone(app.lookup_session_user(second_token))

    def test_session_created_more_than_two_hours_ago_is_rejected(self):
        with app.open_auth_db() as conn:
            token = app.create_session(conn, 1, "127.0.0.1", "old-device")
            conn.execute(
                """
                UPDATE sessions
                SET data_criacao = ?, data_expiracao = ?
                WHERE token_hash = ?
                """,
                (
                    app.utc_iso(app.utc_now() - app.timedelta(hours=3)),
                    app.utc_iso(app.utc_now() + app.timedelta(hours=9)),
                    app.hash_token(token),
                ),
            )
            conn.commit()

        self.assertIsNone(app.lookup_session_user(token))

    def test_history_updates_repeated_cnpj_without_duplicate(self):
        app.save_search_history(
            1,
            "11.222.333/0001-44",
            {"query": "11.222.333/0001-44", "total": 0, "company_name": ""},
        )
        app.save_search_history(
            1,
            "11222333000144",
            {"query": "11222333000144", "total": 4, "company_name": "Cliente Atualizado"},
        )

        items = app.list_search_history(1)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["company_name"], "Cliente Atualizado")
        self.assertTrue(items[0]["found"])

    def test_admin_can_create_team_and_assign_user(self):
        status, created = app.create_team("Comercial SP")
        self.assertEqual(status, app.HTTPStatus.CREATED)
        team_id = created["team"]["id"]

        status, response = app.assign_user_team(1, team_id)
        self.assertEqual(status, app.HTTPStatus.OK)
        self.assertTrue(response["ok"])
        user = next(item for item in app.list_users() if item["id"] == 1)
        self.assertEqual(user["equipe_id"], team_id)
        self.assertEqual(user["equipe_nome"], "Comercial SP")
        self.assertEqual(app.list_teams()[0]["total_membros"], 1)

    def test_user_can_be_removed_from_team(self):
        _, created = app.create_team("Suporte")
        app.assign_user_team(1, created["team"]["id"])
        status, _ = app.assign_user_team(1, None)
        self.assertEqual(status, app.HTTPStatus.OK)
        self.assertIsNone(app.list_users()[0]["equipe_id"])

    def test_supervisor_profile_requires_and_keeps_a_team(self):
        user_id = self.create_active_user("Supervisora", "supervisora@example.com")
        status, response = app.assign_user_profile({"id": 1}, user_id, "SUPERVISOR")
        self.assertEqual(status, app.HTTPStatus.BAD_REQUEST)
        self.assertIn("equipe", response["message"].lower())

        _, created = app.create_team("Equipe Centro")
        team_id = created["team"]["id"]
        app.assign_user_team(user_id, team_id)
        status, response = app.assign_user_profile({"id": 1}, user_id, "SUPERVISOR")
        self.assertEqual(status, app.HTTPStatus.OK)
        self.assertTrue(response["ok"])
        supervisor = next(item for item in app.list_users() if item["id"] == user_id)
        self.assertEqual(supervisor["perfil"], "SUPERVISOR")

        with app.open_auth_db() as conn:
            token = app.create_session(conn, user_id, "127.0.0.1", "tests")
        session_user = app.lookup_session_user(token)
        self.assertEqual(session_user["equipe_id"], team_id)
        self.assertEqual(session_user["equipe_nome"], "Equipe Centro")

        status, response = app.assign_user_team(user_id, None)
        self.assertEqual(status, app.HTTPStatus.BAD_REQUEST)
        self.assertIn("equipe", response["message"].lower())

    def test_supervisor_report_contains_only_own_team(self):
        _, team_a = app.create_team("Equipe A")
        _, team_b = app.create_team("Equipe B")
        team_a_id = team_a["team"]["id"]
        team_b_id = team_b["team"]["id"]
        supervisor_id = self.create_active_user(
            "Supervisor A", "supervisor-a@example.com", team_a_id, "SUPERVISOR"
        )
        member_a_id = self.create_active_user(
            "Pessoa A", "pessoa-a@example.com", team_a_id
        )
        member_b_id = self.create_active_user(
            "Pessoa B", "pessoa-b@example.com", team_b_id
        )
        app.save_search_history(
            supervisor_id,
            "11.111.111/0001-11",
            {"query": "11.111.111/0001-11", "total": 1, "company_name": "Cliente A"},
        )
        app.save_search_history(
            member_a_id,
            "22.222.222/0001-22",
            {"query": "22.222.222/0001-22", "total": 1, "company_name": "Cliente B"},
        )
        app.save_search_history(
            member_b_id,
            "33.333.333/0001-33",
            {"query": "33.333.333/0001-33", "total": 1, "company_name": "Cliente externo"},
        )

        report = app.usage_ranking_report(team_a_id, "Equipe A")
        self.assertEqual(report["scope"]["type"], "team")
        self.assertEqual(report["scope"]["team_name"], "Equipe A")
        self.assertEqual(
            {item["nome_completo"] for item in report["items"]},
            {"Supervisor A", "Pessoa A"},
        )
        self.assertEqual(report["summary"]["consultas_totais"], 2)
        self.assertEqual([team["equipe"] for team in report["teams"]], ["Equipe A"])
        self.assertNotIn("Cliente externo", [client["cliente"] for client in report["top_clients"]])

    def test_supervisor_can_be_assigned_to_manager(self):
        manager_id = self.create_active_user(
            "Gestora Regional", "gestora@example.com", profile="GESTOR"
        )
        _, created = app.create_team("Equipe Norte")
        supervisor_id = self.create_active_user(
            "Supervisor Norte",
            "supervisor-norte@example.com",
            created["team"]["id"],
            "SUPERVISOR",
        )

        status, response = app.assign_user_manager(supervisor_id, manager_id)

        self.assertEqual(status, app.HTTPStatus.OK)
        self.assertTrue(response["ok"])
        supervisor = next(item for item in app.list_users() if item["id"] == supervisor_id)
        self.assertEqual(supervisor["gestor_id"], manager_id)
        self.assertEqual(supervisor["gestor_nome"], "Gestora Regional")

    def test_only_supervisor_can_be_assigned_to_manager(self):
        manager_id = self.create_active_user(
            "Gestor", "gestor-validacao@example.com", profile="GESTOR"
        )
        user_id = self.create_active_user("Pessoa", "pessoa-validacao@example.com")

        status, response = app.assign_user_manager(user_id, manager_id)

        self.assertEqual(status, app.HTTPStatus.BAD_REQUEST)
        self.assertIn("supervisores", response["message"].lower())

    def test_manager_profile_cannot_change_with_assigned_supervisors(self):
        manager_id = self.create_active_user(
            "Gestora", "gestora-bloqueio@example.com", profile="GESTOR"
        )
        _, created = app.create_team("Equipe Bloqueio")
        self.create_active_user(
            "Supervisora",
            "supervisora-bloqueio@example.com",
            created["team"]["id"],
            "SUPERVISOR",
            manager_id,
        )

        status, response = app.assign_user_profile({"id": 1}, manager_id, "USUARIO")

        self.assertEqual(status, app.HTTPStatus.BAD_REQUEST)
        self.assertIn("reatribua", response["message"].lower())

        status, response = app.update_user_status({"id": 1}, manager_id, "cancelar")
        self.assertEqual(status, app.HTTPStatus.BAD_REQUEST)
        self.assertIn("reatribua", response["message"].lower())

    def test_manager_report_contains_only_assigned_supervisors_teams(self):
        manager_id = self.create_active_user(
            "Gestor Sudeste", "gestor-sudeste@example.com", profile="GESTOR"
        )
        other_manager_id = self.create_active_user(
            "Gestor Sul", "gestor-sul@example.com", profile="GESTOR"
        )
        _, team_a = app.create_team("Equipe A Gestor")
        _, team_b = app.create_team("Equipe B Gestor")
        team_a_id = team_a["team"]["id"]
        team_b_id = team_b["team"]["id"]
        supervisor_id = self.create_active_user(
            "Supervisor A",
            "supervisor-gestor-a@example.com",
            team_a_id,
            "SUPERVISOR",
            manager_id,
        )
        member_id = self.create_active_user(
            "Pessoa A", "pessoa-gestor-a@example.com", team_a_id
        )
        external_id = self.create_active_user(
            "Pessoa B", "pessoa-gestor-b@example.com", team_b_id
        )
        self.create_active_user(
            "Supervisor B",
            "supervisor-gestor-b@example.com",
            team_b_id,
            "SUPERVISOR",
            other_manager_id,
        )
        for user_id, cnpj, client in (
            (supervisor_id, "11.111.111/0001-11", "Cliente Supervisor"),
            (member_id, "22.222.222/0001-22", "Cliente Equipe"),
            (external_id, "33.333.333/0001-33", "Cliente Externo"),
        ):
            app.save_search_history(
                user_id,
                cnpj,
                {"query": cnpj, "total": 1, "company_name": client},
            )

        scope = app.manager_report_scope(manager_id)
        report = app.usage_ranking_report(
            team_ids=scope["team_ids"],
            manager_name="Gestor Sudeste",
            supervisors=scope["supervisors"],
        )

        self.assertEqual(report["scope"]["type"], "manager")
        self.assertEqual(report["scope"]["manager_name"], "Gestor Sudeste")
        self.assertEqual(len(report["scope"]["supervisors"]), 1)
        self.assertEqual(
            {item["nome_completo"] for item in report["items"]},
            {"Supervisor A", "Pessoa A"},
        )
        self.assertEqual(report["summary"]["consultas_totais"], 2)
        self.assertNotIn(
            "Cliente Externo",
            [client["cliente"] for client in report["top_clients"]],
        )

        user_report = app.usage_ranking_report(
            team_ids=scope["team_ids"],
            manager_name="Gestor Sudeste",
            supervisors=scope["supervisors"],
            filter_user_id=member_id,
        )
        self.assertEqual(
            [item["nome_completo"] for item in user_report["items"]],
            ["Pessoa A"],
        )
        self.assertEqual(user_report["summary"]["consultas_totais"], 1)
        self.assertEqual(user_report["filters"]["selected_user_name"], "Pessoa A")
        self.assertEqual(len(user_report["filters"]["users"]), 2)

        outside_team_report = app.usage_ranking_report(
            team_ids=scope["team_ids"],
            filter_team_id=team_b_id,
        )
        self.assertEqual(outside_team_report["items"], [])
        self.assertEqual(outside_team_report["filters"]["selected_team_name"], "")

    def test_usage_report_can_filter_by_team(self):
        _, team_a = app.create_team("Equipe Filtro A")
        _, team_b = app.create_team("Equipe Filtro B")
        member_a_id = self.create_active_user(
            "Pessoa Filtro A", "filtro-a@example.com", team_a["team"]["id"]
        )
        member_b_id = self.create_active_user(
            "Pessoa Filtro B", "filtro-b@example.com", team_b["team"]["id"]
        )
        for user_id, cnpj in (
            (member_a_id, "44.444.444/0001-44"),
            (member_b_id, "55.555.555/0001-55"),
        ):
            app.save_search_history(
                user_id,
                cnpj,
                {"query": cnpj, "total": 1, "company_name": "Cliente Filtro"},
            )

        report = app.usage_ranking_report(filter_team_id=team_a["team"]["id"])

        self.assertEqual(
            [item["nome_completo"] for item in report["items"]],
            ["Pessoa Filtro A"],
        )
        self.assertEqual(report["summary"]["consultas_totais"], 1)
        self.assertEqual(report["filters"]["selected_team_name"], "Equipe Filtro A")
        self.assertEqual(
            {team["nome"] for team in report["filters"]["teams"]},
            {"Equipe Filtro A", "Equipe Filtro B"},
        )

    def test_usage_report_counts_repeated_consultations(self):
        app.save_search_history(
            1,
            "11.222.333/0001-44",
            {"query": "11.222.333/0001-44", "total": 1, "company_name": "Cliente"},
        )
        app.save_search_history(
            1,
            "11222333000144",
            {"query": "11222333000144", "total": 1, "company_name": "Cliente"},
        )

        report = app.usage_ranking_report()
        admin = next(item for item in report["items"] if item["perfil"] == "ADMIN")
        self.assertEqual(admin["consultas_totais"], 2)
        self.assertEqual(admin["consultas_mensais"], 2)
        self.assertEqual(admin["consultas_diarias"], 2)
        self.assertEqual(admin["clientes_unicos_mes"], 1)
        self.assertEqual(admin["posicao"], 1)
        self.assertEqual(report["summary"]["clientes_unicos_mes"], 1)
        self.assertEqual(report["summary"]["adocao_mensal"], 100.0)
        self.assertEqual(sum(item["consultas"] for item in report["daily_trend"]), 2)
        self.assertEqual(report["top_clients"][0]["consultas"], 2)
        self.assertEqual(report["teams"][0]["equipe"], "Sem equipe")


if __name__ == "__main__":
    unittest.main()
