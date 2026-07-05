import os
from pathlib import Path

from django.http import Http404, HttpResponse


def _openapi_spec_path() -> Path:
    backend_root = Path(__file__).resolve().parents[2]
    configured_path = os.environ.get("HR_APP_OPENAPI_SPEC_PATH")
    candidates = [
        Path(configured_path).expanduser() if configured_path else None,
        backend_root / "openapi.yaml",
        backend_root.parent / "hr-app" / "lib" / "api-spec" / "openapi.yaml",
    ]

    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate

    return backend_root.parent / "hr-app" / "lib" / "api-spec" / "openapi.yaml"


def openapi_spec_view(_request):
    spec_path = _openapi_spec_path()
    if not spec_path.exists():
        raise Http404("OpenAPI spec file was not found.")

    return HttpResponse(spec_path.read_text(encoding="utf-8"), content_type="application/yaml")


def swagger_ui_view(request):
    spec_url = request.build_absolute_uri("openapi.yaml")
    html = f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>HR App API Docs</title>
    <link
      rel="stylesheet"
      href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"
    />
    <style>
      body {{
        margin: 0;
        background: #fafafa;
      }}
      .topbar {{
        display: none;
      }}
    </style>
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      window.ui = SwaggerUIBundle({{
        url: "{spec_url}",
        dom_id: "#swagger-ui",
        deepLinking: true,
        displayRequestDuration: true,
        docExpansion: "none",
        defaultModelsExpandDepth: -1,
      }});
    </script>
  </body>
</html>"""
    return HttpResponse(html)
