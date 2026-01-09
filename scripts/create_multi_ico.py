"""
Create a multi-resolution ICO file from individual ICO files.
For Windows desktop shortcuts to display correctly, the ICO file must contain multiple sizes.
"""
from PIL import Image
import os

# Input files (individual ICOs)
downloads = r"C:\Users\HI\Downloads"
ico_files = [
    (os.path.join(downloads, "favicon16.ico"), 16),
    (os.path.join(downloads, "favicon32.ico"), 32),
    (os.path.join(downloads, "favicon48.ico"), 48),
    (os.path.join(downloads, "favicon64.ico"), 64),
    (os.path.join(downloads, "favico-128.ico"), 128),
    (os.path.join(downloads, "favicon256.ico"), 256),
]

# Output path
output_ico = r"E:\workspace\code\DouDouChat\electron\icons\icon.ico"
output_ico_build = r"E:\workspace\code\DouDouChat\build\icon.ico"

# Load images and resize if needed
images = []
sizes = []

for ico_path, expected_size in ico_files:
    if os.path.exists(ico_path):
        img = Image.open(ico_path)
        # Convert to RGBA if not already
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        # Resize if size doesn't match (some ICO files may have different sizes)
        if img.size[0] != expected_size:
            img = img.resize((expected_size, expected_size), Image.Resampling.LANCZOS)
        images.append(img)
        sizes.append((expected_size, expected_size))
        print(f"Loaded: {ico_path} -> {expected_size}x{expected_size}")
    else:
        print(f"Not found: {ico_path}")

if not images:
    print("No images found!")
    exit(1)

# Use the largest image as base and save all sizes
base_image = images[-1]  # 256x256

# Create multi-resolution ICO
# PIL's save with sizes parameter creates multi-resolution ICO
base_image.save(
    output_ico,
    format='ICO',
    sizes=sizes
)
print(f"\nCreated multi-resolution ICO: {output_ico}")

# Also copy to build directory
base_image.save(
    output_ico_build,
    format='ICO',
    sizes=sizes
)
print(f"Copied to: {output_ico_build}")

# Verify the new ICO
new_ico = Image.open(output_ico)
print(f"\nVerification - ICO contains sizes: {new_ico.info.get('sizes', 'unknown')}")
