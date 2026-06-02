package com.summary.app.data

import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path

interface SummaryApi {
    @POST("auth/register")
    suspend fun register(@Body body: AuthRequest): TokenPair

    @POST("auth/login")
    suspend fun login(@Body body: AuthRequest): TokenPair

    @POST("auth/refresh")
    suspend fun refresh(@Body body: RefreshRequest): TokenPair

    @GET("recordings")
    suspend fun recordings(): List<RecordingResponse>

    @POST("recordings")
    suspend fun createRecording(@Body body: RecordingCreate): RecordingResponse

    @GET("recordings/{id}")
    suspend fun recording(@Path("id") id: String): RecordingResponse

    @PATCH("recordings/{id}")
    suspend fun updateRecording(@Path("id") id: String, @Body body: Map<String, String>): RecordingResponse

    @DELETE("recordings/{id}")
    suspend fun deleteRecording(@Path("id") id: String)

    @POST("recordings/{id}/upload-url")
    suspend fun uploadUrl(@Path("id") id: String, @Body body: UploadUrlRequest): UploadUrlResponse

    @POST("recordings/{id}/complete-upload")
    suspend fun completeUpload(@Path("id") id: String, @Body body: CompleteUploadRequest): RecordingResponse

    @POST("recordings/{id}/retry")
    suspend fun retry(@Path("id") id: String): RecordingResponse

    @GET("recordings/{id}/transcript")
    suspend fun transcript(@Path("id") id: String): TranscriptResponse

    @GET("recordings/{id}/summary")
    suspend fun summary(@Path("id") id: String): SummaryResponse

    @PATCH("recordings/{id}/summary")
    suspend fun updateSummary(@Path("id") id: String, @Body body: Map<String, SummaryPayload>): SummaryResponse

    @GET("music-searches")
    suspend fun musicSearches(): List<MusicSearchResponse>

    @POST("music-searches")
    suspend fun createMusicSearch(@Body body: MusicSearchCreate): MusicSearchResponse

    @GET("music-searches/{id}")
    suspend fun musicSearch(@Path("id") id: String): MusicSearchResponse

    @DELETE("music-searches/{id}")
    suspend fun deleteMusicSearch(@Path("id") id: String)

    @POST("music-searches/{id}/upload-url")
    suspend fun musicSearchUploadUrl(@Path("id") id: String, @Body body: UploadUrlRequest): UploadUrlResponse

    @POST("music-searches/{id}/complete-upload")
    suspend fun completeMusicSearchUpload(@Path("id") id: String, @Body body: CompleteUploadRequest): MusicSearchResponse

    @POST("music-searches/{id}/retry")
    suspend fun retryMusicSearch(@Path("id") id: String): MusicSearchResponse
}
