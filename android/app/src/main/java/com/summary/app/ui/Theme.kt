package com.summary.app.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val ColorScheme = lightColorScheme(
    primary = Color(0xFF2458A6),
    secondary = Color(0xFF006D5B),
    tertiary = Color(0xFF8A4B22),
    surface = Color(0xFFFAFBFD),
    background = Color(0xFFF7F8FA),
)

@Composable
fun SummaryTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = ColorScheme, content = content)
}

