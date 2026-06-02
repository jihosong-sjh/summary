package com.summary.app.data

import okhttp3.MediaType
import okhttp3.RequestBody
import okio.BufferedSink
import okio.source
import java.io.File

class ProgressRequestBody(
    private val file: File,
    private val contentType: MediaType?,
    private val onProgress: (Int) -> Unit,
) : RequestBody() {
    override fun contentType(): MediaType? = contentType

    override fun contentLength(): Long = file.length()

    override fun writeTo(sink: BufferedSink) {
        val total = contentLength().coerceAtLeast(1)
        var written = 0L
        file.source().use { source ->
            val buffer = okio.Buffer()
            while (true) {
                val read = source.read(buffer, 8 * 1024)
                if (read == -1L) break
                sink.write(buffer, read)
                written += read
                onProgress(((written * 100) / total).toInt().coerceIn(0, 100))
            }
        }
    }
}

