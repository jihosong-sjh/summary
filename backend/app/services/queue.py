from dataclasses import dataclass

from app.core.config import get_settings


@dataclass
class ProcessingQueue:
    def enqueue_recording_processing(self, recording_id: str) -> None:
        settings = get_settings()
        if settings.queue_mode == "disabled":
            return
        if settings.queue_mode == "inline":
            from app.workers.tasks import process_recording

            process_recording(recording_id)
            return

        from app.workers.tasks import process_recording_task

        process_recording_task.delay(recording_id)

