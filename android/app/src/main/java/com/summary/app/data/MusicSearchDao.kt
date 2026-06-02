package com.summary.app.data

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import kotlinx.coroutines.flow.Flow

@Dao
interface MusicSearchDao {
    @Query("SELECT * FROM music_searches WHERE status != 'DELETED' ORDER BY createdAtMillis DESC")
    fun observeAll(): Flow<List<MusicSearchEntity>>

    @Query("SELECT * FROM music_searches WHERE localId = :localId LIMIT 1")
    fun observeById(localId: Long): Flow<MusicSearchEntity?>

    @Query("SELECT * FROM music_searches WHERE localId = :localId LIMIT 1")
    suspend fun getById(localId: Long): MusicSearchEntity?

    @Query("SELECT * FROM music_searches WHERE serverId = :serverId LIMIT 1")
    suspend fun getByServerId(serverId: String): MusicSearchEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(musicSearch: MusicSearchEntity): Long

    @Update
    suspend fun update(musicSearch: MusicSearchEntity)

    @Delete
    suspend fun delete(musicSearch: MusicSearchEntity)
}
