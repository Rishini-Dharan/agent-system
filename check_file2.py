with open('tests/test_router.py', 'rb') as f:
    content = f.read()

# Check for BOM
print(f'Starts with BOM: {content.startswith(b"\xef\xbb\xbf")}')

# Check first 500 bytes
print(f'First 500 bytes:')
print(content[:500])