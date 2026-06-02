package com.summary.app.data

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

enum class LocalMusicSearchStatus {
    LOCAL,
    UPLOADING,
    UPLOADED,
    ANALYZING,
    COMPLETED,
    FAILED,
    DELETED,
}

@Entity(tableName = "music_searches")
data class MusicSearchEntity(
    @PrimaryKey(autoGenerate = true) val localId: Long = 0,
    val serverId: String? = null,
    val filePath: String,
    val contentType: String = "audio/mp4",
    val durationSeconds: Int? = null,
    val sizeBytes: Long? = null,
    val status: LocalMusicSearchStatus = LocalMusicSearchStatus.LOCAL,
    val uploadProgress: Int = 0,
    val transcriptExcerpt: String? = null,
    val resultJson: String? = null,
    val errorMessage: String? = null,
    @ColumnInfo(defaultValue = "0") val createdAtMillis: Long = System.currentTimeMillis(),
    @ColumnInfo(defaultValue = "0") val updatedAtMillis: Long = System.currentTimeMillis(),
)
