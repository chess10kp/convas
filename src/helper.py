import logging

logging.basicConfig(level=logging.INFO, filename="log")
Logger = logging.getLogger("samplelogger")
Logger.info("Logging Has started")
