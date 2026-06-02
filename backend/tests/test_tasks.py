from pathlib import Path


def test_audio_download_path_preserves_object_key_extension(tmp_path):
    from app.workers.tasks import _audio_download_path

    path = _audio_download_path(
        tmp_path,
        "users/user-id/recordings/recording-id/audio.m4a",
    )

    assert path == tmp_path / "audio.m4a"


def test_audio_download_path_defaults_to_m4a(tmp_path):
    from app.workers.tasks import _audio_download_path

    path = _audio_download_path(tmp_path, "users/user-id/recordings/recording-id/audio")

    assert path == tmp_path / "audio.m4a"
