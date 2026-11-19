import json
import urllib.error
import urllib.request
from typing import Any


class ApiError(Exception):
    """Error returned by the library API or its transport."""


class ApiClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = 10,
        access_token: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.access_token = access_token

    def set_access_token(self, access_token: str | None) -> None:
        self.access_token = access_token

    def request(
        self,
        path: str,
        method: str = "GET",
        data: dict[str, Any] | None = None,
    ) -> Any:
        body = json.dumps(data).encode("utf-8") if data is not None else None
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                if response.status == 204:
                    return None
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            try:
                detail = json.loads(error.read().decode("utf-8")).get(
                    "detail", str(error)
                )
            except (json.JSONDecodeError, UnicodeDecodeError):
                detail = str(error)
            raise ApiError(f"Error {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise ApiError(
                f"No se pudo conectar con la API ({self.base_url}). "
                "Verificá que el backend esté iniciado."
            ) from error
