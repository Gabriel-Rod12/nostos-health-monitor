# Pruebas automatizadas de NOSTOS

## Preparar el entorno

Desde la carpeta raíz del repositorio:

```bash
python -m pip install -r requirements-dev.txt
```

## Ejecutar todas las pruebas

```bash
python -m pytest tests/ -v
```

Las pruebas usan datos sintéticos y no necesitan conectarse a sensores ni servicios externos.
