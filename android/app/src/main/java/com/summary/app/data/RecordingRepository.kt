package com.summary.app.data

import android.content.Context
import androidx.work.Constraints
import androidx.work.Data
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import com.google.gson.Gson
import com.summary.app.data.UploadRecordingWorker.Companion.KEY_LOCAL_ID
import kotlinx.coroutines.flow.Flow
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File

class RecordingRepository(
    private val context: Context,
    private val api: SummaryApi,
    private val authStore: AuthStore,
    private val dao: RecordingDao,
    private val workManager: WorkManager,
    private val uploadClient: OkHttpClient,
    private val gson: Gson,
) {
    val recordings: Flow<List<RecordingEntity>> = dao.observeAll()
    val isAuthenticated: Flow<Boolean> = authStore.isAuthenticated

    fun observeRecording(localId: Long): Flow<RecordingEntity?> = dao.observeById(localId)

    suspend fun login(email: String, password: String) {
        authStore.save(api.login(AuthRequest(email, password)))
    }

    suspend fun register(email: String, password: String) {
        authStore.save(api.register(AuthRequest(email, password)))
    }

    suspend fun logout() {
        authStore.clear()
    }

    suspend fun createLocalRecording(title: String, file: File, durationSeconds: Int?): Long {
        val entity = RecordingEntity(
            title = title,
            filePath = file.absolutePath,
            durationSeconds = durationSeconds,
            sizeBytes = file.length(),
            status = LocalRecordingStatus.LOCAL,
            createdAtMillis = System.currentTimeMillis(),
            updatedAtMillis = System.currentTimeMillis(),
        )
        val id = dao.insert(entity)
        enqueueUpload(id)
        return id
    }

    fun enqueueUpload(localId: Long) {
        val request = OneTimeWorkRequestBuilder<UploadRecordingWorker>()
            .setConstraints(Constraints(requiredNetworkType = NetworkType.CONNECTED))
            .setInputData(Data.Builder().putLong(KEY_LOCAL_ID, localId).build())
            .build()
        workManager.enqueue(request)
    }

    fun enqueueSync() {
        val request = OneTimeWorkRequestBuilder<StatusSyncWorker>()
            .setConstraints(Constraints(requiredNetworkType = NetworkType.CONNECTED))
            .build()
        workManager.enqueue(request)
    }

    suspend fun uploadRecording(localId: Long) {
        val local = dao.getById(localId) ?: return
        val file = File(local.filePath)
        if (!file.exists()) {
            dao.update(local.copy(status = LocalRecordingStatus.FAILED, errorMessage = "Local file missing"))
            return
        }

        dao.update(local.copy(status = LocalRecordingStatus.UPLOADING, uploadProgress = 0, errorMessage = null))
        val created = if (local.serverId == null) {
            api.createRecording(
                RecordingCreate(
                    title = local.title,
                    durationSeconds = local.durationSeconds,
                    contentType = local.contentType,
                ),
            )
        } else {
            api.recording(local.serverId)
        }
        dao.update(
            (dao.getById(localId) ?: local).copy(
                serverId = created.id,
                status = remoteToLocalStatus(created.status),
                updatedAtMillis = System.currentTimeMillis(),
            ),
        )

        val upload = api.uploadUrl(created.id, UploadUrlRequest(local.contentType, file.name))
        val mediaType = local.contentType.toMediaTypeOrNull()
        val body = ProgressRequestBody(file, mediaType) { progress ->
            val current = daoSnapshot(localId) ?: return@ProgressRequestBody
            runCatching {
                kotlinx.coroutines.runBlocking {
                    dao.update(current.copy(uploadProgress = progress, updatedAtMillis = System.currentTimeMillis()))
                }
            }
        }
        val response = uploadClient.newCall(
            Request.Builder()
                .url(upload.uploadUrl)
                .put(body)
                .header("Content-Type", local.contentType)
                .build(),
        ).execute()
        response.use {
            if (!it.isSuccessful) error("Upload failed: HTTP ${it.code}")
        }

        val completed = api.completeUpload(
            created.id,
            CompleteUploadRequest(file.length().toInt(), local.durationSeconds),
        )
        dao.update(
            (dao.getById(localId) ?: local).copy(
                serverId = completed.id,
                status = remoteToLocalStatus(completed.status),
                uploadProgress = 100,
                updatedAtMillis = System.currentTimeMillis(),
            ),
        )
        enqueueSync()
    }

    suspend fun syncRemote() {
        api.recordings().forEach { remote ->
            val local = dao.getByServerId(remote.id) ?: return@forEach
            val status = remoteToLocalStatus(remote.status)
            var transcript: String? = local.transcript
            var summaryJson: String? = local.summaryJson
            if (status == LocalRecordingStatus.COMPLETED) {
                transcript = runCatching { api.transcript(remote.id).rawText }.getOrNull() ?: transcript
                summaryJson = runCatching { gson.toJson(api.summary(remote.id).data) }.getOrNull() ?: summaryJson
            }
            dao.update(
                local.copy(
                    title = remote.title,
                    status = status,
                    transcript = transcript,
                    summaryJson = summaryJson,
                    errorMessage = remote.errorMessage,
                    updatedAtMillis = System.currentTimeMillis(),
                ),
            )
        }
    }

    suspend fun updateLocalSummary(localId: Long, summaryJson: String) {
        val local = dao.getById(localId) ?: return
        dao.update(local.copy(summaryJson = summaryJson, updatedAtMillis = System.currentTimeMillis()))
    }

    suspend fun deleteRecording(localId: Long) {
        val local = dao.getById(localId) ?: return
        if (local.serverId != null) {
            runCatching { api.deleteRecording(local.serverId) }
        }
        dao.update(local.copy(status = LocalRecordingStatus.DELETED, updatedAtMillis = System.currentTimeMillis()))
    }

    private fun remoteToLocalStatus(status: String): LocalRecordingStatus = when (status) {
        "created" -> LocalRecordingStatus.LOCAL
        "uploading" -> LocalRecordingStatus.UPLOADING
        "uploaded" -> LocalRecordingStatus.UPLOADED
        "transcribing" -> LocalRecordingStatus.TRANSCRIBING
        "summarizing" -> LocalRecordingStatus.SUMMARIZING
        "completed" -> LocalRecordingStatus.COMPLETED
        "deleted" -> LocalRecordingStatus.DELETED
        else -> LocalRecordingStatus.FAILED
    }

    private fun daoSnapshot(localId: Long): RecordingEntity? = kotlinx.coroutines.runBlocking {
        dao.getById(localId)
    }
}

