"""One APP-owned job catalog/admission lock shared by preparation and labeling."""
from threading import RLock
jobs = {}
guard = RLock()


def busy(*, ignore_training=False):
    return any(job['thread'].is_alive() if 'thread' in job else job['status']['state'] in ('queued','running','cancelling') for job in jobs.values() if not (ignore_training and job.get("kind")=="training"))
