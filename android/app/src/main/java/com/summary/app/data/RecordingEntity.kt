package com.summary.app.data

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

enum class LocalRecordingStatus {
    LOCAL,
    UPLOADING,
    UPLOADED,
    TRANSCRIBING,
    SUMMARIZING,
    COMPLETED,
    FAILED,
    DELETED,
}

@Entity(tableName = "recordings")
data class RecordingEntity(
    @PrimaryKey(autoGenerate = true) val localId: Long = 0,
    val serverId: String? = null,
    val title: String,
    val filePath: String,
    val contentType: String = "audio/mp4",
    val durationSeconds: Int? = null,
    val sizeBytes: Long? = null,
    val status: LocalRecordingStatus = LocalRecordingStatus.LOCAL,
    val uploadProgress: Int = 0,
    val transcript: String? = null,
    val summaryJson: String? = null,
    val errorMessage: String? = null,
    @ColumnInfo(defaultValue = "0") val createdAtMillis: Long = System.currentTimeMillis(),
    @ColumnInfo(defaultValue = "0") val updatedAtMillis: Long = System.currentTimeMillis(),
)

