import tempfile
import unittest
from datetime import date
from pathlib import Path

import calculator_engine
from calculator_engine import (
    CalculationError,
    apply_function,
    calculate_age,
    calculate_bmi,
    convert_currency,
    convert_units,
    currency_codes,
    download_rates,
    evaluate,
    format_number,
    graph_points,
    load_history,
    load_saved_rates,
    parse_rates,
    save_history,
)


class EvaluateTests(unittest.TestCase):
    def test_four_basic_operations(self) -> None:
        self.assertEqual(evaluate("5 + 10"), 15)
        self.assertEqual(evaluate("9 − 4"), 5)
        self.assertEqual(evaluate("6 × 7"), 42)
        self.assertEqual(evaluate("7 ÷ 2"), 3.5)
        self.assertEqual(evaluate("2 + 3 * 4"), 14)
        self.assertEqual(evaluate("(2 + 3) * 4"), 20)
        self.assertEqual(evaluate("2^10"), 1024)

    def test_multiplication_can_be_written_like_on_paper(self) -> None:
        self.assertEqual(evaluate("2(3 + 4)"), 14)
        self.assertEqual(evaluate("(1 + 2)(3)"), 9)
        self.assertAlmostEqual(evaluate("2π"), 6.283185307179586)
        self.assertEqual(evaluate("2e2"), 200)

    def test_scientific_functions_and_constants(self) -> None:
        self.assertAlmostEqual(evaluate("sin(30)"), 0.5)
        self.assertEqual(evaluate("sin(180)"), 0)
        self.assertAlmostEqual(evaluate("sqrt(81) + log(100)"), 11.0)
        self.assertAlmostEqual(evaluate("ln(e)"), 1.0)
        self.assertAlmostEqual(evaluate("asin(0.5)"), 30.0)
        self.assertAlmostEqual(evaluate("sin(π / 2)", degrees=False), 1.0)
        self.assertEqual(evaluate("fact(5)"), 120)

    def test_function_button_works_on_number_on_screen(self) -> None:
        self.assertEqual(apply_function("sqrt", 81), 9)
        self.assertAlmostEqual(apply_function("cos", 60), 0.5)
        self.assertAlmostEqual(apply_function("sin", 3.141592653589793 / 2, degrees=False), 1.0)

    def test_invalid_input_shows_an_error(self) -> None:
        for expression in ("", "a + b", "1 / 0", "sqrt(-1)", "5 +", "tan(90)", "__import__('os')", "pi.real"):
            with self.subTest(expression=expression):
                with self.assertRaises(CalculationError):
                    evaluate(expression)

    def test_huge_answers_are_rejected(self) -> None:
        for expression in ("fact(170) * fact(170)", "10 ** 400", "(10 ** 300 * 10) ** 1000", "(-1) ** 0.5"):
            with self.subTest(expression=expression):
                with self.assertRaises(CalculationError):
                    evaluate(expression)

    def test_format_number(self) -> None:
        self.assertEqual(format_number(evaluate("0.1 + 0.2")), "0.3")
        self.assertEqual(format_number(evaluate("10 / 2")), "5")
        self.assertEqual(format_number(15), "15")


class EverydayToolTests(unittest.TestCase):
    def test_bmi(self) -> None:
        self.assertEqual(calculate_bmi(60, 165), (22.0, "Normal weight"))
        self.assertEqual(calculate_bmi(90, 170)[1], "Obese")
        with self.assertRaises(CalculationError):
            calculate_bmi(0, 170)

    def test_age(self) -> None:
        self.assertEqual(calculate_age(date(1990, 5, 20), date(2026, 10, 28)), (36, 5, 8, 204))
        self.assertEqual(calculate_age(date(2000, 10, 28), date(2026, 10, 28))[3], 0)
        with self.assertRaises(CalculationError):
            calculate_age(date(2030, 1, 1), date(2026, 10, 28))


class UnitConverterTests(unittest.TestCase):
    def test_common_conversions(self) -> None:
        self.assertAlmostEqual(convert_units(1, "Length", "Kilometre", "Metre"), 1000)
        self.assertAlmostEqual(convert_units(1, "Length", "Mile", "Kilometre"), 1.609344)
        self.assertAlmostEqual(convert_units(1, "Weight", "Kilogram", "Pound"), 2.20462262, places=6)
        self.assertAlmostEqual(convert_units(1, "Time", "Day", "Hour"), 24)
        self.assertAlmostEqual(convert_units(36, "Speed", "Kilometre per hour", "Metre per second"), 10)
        self.assertAlmostEqual(convert_units(1, "Volume", "Gallon (US)", "Litre"), 3.785411784)

    def test_temperature(self) -> None:
        self.assertAlmostEqual(convert_units(100, "Temperature", "Celsius", "Fahrenheit"), 212)
        self.assertAlmostEqual(convert_units(32, "Temperature", "Fahrenheit", "Celsius"), 0)
        self.assertAlmostEqual(convert_units(0, "Temperature", "Kelvin", "Celsius"), -273.15)
        with self.assertRaises(CalculationError):
            convert_units(-300, "Temperature", "Celsius", "Kelvin")

    def test_negative_length_is_rejected(self) -> None:
        with self.assertRaises(CalculationError):
            convert_units(-5, "Length", "Metre", "Foot")


class SavedHistoryTests(unittest.TestCase):
    def test_history_is_kept_between_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.json"
            self.assertEqual(load_history(path), [])
            save_history(["2+2 = 4", "√(81) = 9"], path)
            self.assertEqual(load_history(path), ["2+2 = 4", "√(81) = 9"])

    def test_only_latest_100_are_kept(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.json"
            save_history([f"{n}+0 = {n}" for n in range(150)], path)
            self.assertEqual(len(load_history(path)), 100)

    def test_broken_file_gives_empty_history(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.json"
            path.write_text("not json", encoding="utf-8")
            self.assertEqual(load_history(path), [])


class GraphTests(unittest.TestCase):
    def test_points_follow_the_formula(self) -> None:
        points = graph_points("x^2", -2, 2, steps=4)
        self.assertEqual(points, [(-2, 4), (-1, 1), (0, 0), (1, 1), (2, 4)])

    def test_no_answer_gives_a_gap(self) -> None:
        points = graph_points("sqrt(x)", -1, 1, steps=2)
        self.assertEqual(points, [(-1, None), (0, 0), (1, 1)])

    def test_wrong_formula_or_range_is_rejected(self) -> None:
        for formula, x_from, x_to in (("sin(y)", 0, 1), ("x +", 0, 1), ("x", 5, 1)):
            with self.subTest(formula=formula):
                with self.assertRaises(CalculationError):
                    graph_points(formula, x_from, x_to)


class CurrencyTests(unittest.TestCase):
    RATES = {"source": "test", "date": "2026-10-28", "rates": {"USD": 1.0, "INR": 88.0, "EUR": 0.8}}

    def test_conversion_goes_through_dollars(self) -> None:
        self.assertAlmostEqual(convert_currency(10, "USD", "INR", self.RATES), 880)
        self.assertAlmostEqual(convert_currency(880, "INR", "EUR", self.RATES), 8)
        with self.assertRaises(CalculationError):
            convert_currency(-1, "USD", "INR", self.RATES)

    def test_both_rate_services_are_understood(self) -> None:
        frankfurter = {"base": "USD", "date": "2026-10-28", "rates": {"INR": 88.0}}
        exchange_rate_api = {"result": "success", "time_last_update_utc": "Wed, 28 Oct 2026 00:00:01 +0000",
                             "rates": {"USD": 1, "INR": 88.0}}
        self.assertEqual(parse_rates(frankfurter, "a")["rates"], {"INR": 88.0, "USD": 1.0})
        self.assertEqual(parse_rates(exchange_rate_api, "b")["date"], "Wed, 28 Oct 2026")
        self.assertEqual(currency_codes(self.RATES), ["INR", "USD", "EUR"])

    def test_certificate_problem_falls_back_to_curl(self) -> None:
        from unittest import mock

        reply = b'{"base": "USD", "date": "2026-10-28", "rates": {"INR": 88.0}}'
        certificate_error = OSError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
        curl_result = mock.Mock(returncode=0, stdout=reply)
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch("urllib.request.urlopen", side_effect=certificate_error), \
                mock.patch("shutil.which", return_value="/usr/bin/curl"), \
                mock.patch("subprocess.run", return_value=curl_result):
            rates = download_rates(Path(folder) / "rates.json")
            self.assertEqual(rates["rates"]["INR"], 88.0)
            self.assertEqual(load_saved_rates(Path(folder) / "rates.json")["rates"]["INR"], 88.0)

    def test_offline_uses_nothing_and_says_so(self) -> None:
        original = calculator_engine.RATE_SOURCES
        calculator_engine.RATE_SOURCES = (("nowhere", "http://127.0.0.1:9/"),)
        try:
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(CalculationError):
                    download_rates(Path(folder) / "rates.json", timeout=1)
                self.assertIsNone(load_saved_rates(Path(folder) / "rates.json"))
        finally:
            calculator_engine.RATE_SOURCES = original


if __name__ == "__main__":
    unittest.main()
