with open('debug_final3.py', 'rb') as f:
    content = f.read()

# Check for any non-ASCII or control characters
for i, b in enumerate(content):
    if b > 127 or (b < 32 and b not in (9, 10, 13)):
        print(f'Byte {i}: {b} ({chr(b) if b < 128 else "?"})')

print('File size:', len(content))