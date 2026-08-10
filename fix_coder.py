# Read the file
with open('agent_system/agents/coder.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the factory function
old = '''def create_coder_agent(tool_manager=None) -> CoderAgent:
    """Factory function to create coder agent."""
    models_config = get_config("models")
    coder_config = models_config.get("coder", {})
    agents_config = get_config("agents")
    agent_config = agents_config.get("coder", {})
    
    config = AgentConfig(
        name=AgentName.CODER,
        description=agent_config.get("description", "Code implementation and modification"),
        permissions=agent_config.get("permissions", "SAFE_WRITE"),
        default_model=coder_config.get("model", "glm-4.5"),
        fallback_models=agent_config.get("fallback_models", []),
        capabilities=agent_config.get("capabilities", []),
        max_parallel_subtasks=agent_config.get("max_parallel_subtasks", 2),
        timeout=agent_config.get("timeout", 300),
        system_prompt=agent_config.get("system_prompt", ""),
    )
    
    return CoderAgent(config, tool_manager)'''

new = '''def create_coder_agent(tool_manager=None) -> CoderAgent:
    models_config = get_config("models")
    coder_config = models_config.get("coder", {})
    agents_config = get_config("agents")
    agent_config = agents_config.get("coder", {})
    
    config = AgentConfig(
        name=AgentName.CODER,
        description=agent_config.get("description", "Code implementation and modification"),
        permissions=agent_config.get("permissions", "SAFE_WRITE"),
        default_model=coder_config.get("model", "glm-4.5"),
        fallback_models=agent_config.get("fallback_models", []),
        capabilities=agent_config.get("capabilities", []),
        max_parallel_subtasks=agent_config.get("max_parallel_subtasks", 2),
        timeout=agent_config.get("timeout", 300),
        system_prompt=agent_config.get("system_prompt", ""),
    )
    
    return CoderAgent(config, tool_manager)'''

if old in content:
    content = content.replace(old, new)
    with open('agent_system/agents/coder.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Replaced')
else:
    print('Old text not found')