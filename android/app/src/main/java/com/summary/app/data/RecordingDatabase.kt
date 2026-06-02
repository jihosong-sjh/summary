package com.summary.app.data

import androidx.room.Database
import androidx.room.RoomDatabase

@Database(entities = [RecordingEntity::class], version = 1, exportSchema = false)
abstract class RecordingDatabase : RoomDatabase() {
    abstract fun recordingDao(): RecordingDao
}
