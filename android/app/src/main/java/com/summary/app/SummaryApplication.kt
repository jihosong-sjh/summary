package com.summary.app

import android.app.Application
import androidx.room.Room
import androidx.work.WorkManager
import com.google.gson.Gson
import com.summary.app.data.AuthStore
import com.summary.app.data.RecordingDatabase
import com.summary.app.data.RecordingRepository
import com.summary.app.data.RefreshRequest
import com.summary.app.data.SummaryApi
import com.summary.app.data.TokenPair
import kotlinx.coroutines.flow.firstOrNull
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

class SummaryApplication : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }
}

class AppContainer(private val application: Application) {
    private val gson = Gson()
    val authStore = AuthStore(application)
    private val database = Room.databaseBuilder(
        application,
        RecordingDatabase::class.java,
        "summary.db",
    ).addMigrations(RecordingDatabase.MIGRATION_1_2).build()

    private val tokenRefreshClient = OkHttpClient()

    private val authClient = OkHttpClient.Builder()
        .addInterceptor(Interceptor { chain ->
            val original = chain.request()
            val token = runBlocking { authStore.accessToken.firstOrNull() }
            val request = if (!token.isNullOrBlank()) {
                original.newBuilder()
                    .header("Authorization", "Bearer $token")
                    .build()
            } else {
                original
            }
            val response = chain.proceed(request)
            if (response.code != 401 || original.url.encodedPath.startsWith("/auth/")) {
                return@Interceptor response
            }

            val refreshToken = runBlocking { authStore.refreshToken.firstOrNull() }
            if (refreshToken.isNullOrBlank()) {
                return@Interceptor response
            }

            val refreshed = refreshAccessToken(refreshToken) ?: return@Interceptor response
            response.close()
            runBlocking { authStore.save(refreshed) }
            chain.proceed(
                original.newBuilder()
                    .header("Authorization", "Bearer ${refreshed.accessToken}")
                    .build(),
            )
        })
        .build()

    private val retrofit = Retrofit.Builder()
        .baseUrl(BuildConfig.API_BASE_URL)
        .client(authClient)
        .addConverterFactory(GsonConverterFactory.create(gson))
        .build()

    val repository = RecordingRepository(
        context = application,
        api = retrofit.create(SummaryApi::class.java),
        authStore = authStore,
        dao = database.recordingDao(),
        musicSearchDao = database.musicSearchDao(),
        workManager = WorkManager.getInstance(application),
        uploadClient = OkHttpClient(),
        gson = gson,
    )

    private fun refreshAccessToken(refreshToken: String): TokenPair? {
        val body = gson.toJson(RefreshRequest(refreshToken))
            .toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url("${BuildConfig.API_BASE_URL.trimEnd('/')}/auth/refresh")
            .post(body)
            .build()
        return runCatching {
            tokenRefreshClient.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return null
                response.body?.string()?.let { gson.fromJson(it, TokenPair::class.java) }
            }
        }.getOrNull()
    }
}
