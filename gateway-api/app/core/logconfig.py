# app/logconfig.py
import logging
import logging.config
import os
from typing import Any

# Important  logging config should not depend on app settings to avoid initialization problema
# from app.core.settings import getAppSettings # 🔴 Dont do it, please

ENV = (
    "production"
    if os.getenv("ENV", "").lower() in ["", "production", "prod"]
    else "development"
).lower()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# --- Definiciones de Formato y Estructura ---

# Formato de Fecha (ISO-8601)
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

# A. Formato de Desarrollo (Color y Alineación Fija)
# Utiliza colorlog.ColoredFormatter
DEV_FORMATTER_SPEC = (
    # "%(asctime)s %(name)s %(levelname)s %(message)s"
    "[%(asctime)s][%(log_color)s%(levelname)-8s%(reset)s][%(name)-30s] %(message)s "
    # "(%(filename)s:%(lineno)d)"
)
DEV_FORMATTER = {
    "()": "colorlog.ColoredFormatter",
    "format": DEV_FORMATTER_SPEC,
    "datefmt": DATE_FORMAT,
    "log_colors": {
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red,bg_white",
    },
}

# B. Formato de Producción (JSON)
# Utiliza pythonjsonlogger.json.JsonFormatter (DEFAULT)
PROD_FORMATTER_SPEC = (
    "%(asctime)s %(levelname)s %(name)s %(module)s %(funcName)s %(lineno)d %(message)s"
)
PROD_FORMATTER = {
    "()": "pythonjsonlogger.json.JsonFormatter",
    "format": PROD_FORMATTER_SPEC,
    "datefmt": DATE_FORMAT,
}

# ----------------------------------------------------
# Base de Configuración Dinámica
# ----------------------------------------------------


def get_logging_config() -> dict[str, Any]:
    """
    Construye el diccionario de configuración de logging basado en el entorno.
    """
    # 1. Seleccionar el Formatter según el entorno
    formatter_name = "json_formatter" if ENV == "production" else "dev_formatter"
    current_formatter = PROD_FORMATTER if ENV == "production" else DEV_FORMATTER

    # 2. Definir la Configuración Base
    LOGGING_CONFIG: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            # Se inyecta el formatter seleccionado
            formatter_name: current_formatter,
        },
        "handlers": {
            # Handler principal para logs normales (stdout)
            "default": {
                "formatter": formatter_name,
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "level": LOG_LEVEL,
            },
            # Handler específico para errores (stderr)
            "error_handler": {
                "formatter": formatter_name,
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
                "level": "ERROR",  # Captura solo ERROR y CRITICAL
            },
        },
        "loggers": {
            # Logger Raíz
            "": {
                # Usamos los dos handlers: default para INFO/DEBUG/WARN y error_handler para ERROR/CRITICAL
                "handlers": ["default", "error_handler"],
                "level": LOG_LEVEL,
                "propagate": False,
            },
            # Control específico para Uvicorn (opcional, pero recomendado)
            "sqlalchemy": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.error": {
                "handlers": ["error_handler"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["default"],
                "level": "WARNING",
                "propagate": False,
            },
        },
    }
    return LOGGING_CONFIG


def setup_logging() -> None:
    """
    Configura el sistema de logging.
    """
    logging.config.dictConfig(get_logging_config())
    logging.getLogger(__name__).info(
        f"Logging configurado. Entorno: {ENV} (Nivel: {LOG_LEVEL})."
    )


# Ejemplo de uso
if __name__ == "__main__":
    # Simular entorno de desarrollo para ver el formato alineado
    os.environ["ENVIRONMENT"] = "development"
    setup_logging()

    logger = logging.getLogger(__name__)
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")

    # Ejemplo de mensaje multilinea
    logger.critical("This a multiline\nmessage")

    # Simular entorno de producción para ver el formato JSON (por defecto)
    os.environ["ENVIRONMENT"] = "production"
    setup_logging()

    logger_prod = logging.getLogger("app.core.usescases.ProdService")
    logger_prod.info("Production service started")
