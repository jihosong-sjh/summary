package com.summary.app.recording

import android.content.Context
import android.media.MediaRecorder
import android.os.Build
import java.io.File

class AudioRecorder(private val context: Context) {
    private var recorder: MediaRecorder? = null
    var outputFile: File? = null
        private set

    fun start(file: File) {
        stopSilently()
        file.parentFile?.mkdirs()
        outputFile = file
        recorder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) MediaRecorder(context) else MediaRecorder()
        recorder?.apply {
            setAudioSource(MediaRecorder.AudioSource.MIC)
            setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            setAudioChannels(1)
            setAudioSamplingRate(44_100)
            setAudioEncodingBitRate(48_000)
            setOutputFile(file.absolutePath)
            prepare()
            start()
        }
    }

    fun pause() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            recorder?.pause()
        }
    }

    fun resume() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            recorder?.resume()
        }
    }

    fun stop(): File? {
        val file = outputFile
        recorder?.runCatching { stop() }
        recorder?.release()
        recorder = null
        outputFile = null
        return file
    }

    fun stopSilently() {
        runCatching { stop() }
    }
}

