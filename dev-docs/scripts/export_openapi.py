import sys
import os
import yaml
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

# Ensure we can import from the 'server' directory
# The script is now in 'dev-docs/scripts', 
# so we need to add 'E:\workspace\code\DouDouChat\server' to path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
server_dir = os.path.join(root_dir, "server")
sys.path.append(server_dir)

from app.api.endpoints import chat, health, llm, friend

def export_docs():
    # Mapping of filename (without ext) -> router
    routes_map = {
        "chat": {"router": chat.router, "prefix": "/chat"},
        "health": {"router": health.router, "prefix": "/health"},
        "llm": {"router": llm.router, "prefix": "/llm"},
        "friend": {"router": friend.router, "prefix": "/friends"},
    }

    # Output to dev-docs/swagger-api
    output_dir = os.path.join(root_dir, "dev-docs", "swagger-api")
    os.makedirs(output_dir, exist_ok=True)

    print(f"Exporting OpenAPI specs to: {output_dir}")

    for name, config in routes_map.items():
        sub_app = FastAPI(title=f"DouDouChat - {name.capitalize()} API")
        sub_app.include_router(config["router"], prefix=config["prefix"])

        openapi_schema = get_openapi(
            title=sub_app.title,
            version="1.0.0",
            openapi_version=sub_app.openapi_version,
            description=f"OpenAPI specification for the {name} module",
            routes=sub_app.routes,
        )

        output_file = os.path.join(output_dir, f"{name}.yaml")
        with open(output_file, "w", encoding="utf-8") as f:
            yaml.dump(openapi_schema, f, allow_unicode=True, sort_keys=False)
        
        print(f"Generated: {output_file}")

if __name__ == "__main__":
    export_docs()
