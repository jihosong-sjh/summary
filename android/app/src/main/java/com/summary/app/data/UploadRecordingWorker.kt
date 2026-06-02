package com.summary.app.data

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.summary.app.SummaryApplication

class UploadRecordingWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        val localId = inputData.getLong(KEY_LOCAL_ID, -1)
        if (localId <= 0) return Result.failure()
        val repository = (applicationContext as SummaryApplication).container.repository
        return runCatching {
            repository.uploadRecording(localId)
            Result.success()
        }.getOrElse {
            val retrying = runAttemptCount < MAX_RETRY_ATTEMPTS
            repository.markRecordingUploadError(localId, it.uploadErrorMessage(), retrying)
            if (retrying) Result.retry() else Result.failure()
        }
    }

    companion object {
        const val KEY_LOCAL_ID = "local_id"
        private const val MAX_RETRY_ATTEMPTS = 5
    }
}
