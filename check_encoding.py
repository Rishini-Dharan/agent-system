with open('tests/test_router.py', 'rb') as f:
    content = f.read()

print(f'File size: {len(content)} bytes')
print(f'Starts with BOM: {content.startswith(b"\xef\xbb\xbf")}')

# Check for any non-ASCII characters
for i, byte in enumerate(content):
    if byte > 127:
        print(f'Non-ASCII at byte {i}: {byte}')