import importlib
import importlib.util
from pathlib import Path
from typing import Dict
from agentmesh.tools.base_tool import BaseTool
from agentmesh.common import config
from agentmesh.common.utils.log import logger  # Import the logging module


class ToolManager:
    """
    Tool manager for managing tools.
    """
    _instance = None

    def __new__(cls):
        """Singleton pattern to ensure only one instance of ToolManager exists."""
        if cls._instance is None:
            cls._instance = super(ToolManager, cls).__new__(cls)
            cls._instance.tool_classes = {}  # Store tool classes instead of instances
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        # Initialize only once
        if not hasattr(self, 'tool_classes'):
            self.tool_classes = {}  # Dictionary to store tool classes

    def load_tools(self, tools_dir: str = "agentmesh/tools"):
        """
        Load tools from both directory and configuration.

        :param tools_dir: Directory to scan for tool modules
        """
        # First, load tools from directory (for backward compatibility)
        self._load_tools_from_directory(tools_dir)

        # Then, configure tools from config file
        self._configure_tools_from_config()

    def _load_tools_from_directory(self, tools_dir: str):
        """Dynamically load tool classes from directory"""
        tools_path = Path(tools_dir)

        # Traverse all .py files
        for py_file in tools_path.rglob("*.py"):
            # Skip initialization files and base tool files
            if py_file.name in ["__init__.py", "base_tool.py", "tool_manager.py"]:
                continue

            # Get module name
            module_name = py_file.stem

            try:
                # Load module directly from file
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Find tool classes in the module
                    for attr_name in dir(module):
                        cls = getattr(module, attr_name)
                        if (
                                isinstance(cls, type)
                                and issubclass(cls, BaseTool)
                                and cls != BaseTool
                        ):
                            try:
                                # Create a temporary instance to get the name
                                temp_instance = cls()
                                tool_name = temp_instance.name
                                # Store the class, not the instance
                                self.tool_classes[tool_name] = cls
                            except ImportError as e:
                                # Ignore browser_use dependency missing errors
                                if "browser_use" in str(e):
                                    pass
                                else:
                                    print(f"Error initializing tool class {cls.__name__}: {e}")
                            except Exception as e:
                                print(f"Error initializing tool class {cls.__name__}: {e}")
            except Exception as e:
                print(f"Error importing module {py_file}: {e}")

    def _configure_tools_from_config(self):
        """Configure tool classes based on configuration file"""
        try:
            # Get tools configuration
            tools_config = config().get("tools", {})

            # Record tools that are configured but not loaded
            missing_tools = []

            # Store configurations for later use when instantiating
            self.tool_configs = tools_config

            # Check which configured tools are missing
            for tool_name in tools_config:
                if tool_name not in self.tool_classes:
                    missing_tools.append(tool_name)

            # If there are missing tools, record warnings
            if missing_tools:
                for tool_name in missing_tools:
                    if tool_name == "browser":
                        logger.error(
                            "Browser tool is configured but could not be loaded. "
                            "Please install the required dependency with: "
                            "pip install browser-use>=0.1.40 or pip install agentmesh-sdk[full]"
                        )
                    else:
                        logger.warning(f"Tool '{tool_name}' is configured but could not be loaded.")

        except Exception as e:
            logger.error(f"Error configuring tools from config: {e}")

    def create_tool(self, name: str) -> BaseTool:
        """
        Get a new instance of a tool by name.

        :param name: The name of the tool to get.
        :return: A new instance of the tool or None if not found.
        """
        tool_class = self.tool_classes.get(name)
        if tool_class:
            # Create a new instance
            tool_instance = tool_class()

            # Apply configuration if available
            if hasattr(self, 'tool_configs') and name in self.tool_configs:
                tool_instance.config = self.tool_configs[name]

            return tool_instance
        return None

    def list_tools(self) -> dict:
        """
        Get information about all loaded tools.

        :return: A dictionary with tool information.
        """
        result = {}
        for name, tool_class in self.tool_classes.items():
            # Create a temporary instance to get schema
            temp_instance = tool_class()
            result[name] = {
                "description": temp_instance.description,
                "parameters": temp_instance.get_json_schema()
            }
        return result
