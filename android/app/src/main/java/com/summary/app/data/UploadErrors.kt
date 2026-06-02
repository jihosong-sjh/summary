package com.summary.app.data

internal fun Throwable.uploadErrorMessage(): String {
    val raw = message?.takeIf { it.isNotBlank() } ?: javaClass.simpleName
    return raw.replace('\n', ' ').take(240)
}
