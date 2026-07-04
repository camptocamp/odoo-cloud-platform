import psutil
from prometheus_client import Gauge

MEMORY_USAGE_VMS = Gauge(
    "odoo_worker_memory_user_vms_mb", "Memory usage in MB", ["process", "pid"]
)

MEMORY_USAGE_RSS = Gauge(
    "odoo_worker_memory_user_rss_mb", "Memory usage in MB", ["process", "pid"]
)


def get_process_info():
    for process in psutil.process_iter(
        ["pid", "name", "memory_full_info", "cmdline", "nice"]
    ):
        try:
            mem = process.info["memory_full_info"]
            # rss == 0 means a zombie/dying process: skip to avoid
            # publishing garbage series
            if mem and mem.rss:
                # cmdline is None for processes that died mid-iteration
                cmdline = process.info["cmdline"] or []
                if process.info["nice"] == 10:
                    ProcessLabel = "workercron"
                elif process.info["pid"] == 1:
                    ProcessLabel = "dispatcher"
                elif any("gevent" in x for x in cmdline):
                    ProcessLabel = "gevent"
                elif any("odoo" in x for x in cmdline):
                    ProcessLabel = "workerhttp"
                elif any("shell" in x for x in cmdline):
                    ProcessLabel = "OdooShell"
                else:
                    ProcessLabel = "other"
                MEMORY_USAGE_VMS.labels(ProcessLabel, process.info["pid"]).set(
                    mem.vms // 1000000
                )
                MEMORY_USAGE_RSS.labels(ProcessLabel, process.info["pid"]).set(
                    mem.rss // 1000000
                )

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
