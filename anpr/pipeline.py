import re
from collections import Counter

import cv2
import numpy as np
import pytesseract

PLATE_REGEX = re.compile(r'^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$')
CONFIDENCE_THRESHOLD = 60

LENGTH_TO_PATTERN = {
    9: 'LLDDLDDDD',
    10: 'LLDDLLDDDD',
}

TESSERACT_CONFIG = '--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'


def fix_ambiguous_chars(text):
    pattern = LENGTH_TO_PATTERN.get(len(text))
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
    confs = [
        int(c) for c, t in zip(data['conf'], data['text'])
        if c != '-1' and t.strip()
    ]
    return sum(confs) / len(confs) if confs else 0


class ReadResult:
    def __init__(self, plate, confidence, raw_text, valid):
        self.plate = plate
        self.confidence = confidence
        self.raw_text = raw_text
        self.valid = valid


def read_plate_from_array(img):
    """Runs the pipeline on a single OpenCV image (numpy array). Returns a ReadResult."""
    if img is None:
        return ReadResult(None, 0, '', False)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    filtered = cv2.bilateralFilter(gray, 11, 17, 17)
    _, thresh = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    raw_text = pytesseract.image_to_string(thresh, config=TESSERACT_CONFIG)
    cleaned = raw_text.strip().upper().replace(' ', '')
    corrected = fix_ambiguous_chars(cleaned)

    data = pytesseract.image_to_data(thresh, config=TESSERACT_CONFIG, output_type=pytesseract.Output.DICT)
    conf = text_confidence(data)

    valid = bool(PLATE_REGEX.match(corrected)) and conf >= CONFIDENCE_THRESHOLD
    return ReadResult(corrected if valid else None, conf, raw_text.strip(), valid)


def read_plate_from_bytes(image_bytes):
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return read_plate_from_array(img)


def vote_across_frames(results):
    """Given a list of ReadResult, pick the plate with the most agreeing valid votes.
    Returns (plate_or_none, best_confidence, best_raw_text)."""
    valid_results = [r for r in results if r.valid]
    if not valid_results:
        # no valid read at all; report the highest-confidence raw attempt for the log
        best = max(results, key=lambda r: r.confidence, default=None)
        return None, best.confidence if best else 0, best.raw_text if best else ''

    votes = Counter(r.plate for r in valid_results)
    winner, _ = votes.most_common(1)[0]
    winning_reads = [r for r in valid_results if r.plate == winner]
    best_conf = max(r.confidence for r in winning_reads)
    return winner, best_conf, winner
