"""Unit conversion and display utilities for PHMS.

Supports both metric (SI) and imperial unit systems with bidirectional conversion.
Provides formatting for profile display and data storage.

Units:
    - Height: centimeters (metric) ↔ inches (imperial)
    - Weight: kilograms (metric) ↔ pounds (imperial)
    - BMI: kg/m² (metric) ↔ lb/in² (imperial)

Usage:
    >>> from PHMS.utils.units import convert_height, format_height
    >>> convert_height(170, 'metric', 'imperial')  # cm to inches
    66.93
    >>> format_height(170, 'metric', 'en')  # "170 cm"
    '170 cm'
"""

from typing import Optional, Tuple
from utils.i18n import get_translations


class UnitSystem:
    """Unit system constants."""
    METRIC = 'metric'
    IMPERIAL = 'imperial'
    
    @staticmethod
    def all_systems():
        return [UnitSystem.METRIC, UnitSystem.IMPERIAL]


# Conversion factors
CM_TO_INCHES = 0.393701
INCHES_TO_CM = 1 / CM_TO_INCHES
KG_TO_LBS = 2.20462
LBS_TO_KG = 1 / KG_TO_LBS
KG_M2_TO_LB_IN2 = 0.703  # BMI conversion factor


def convert_height(value: float, from_system: str, to_system: str) -> float:
    """Convert height between metric and imperial systems.
    
    Args:
        value: Height value to convert
        from_system: Source system ('metric' for cm, 'imperial' for inches)
        to_system: Target system ('metric' for cm, 'imperial' for inches)
    
    Returns:
        Converted height value, rounded to 2 decimal places
    
    Example:
        >>> convert_height(170, 'metric', 'imperial')  # cm → inches
        66.93
        >>> convert_height(66.93, 'imperial', 'metric')  # inches → cm
        170.0
    """
    if from_system == to_system:
        return round(value, 2)
    
    if from_system == 'metric' and to_system == 'imperial':
        return round(value * CM_TO_INCHES, 2)
    elif from_system == 'imperial' and to_system == 'metric':
        return round(value * INCHES_TO_CM, 2)
    
    return round(value, 2)


def convert_weight(value: float, from_system: str, to_system: str) -> float:
    """Convert weight between metric and imperial systems.
    
    Args:
        value: Weight value to convert
        from_system: Source system ('metric' for kg, 'imperial' for lbs)
        to_system: Target system ('metric' for kg, 'imperial' for lbs)
    
    Returns:
        Converted weight value, rounded to 2 decimal places
    
    Example:
        >>> convert_weight(70, 'metric', 'imperial')  # kg → lbs
        154.32
        >>> convert_weight(154.32, 'imperial', 'metric')  # lbs → kg
        70.0
    """
    if from_system == to_system:
        return round(value, 2)
    
    if from_system == 'metric' and to_system == 'imperial':
        return round(value * KG_TO_LBS, 2)
    elif from_system == 'imperial' and to_system == 'metric':
        return round(value * LBS_TO_KG, 2)
    
    return round(value, 2)


def convert_bmi(value: float, from_system: str, to_system: str) -> float:
    """Convert BMI between metric and imperial systems.
    
    Args:
        value: BMI value to convert
        from_system: Source system ('metric' for kg/m², 'imperial' for lb/in²)
        to_system: Target system ('metric' for kg/m², 'imperial' for lb/in²)
    
    Returns:
        Converted BMI value, rounded to 2 decimal places
    
    Example:
        >>> convert_bmi(24.2, 'metric', 'imperial')  # kg/m² → lb/in²
        1.67
    """
    if from_system == to_system:
        return round(value, 2)
    
    if from_system == 'metric' and to_system == 'imperial':
        return round(value * KG_M2_TO_LB_IN2, 2)
    elif from_system == 'imperial' and to_system == 'metric':
        return round(value / KG_M2_TO_LB_IN2, 2)
    
    return round(value, 2)


def get_height_display_unit(system: str) -> str:
    """Get height unit symbol for display.
    
    Args:
        system: Unit system ('metric' or 'imperial')
    
    Returns:
        Unit symbol ("cm" or "in")
    """
    return 'in' if system == 'imperial' else 'cm'


def get_weight_display_unit(system: str) -> str:
    """Get weight unit symbol for display.
    
    Args:
        system: Unit system ('metric' or 'imperial')
    
    Returns:
        Unit symbol ("kg" or "lbs")
    """
    return 'lbs' if system == 'imperial' else 'kg'


def get_bmi_display_unit(system: str) -> str:
    """Get BMI unit symbol for display.
    
    Args:
        system: Unit system ('metric' or 'imperial')
    
    Returns:
        Unit symbol ("kg/m²" or "lb/in²")
    """
    return 'lb/in²' if system == 'imperial' else 'kg/m²'


def format_height(value: Optional[float], system: str, language: str = 'en') -> str:
    """Format height for display with appropriate unit.
    
    Args:
        value: Height value in centimeters (metric)
        system: Target unit system ('metric' or 'imperial')
        language: Language code for translations
    
    Returns:
        Formatted height string, e.g., "170 cm" or "66.93 in"
    
    Example:
        >>> format_height(170, 'metric', 'en')
        '170 cm'
        >>> format_height(170, 'imperial', 'en')
        '66.93 in'
    """
    if value is None:
        return 'N/A'
    
    converted = convert_height(value, 'metric', system)
    unit = get_height_display_unit(system)
    return f"{converted} {unit}"


def format_weight(value: Optional[float], system: str, language: str = 'en') -> str:
    """Format weight for display with appropriate unit.
    
    Args:
        value: Weight value in kilograms (metric)
        system: Target unit system ('metric' or 'imperial')
        language: Language code for translations
    
    Returns:
        Formatted weight string, e.g., "70 kg" or "154.32 lbs"
    
    Example:
        >>> format_weight(70, 'metric', 'en')
        '70 kg'
        >>> format_weight(70, 'imperial', 'en')
        '154.32 lbs'
    """
    if value is None:
        return 'N/A'
    
    converted = convert_weight(value, 'metric', system)
    unit = get_weight_display_unit(system)
    return f"{converted} {unit}"


def format_bmi(value: Optional[float], system: str, language: str = 'en') -> str:
    """Format BMI for display with appropriate unit.
    
    Args:
        value: BMI value in kg/m² (metric)
        system: Target unit system ('metric' or 'imperial')
        language: Language code for translations
    
    Returns:
        Formatted BMI string, e.g., "24.2 kg/m²" or "1.67 lb/in²"
    
    Example:
        >>> format_bmi(24.2, 'metric', 'en')
        '24.2 kg/m²'
        >>> format_bmi(24.2, 'imperial', 'en')
        '1.67 lb/in²'
    """
    if value is None:
        return 'N/A'
    
    converted = convert_bmi(value, 'metric', system)
    unit = get_bmi_display_unit(system)
    return f"{converted} {unit}"


def get_all_metrics_formatted(
    height: Optional[float],
    weight: Optional[float],
    bmi: Optional[float],
    system: str,
    language: str = 'en'
) -> dict:
    """Get all metrics formatted for display.
    
    Args:
        height: Height in cm
        weight: Weight in kg
        bmi: BMI in kg/m²
        system: Unit system ('metric' or 'imperial')
        language: Language code
    
    Returns:
        Dictionary with formatted metrics and raw converted values
    
    Example:
        >>> get_all_metrics_formatted(170, 70, 24.2, 'metric', 'en')
        {
            'height_display': '170 cm',
            'height_value': 170,
            'weight_display': '70 kg',
            'weight_value': 70,
            'bmi_display': '24.2 kg/m²',
            'bmi_value': 24.2,
            'system': 'metric'
        }
    """
    return {
        'height_display': format_height(height, system, language),
        'height_value': convert_height(height, 'metric', system) if height else None,
        'height_unit': get_height_display_unit(system),
        'weight_display': format_weight(weight, system, language),
        'weight_value': convert_weight(weight, 'metric', system) if weight else None,
        'weight_unit': get_weight_display_unit(system),
        'bmi_display': format_bmi(bmi, system, language),
        'bmi_value': convert_bmi(bmi, 'metric', system) if bmi else None,
        'bmi_unit': get_bmi_display_unit(system),
        'system': system
    }
