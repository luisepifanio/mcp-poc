# MCP Server — Instrucciones de pruebas

Para ejecutar la suite de tests desde la raíz del proyecto (forma recomendada):

```
uv run pytest -q
```

Notas:

- No es necesario exportar `PYTHONPATH` manualmente si ejecutas el comando desde la raíz del proyecto: `pyproject.toml` ya contiene `pythonpath = ["."]` bajo `[tool.pytest.ini_options]`.
- Si ejecutas desde otra carpeta, puedes usar temporalmente `PYTHONPATH=. uv run pytest -q`.

Esto ejecuta las pruebas unitarias y funcionales configuradas para el proyecto.
