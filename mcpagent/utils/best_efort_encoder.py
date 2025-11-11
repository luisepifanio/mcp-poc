import json
from typing import Any
import datetime
from decimal import Decimal

# --- Constantes y Fórmulas ---
NON_SERIALIZABLE_TEMPLATE = "🫢 <non-serializable: {type_name}>"

# --- 1. Definición del Custom Encoder (Extensible) ---


class BestEffortEncoder(json.JSONEncoder):
    """
    JSONEncoder de 'Mejor Esfuerzo' que intenta recursivamente serializar atributos
    de objetos no serializables (como instancias de clases) y, si falla,
    deja una marca de no serializable en el valor.
    """

    def default(self, o):
        """
        Método sobreescrito que maneja tipos que el encoder base no sabe manejar.
        """
        # 1. Manejo de tipos nativos complejos (Opcional: Mejora de UX)
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()
        if isinstance(o, Decimal):
            return str(o)

        # 2. Intento de Navegación (Best Effort)
        try:
            # Si el objeto tiene un método .__dict__ (mayoría de instancias)
            if hasattr(o, "__dict__"):
                # Retorna el diccionario de atributos para que el encoder lo navegue.
                # Esto es la clave de la recursividad eficiente.
                return o.__dict__

            # Intento de conversión simple a string (e.g., para clases base sin __dict__)
            return str(o)

        except Exception:
            # Si la inspección (e.g., acceso a __dict__) o la conversión a str falla
            # (ej: objetos con acceso restringido), aplica la marca de no serializable.
            pass

        # 3. Fallback: Marcado de No Serializable
        type_name = type(o).__qualname__
        return NON_SERIALIZABLE_TEMPLATE.format(type_name=type_name)


# --- 2. Función de Interfaz (Concisa y Minimalista) ---


def best_effort_serialize(obj: Any) -> str:
    """
    Serializa un objeto Python con la estrategia de 'mejor esfuerzo'.

    Aprovecha el BestEffortEncoder para serializar propiedades que son posibles
    y marcar aquellas que no lo son.
    """
    return json.dumps(
        obj,
        cls=BestEffortEncoder,  # Uso del mecanismo 'cls'
        sort_keys=True,
        indent=2,
    )
