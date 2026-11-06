"""One APP-owned job catalog/admission lock shared by preparation and labeling."""
from threading import RLock
jobs = {}
guard = RLock()


def busy():
    return any(job['thread'].is_alive() if 'thread' in job else job['status']['state'] in ('queued','running','cancelling') for job in jobs.values())
