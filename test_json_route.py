import sys
import json
sys.path.insert(0, '.')

from agent_system.router import ModelRouter, RoutingContext
from agent_system.schemas import TaskType

# Create router with test config using JSON
test_config = json.loads('{"routing": {"task_routes": {"research": {"primary_agent": "researcher", "fallback_agents": ["orchestrator"]}}}, "models": {"researcher": {"provider": "nvidia", "model": "model1"}}, "limits": {"retry": {"max_retries": 3}}}')

from agent_system.router import ModelRouter, RoutingContext
from agent_system.schemas import TaskType

router = ModelRouter(config=test_config)
context = RoutingContext(task_type=TaskType.RESEARCH)
decision = router.route(context)
print('Decision:', decision)
print('Provider:', decision.provider)
print('Model:', decision.model)