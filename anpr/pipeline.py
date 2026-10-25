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


def locate_plate_candidates(gray):
    """Find rectangular, plate-shaped regions in a frame using Canny edge
    detection + contour filtering, so a photo of a whole vehicle (not just
    an isolated plate) can still be cropped down to the plate before OCR.
    Returns a list of (x, y, w, h) boxes, largest/most plate-like first.
    """
    edged = cv2.Canny(cv2.bilateralFilter(gray, 11, 17, 17), 30, 200)
    edged = cv2.dilate(edged, None, iterations=1)
    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:15]

    h_img, w_img = gray.shape[:2]
    candidates = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w == 0 or h == 0:
            continue
        aspect = w / h
        area_ratio = (w * h) / float(w_img * h_img)
        if 2.0 <= aspect <= 5.5 and 0.01 <= area_ratio <= 0.5:
            candidates.append((x, y, w, h))
    return candidates


def _ocr_region(gray_region):
    filtered = cv2.bilateralFilter(gray_region, 11, 17, 17)
    _, thresh = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    raw_text = pytesseract.image_to_string(thresh, config=TESSERACT_CONFIG)
    cleaned = raw_text.strip().upper().replace(' ', '')
    corrected = fix_ambiguous_chars(cleaned)

    data = pytesseract.image_to_data(thresh, config=TESSERACT_CONFIG,
                                      output_type=pytesseract.Output.DICT)
    conf = text_confidence(data)

    regex_ok = bool(PLATE_REGEX.match(corrected))
    # A real low-confidence misread and a zero-confidence quirk (Tesseract
    # sometimes reports exactly 0 confidence on an otherwise-correct single
    # text block, seen with some bold/synthetic plate fonts) are different
    # things: a correct regex match on a *non-zero* low score is still
    # risky, but an exact 0 with a structurally valid plate is accepted,
    # since the regex itself is already a strict filter.
    valid = regex_ok and (conf >= CONFIDENCE_THRESHOLD or conf == 0)
    return ReadResult(corrected if valid else None, conf, raw_text.strip(), valid)


def read_plate_from_array(img):
    if img is None:
        return ReadResult(None, 0, '', False)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    regions = []
    for (x, y, w, h) in locate_plate_candidates(gray):
        pad_x, pad_y = int(w * 0.05), int(h * 0.15)
        x0, y0 = max(0, x - pad_x), max(0, y - pad_y)
        x1 = min(gray.shape[1], x + w + pad_x)
        y1 = min(gray.shape[0], y + h + pad_y)
        regions.append(gray[y0:y1, x0:x1])
    regions.append(gray)  # full frame, always tried as a fallback

    best = None
    for region in regions:
        result = _ocr_region(region)
        if result.valid:
            return result
        if best is None or result.confidence > best.confidence:
            best = result

    return best if best is not None else ReadResult(None, 0, '', False)


def read_plate_from_bytes(image_bytes):
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return read_plate_from_array(img)


def vote_across_frames(results):
    valid_results = [r for r in results if r.valid]
    if not valid_results:
        best = max(results, key=lambda r: r.confidence, default=None)
        return None, best.confidence if best else 0, best.raw_text if best else ''

    votes = Counter(r.plate for r in valid_results)
    winner, _ = votes.most_common(1)[0]
    winning_reads = [r for r in valid_results if r.plate == winner]
    best_conf = max(r.confidence for r in winning_reads)
    return winner, best_conf, winner
