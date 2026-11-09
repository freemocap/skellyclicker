"""Report one actionable error when a DLC subprocess exits unexpectedly."""
import os
import shutil


def describe_worker_failure(mode, code, job, logger):
    work = job["work"]
    path = work / f"{mode}.log"
    trace = job.get("worker_traceback")
    if not trace:
        try:
            with path.open("rb") as stream:
                stream.seek(max(0, os.fstat(stream.fileno()).st_size - 8192))
                trace = stream.read().decode("utf-8", errors="replace").strip()
        except OSError:
            trace = ""
    try:
        free = shutil.disk_usage(work).free
    except OSError:
        free = None

    stage = job.get("worker_stage", {})
    checkpoint = job.get("last_checkpoint_event")
    detail = job.get("worker_error") or (trace.splitlines()[-1] if trace else f"Worker exited with code {code}")
    summary = f"{mode} failed. {detail}"
    if mode == "train" and stage.get("stage") == "save_weights":
        summary = f"Could not save the checkpoint for epoch {stage.get('completed', '?')}. {detail}"
    if free is not None:
        summary += f" Free disk space: {free / 2**20:,.0f} MiB."
    if checkpoint:
        summary += f" Last saved checkpoint: epoch {checkpoint['epoch']}."
    logger.error("%s | Run %s | Exit %s | Worker log: %s\n%s", summary, work.name, code, path, trace[-16384:])
    return summary
