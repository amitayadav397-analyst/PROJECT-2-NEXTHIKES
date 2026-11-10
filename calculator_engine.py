"""The calculation logic of SmartCalc: maths, graphs, units, currency, BMI, age and history.

This file has no window code. main.py builds the window and asks this file
to do every calculation, so the maths can be tested on its own.
"""

import ast
import json
import math
import operator
import re
import shutil
import subprocess
import urllib.request
from datetime import date
from pathlib import Path
from typing import Callable


class CalculationError(ValueError):
    """Raised when an input is invalid or cannot be calculated."""


_BINARY_OPERATORS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# Larger whole numbers cannot be shown as a decimal, so treat them as too large.
_LARGEST_RESULT = 10**300

_UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# The screen shows friendly symbols; Python needs its own operators.
_SYMBOLS = {"×": "*", "÷": "/", "−": "-", "^": "**", "π": "pi", "√": "sqrt"}

FUNCTION_NAMES = ("sin", "cos", "tan", "asin", "acos", "atan", "sqrt", "log", "ln", "exp", "abs", "fact")


def _functions(degrees: bool) -> dict[str, Callable[[float], float]]:
    angle = math.radians if degrees else float
    inverse_angle = math.degrees if degrees else float
    return {
        "sin": lambda value: _round_tiny(math.sin(angle(value))),
        "cos": lambda value: _round_tiny(math.cos(angle(value))),
        "tan": lambda value: _tangent(angle(value)),
        "asin": lambda value: inverse_angle(math.asin(value)),
        "acos": lambda value: inverse_angle(math.acos(value)),
        "atan": lambda value: inverse_angle(math.atan(value)),
        "sqrt": math.sqrt,
        "log": math.log10,
        "ln": math.log,
        "exp": math.exp,
        "abs": abs,
        "fact": _factorial,
    }


def evaluate(expression: str, *, degrees: bool = True) -> float:
    """Calculate a typed expression such as '5 + 10 × 2' or 'sin(30)'."""
    return _run(_parse(expression), degrees, {})


def graph_points(
    expression: str, x_from: float, x_to: float, *, degrees: bool = True, steps: int = 400
) -> list[tuple[float, float | None]]:
    """Work out y for many x values between x_from and x_to, for drawing a graph.

    y is None where the function has no answer, such as sqrt(x) for negative x.
    """
    if not (math.isfinite(x_from) and math.isfinite(x_to)) or x_from >= x_to:
        raise CalculationError("'From x' must be smaller than 'To x'")
    tree = _parse(expression)
    # Check the formula once, so a typing mistake gives one clear error.
    _run(tree, degrees, {"x": (x_from + x_to) / 2}, check_names_only=True)
    points: list[tuple[float, float | None]] = []
    for step in range(steps + 1):
        x = x_from + (x_to - x_from) * step / steps
        try:
            points.append((x, float(_run(tree, degrees, {"x": x}))))
        except CalculationError:
            points.append((x, None))
    return points


def _parse(expression: str) -> ast.expr:
    expression = expression.strip()
    for symbol, python_operator in _SYMBOLS.items():
        expression = expression.replace(symbol, python_operator)
    # Let people write 2x, 3π or 2(4) the way they would on paper.
    # The letter e is left out so that 2e5 still means 2 × 10⁵.
    expression = re.sub(r"(\d)\s*(?=[a-df-zA-Z(])", r"\1*", expression)
    expression = re.sub(r"\)\s*(?=[\w(])", ")*", expression)
    if not expression:
        raise CalculationError("Enter a number first")
    if len(expression) > 200:
        raise CalculationError("Input is too long")
    try:
        return ast.parse(expression, mode="eval").body
    except SyntaxError as error:
        raise CalculationError(_friendly_error(error)) from error


def _run(tree: ast.expr, degrees: bool, names: dict[str, float], check_names_only: bool = False) -> float:
    names = {"pi": math.pi, "e": math.e, **names}
    try:
        result = _evaluate_node(tree, _functions(degrees), names)
    except CalculationError as error:
        if check_names_only and str(error) != "Invalid input":
            return 0.0  # A maths error at one x is fine; only typing mistakes matter here.
        raise
    except (ArithmeticError, TypeError, ValueError) as error:
        if check_names_only:
            return 0.0
        raise CalculationError(_friendly_error(error)) from error
    return _check_result(result)


def apply_function(name: str, value: float, *, degrees: bool = True) -> float:
    """Apply one function button (such as √ or sin) to the number on screen."""
    try:
        result = _functions(degrees)[name](value)
    except CalculationError:
        raise
    except (ArithmeticError, TypeError, ValueError) as error:
        raise CalculationError(_friendly_error(error)) from error
    return _check_result(result)


def format_number(value: float) -> str:
    """Show a result without long tails, so 0.1 + 0.2 shows 0.3."""
    if isinstance(value, int) and abs(value) < 10**15:
        return str(value)
    text = f"{value:.12g}"
    return text[:-2] if text.endswith(".0") else text


# How many of the base unit (metre, kilogram, litre, metre per second, second)
# one of each unit is. Temperature is handled separately because it has an offset.
UNITS: dict[str, dict[str, float]] = {
    "Length": {
        "Millimetre": 0.001,
        "Centimetre": 0.01,
        "Metre": 1,
        "Kilometre": 1000,
        "Inch": 0.0254,
        "Foot": 0.3048,
        "Yard": 0.9144,
        "Mile": 1609.344,
    },
    "Weight": {
        "Milligram": 0.000001,
        "Gram": 0.001,
        "Kilogram": 1,
        "Tonne": 1000,
        "Ounce": 0.028349523125,
        "Pound": 0.45359237,
    },
    "Volume": {
        "Millilitre": 0.001,
        "Litre": 1,
        "Cubic metre": 1000,
        "Cup (US)": 0.2365882365,
        "Gallon (US)": 3.785411784,
    },
    "Speed": {
        "Metre per second": 1,
        "Kilometre per hour": 1 / 3.6,
        "Mile per hour": 0.44704,
        "Knot": 1852 / 3600,
    },
    "Time": {
        "Second": 1,
        "Minute": 60,
        "Hour": 3600,
        "Day": 86400,
        "Week": 604800,
    },
    "Temperature": {"Celsius": 0, "Fahrenheit": 0, "Kelvin": 0},
}


def convert_units(value: float, category: str, from_unit: str, to_unit: str) -> float:
    """Convert a value, for example 5 Kilometre to Mile."""
    if not math.isfinite(value):
        raise CalculationError("Enter a number")
    if category == "Temperature":
        return _convert_temperature(value, from_unit, to_unit)
    if value < 0 and category != "Speed":
        raise CalculationError(f"{category} cannot be negative")
    factors = UNITS[category]
    # Change to the base unit first, then from the base unit to the target unit.
    return value * factors[from_unit] / factors[to_unit]


def _convert_temperature(value: float, from_unit: str, to_unit: str) -> float:
    if from_unit == "Fahrenheit":
        celsius = (value - 32) * 5 / 9
    elif from_unit == "Kelvin":
        celsius = value - 273.15
    else:
        celsius = value
    if celsius < -273.15 - 1e-9:
        raise CalculationError("Below absolute zero, which is impossible")
    if to_unit == "Fahrenheit":
        return celsius * 9 / 5 + 32
    if to_unit == "Kelvin":
        return celsius + 273.15
    return celsius


# Free exchange-rate services that need no sign-up. The first one that answers is used.
RATE_SOURCES = (
    ("European Central Bank (frankfurter.dev)", "https://api.frankfurter.dev/v1/latest?base=USD"),
    ("European Central Bank (frankfurter.app)", "https://api.frankfurter.app/latest?from=USD"),
    ("ExchangeRate-API", "https://open.er-api.com/v6/latest/USD"),
)
RATES_FILE = Path.home() / ".smartcalc_rates.json"
FIRST_CURRENCIES = ("INR", "USD", "EUR", "GBP", "AED", "SGD", "AUD", "CAD", "JPY")


def download_rates(path: Path = RATES_FILE, timeout: float = 6) -> dict:
    """Download today's rates (per 1 US dollar), save them for offline use and return them."""
    problems = []
    for source, url in RATE_SOURCES:
        try:
            rates = parse_rates(json.loads(_fetch(url, timeout)), source)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            problems.append(str(error))
            continue
        try:
            path.write_text(json.dumps(rates, indent=1), encoding="utf-8")
        except OSError:
            pass
        return rates
    if any("CERTIFICATE" in problem for problem in problems):
        raise CalculationError(
            "Secure connection failed. On a Mac, open Applications > Python 3.12 and run "
            "'Install Certificates.command' once"
        )
    raise CalculationError("Could not download rates. Check the internet connection")


def _fetch(url: str, timeout: float) -> str:
    """Download a web page as text."""
    request = urllib.request.Request(url, headers={"User-Agent": "SmartCalc"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except OSError as error:
        # Python from python.org on a Mac has no security certificates until
        # 'Install Certificates.command' is run. The Mac's own curl tool uses the
        # system certificates, so try it before giving up.
        curl = shutil.which("curl")
        if "CERTIFICATE" not in str(error) or curl is None:
            raise
        result = subprocess.run(
            [curl, "--silent", "--fail", "--location", "--max-time", str(timeout), url],
            capture_output=True,
            timeout=timeout + 2,
        )
        if result.returncode != 0:
            raise
        return result.stdout.decode("utf-8")


def parse_rates(data: dict, source: str) -> dict:
    """Turn a rate service's reply into {'source', 'date', 'rates'}, with rates per 1 USD."""
    if not isinstance(data, dict) or not isinstance(data.get("rates"), dict):
        raise ValueError("Unexpected reply from the rate service")
    date_text = data.get("date") or data.get("time_last_update_utc", "")[:16]
    rates = {
        code: float(value)
        for code, value in data["rates"].items()
        if isinstance(code, str) and isinstance(value, (int, float)) and value > 0
    }
    rates["USD"] = 1.0
    return {"source": source, "date": str(date_text), "rates": rates}


def load_saved_rates(path: Path = RATES_FILE) -> dict | None:
    """Rates saved by the last successful download, or None."""
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        return parse_rates(saved, saved.get("source", "saved rates"))
    except (OSError, ValueError, AttributeError):
        return None


def currency_codes(rates: dict) -> list[str]:
    """Common currencies first, then the rest in A to Z order."""
    available = rates["rates"]
    first = [code for code in FIRST_CURRENCIES if code in available]
    return first + sorted(code for code in available if code not in first)


def convert_currency(value: float, from_code: str, to_code: str, rates: dict) -> float:
    """Convert money using rates per 1 US dollar: go to dollars first, then to the target."""
    if not math.isfinite(value) or value < 0:
        raise CalculationError("Enter an amount of 0 or more")
    table = rates["rates"]
    if from_code not in table or to_code not in table:
        raise CalculationError("No rate for this currency")
    return value / table[from_code] * table[to_code]


# History is saved in the user's home folder so it is kept after the app closes.
HISTORY_FILE = Path.home() / ".smartcalc_history.json"
HISTORY_LIMIT = 100


def load_history(path: Path = HISTORY_FILE) -> list[str]:
    """Read saved calculations, newest first. A missing or broken file gives an empty list."""
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, str)][:HISTORY_LIMIT]


def save_history(items: list[str], path: Path = HISTORY_FILE) -> None:
    """Save calculations, newest first, keeping only the latest 100."""
    try:
        path.write_text(json.dumps(items[:HISTORY_LIMIT], ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        # Saving is a convenience: the calculator keeps working if the disk is not writable.
        pass


def calculate_bmi(weight_kg: float, height_cm: float) -> tuple[float, str]:
    """Return the body mass index and its WHO category."""
    if not 1 <= weight_kg <= 500:
        raise CalculationError("Weight must be between 1 and 500 kg")
    if not 30 <= height_cm <= 300:
        raise CalculationError("Height must be between 30 and 300 cm")
    bmi = weight_kg / (height_cm / 100) ** 2
    if bmi < 18.5:
        category = "Underweight"
    elif bmi < 25:
        category = "Normal weight"
    elif bmi < 30:
        category = "Overweight"
    else:
        category = "Obese"
    return round(bmi, 1), category


def calculate_age(birth: date, today: date) -> tuple[int, int, int, int]:
    """Return age as (years, months, days) and days until the next birthday."""
    if birth > today:
        raise CalculationError("Date of birth cannot be in the future")
    years = today.year - birth.year
    months = today.month - birth.month
    days = today.day - birth.day
    if days < 0:
        months -= 1
        previous_month_end = date(today.year, today.month, 1).toordinal() - 1
        days += date.fromordinal(previous_month_end).day
    if months < 0:
        years -= 1
        months += 12

    next_birthday = _birthday_in(birth, today.year)
    if next_birthday < today:
        next_birthday = _birthday_in(birth, today.year + 1)
    return years, months, days, (next_birthday - today).days


def _birthday_in(birth: date, year: int) -> date:
    # People born on 29 February celebrate on 28 February in other years.
    try:
        return birth.replace(year=year)
    except ValueError:
        return date(year, 2, 28)


def _evaluate_node(
    node: ast.expr, functions: dict[str, Callable[[float], float]], names: dict[str, float]
) -> float:
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value

    if isinstance(node, ast.Name) and node.id in names:
        return names[node.id]

    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _evaluate_node(node.left, functions, names)
        right = _evaluate_node(node.right, functions, names)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise CalculationError("Use a power between -1000 and 1000")
        if isinstance(node.op, ast.Pow) and abs(left) > _LARGEST_RESULT:
            raise CalculationError("The answer is too large")
        return _BINARY_OPERATORS[type(node.op)](left, right)

    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _UNARY_OPERATORS[type(node.op)](_evaluate_node(node.operand, functions, names))

    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in functions
        and len(node.args) == 1
        and not node.keywords
    ):
        return functions[node.func.id](_evaluate_node(node.args[0], functions, names))

    # Letters such as a + b, or anything else a calculator cannot work out.
    raise CalculationError("Invalid input")


def _check_result(result: float) -> float:
    if type(result) not in (int, float):
        raise CalculationError("Invalid input")
    if isinstance(result, int) and abs(result) > _LARGEST_RESULT:
        raise CalculationError("The answer is too large")
    if not math.isfinite(result):
        raise CalculationError("The answer is not a real number")
    return result


def _round_tiny(value: float) -> float:
    # sin(180) gives 1.2e-16 because of rounding; show it as 0.
    return 0.0 if abs(value) < 1e-12 else value


def _tangent(radians: float) -> float:
    if abs(math.cos(radians)) < 1e-12:
        raise CalculationError("tan is undefined for this angle")
    return _round_tiny(math.tan(radians))


def _factorial(value: float) -> int:
    if not float(value).is_integer() or value < 0 or value > 170:
        raise CalculationError("x! needs a whole number from 0 to 170")
    return math.factorial(int(value))


def _friendly_error(error: Exception) -> str:
    if isinstance(error, ZeroDivisionError):
        return "Cannot divide by zero"
    if isinstance(error, OverflowError):
        return "The answer is too large"
    if isinstance(error, SyntaxError):
        return "Invalid input"
    return "Math error: check the input"
