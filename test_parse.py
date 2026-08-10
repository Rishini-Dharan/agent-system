import ast

with open('tests/test_router.py', 'r') as f:
    source = f.read()

# Try removing the braces from the mock content
modified = source.replace('{"status": "success", "summary": "Done"}', '"status: success, summary: Done"')

try:
    ast.parse(modified)
    print('Modified parse successful!')
except SyntaxError as e:
    print(f'Still fails at line {e.lineno}: {e.msg}')