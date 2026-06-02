package com.summary.app.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.authDataStore by preferencesDataStore(name = "auth")

class AuthStore(private val context: Context) {
    private val accessTokenKey = stringPreferencesKey("access_token")
    private val refreshTokenKey = stringPreferencesKey("refresh_token")

    val accessToken: Flow<String?> = context.authDataStore.data.map { it[accessTokenKey] }
    val refreshToken: Flow<String?> = context.authDataStore.data.map { it[refreshTokenKey] }
    val isAuthenticated: Flow<Boolean> = accessToken.map { !it.isNullOrBlank() }

    suspend fun save(pair: TokenPair) {
        context.authDataStore.edit {
            it[accessTokenKey] = pair.accessToken
            it[refreshTokenKey] = pair.refreshToken
        }
    }

    suspend fun clear() {
        context.authDataStore.edit { it.clear() }
    }
}

