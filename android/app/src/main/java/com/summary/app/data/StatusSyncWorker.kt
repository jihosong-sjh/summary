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
            repository.syncRemote()
            Result.success()
        }.getOrElse {
            if (runAttemptCount < 5) Result.retry() else Result.failure()
        }
    }
}

