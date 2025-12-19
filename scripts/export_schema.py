import json
import os
import sys

# Ensure src module is visible
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.core.config import AppConfig

def export_schema():
    """
    Exports the Pydantic model schema to JSON for frontend integration.
    """
    schema = AppConfig.model_json_schema()
    output_dir = os.path.join(os.path.dirname(__file__), '../config')
    output_path = os.path.join(output_dir, 'frontend_schema.json')

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    print(f"Schema exported to {output_path}")

if __name__ == "__main__":
    export_schema()
