"""Route layer entry point.

This file only does two things: create the main router api_router, and automatically scan and register all submodules' routers under the api package.
Specific interfaces are written in business files in the same directory (account.py / user.py / files.py ...),
When adding a new business domain, just create a new file in this directory and define the router, without modifying this file.
"""

import importlib
import pkgutil

from fastapi import APIRouter

api_router = APIRouter()

for _, module_name, _ in pkgutil.iter_modules(__path__, __name__ + "."):
    module = importlib.import_module(module_name)
    if hasattr(module, "router"):
        api_router.include_router(module.router)
