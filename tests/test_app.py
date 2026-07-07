import os
import tempfile
import unittest
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


class MobileInfoParsingTest(unittest.TestCase):
    def test_parse_decimal_accepts_brazilian_decimal(self):
        self.assertEqual(app.parse_decimal("1.234,56"), app.Decimal("1234.56"))
        self.assertEqual(app.parse_decimal("99,98"), app.Decimal("99.98"))

    def test_m_range_key_groups_expected_ranges(self):
        self.assertEqual(app.m_range_key("16"), "m0_m16")
        self.assertEqual(app.m_range_key("17"), "m17")
        self.assertEqual(app.m_range_key("18"), "above_m17")


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


class DataUploadTest(unittest.TestCase):
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
        admin = next(item for item in report["items"] if item["email"] == "admin@a7connect.local")
        self.assertEqual(admin["consultas_totais"], 2)
        self.assertEqual(admin["consultas_mensais"], 2)
        self.assertEqual(admin["consultas_diarias"], 2)
        self.assertEqual(admin["posicao"], 1)


if __name__ == "__main__":
    unittest.main()
