import logging
from app.core.trace import trace_id_var

class TraceLogFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = trace_id_var.get() or "-"
        return True

def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [trace_id=%(trace_id)s] %(message)s"
    )
    logging.getLogger().addFilter(TraceLogFilter())
