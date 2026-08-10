import sys
sys.path.insert(0, '..')

from agent_system.router import ModelRouter, RoutingContext
from agent_system.schemas import TaskType

# Create router with test config
test_config = {
    'routing': {
        'task_routes': {
            'research': {
                'primary_agent': 'researcher',
                'fallback_agents': ['orchestrator'],
            },
        },
        'models': {
            'researcher': {'provider': 'nvidia', 'model': 'model1'},
        },
        'limits': {
            'retry': {'max_retries': 3},
        },
    }

router = ModelRouter(config=test_config)

# Create context
context = RoutingContext(task_type=TaskType.RESEARCH)

print('Context:', context)
print('Context task_type:', context.task_type)
print('Context task_type value:', context.task_type.value)
print('Context required_capabilities:', context.required_capabilities)
print('Context excluded_providers:', context.excluded_providers)

# Check router config
print('Router routing_config:', router.routing_config)
print('Router models_config:', router.models_config)
print('Router capability_requirements:', router.capability_requirements)

# Try routing
decision = router.route(context)
print('Decision:', decision)
print('Provider:', decision.provider)
print('Model:', decision.model)