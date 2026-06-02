package com.summary.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MusicNote
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Save
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.ScrollableTabRow
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.google.gson.Gson
import com.summary.app.data.LocalMusicSearchStatus
import com.summary.app.data.LocalRecordingStatus
import com.summary.app.data.MusicCandidate
import com.summary.app.data.MusicSearchEntity
import com.summary.app.data.MusicSearchResult
import com.summary.app.data.RecordingEntity
import com.summary.app.data.SummaryPayload
import com.summary.app.ui.MainViewModel
import com.summary.app.ui.SummaryTheme
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private val summaryFormatterGson = Gson()
private val musicFormatterGson = Gson()

private enum class HomeTab {
    RECORDINGS,
    MUSIC,
}

class MainActivity : ComponentActivity() {
    private val viewModel: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            SummaryTheme {
                SummaryApp(viewModel)
            }
        }
    }
}

@Composable
fun SummaryApp(viewModel: MainViewModel) {
    val navController = rememberNavController()
    val authenticated by viewModel.isAuthenticated.collectAsStateWithLifecycle(initialValue = false)

    LaunchedEffect(authenticated) {
        if (authenticated) {
            navController.navigate("consent") { popUpTo("auth") { inclusive = true } }
        } else {
            navController.navigate("auth") { popUpTo(0) }
        }
    }

    NavHost(navController = navController, startDestination = "auth") {
        composable("auth") { AuthScreen(viewModel) }
        composable("consent") { ConsentScreen(onContinue = { navController.navigate("home") }) }
        composable("home") { HomeScreen(viewModel, navController) }
        composable("record") { RecorderScreen(viewModel, navController) }
        composable("settings") { SettingsScreen(viewModel, navController) }
        composable("detail/{localId}") { entry ->
            val id = entry.arguments?.getString("localId")?.toLongOrNull()
            if (id != null) DetailScreen(viewModel, navController, id)
        }
        composable("music-detail/{localId}") { entry ->
            val id = entry.arguments?.getString("localId")?.toLongOrNull()
            if (id != null) MusicSearchDetailScreen(viewModel, navController, id)
        }
    }
}

@Composable
private fun AuthScreen(viewModel: MainViewModel) {
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var isRegister by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    Box(modifier = Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
        Column(verticalArrangement = Arrangement.spacedBy(14.dp), modifier = Modifier.fillMaxWidth()) {
            Text("Summary", style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
            OutlinedTextField(email, { email = it }, label = { Text("이메일") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(
                password,
                { password = it },
                label = { Text("비밀번호") },
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                modifier = Modifier.fillMaxWidth(),
            )
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Button(
                onClick = {
                    error = null
                    if (isRegister) viewModel.register(email, password) { error = it }
                    else viewModel.login(email, password) { error = it }
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (isRegister) "가입" else "로그인")
            }
            TextButton(onClick = { isRegister = !isRegister }) {
                Text(if (isRegister) "로그인으로 돌아가기" else "새 계정 만들기")
            }
        }
    }
}

@Composable
private fun ConsentScreen(onContinue: () -> Unit) {
    Scaffold(topBar = { AppTopBar(title = "녹음 동의") }) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            Text(
                "녹음 전 참석자 동의가 필요할 수 있습니다. 음성 파일은 서버로 업로드되어 텍스트 변환과 요약 처리에 사용되며, 삭제하면 서버의 음성 파일과 결과도 삭제됩니다.",
                style = MaterialTheme.typography.bodyLarge,
            )
            Button(onClick = onContinue, modifier = Modifier.fillMaxWidth()) {
                Text("동의하고 시작")
            }
        }
    }
}

@Composable
@OptIn(ExperimentalMaterial3Api::class)
private fun HomeScreen(viewModel: MainViewModel, navController: NavHostController) {
    var selectedTab by remember { mutableStateOf(HomeTab.RECORDINGS) }

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = { Text(if (selectedTab == HomeTab.RECORDINGS) "녹음" else "노래찾기") },
                actions = {
                    IconButton(onClick = { viewModel.refreshStatus() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "새로고침")
                    }
                    IconButton(onClick = { navController.navigate("settings") }) {
                        Icon(Icons.Default.Settings, contentDescription = "설정")
                    }
                },
            )
        },
        bottomBar = {
            NavigationBar {
                NavigationBarItem(
                    selected = selectedTab == HomeTab.RECORDINGS,
                    onClick = { selectedTab = HomeTab.RECORDINGS },
                    icon = { Icon(Icons.Default.Mic, contentDescription = null) },
                    label = { Text("녹음") },
                )
                NavigationBarItem(
                    selected = selectedTab == HomeTab.MUSIC,
                    onClick = { selectedTab = HomeTab.MUSIC },
                    icon = { Icon(Icons.Default.MusicNote, contentDescription = null) },
                    label = { Text("노래찾기") },
                )
            }
        },
        floatingActionButton = {
            if (selectedTab == HomeTab.RECORDINGS) {
                FloatingActionButton(onClick = { navController.navigate("record") }) {
                    Icon(Icons.Default.Mic, contentDescription = "녹음")
                }
            }
        },
    ) { padding ->
        when (selectedTab) {
            HomeTab.RECORDINGS -> RecordingListContent(
                viewModel = viewModel,
                navController = navController,
                modifier = Modifier.padding(padding),
            )
            HomeTab.MUSIC -> MusicSearchTab(
                viewModel = viewModel,
                navController = navController,
                modifier = Modifier.padding(padding),
            )
        }
    }
}

@Composable
private fun RecordingListContent(
    viewModel: MainViewModel,
    navController: NavHostController,
    modifier: Modifier = Modifier,
) {
    val recordings by viewModel.recordings.collectAsStateWithLifecycle(initialValue = emptyList())

    if (recordings.isEmpty()) {
        Box(modifier = modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text("저장된 녹음이 없습니다.")
        }
    } else {
        LazyColumn(
            modifier = modifier.fillMaxSize().padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            items(recordings, key = { it.localId }) { recording ->
                RecordingRow(recording, onClick = { navController.navigate("detail/${recording.localId}") })
            }
        }
    }
}

@Composable
private fun MusicSearchTab(
    viewModel: MainViewModel,
    navController: NavHostController,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val session by viewModel.musicSearchSessionState.collectAsStateWithLifecycle()
    val musicSearches by viewModel.musicSearches.collectAsStateWithLifecycle(initialValue = emptyList())
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        val audioGranted = result[Manifest.permission.RECORD_AUDIO] == true
        if (audioGranted) viewModel.startMusicSearch(context)
        else Toast.makeText(context, "마이크 권한이 필요합니다.", Toast.LENGTH_SHORT).show()
    }

    LazyColumn(
        modifier = modifier.fillMaxSize().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            MusicCapturePanel(
                elapsedSeconds = session.elapsedSeconds,
                isRecording = session.isRecording,
                errorMessage = session.errorMessage,
                onStart = {
                    val permissions = buildList {
                        add(Manifest.permission.RECORD_AUDIO)
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) add(Manifest.permission.POST_NOTIFICATIONS)
                    }
                    val hasAudio = ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
                    val hasNotification = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
                        ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
                    if (hasAudio && hasNotification) viewModel.startMusicSearch(context) else permissionLauncher.launch(permissions.toTypedArray())
                },
                onStop = { viewModel.stopMusicSearch(context) },
            )
        }
        if (musicSearches.isEmpty()) {
            item {
                Box(modifier = Modifier.fillMaxWidth().padding(vertical = 48.dp), contentAlignment = Alignment.Center) {
                    Text("최근 노래찾기 기록이 없습니다.")
                }
            }
        } else {
            items(musicSearches, key = { it.localId }) { musicSearch ->
                MusicSearchRow(musicSearch, onClick = { navController.navigate("music-detail/${musicSearch.localId}") })
            }
        }
    }
}

@Composable
private fun MusicCapturePanel(
    elapsedSeconds: Int,
    isRecording: Boolean,
    errorMessage: String?,
    onStart: () -> Unit,
    onStop: () -> Unit,
) {
    Card(
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Icon(Icons.Default.MusicNote, contentDescription = null)
                Column(modifier = Modifier.weight(1f)) {
                    Text("12초 노래찾기", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text("${formatDuration(elapsedSeconds)} / ${formatDuration(MainViewModel.MUSIC_SEARCH_SECONDS)}")
                }
                if (isRecording) {
                    FilledTonalButton(onClick = onStop) {
                        Icon(Icons.Default.Stop, contentDescription = null)
                        Text("중지")
                    }
                } else {
                    FilledTonalButton(onClick = onStart) {
                        Icon(Icons.Default.Mic, contentDescription = null)
                        Text("시작")
                    }
                }
            }
            LinearProgressIndicator(
                progress = { elapsedSeconds / MainViewModel.MUSIC_SEARCH_SECONDS.toFloat() },
                modifier = Modifier.fillMaxWidth(),
            )
            errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        }
    }
}

@Composable
private fun MusicSearchRow(musicSearch: MusicSearchEntity, onClick: () -> Unit) {
    val result = parseMusicSearchResult(musicSearch.resultJson)
    val bestCandidate = result?.candidates?.firstOrNull()
    val title = bestCandidate?.let { "${it.title} - ${it.artist}" }
        ?: result?.noMatchReason
        ?: "노래찾기 ${formatDate(musicSearch.createdAtMillis)}"

    Card(
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text("${musicSearchStatusLabel(musicSearch.status)} · ${formatDuration(musicSearch.durationSeconds ?: 0)}")
            if (musicSearch.status == LocalMusicSearchStatus.UPLOADING) {
                Text("업로드 ${musicSearch.uploadProgress}%")
            }
            musicSearch.transcriptExcerpt?.takeIf { it.isNotBlank() }?.let {
                Text(it, maxLines = 2, overflow = TextOverflow.Ellipsis)
            }
            musicSearch.errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error, maxLines = 2) }
        }
    }
}

@Composable
private fun RecordingRow(recording: RecordingEntity, onClick: () -> Unit) {
    Card(
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(recording.title, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text("${statusLabel(recording.status)} · ${formatDuration(recording.durationSeconds ?: 0)}")
            if (recording.status == LocalRecordingStatus.UPLOADING) {
                Text("업로드 ${recording.uploadProgress}%")
            }
            recording.errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error, maxLines = 2) }
        }
    }
}

@Composable
private fun RecorderScreen(viewModel: MainViewModel, navController: NavHostController) {
    val context = LocalContext.current
    val session by viewModel.sessionState.collectAsStateWithLifecycle()
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        val audioGranted = result[Manifest.permission.RECORD_AUDIO] == true
        if (audioGranted) viewModel.startRecording(context)
        else Toast.makeText(context, "마이크 권한이 필요합니다.", Toast.LENGTH_SHORT).show()
    }

    Scaffold(topBar = { AppTopBar("새 녹음", navController) }) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Text(formatDuration(session.elapsedSeconds), style = MaterialTheme.typography.displayMedium, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(28.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(14.dp), verticalAlignment = Alignment.CenterVertically) {
                if (!session.isRecording) {
                    FilledIconButton(onClick = {
                        val permissions = buildList {
                            add(Manifest.permission.RECORD_AUDIO)
                            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) add(Manifest.permission.POST_NOTIFICATIONS)
                        }
                        val hasAudio = ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
                        val hasNotification = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
                            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
                        if (hasAudio && hasNotification) viewModel.startRecording(context) else permissionLauncher.launch(permissions.toTypedArray())
                    }) {
                        Icon(Icons.Default.Mic, contentDescription = "시작")
                    }
                } else {
                    FilledIconButton(onClick = {
                        if (session.isPaused) viewModel.resumeRecording() else viewModel.pauseRecording()
                    }) {
                        Icon(if (session.isPaused) Icons.Default.PlayArrow else Icons.Default.Pause, contentDescription = "일시정지")
                    }
                    FilledIconButton(onClick = {
                        viewModel.stopRecording(context)
                        navController.popBackStack()
                    }) {
                        Icon(Icons.Default.Stop, contentDescription = "종료")
                    }
                }
            }
            session.errorMessage?.let {
                Spacer(Modifier.height(16.dp))
                Text(it, color = MaterialTheme.colorScheme.error)
            }
        }
    }
}

@Composable
private fun DetailScreen(viewModel: MainViewModel, navController: NavHostController, localId: Long) {
    val recording by viewModel.observeRecording(localId).collectAsStateWithLifecycle(initialValue = null)
    var tab by remember { mutableIntStateOf(0) }

    Scaffold(topBar = { AppTopBar(recording?.title ?: "상세", navController) }) { padding ->
        if (recording == null) {
            Box(modifier = Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                Text("녹음을 찾을 수 없습니다.")
            }
            return@Scaffold
        }

        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            ScrollableTabRow(selectedTabIndex = tab, edgePadding = 12.dp) {
                listOf("요약", "원문", "파일 정보").forEachIndexed { index, label ->
                    Tab(selected = tab == index, onClick = { tab = index }, text = { Text(label) })
                }
            }
            when (tab) {
                0 -> SummaryTab(recording!!, viewModel)
                1 -> TextTab(recording!!.transcript ?: "원문이 아직 준비되지 않았습니다.")
                2 -> FileInfoTab(recording!!, onDelete = {
                    viewModel.deleteRecording(localId)
                    navController.popBackStack()
                })
            }
        }
    }
}

@Composable
private fun MusicSearchDetailScreen(viewModel: MainViewModel, navController: NavHostController, localId: Long) {
    val musicSearch by viewModel.observeMusicSearch(localId).collectAsStateWithLifecycle(initialValue = null)
    val context = LocalContext.current

    Scaffold(topBar = { AppTopBar("찾은 곡 후보", navController) }) { padding ->
        if (musicSearch == null) {
            Box(modifier = Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                Text("노래찾기 기록을 찾을 수 없습니다.")
            }
            return@Scaffold
        }

        val result = parseMusicSearchResult(musicSearch!!.resultJson)
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("상태: ${musicSearchStatusLabel(musicSearch!!.status)}")
                    Text("길이: ${formatDuration(musicSearch!!.durationSeconds ?: 0)}")
                    musicSearch!!.transcriptExcerpt?.takeIf { it.isNotBlank() }?.let {
                        HorizontalDivider()
                        Text("들린 가사 조각", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                        Text(it, style = MaterialTheme.typography.bodyMedium)
                    }
                    musicSearch!!.errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                }
            }

            if (result == null) {
                item { Text("후보 검색 결과가 아직 준비되지 않았습니다.") }
            } else if (result.candidates.isEmpty()) {
                item {
                    Text(
                        result.noMatchReason ?: "찾은 곡 후보가 없습니다.",
                        style = MaterialTheme.typography.bodyLarge,
                    )
                }
            } else {
                items(result.candidates) { candidate ->
                    MusicCandidateCard(candidate, onOpenUrl = { openUrl(context, it) })
                }
            }

            val sources = result?.sources.orEmpty()
            if (sources.isNotEmpty()) {
                item {
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        HorizontalDivider()
                        Text("출처", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                        sources.forEach { url ->
                            TextButton(onClick = { openUrl(context, url) }) {
                                Icon(Icons.AutoMirrored.Filled.OpenInNew, contentDescription = null)
                                Text(url, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            }
                        }
                    }
                }
            }

            item {
                OutlinedButton(onClick = {
                    viewModel.deleteMusicSearch(localId)
                    navController.popBackStack()
                }) {
                    Icon(Icons.Default.Delete, contentDescription = null)
                    Text("삭제")
                }
            }
        }
    }
}

@Composable
private fun MusicCandidateCard(candidate: MusicCandidate, onOpenUrl: (String) -> Unit) {
    Card(
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(candidate.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(candidate.artist)
            val details = listOfNotNull(candidate.album, candidate.releaseYear?.toString()).joinToString(" · ")
            if (details.isNotBlank()) Text(details, style = MaterialTheme.typography.bodyMedium)
            Text("신뢰도 %.0f%%".format(candidate.confidence * 100))
            Text(candidate.matchReason, style = MaterialTheme.typography.bodyMedium)
            candidate.sourceUrls.forEach { url ->
                TextButton(onClick = { onOpenUrl(url) }) {
                    Icon(Icons.AutoMirrored.Filled.OpenInNew, contentDescription = null)
                    Text(url, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
            }
        }
    }
}

@Composable
private fun SummaryTab(recording: RecordingEntity, viewModel: MainViewModel) {
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    var text by remember(recording.summaryJson, recording.title) {
        mutableStateOf(formatSummaryForMarkdown(recording.summaryJson, recording.title))
    }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        OutlinedTextField(
            value = text,
            onValueChange = { text = it },
            modifier = Modifier.fillMaxWidth().weight(1f),
            label = { Text("요약") },
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            IconButton(onClick = { viewModel.updateLocalSummary(recording.localId, text) }) {
                Icon(Icons.Default.Save, contentDescription = "저장")
            }
            IconButton(onClick = {
                clipboard.setText(AnnotatedString(text))
                Toast.makeText(context, "복사했습니다.", Toast.LENGTH_SHORT).show()
            }) {
                Icon(Icons.Default.ContentCopy, contentDescription = "복사")
            }
            IconButton(onClick = { shareText(context, recording.title, text) }) {
                Icon(Icons.Default.Share, contentDescription = "공유")
            }
        }
    }
}

private fun formatSummaryForMarkdown(summaryJson: String?, fallbackTitle: String): String {
    if (summaryJson.isNullOrBlank()) {
        return "요약이 아직 준비되지 않았습니다."
    }

    val payload = runCatching {
        summaryFormatterGson.fromJson(summaryJson, SummaryPayload::class.java)
    }.getOrNull() ?: return summaryJson

    val title = payload.title.ifBlank { fallbackTitle }
    return buildString {
        appendLine("# $title")
        appendLine()
        if (payload.overview.isNotBlank()) {
            appendLine("## 개요")
            appendLine(payload.overview)
            appendLine()
        }
        appendMarkdownList("핵심 내용", payload.keyPoints)
        appendMarkdownList("주제", payload.topics)
        appendMarkdownList("결정 사항", payload.decisions)
        appendMarkdownList("할 일", payload.actionItems)
        appendMarkdownList("리스크", payload.risks)
        appendMarkdownList("다음 단계", payload.nextSteps)
    }.trim()
}

private fun StringBuilder.appendMarkdownList(title: String, items: List<String>) {
    val cleaned = items.map { it.trim() }.filter { it.isNotBlank() }
    if (cleaned.isEmpty()) return
    appendLine("## $title")
    cleaned.forEach { appendLine("- $it") }
    appendLine()
}

@Composable
private fun TextTab(text: String) {
    LazyColumn(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        item { Text(text, style = MaterialTheme.typography.bodyLarge) }
    }
}

@Composable
private fun FileInfoTab(recording: RecordingEntity, onDelete: () -> Unit) {
    Column(modifier = Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(recording.title, style = MaterialTheme.typography.titleLarge)
        HorizontalDivider()
        Text("상태: ${statusLabel(recording.status)}")
        Text("길이: ${formatDuration(recording.durationSeconds ?: 0)}")
        Text("크기: ${formatBytes(recording.sizeBytes ?: 0L)}")
        Text("생성: ${formatDate(recording.createdAtMillis)}")
        OutlinedButton(onClick = onDelete) {
            Icon(Icons.Default.Delete, contentDescription = null)
            Text("삭제")
        }
    }
}

@Composable
private fun SettingsScreen(viewModel: MainViewModel, navController: NavHostController) {
    Scaffold(topBar = { AppTopBar("설정", navController) }) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Button(onClick = { viewModel.logout() }, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.AutoMirrored.Filled.Logout, contentDescription = null)
                Text("로그아웃")
            }
        }
    }
}

@Composable
@OptIn(ExperimentalMaterial3Api::class)
private fun AppTopBar(title: String, navController: NavHostController? = null) {
    CenterAlignedTopAppBar(
        title = { Text(title, maxLines = 1, overflow = TextOverflow.Ellipsis) },
        navigationIcon = {
            if (navController != null) {
                IconButton(onClick = { navController.popBackStack() }) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "뒤로")
                }
            }
        },
    )
}

private fun statusLabel(status: LocalRecordingStatus): String = when (status) {
    LocalRecordingStatus.LOCAL -> "로컬 저장됨"
    LocalRecordingStatus.UPLOADING -> "업로드 중"
    LocalRecordingStatus.UPLOADED -> "업로드 완료"
    LocalRecordingStatus.TRANSCRIBING -> "텍스트 변환 중"
    LocalRecordingStatus.SUMMARIZING -> "요약 생성 중"
    LocalRecordingStatus.COMPLETED -> "완료"
    LocalRecordingStatus.FAILED -> "실패"
    LocalRecordingStatus.DELETED -> "삭제됨"
}

private fun musicSearchStatusLabel(status: LocalMusicSearchStatus): String = when (status) {
    LocalMusicSearchStatus.LOCAL -> "로컬 저장됨"
    LocalMusicSearchStatus.UPLOADING -> "업로드 중"
    LocalMusicSearchStatus.UPLOADED -> "업로드 완료"
    LocalMusicSearchStatus.ANALYZING -> "후보 검색 중"
    LocalMusicSearchStatus.COMPLETED -> "완료"
    LocalMusicSearchStatus.FAILED -> "실패"
    LocalMusicSearchStatus.DELETED -> "삭제됨"
}

private fun parseMusicSearchResult(resultJson: String?): MusicSearchResult? {
    if (resultJson.isNullOrBlank()) return null
    return runCatching {
        musicFormatterGson.fromJson(resultJson, MusicSearchResult::class.java)
    }.getOrNull()
}

private fun formatDuration(seconds: Int): String {
    val minutes = seconds / 60
    val secs = seconds % 60
    return "%02d:%02d".format(minutes, secs)
}

private fun formatBytes(bytes: Long): String = when {
    bytes >= 1024L * 1024L -> "%.1f MB".format(bytes / 1024f / 1024f)
    bytes >= 1024L -> "%.1f KB".format(bytes / 1024f)
    else -> "$bytes B"
}

private fun formatDate(millis: Long): String = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.KOREA).format(Date(millis))

private fun shareText(context: android.content.Context, title: String, text: String) {
    val intent = Intent(Intent.ACTION_SEND)
        .setType("text/plain")
        .putExtra(Intent.EXTRA_SUBJECT, title)
        .putExtra(Intent.EXTRA_TEXT, text)
    context.startActivity(Intent.createChooser(intent, title))
}

private fun openUrl(context: android.content.Context, url: String) {
    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
    context.startActivity(intent)
}
