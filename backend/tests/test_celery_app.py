def test_celery_registers_recording_processing_task():
    from app.workers.celery_app import celery_app

    celery_app.loader.import_default_modules()

    assert "summary.process_recording" in celery_app.tasks
    assert "summary.process_music_search" in celery_app.tasks
