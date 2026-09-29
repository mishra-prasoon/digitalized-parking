import re
import sys

import cv2
import pytesseract

PLATE_REGEX = re.compile(r'^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$')

# position pattern: L=letter expected, D=digit expected, for the two common lengths
PATTERNS = {
    10: 'LLDDLLDDDD',  # e.g. UP65AB1234 -> wait, that's LLDDLLDDDD? check below
}


def fix_ambiguous_chars(text):
    """Correct O<->0 and I<->1 based on expected letter/digit position for
    the two valid Indian plate lengths: LLDDLDDDD (9 chars) or LLDDLLDDDD (10 chars)."""
    length_to_pattern = {
        9: 'LLDDLDDDD',
        10: 'LLDDLLDDDD',
    }
    pattern = length_to_pattern.get(len(text))
    if not pattern:
        return text

    fixed = []
    for ch, kind in zip(text, pattern):
        if kind == 'D' and ch in ('O', 'Q'):
            fixed.append('0')
        elif kind == 'D' and ch == 'I':
            fixed.append('1')
        elif kind == 'L' and ch == '0':
            fixed.append('O')
        elif kind == 'L' and ch == '1':
            fixed.append('I')
        else:
            fixed.append(ch)
    return ''.join(fixed)


def text_confidence(data):
    """Average confidence only over boxes that actually contain non-whitespace text."""
    confs = [
        int(c) for c, t in zip(data['conf'], data['text'])
        if c != '-1' and t.strip()
    ]
    return sum(confs) / len(confs) if confs else 0


def process(image_path):
    print(f"\n--- {image_path} ---")
    img = cv2.imread(image_path)
    if img is None:
        print("FAILED: could not read image")
        return

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    filtered = cv2.bilateralFilter(gray, 11, 17, 17)
    _, thresh = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    config = '--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    raw_text = pytesseract.image_to_string(thresh, config=config)
    cleaned = raw_text.strip().upper().replace(' ', '')
    corrected = fix_ambiguous_chars(cleaned)

    data = pytesseract.image_to_data(thresh, config=config, output_type=pytesseract.Output.DICT)
    conf = text_confidence(data)

    print(f"Raw: {raw_text!r}  Cleaned: {cleaned!r}  Corrected: {corrected!r}")
    print(f"Text-only confidence: {conf:.1f}")

    if PLATE_REGEX.match(corrected):
        print(f"VALID PLATE: {corrected}")
    else:
        print(f"Still invalid: {corrected!r}")


if __name__ == '__main__':
    for path in sys.argv[1:]:
        process(path)
