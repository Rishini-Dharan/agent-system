with open('tests/test_router.py', 'r') as f:
    lines = f.readlines()

open_braces = 0
in_string = False
string_char = None

for i, line in enumerate(lines):
    for j, char in enumerate(line):
        if char in ('"', "'") and (j == 0 or line[j-1] != '\\'):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
                string_char = None
        elif char == '{' and not in_string:
            print(f'Open brace at line {i+1}: {line.strip()[:60]}')
        elif char == '}' and not in_string:
            print(f'Close brace at line {i+1}')