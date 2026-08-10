import sys
sys.path.insert(0, '..')

import asyncio
from agent_system.router import ModelRouter, RoutingContext
from agent_system.schemas import TaskType as SchemaTaskType
from agent_system.schemas import ModelCapability
from agent_system.providers import ProviderType

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

print(f'Context: {context}')
print(f'Context task_type: {context.task_type}')
print(f'Context task_type value: {context.task_type.value}')
print(f'Context required_capabilities: {context.required_capabilities}')
print(f'Context excluded_providers: {context.excluded_providers}')

# Check router config
print(f'Router routing_config: {router.routing_config}')
print(f'Router models_config: {router.models_config}')
print(f'Router capability_requirements: {router.capability_requirements}')

# Try routing
decision = router.route(context)
print(f'Decision: {decision}')
print(f'Provider: {decision.provider}')
print(f'Model: {decision.model}')