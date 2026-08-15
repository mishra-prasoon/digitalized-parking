import cv2
import pytesseract
import numpy as np
import re
import requests
import os

# Tesseract path for Mac (Homebrew)
pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'

# Django API endpoint
API_BASE_URL = 'http://127.0.0.1:8000/api'


def preprocess_image(image):
    """Apply image processing pipeline to enhance plate detection."""
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply bilateral filter to reduce noise while keeping edges sharp
    filtered = cv2.bilateralFilter(gray, 11, 17, 17)

    # Apply Canny edge detection
    edges = cv2.Canny(filtered, 30, 200)

    return gray, filtered, edges


def find_plate_region(image, edges):
    """Find the rectangular number plate region using contour detection."""
    contours, _ = cv2.findContours(edges.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    # Sort contours by area, keep top 30
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:30]

    plate_contour = None
    for contour in contours:
        # Approximate the contour to a polygon
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)

        # Number plate is roughly rectangular (4 corners)
        if len(approx) == 4:
            plate_contour = approx
            break

    return plate_contour


def extract_plate_text(gray_image, plate_contour):
    """Extract and warp the plate region, then apply OCR."""
    if plate_contour is None:
        return None

    # Create mask and extract plate region
    mask = np.zeros(gray_image.shape, np.uint8)
    cv2.drawContours(mask, [plate_contour], 0, 255, -1)
    plate_region = cv2.bitwise_and(gray_image, gray_image, mask=mask)

    # Get bounding rectangle
    x, y, w, h = cv2.boundingRect(plate_contour)
    cropped_plate = gray_image[y:y+h, x:x+w]

    # Apply thresholding to enhance text
    _, thresh = cv2.threshold(cropped_plate, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Apply morphological operations to clean up
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    # OCR with Tesseract
    config = '--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    raw_text = pytesseract.image_to_string(cleaned, config=config)

    return raw_text


def clean_plate_text(raw_text):
    """Clean and validate the extracted plate text."""
    if not raw_text:
        return None

    # Remove spaces, newlines, special chars
    cleaned = re.sub(r'[^A-Z0-9]', '', raw_text.upper().strip())

    # Validate Indian number plate format
    # Format: XX00XX0000 or XX00X0000
    # Examples: UP32AB1234, DL01C1234, MH12AB3456
    pattern = r'^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{1,4}$'

    if re.match(pattern, cleaned) and len(cleaned) >= 6:
        return cleaned

    # If no match but text is reasonable length, return anyway
    if len(cleaned) >= 6:
        return cleaned

    return None


def send_to_api(plate_number, gate_type='entry'):
    """Send plate number to Django backend API."""
    endpoint = f'{API_BASE_URL}/{gate_type}/'
    try:
        response = requests.post(
            endpoint,
            json={'plate_number': plate_number},
            timeout=10
        )
        return response.json()
    except requests.exceptions.RequestException as e:
        return {'error': str(e)}


def process_image_file(image_path, gate_type='entry'):
    """
    Process a single image file for ANPR.
    gate_type: 'entry' or 'exit'
    """
    print(f"\n{'='*50}")
    print(f"Processing image: {image_path}")
    print(f"Gate type: {gate_type.upper()}")
    print('='*50)

    # Load image
    image = cv2.imread(image_path)
    if image is None:
        print(f"ERROR: Could not load image from {image_path}")
        return None

    # Preprocess
    gray, filtered, edges = preprocess_image(image)
    print("✓ Image preprocessed")

    # Find plate region
    plate_contour = find_plate_region(image, edges)

    if plate_contour is not None:
        print("✓ Plate region detected")
        # Extract text from detected region
        raw_text = extract_plate_text(gray, plate_contour)
    else:
        print("⚠ Plate region not detected, trying full image OCR")
        # Fallback: OCR on full image
        config = '--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        raw_text = pytesseract.image_to_string(gray, config=config)

    print(f"Raw OCR text: {repr(raw_text)}")

    # Clean and validate
    plate_number = clean_plate_text(raw_text)

    if plate_number:
        print(f"✓ Plate number extracted: {plate_number}")

        # Send to API
        print(f"Sending to {gate_type} API...")
        result = send_to_api(plate_number, gate_type)
        print(f"API Response: {result}")
        return result
    else:
        print("✗ Could not extract valid plate number")
        return {'error': 'Could not read plate number'}


def process_camera_feed(gate_type='entry'):
    """
    Process live camera feed for ANPR.
    Press 'c' to capture and process frame.
    Press 'q' to quit.
    """
    print(f"\nStarting camera feed for {gate_type.upper()} gate...")
    print("Press 'c' to capture plate | Press 'q' to quit")

    cap = cv2.VideoCapture(0)  # 0 = default camera

    if not cap.isOpened():
        print("ERROR: Could not open camera")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Show frame with instructions
        display = frame.copy()
        cv2.putText(display, f"GATE: {gate_type.upper()}",
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(display, "Press 'C' to capture | 'Q' to quit",
                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

        cv2.imshow(f'ANPR - {gate_type.upper()} Gate', display)

        key = cv2.waitKey(1) & 0xFF

        if key == ord('c'):
            print("\nCapturing frame...")
            gray, filtered, edges = preprocess_image(frame)
            plate_contour = find_plate_region(frame, edges)

            if plate_contour is not None:
                raw_text = extract_plate_text(gray, plate_contour)
            else:
                config = '--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                raw_text = pytesseract.image_to_string(gray, config=config)

            plate_number = clean_plate_text(raw_text)

            if plate_number:
                print(f"Plate detected: {plate_number}")
                result = send_to_api(plate_number, gate_type)
                print(f"API Response: {result}")

                # Show result on screen
                cv2.putText(display, f"PLATE: {plate_number}",
                           (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                cv2.imshow(f'ANPR - {gate_type.upper()} Gate', display)
                cv2.waitKey(2000)
            else:
                print("Could not read plate. Please try again.")

        elif key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        # Image file mode
        image_path = sys.argv[1]
        gate = sys.argv[2] if len(sys.argv) > 2 else 'entry'
        process_image_file(image_path, gate)
    else:
        # Camera mode
        gate = input("Enter gate type (entry/exit): ").strip().lower()
        process_camera_feed(gate)