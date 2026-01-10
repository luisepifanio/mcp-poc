"""JSON Type definitions for serializable data structures."""

from collections.abc import MutableMapping, Sequence

# JSON scalar types
type JSONScalar = str | int | float | bool | None

# Forward declarations for recursive types
type JSONDict = MutableMapping[str, JSONValue]
type JSONList = Sequence[JSONValue]

# Main JSON value type (can be scalar, dict, or list)
type JSONValue = JSONScalar | JSONDict | JSONList
