import json
import os
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
        admin = next(item for item in report["items"] if item["perfil"] == "ADMIN")
        self.assertEqual(admin["consultas_totais"], 2)
        self.assertEqual(admin["consultas_mensais"], 2)
        self.assertEqual(admin["consultas_diarias"], 2)
        self.assertEqual(admin["posicao"], 1)


if __name__ == "__main__":
    unittest.main()
