from typing import Union


def safe_divide(numerator: Union[int, float], denominator: Union[int, float], default: float = 0.0) -> float:
    """Safely divides two numbers, handling zero denominators and NaNs."""
    if denominator is None or numerator is None:
        return default
    try:
        num = float(numerator)
        den = float(denominator)
        if den == 0.0 or num != num or den != den:  # NaN check
            return default
        return num / den
    except (ValueError, TypeError, ZeroDivisionError):
        return default


def calculate_pct_change(start_val: float, end_val: float, default: float = 0.0) -> float:
    """Calculates percentage change between start and end values safely."""
    if start_val == 0.0 or start_val is None or end_val is None:
        return default
    return round(((end_val - start_val) / abs(start_val)) * 100.0, 4)


def calculate_pp_change(start_rate: float, end_rate: float) -> float:
    """Calculates percentage point difference between two decimal rates (e.g. 0.20 -> 0.25 = +5.0 pp)."""
    if start_rate is None or end_rate is None:
        return 0.0
    return round((end_rate - start_rate) * 100.0, 4)
