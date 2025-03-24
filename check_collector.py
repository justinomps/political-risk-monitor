import sys
import os
from importlib import reload
import inspect

print(f"Python version: {sys.version}")
print(f"Current working directory: {os.getcwd()}")

try:
    import modules.collector
    print(f"Found modules.collector at: {modules.collector.__file__}")
    
    # Check if NewsCollector class exists
    if hasattr(modules.collector, 'NewsCollector'):
        print("NewsCollector class exists")
        
        # Check the methods on NewsCollector
        print("\nMethods in NewsCollector class:")
        for name, method in inspect.getmembers(modules.collector.NewsCollector, predicate=inspect.isfunction):
            print(f"  - {name}")
    else:
        print("NewsCollector class not found!")
        
except ImportError as e:
    print(f"Import error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")