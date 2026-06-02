package com.summary.app.data

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.summary.app.SummaryApplication

class StatusSyncWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        val repository = (applicationContext as SummaryApplication).container.repository
        return runCatching {
            val hasPendingRemoteWork = repository.syncRemote()
            if (hasPendingRemoteWork) {
                repository.enqueueSync(SYNC_POLL_DELAY_SECONDS)
            }
            Result.success()
        }.getOrElse {
            if (runAttemptCount < 5) Result.retry() else Result.failure()
        }
    }

    companion object {
        private const val SYNC_POLL_DELAY_SECONDS = 3L
    }
}
