package com.summary.app.data

import com.google.gson.annotations.SerializedName

data class AuthRequest(val email: String, val password: String)

data class RefreshRequest(@SerializedName("refresh_token") val refreshToken: String)

data class TokenPair(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("refresh_token") val refreshToken: String,
    @SerializedName("token_type") val tokenType: String,
)

data class RecordingCreate(
    val title: String,
    @SerializedName("duration_seconds") val durationSeconds: Int?,
    @SerializedName("content_type") val contentType: String = "audio/mp4",
)

data class MusicSearchCreate(
    @SerializedName("duration_seconds") val durationSeconds: Int?,
    @SerializedName("content_type") val contentType: String = "audio/mp4",
)

data class RecordingResponse(
    val id: String,
    val title: String,
    @SerializedName("content_type") val contentType: String,
    @SerializedName("size_bytes") val sizeBytes: Int?,
    @SerializedName("duration_seconds") val durationSeconds: Int?,
    val status: String,
    @SerializedName("error_message") val errorMessage: String?,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String,
)

data class UploadUrlRequest(
    @SerializedName("content_type") val contentType: String = "audio/mp4",
    @SerializedName("file_name") val fileName: String?,
)

data class UploadUrlResponse(
    @SerializedName("upload_url") val uploadUrl: String,
    @SerializedName("object_key") val objectKey: String,
    @SerializedName("expires_in") val expiresIn: Int,
)

data class CompleteUploadRequest(
    @SerializedName("size_bytes") val sizeBytes: Int,
    @SerializedName("duration_seconds") val durationSeconds: Int?,
)

data class TranscriptResponse(
    @SerializedName("recording_id") val recordingId: String,
    @SerializedName("raw_text") val rawText: String,
    val language: String?,
    @SerializedName("updated_at") val updatedAt: String,
)

data class SummaryPayload(
    val title: String,
    val overview: String,
    @SerializedName("key_points") val keyPoints: List<String>,
    val topics: List<String>,
    val decisions: List<String>,
    @SerializedName("action_items") val actionItems: List<String>,
    val risks: List<String>,
    @SerializedName("next_steps") val nextSteps: List<String>,
)

data class SummaryResponse(
    @SerializedName("recording_id") val recordingId: String,
    val data: SummaryPayload,
    val edited: Boolean,
    @SerializedName("updated_at") val updatedAt: String,
)

data class MusicCandidate(
    val title: String,
    val artist: String,
    val album: String?,
    @SerializedName("release_year") val releaseYear: Int?,
    val confidence: Double,
    @SerializedName("match_reason") val matchReason: String,
    @SerializedName("source_urls") val sourceUrls: List<String>,
)

data class MusicSearchResult(
    @SerializedName("query_text") val queryText: String,
    val candidates: List<MusicCandidate>,
    @SerializedName("no_match_reason") val noMatchReason: String?,
    val sources: List<String>,
)

data class MusicSearchResponse(
    val id: String,
    @SerializedName("content_type") val contentType: String,
    @SerializedName("size_bytes") val sizeBytes: Int?,
    @SerializedName("duration_seconds") val durationSeconds: Int?,
    val status: String,
    @SerializedName("error_message") val errorMessage: String?,
    @SerializedName("transcript_excerpt") val transcriptExcerpt: String?,
    val result: MusicSearchResult?,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String,
)
