"""
Configuration Management
Loads and manages YAML configuration files.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class ConfigManager:
    """Manages configuration loading from YAML files."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            # Default to config directory relative to this file
            self.config_dir = Path(__file__).parent.parent.parent / "config"
        else:
            self.config_dir = config_dir
        
        self._cache: Dict[str, Any] = {}
    
    def load(self, name: str) -> Dict[str, Any]:
        """Load a configuration file."""
        if name in self._cache:
            return self._cache[name]
        
        file_path = self.config_dir / f"{name}.yaml"
        if not file_path.exists():
            # Try with .yml extension
            file_path = self.config_dir / f"{name}.yml"
        
        if not file_path.exists():
            return {}
        
        with open(file_path, "r") as f:
            config = yaml.safe_load(f) or {}
        
        self._cache[name] = config
        return config
    
    def get(self, name: str, key: str, default: Any = None) -> Any:
        """Get a specific configuration value."""
        config = self.load(name)
        keys = key.split(".")
        value = config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value
    
    def reload(self, name: str) -> Dict[str, Any]:
        """Force reload a configuration file."""
        if name in self._cache:
            del self._cache[name]
        return self.load(name)
    
    def load_all(self) -> Dict[str, Dict[str, Any]]:
        """Load all configuration files."""
        configs = {}
        for file_path in self.config_dir.glob("*.yaml"):
            name = file_path.stem
            configs[name] = self.load(name)
        for file_path in self.config_dir.glob("*.yml"):
            name = file_path.stem
            if name not in configs:
                configs[name] = self.load(name)
        return configs


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_dir: Optional[Path] = None) -> ConfigManager:
    """Get the global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_dir)
    return _config_manager


def get_config(name: Optional[str] = None) -> Dict[str, Any]:
    """Get configuration. If name is None, return all configs merged."""
    manager = get_config_manager()
    if name is None:
        return manager.load_all()
    return manager.load(name)


def get_config_value(name: str, key: str, default: Any = None) -> Any:
    """Get a specific configuration value."""
    manager = get_config_manager()
    return manager.get(name, key, default)