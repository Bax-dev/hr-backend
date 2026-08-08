import json
import inspect
import re
from pathlib import Path

from django.urls import URLPattern, URLResolver, get_resolver

OPENAPI_VERSION = "3.0.3"

METHOD_SUMMARIES = {
    "get": "Retrieve resource",
    "post": "Create resource",
    "put": "Replace resource",
    "patch": "Update resource",
    "delete": "Delete resource",
}

PUBLIC_PATHS = {
    "/api/v1/auth/signup/company/",
    "/api/v1/auth/login/",
    "/api/v1/auth/forgot-password/",
    "/api/v1/auth/reset-password/",
}

# App-driven API surface. Derived from the frontend code in
# /Users/mac/Documents/wares/hr-app/apps/hr-system/src, excluding mocks and
# generated client output. Paths not listed here are intentionally omitted from
# Swagger because the current app does not call them.
USED_OPERATIONS = {
    "/api/announcements": {"get", "post"},
    "/api/celebrations": {"get"},
    "/api/dashboard/overview": {"get"},
    "/api/dashboard/stats": {"get"},
    "/api/dashboard/attendance-trend": {"get"},
    "/api/dashboard/recent-activity": {"get"},
    "/api/jobs": {"get", "post"},
    "/api/jobs/{job_id}": {"patch", "delete"},
    "/api/payroll/": {"get"},
    "/api/payroll/summary": {"get"},
    "/api/payroll/run": {"post"},
    "/api/v1/ai-features/": {"get", "post"},
    "/api/v1/ai-features/{record_pk}/": {"patch", "delete"},
    "/api/v1/attendance/": {"get"},
    "/api/v1/attendance/check-in/": {"post"},
    "/api/v1/attendance/check-out/": {"post"},
    "/api/v1/attendance/locations/": {"get", "post"},
    "/api/v1/attendance/locations/{location_pk}/": {"patch", "delete"},
    "/api/v1/auth/change-password/": {"post"},
    "/api/v1/auth/forgot-password/": {"post"},
    "/api/v1/auth/login/": {"post"},
    "/api/v1/auth/logout/": {"post"},
    "/api/v1/auth/me/": {"get"},
    "/api/v1/auth/reset-password/": {"post"},
    "/api/v1/auth/signup/company/": {"post"},
    "/api/v1/employees/": {"get", "post"},
    "/api/v1/employees/me/": {"get", "patch"},
    "/api/v1/employees/{employee_pk}/": {"get", "patch", "delete"},
    "/api/v1/leave/": {"get", "post"},
    "/api/v1/leave/{leave_pk}/": {"patch", "delete"},
    "/api/v1/notifications/": {"get", "post"},
    "/api/v1/notifications/{record_pk}/": {"patch", "delete"},
    "/api/v1/notifications/inbox/": {"get"},
    "/api/v1/notifications/inbox/read-all/": {"post"},
    "/api/v1/notifications/inbox/{notification_pk}/read/": {"post"},
    "/api/v1/people/custom-fields/": set(),
    "/api/v1/people/departments/": {"get", "post"},
    "/api/v1/people/departments/{department_pk}/": {"patch", "delete"},
    "/api/v1/people/designations/": {"get", "post"},
    "/api/v1/people/designations/{designation_pk}/": {"patch", "delete"},
    "/api/v1/people/employees/{employee_pk}/custom-fields/": {"get", "post"},
    "/api/v1/people/employees/{employee_pk}/custom-fields/{field_pk}/": {"patch", "delete"},
    "/api/v1/people/employees/{employee_pk}/documents/": {"get", "post"},
    "/api/v1/people/employees/{employee_pk}/documents/{document_pk}/": {"patch", "delete"},
    "/api/v1/people/employees/{employee_pk}/emergency-contacts/": {"get", "post"},
    "/api/v1/people/employees/{employee_pk}/emergency-contacts/{contact_pk}/": {"patch", "delete"},
    "/api/v1/people/employees/{employee_pk}/employment-history/": {"get", "post"},
    "/api/v1/people/employees/{employee_pk}/employment-history/{entry_pk}/": {"patch", "delete"},
    "/api/v1/people/organization-chart/": {"get"},
    "/api/v1/people/summary/": {"get"},
    "/api/v1/people/teams/": {"get", "post"},
    "/api/v1/people/teams/{team_pk}/": {"patch", "delete"},
    "/api/v1/settings/attendance-policy/": {"get", "patch"},
    "/api/v1/settings/company/": {"get", "patch"},
    "/api/v1/settings/security/": {"get", "patch"},
    "/api/v1/talent/offboarding/": {"get", "post"},
    "/api/v1/talent/offboarding/{record_pk}/": {"patch", "delete"},
    "/api/v1/talent/onboarding/": {"get", "post"},
    "/api/v1/talent/onboarding/{record_pk}/": {"patch", "delete"},
    "/api/v1/talent/performance/": {"get", "post"},
    "/api/v1/talent/performance/{record_pk}/": {"patch", "delete"},
    "/api/v1/talent/summary/": {"get"},
    "/api/v1/uploads/presign/": {"post"},
}

CONVERTER_SCHEMAS = {
    "int": {"type": "integer"},
    "slug": {"type": "string"},
    "str": {"type": "string"},
    "path": {"type": "string"},
    "uuid": {"type": "string", "format": "uuid"},
}

PARAM_RE = re.compile(r"<(?:(?P<converter>[^>:]+):)?(?P<name>[^>]+)>")
HTTP_METHODS_RE = re.compile(r"@require_http_methods\(\[(?P<methods>[^\]]+)\]\)")
SINGLE_METHOD_RE = re.compile(r"@require_(?P<method>GET|POST)\b")


def default_output_path() -> Path:
    return Path(__file__).resolve().parents[2] / "openapi.yaml"


def build_openapi_spec():
    paths = {}
    for route in _iter_routes(get_resolver().url_patterns):
        if not route["path"].startswith("/api/"):
            continue
        if route["openapi_path"] not in USED_OPERATIONS:
            continue

        operations = paths.setdefault(route["openapi_path"], {})
        for method in route["methods"]:
            if method not in USED_OPERATIONS[route["openapi_path"]]:
                continue
            operations[method] = _build_operation(route, method)

        if not operations:
            paths.pop(route["openapi_path"], None)

    return {
        "openapi": OPENAPI_VERSION,
        "info": {
            "title": "HR App Backend API",
            "version": "1.0.0",
            "description": "Auto-generated OpenAPI document built from the Django route table.",
        },
        "servers": [{"url": "/"}],
        "security": [{"bearerAuth": []}],
        "paths": dict(sorted(paths.items())),
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "Token",
                    "description": "Send the API token in the Authorization header as `Bearer <token>`.",
                }
            },
            "schemas": {
                "GenericObject": {
                    "type": "object",
                    "additionalProperties": True,
                },
                "SuccessEnvelope": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "example": True},
                        "message": {"type": "string"},
                        "data": {"$ref": "#/components/schemas/GenericObject"},
                    },
                    "required": ["success"],
                },
                "ErrorEnvelope": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "example": False},
                        "error": {
                            "type": "object",
                            "properties": {
                                "message": {"type": "string"},
                                "code": {"type": "string"},
                                "details": {"$ref": "#/components/schemas/GenericObject"},
                            },
                        },
                    },
                    "required": ["success", "error"],
                },
            },
        },
    }


def write_openapi_spec(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(build_openapi_spec(), indent=2) + "\n", encoding="utf-8")
    return destination


def _iter_routes(patterns, prefix=""):
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            next_prefix = prefix + _route_pattern(pattern.pattern)
            yield from _iter_routes(pattern.url_patterns, next_prefix)
            continue

        if isinstance(pattern, URLPattern):
            route = prefix + _route_pattern(pattern.pattern)
            if not route.startswith("/"):
                route = "/" + route
            yield {
                "callback": pattern.callback,
                "methods": _allowed_methods(pattern.callback),
                "name": pattern.name or pattern.callback.__name__,
                "path": route,
                "openapi_path": _to_openapi_path(route),
                "parameters": _extract_parameters(route),
            }


def _route_pattern(pattern):
    return getattr(pattern, "_route", str(pattern))


def _allowed_methods(callback):
    current = callback
    seen = set()
    while current and id(current) not in seen:
        seen.add(id(current))
        methods = getattr(current, "allowed_methods", None)
        if methods:
            return [method.lower() for method in methods if method not in {"HEAD", "OPTIONS"}]
        current = getattr(current, "__wrapped__", None)

    unwrapped = inspect.unwrap(callback)
    methods = getattr(unwrapped, "allowed_methods", None)
    if methods:
        return [method.lower() for method in methods if method not in {"HEAD", "OPTIONS"}]
    methods = _allowed_methods_from_source(unwrapped)
    if methods:
        return methods
    return ["get"]


def _allowed_methods_from_source(callback):
    try:
        source = inspect.getsource(callback)
    except (OSError, TypeError):
        return None

    match = HTTP_METHODS_RE.search(source)
    if match:
        raw_methods = match.group("methods")
        methods = [
            token.strip().strip("'\"").lower()
            for token in raw_methods.split(",")
            if token.strip()
        ]
        return [method for method in methods if method not in {"head", "options"}]

    single_methods = SINGLE_METHOD_RE.findall(source)
    if single_methods:
        return [method.lower() for method in single_methods]

    return None


def _to_openapi_path(path):
    return PARAM_RE.sub(lambda match: "{" + match.group("name") + "}", path)


def _extract_parameters(path):
    parameters = []
    for match in PARAM_RE.finditer(path):
        converter = match.group("converter") or "str"
        name = match.group("name")
        schema = dict(CONVERTER_SCHEMAS.get(converter, {"type": "string"}))
        parameters.append(
            {
                "name": name,
                "in": "path",
                "required": True,
                "schema": schema,
            }
        )
    return parameters


def _build_operation(route, method):
    callback = route["callback"]
    summary = METHOD_SUMMARIES.get(method, "Handle request")
    docstring = (callback.__doc__ or "").strip()
    operation = {
        "operationId": f"{route['name'].replace('-', '_')}_{method}",
        "tags": [_tag_for_path(route["path"])],
        "summary": summary,
        "responses": _responses_for_method(method),
    }

    if docstring:
        operation["description"] = docstring
    if route["parameters"]:
        operation["parameters"] = route["parameters"]
    if method in {"post", "put", "patch"}:
        operation["requestBody"] = {
            "required": method in {"post", "put"},
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/GenericObject"}
                }
            },
        }
    if route["path"] in PUBLIC_PATHS:
        operation["security"] = []
    return operation


def _responses_for_method(method):
    success_code = "201" if method == "post" else "204" if method == "delete" else "200"
    success_description = {
        "get": "Successful response.",
        "post": "Resource created successfully.",
        "put": "Resource replaced successfully.",
        "patch": "Resource updated successfully.",
        "delete": "Resource deleted successfully.",
    }.get(method, "Successful response.")

    response = {
        success_code: {
            "description": success_description,
        },
        "400": {
            "description": "Validation or bad request error.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorEnvelope"}
                }
            },
        },
        "401": {
            "description": "Authentication failed or credentials were not supplied.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorEnvelope"}
                }
            },
        },
    }
    if method != "delete":
        response[success_code]["content"] = {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/SuccessEnvelope"}
            }
        }
    return response


def _tag_for_path(path):
    parts = [part for part in path.strip("/").split("/") if part]
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "v1":
        return parts[2]
    if len(parts) >= 2 and parts[0] == "api":
        return parts[1]
    return "api"
