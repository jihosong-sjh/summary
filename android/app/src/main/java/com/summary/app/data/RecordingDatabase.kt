package com.summary.app.data

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(entities = [RecordingEntity::class, MusicSearchEntity::class], version = 2, exportSchema = false)
abstract class RecordingDatabase : RoomDatabase() {
    abstract fun recordingDao(): RecordingDao
    abstract fun musicSearchDao(): MusicSearchDao

    companion object {
        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS `music_searches` (
                        `localId` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                        `serverId` TEXT,
                        `filePath` TEXT NOT NULL,
                        `contentType` TEXT NOT NULL,
                        `durationSeconds` INTEGER,
                        `sizeBytes` INTEGER,
                        `status` TEXT NOT NULL,
                        `uploadProgress` INTEGER NOT NULL,
                        `transcriptExcerpt` TEXT,
                        `resultJson` TEXT,
                        `errorMessage` TEXT,
                        `createdAtMillis` INTEGER NOT NULL DEFAULT 0,
                        `updatedAtMillis` INTEGER NOT NULL DEFAULT 0
                    )
                    """.trimIndent(),
                )
            }
        }
    }
}
