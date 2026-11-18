import unicodedata
from abc import ABC


class InvalidPrestamoTransition(ValueError):
    pass


class PrestamoState(ABC):
    name = ""
    allowed_transitions = frozenset()

    def transition_to(self, target):
        if target.name not in self.allowed_transitions:
            raise InvalidPrestamoTransition(
                f"No se puede cambiar el préstamo de {self.name} a {target.name}"
            )


class PendienteState(PrestamoState):
    name = "Pendiente"
    allowed_transitions = frozenset({"Activo"})


class ActivoState(PrestamoState):
    name = "Activo"
    allowed_transitions = frozenset({"Vencido", "Devuelto"})


class VencidoState(PrestamoState):
    name = "Vencido"
    allowed_transitions = frozenset({"Devuelto"})


class DevueltoState(PrestamoState):
    name = "Devuelto"


class CanceladoState(PrestamoState):
    name = "Cancelado"


_STATE_TYPES = {
    "pendiente": PendienteState,
    "activo": ActivoState,
    "en curso": ActivoState,
    "prestado": ActivoState,
    "vencido": VencidoState,
    "atrasado": VencidoState,
    "devuelto": DevueltoState,
    "finalizado": DevueltoState,
    "cancelado": CanceladoState,
}


def get_prestamo_state(description):
    normalized = unicodedata.normalize("NFKD", description.strip().lower())
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    state_type = _STATE_TYPES.get(normalized)
    if state_type is None:
        raise ValueError(f"Estado de préstamo desconocido: {description}")
    return state_type()


def validate_prestamo_transition(current_description, target_description):
    current_state = get_prestamo_state(current_description)
    target_state = get_prestamo_state(target_description)
    current_state.transition_to(target_state)


def validate_initial_prestamo_state(description):
    if not isinstance(get_prestamo_state(description), ActivoState):
        raise InvalidPrestamoTransition(
            "Un préstamo local nuevo debe comenzar Activo"
        )