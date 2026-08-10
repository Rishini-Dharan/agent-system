import sys
sys.path.insert(0, '..')

from agent_system.router import ModelRouter, RoutingContext
from agent_system.schemas import TaskType as SchemaTaskType
from agent_system.schemas import ModelCapability

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
context = RoutingContext(task_type='research')

# Try routing
decision = router.route(context)
print(f'Decision: {decision}')
print(f'Provider: {decision.provider}')
print(f'Model: {decision.model}')