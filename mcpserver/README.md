# MCP Server — Instrucciones de pruebas

Para ejecutar la suite de tests desde la raíz del proyecto (forma recomendada):

```
uv run pytest -q
```

Notas:

- No es necesario exportar `PYTHONPATH` manualmente si ejecutas el comando desde la raíz del proyecto: `pyproject.toml` ya contiene `pythonpath = ["."]` bajo `[tool.pytest.ini_options]`.
- Si ejecutas desde otra carpeta, puedes usar temporalmente `PYTHONPATH=. uv run pytest -q`.

Esto ejecuta las pruebas unitarias y funcionales configuradas para el proyecto.

---

## ⚠️ Regla de Separación: Código de Producción vs Testing

**Regla Crítica**: El paquete `app/` **NO debe tener dependencias** con paquetes de testing (`unittest.mock`, `pytest`, `pytest-mock`, etc.) definidos en `dependency-groups -> dev` del `pyproject.toml`.

El código en `app/` es el que se containeriza y despliega en producción. Las dependencias de testing no deben estar presentes en runtime.

**Alternativas para distinguir comportamiento en tests**:
- **Duck typing**: `isinstance(obj, RealClass)` en lugar de `isinstance(obj, MagicMock)`
- **Inyección de dependencias**: Pasar comportamientos como parámetros
- **Interfaces/Protocolos**: Definir contratos que implementaciones reales y mocks cumplan

Ver [Agents.md](Agents.md) para más detalles y ejemplos.

---

## Testing tips (caché de settings)

- Si un test necesita modificar variables de entorno (p. ej. `DATABASE_URL`), es importante asegurarse de que la caché de configuración se limpie después del test para evitar contaminación entre pruebas.
- Uso recomendado: llamar a `clearAppSettings()` en el teardown del test o usar `getAppSettings(reload=True)` al obtener la configuración.
- El repositorio incluye un fixture global de test (`tests/conftest.py`) que limpia automáticamente la caché `AppSettings` después de cada test. No es necesario que los tests individuales limpien manualmente la caché si confían en el fixture global, pero es una buena práctica hacerlo explícito cuando el test modifica el entorno.

Ejemplo breve (teardown explícito):

```
from app.core import settings as settings_mod

def test_example(monkeypatch):
	monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
	try:
		# ... test logic ...
		pass
	finally:
		settings_mod.clearAppSettings()
```

O, alternativamente, solicitar recarga al obtener settings:

```
settings = settings_mod.getAppSettings(reload=True)
```
