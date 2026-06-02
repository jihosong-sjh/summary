package com.summary.app.data

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import kotlinx.coroutines.flow.Flow

@Dao
interface RecordingDao {
    @Query("SELECT * FROM recordings WHERE status != 'DELETED' ORDER BY createdAtMillis DESC")
    fun observeAll(): Flow<List<RecordingEntity>>

    @Query("SELECT * FROM recordings WHERE localId = :localId LIMIT 1")
    fun observeById(localId: Long): Flow<RecordingEntity?>

    @Query("SELECT * FROM recordings WHERE localId = :localId LIMIT 1")
    suspend fun getById(localId: Long): RecordingEntity?

    @Query("SELECT * FROM recordings WHERE serverId = :serverId LIMIT 1")
    suspend fun getByServerId(serverId: String): RecordingEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(recording: RecordingEntity): Long

    @Update
    suspend fun update(recording: RecordingEntity)

    @Delete
    suspend fun delete(recording: RecordingEntity)
}

