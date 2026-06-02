package com.summary.app.ui

import android.app.Application
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.summary.app.SummaryApplication
import com.summary.app.data.MusicSearchEntity
import com.summary.app.data.RecordingEntity
import com.summary.app.recording.AudioRecorder
import com.summary.app.recording.RecordingForegroundService
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class RecordingSessionState(
    val isRecording: Boolean = false,
    val isPaused: Boolean = false,
    val elapsedSeconds: Int = 0,
    val errorMessage: String? = null,
)

data class MusicSearchSessionState(
    val isRecording: Boolean = false,
    val elapsedSeconds: Int = 0,
    val errorMessage: String? = null,
)

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = (application as SummaryApplication).container.repository
    private val recorder = AudioRecorder(application)
    private val musicRecorder = AudioRecorder(application)
    private val _sessionState = MutableStateFlow(RecordingSessionState())
    private val _musicSearchSessionState = MutableStateFlow(MusicSearchSessionState())
    private var ticker: Job? = null
    private var musicTicker: Job? = null
    private var startedAtMillis: Long = 0L
    private var musicStartedAtMillis: Long = 0L
    private var pausedSeconds: Int = 0

    val sessionState: StateFlow<RecordingSessionState> = _sessionState.asStateFlow()
    val musicSearchSessionState: StateFlow<MusicSearchSessionState> = _musicSearchSessionState.asStateFlow()
    val recordings: Flow<List<RecordingEntity>> = repository.recordings
    val musicSearches: Flow<List<MusicSearchEntity>> = repository.musicSearches
    val isAuthenticated: Flow<Boolean> = repository.isAuthenticated

    fun observeRecording(localId: Long): Flow<RecordingEntity?> = repository.observeRecording(localId)
    fun observeMusicSearch(localId: Long): Flow<MusicSearchEntity?> = repository.observeMusicSearch(localId)

    fun login(email: String, password: String, onError: (String) -> Unit) {
        viewModelScope.launch {
            runCatching { repository.login(email, password) }
                .onFailure { onError(it.message ?: "로그인에 실패했습니다.") }
        }
    }

    fun register(email: String, password: String, onError: (String) -> Unit) {
        viewModelScope.launch {
            runCatching { repository.register(email, password) }
                .onFailure { onError(it.message ?: "가입에 실패했습니다.") }
        }
    }

    fun logout() {
        viewModelScope.launch { repository.logout() }
    }

    fun refreshStatus() {
        repository.enqueueSync()
    }

    fun startRecording(context: Context) {
        if (_musicSearchSessionState.value.isRecording) {
            _sessionState.value = RecordingSessionState(errorMessage = "노래찾기 녹음이 끝난 뒤 시작할 수 있습니다.")
            return
        }
        runCatching {
            val stamp = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(Date())
            val file = File(context.filesDir, "recordings/summary-$stamp.m4a")
            recorder.start(file)
            RecordingForegroundService.start(context)
            startedAtMillis = System.currentTimeMillis()
            pausedSeconds = 0
            _sessionState.value = RecordingSessionState(isRecording = true)
            startTicker()
        }.onFailure {
            _sessionState.value = RecordingSessionState(errorMessage = it.message ?: "녹음을 시작할 수 없습니다.")
        }
    }

    fun startMusicSearch(context: Context) {
        if (_sessionState.value.isRecording) {
            _musicSearchSessionState.value = MusicSearchSessionState(errorMessage = "녹음이 끝난 뒤 노래찾기를 시작할 수 있습니다.")
            return
        }
        runCatching {
            val stamp = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(Date())
            val file = File(context.filesDir, "music-searches/music-$stamp.m4a")
            musicRecorder.start(file, bitRate = AudioRecorder.MUSIC_SEARCH_BIT_RATE)
            RecordingForegroundService.start(context)
            musicStartedAtMillis = System.currentTimeMillis()
            _musicSearchSessionState.value = MusicSearchSessionState(isRecording = true)
            startMusicTicker(context)
        }.onFailure {
            _musicSearchSessionState.value = MusicSearchSessionState(errorMessage = it.message ?: "노래찾기 녹음을 시작할 수 없습니다.")
        }
    }

    fun pauseRecording() {
        recorder.pause()
        pausedSeconds = _sessionState.value.elapsedSeconds
        ticker?.cancel()
        _sessionState.value = _sessionState.value.copy(isPaused = true)
    }

    fun resumeRecording() {
        recorder.resume()
        startedAtMillis = System.currentTimeMillis()
        _sessionState.value = _sessionState.value.copy(isPaused = false)
        startTicker()
    }

    fun stopRecording(context: Context) {
        val elapsed = _sessionState.value.elapsedSeconds
        val file = recorder.stop()
        RecordingForegroundService.stop(context)
        ticker?.cancel()
        _sessionState.value = RecordingSessionState()
        if (file != null && file.length() > 0L) {
            viewModelScope.launch {
                repository.createLocalRecording(
                    title = "녹음 ${SimpleDateFormat("MM/dd HH:mm", Locale.KOREA).format(Date())}",
                    file = file,
                    durationSeconds = elapsed,
                )
            }
        }
    }

    fun stopMusicSearch(context: Context) {
        finishMusicSearch(context, _musicSearchSessionState.value.elapsedSeconds, cancelTicker = true)
    }

    fun updateLocalSummary(localId: Long, summaryJson: String) {
        viewModelScope.launch { repository.updateLocalSummary(localId, summaryJson) }
    }

    fun deleteRecording(localId: Long) {
        viewModelScope.launch { repository.deleteRecording(localId) }
    }

    fun deleteMusicSearch(localId: Long) {
        viewModelScope.launch { repository.deleteMusicSearch(localId) }
    }

    fun retryMusicSearch(localId: Long, onError: (String) -> Unit) {
        viewModelScope.launch {
            runCatching { repository.retryMusicSearch(localId) }
                .onFailure { onError(it.message ?: "다시 분석을 시작할 수 없습니다.") }
        }
    }

    override fun onCleared() {
        recorder.stopSilently()
        musicRecorder.stopSilently()
        ticker?.cancel()
        musicTicker?.cancel()
    }

    private fun startTicker() {
        ticker?.cancel()
        ticker = viewModelScope.launch {
            while (true) {
                val delta = ((System.currentTimeMillis() - startedAtMillis) / 1000).toInt()
                _sessionState.value = _sessionState.value.copy(elapsedSeconds = pausedSeconds + delta)
                delay(1000)
            }
        }
    }

    private fun startMusicTicker(context: Context) {
        musicTicker?.cancel()
        musicTicker = viewModelScope.launch {
            while (true) {
                val elapsed = ((System.currentTimeMillis() - musicStartedAtMillis) / 1000).toInt()
                    .coerceAtMost(MUSIC_SEARCH_SECONDS)
                _musicSearchSessionState.value = _musicSearchSessionState.value.copy(elapsedSeconds = elapsed)
                if (elapsed >= MUSIC_SEARCH_SECONDS) {
                    finishMusicSearch(context, MUSIC_SEARCH_SECONDS, cancelTicker = false)
                    break
                }
                delay(250)
            }
        }
    }

    private fun finishMusicSearch(context: Context, elapsed: Int, cancelTicker: Boolean) {
        if (cancelTicker) musicTicker?.cancel()
        musicTicker = null
        val file = musicRecorder.stop()
        RecordingForegroundService.stop(context)
        _musicSearchSessionState.value = MusicSearchSessionState()
        if (file != null && file.length() > 0L) {
            viewModelScope.launch {
                repository.createLocalMusicSearch(
                    file = file,
                    durationSeconds = elapsed.coerceAtMost(MUSIC_SEARCH_SECONDS),
                )
            }
        }
    }

    companion object {
        const val MUSIC_SEARCH_SECONDS = 12
    }
}
