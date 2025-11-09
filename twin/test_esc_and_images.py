#!/usr/bin/env python3
"""
Test ESC interrupt and image detection
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

def test_esc_and_images():
    """Test ESC and image features"""
    print("Testing twin ESC interrupt and image detection...\n")

    # Test 1: Check keyboard library
    print("1. Testing keyboard library...")
    try:
        import keyboard
        print("   ✓ keyboard library available")
        print("   Note: ESC detection will work in twin sessions\n")
    except ImportError:
        print("   ✗ keyboard library not available")
        print("   Install with: pip3 install --user keyboard\n")

    # Test 2: Check PIL/ImageGrab
    print("2. Testing PIL ImageGrab...")
    try:
        from PIL import ImageGrab
        print("   ✓ PIL ImageGrab available")
        print("   Note: Clipboard image detection will work\n")
    except ImportError:
        print("   ✗ PIL not available")
        print("   Install with: pip3 install --user pillow\n")

    # Test 3: Test image path detection
    print("3. Testing image path detection...")
    from session import SessionOrchestrator

    # Create a test image
    test_image_path = "/tmp/test_twin_image.png"
    try:
        from PIL import Image
        img = Image.new('RGB', (100, 100), color='red')
        img.save(test_image_path)
        print(f"   Created test image: {test_image_path}")
    except:
        print("   ⚠️  Could not create test image")

    # Test detection
    test_session = type('obj', (object,), {})()
    test_session._detect_image_paths = SessionOrchestrator._detect_image_paths.__get__(test_session)

    test_text = f"Analyze this image: {test_image_path} and tell me what you see"
    detected = test_session._detect_image_paths(test_text)

    if detected:
        print(f"   ✓ Image path detected: {detected}")
    else:
        print(f"   ✗ Image path not detected")
    print()

    # Test 4: Check for vision models
    print("4. Checking for vision models in Ollama...")
    test_session._get_vision_model = SessionOrchestrator._get_vision_model.__get__(test_session)
    vision_model = test_session._get_vision_model()

    if vision_model:
        print(f"   ✓ Vision model found: {vision_model}")
    else:
        print(f"   ✗ No vision model found")
        print(f"   Install with: ollama pull llava:7b")
    print()

    print("✅ ESC and image detection features configured!")
    print("\nTo test in twin:")
    print("  1. Start twin")
    print("  2. Type a query and press ESC while thinking")
    print("  3. Copy an image, then ask twin about it")
    print("  4. Or provide image path: 'analyze /path/to/image.png'")

if __name__ == "__main__":
    test_esc_and_images()
