code = "x = {\"routing\": {\"task_routes\": {\"research\": {\"primary_agent\": \"researcher\", \"fallback_agents\": [\"orchestrator\"]}}}}"

import ast
ast.parse(code)
print('Nested dict with string keys OK')