with open('tests/test_router.py', 'rb') as f:
    content = f.read()

# Check if filePath ends with newline
print(f'Ends with newline: {content.endswith(b"\n")}')

# Check last 100 bytes
print(f'Last 100 bytes: {content[-100:]}')