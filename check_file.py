import sys

with open('tests/test_router.py', 'rb') as f:
    content = f.read()

# Check for BOM
if content.startswith(b'\xef\xbb\xbf'):
    print('Has BOM')
else:
    print('No BOM')

# Check line endings
if b'\r\n' in content:
    print('Line endings: CRLF')
else:
    print('Line endings: LF')

# Check for null bytes
if b'\x00' in content:
    print('Has null bytes')

# Check the exact bytes around line 160
lines = content.split(b'\n')
for i, line in enumerate(lines[155:180], 156):
    print(f'{i}: {line}')