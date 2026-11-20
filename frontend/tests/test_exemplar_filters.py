from types import SimpleNamespace

import flet as ft

from frontend.ui.views.ejemplares.ejemplares import (
    PHYSICAL_CONDITIONS,
    build,
)


class FakeApi:
    def request(self, path: str) -> list[dict]:
        responses = {
            "/api/ejemplar": [
                {
                    "id": 1,
                    "codigo": "EX-1",
                    "estado_fisico": "Bueno",
                    "libro_id": 1,
                    "sede_id": 1,
                }
            ],
            "/api/libro": [{"id": 1, "titulo": "Libro de prueba"}],
            "/api/sede": [{"id": 1, "nombre": "Sede de prueba"}],
            "/api/ejemplar/disponibilidad": [],
        }
        return responses[path]


def _walk_controls(control: ft.Control):
    yield control
    content = getattr(control, "content", None)
    if content is not None:
        yield from _walk_controls(content)
    for child in getattr(control, "controls", []):
        yield from _walk_controls(child)


def test_exemplar_physical_filter_lists_all_valid_states() -> None:
    app = SimpleNamespace(
        api=FakeApi(),
        page=SimpleNamespace(update=lambda: None),
        current_user=None,
    )

    view = build(app)
    physical_filter = next(
        control
        for control in _walk_controls(view)
        if isinstance(control, ft.Dropdown)
        and control.label == "Estado físico"
        and control.value == "__all__"
    )

    assert [option.key for option in physical_filter.options] == [
        "__all__",
        *PHYSICAL_CONDITIONS,
    ]
