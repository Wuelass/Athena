import re
from typing import Optional

from PIL import Image
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def image_to_text(image: Image.Image) -> str:
    """
    OCR brut d'une image
    """
    text = pytesseract.image_to_string(image, lang="eng")
    return text.strip()


def clean_text(text: str) -> str:
    """
    Nettoyage simple du texte OCR
    """
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_playtime(text: str) -> Optional[str]:
    """
    Extrait une chaîne de type :
    - 12 min
    - 3 h 18 min
    - 1 j 4 h
    - 2 j 0 h 5 min
    """
    text = text.lower()

    pattern = r"(\d+\s*j)?\s*(\d+\s*h)?\s*(\d+\s*min)?"
    match = re.search(pattern, text)

    if not match:
        return None

    parts = [p for p in match.groups() if p]
    if not parts:
        return None

    return " ".join(parts)


def playtime_to_hours(playtime_str: str) -> float:
    """
    Convertit "1 j 2 h 30 min" -> heures
    """
    if not playtime_str:
        return 0.0

    days = hours = minutes = 0

    d = re.search(r"(\d+)\s*j", playtime_str)
    h = re.search(r"(\d+)\s*h", playtime_str)
    m = re.search(r"(\d+)\s*min", playtime_str)

    if d:
        days = int(d.group(1))
    if h:
        hours = int(h.group(1))
    if m:
        minutes = int(m.group(1))

    total_hours = days * 24 + hours + minutes / 60
    return round(total_hours, 2)