package com.i4c.cybershield.ui.screens

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material.ripple.rememberRipple
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.i4c.cybershield.MainViewModel
import com.i4c.cybershield.net.ConnectionState
import com.i4c.cybershield.ui.activity.ActivityScreen
import com.i4c.cybershield.ui.cases.CasesScreen
import com.i4c.cybershield.ui.radar.RadarMapScreen
import com.i4c.cybershield.ui.theme.*

data class TabItem(
    val index: Int,
    val label: String,
    val selectedIcon: ImageVector,
    val unselectedIcon: ImageVector
)

val bottomTabs = listOf(
    TabItem(0, "MAP", Icons.Filled.Map, Icons.Outlined.Map),
    TabItem(1, "CASES", Icons.Filled.FactCheck, Icons.Outlined.FactCheck),
    TabItem(2, "ACTIVITY", Icons.Filled.History, Icons.Outlined.History)
)

@Composable
fun MainScreen(
    viewModel: MainViewModel,
    onOpenCase: (String) -> Unit
) {
    Scaffold(
        containerColor = BgDeepSlate,
        topBar = {
            NetworkStatusBar(
                connectionState = viewModel.connectionState,
                statusMessage = viewModel.backendMessage,
                serverUrl = viewModel.currentServerUrl,
                onTap = { viewModel.showNetworkDialog() }
            )
        },
        bottomBar = {
            CyberShieldBottomBar(
                currentTab = viewModel.currentTab,
                onTabSelected = viewModel::selectTab
            )
        },
        snackbarHost = {
            AnimatedVisibility(
                visible = viewModel.toastMessage != null,
                enter = slideInVertically(initialOffsetY = { it }) + fadeIn(),
                exit = slideOutVertically(targetOffsetY = { it }) + fadeOut()
            ) {
                viewModel.toastMessage?.let { message ->
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 8.dp),
                        shape = RoundedCornerShape(12.dp),
                        colors = CardDefaults.cardColors(containerColor = SuccessGreen.copy(alpha = 0.95f))
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(14.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            Icon(Icons.Default.CheckCircle, contentDescription = null, tint = TextOffWhite, modifier = Modifier.size(20.dp))
                            Text(text = message, color = TextOffWhite, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                        }
                    }
                }
            }
        }
    ) { innerPadding ->
        Box(modifier = Modifier.padding(innerPadding)) {
            when (viewModel.currentTab) {
                0 -> RadarMapScreen(
                    terminals = viewModel.filteredTerminals,
                    searchQuery = viewModel.terminalSearch,
                    activeFilter = viewModel.activeFilter,
                    selectedTerminal = viewModel.selectedTerminal,
                    isHeatmapEnabled = viewModel.isHeatmapEnabled,
                    heatmapPoints = viewModel.heatmapPoints,
                    heatmapEventType = viewModel.heatmapEventType,
                    onToggleHeatmap = viewModel::toggleHeatmap,
                    onHeatmapEventTypeChanged = viewModel::updateHeatmapEventType,
                    onFilterChanged = viewModel::setFilter,
                    onSearchChanged = viewModel::onTerminalSearchChanged,
                    onTerminalSelected = viewModel::selectTerminal,
                    onTerminalDismissed = { viewModel.selectTerminal(null) },
                    onInspectTerminal = { terminal ->
                        viewModel.selectTerminal(null)
                        viewModel.caseForTerminal(terminal.id)?.let { onOpenCase(it.ncrpId) }
                    }
                )

                1 -> CasesScreen(
                    allCases = viewModel.cases,
                    summaries = viewModel.queueSummaries,
                    userRole = viewModel.userRole,
                    backendMessage = viewModel.backendMessage,
                    backendOnline = viewModel.backendOnline,
                    onCaseSelected = onOpenCase
                )

                2 -> ActivityScreen(auditLog = viewModel.auditLog)
            }
        }
    }

    if (viewModel.showNetworkConfigDialog) {
        NetworkConfigDialog(
            currentState = viewModel.connectionState,
            currentUrl = viewModel.currentServerUrl,
            statusMessage = viewModel.backendMessage,
            onDismiss = viewModel::dismissNetworkDialog,
            onRetryDiscovery = {
                viewModel.retryDiscovery()
                viewModel.dismissNetworkDialog()
            },
            onSaveManual = { host, port ->
                viewModel.setManualHost(host, port)
                viewModel.dismissNetworkDialog()
            }
        )
    }
}

// ─── Network Status Header Bar ──────────────────────────────────────────

@Composable
private fun NetworkStatusBar(
    connectionState: ConnectionState,
    statusMessage: String,
    serverUrl: String,
    onTap: () -> Unit
) {
    val (dotColor, stateText) = when (connectionState) {
        ConnectionState.CONNECTED -> SuccessGreen to "LIVE BACKEND"
        ConnectionState.DISCOVERING -> WarningYellow to "DISCOVERING BACKEND..."
        ConnectionState.RECONNECTING -> AlertOrange to "RECONNECTING..."
        ConnectionState.BACKEND_NOT_FOUND, ConnectionState.DISCONNECTED -> BorderTaupe to "OFFLINE MODE"
    }

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onTap() },
        color = BgDeepSlate
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 8.dp)
                .statusBarsPadding(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .clip(CircleShape)
                        .background(dotColor)
                )
                Text(
                    text = stateText,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    color = dotColor,
                    letterSpacing = 1.sp
                )
            }

            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                Text(
                    text = if (connectionState == ConnectionState.CONNECTED) serverUrl.removePrefix("http://") else "Tap to configure",
                    fontSize = 11.sp,
                    color = BorderTaupe
                )
                Icon(
                    imageVector = Icons.Default.Wifi,
                    contentDescription = null,
                    tint = dotColor,
                    modifier = Modifier.size(14.dp)
                )
            }
        }
    }
}

// ─── Network Configuration Modal ───────────────────────────────────────

@Composable
private fun NetworkConfigDialog(
    currentState: ConnectionState,
    currentUrl: String,
    statusMessage: String,
    onDismiss: () -> Unit,
    onRetryDiscovery: () -> Unit,
    onSaveManual: (host: String, port: Int) -> Unit
) {
    var manualIp by remember { mutableStateOf("") }
    var manualPort by remember { mutableStateOf("8080") }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = SurfaceCharcoal,
        titleContentColor = TextOffWhite,
        textContentColor = BorderTaupe,
        title = {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Icon(Icons.Default.SettingsEthernet, contentDescription = null, tint = AlertOrange, modifier = Modifier.size(24.dp))
                Text("Backend LAN Discovery", fontSize = 18.sp, fontWeight = FontWeight.Bold)
            }
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(
                    "CyberShield dynamically discovers the SIH26184 backend across Wi-Fi/Hotspots using native mDNS & UDP broadcast.",
                    fontSize = 12.sp, color = BorderTaupe, lineHeight = 16.sp
                )

                Card(
                    shape = RoundedCornerShape(10.dp),
                    colors = CardDefaults.cardColors(containerColor = BgDeepSlate)
                ) {
                    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("Status: ${currentState.name}", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = TextOffWhite)
                        Text(statusMessage, fontSize = 11.sp, color = BorderTaupe)
                        if (currentState == ConnectionState.CONNECTED) {
                            Text("Active URL: $currentUrl", fontSize = 11.sp, color = SuccessGreen, fontWeight = FontWeight.SemiBold)
                        }
                    }
                }

                Button(
                    onClick = onRetryDiscovery,
                    modifier = Modifier.fillMaxWidth().height(44.dp),
                    shape = RoundedCornerShape(10.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = AlertOrange, contentColor = TextOffWhite)
                ) {
                    Icon(Icons.Default.Refresh, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Auto-Discover on Hotspot / Wi-Fi", fontWeight = FontWeight.Bold, fontSize = 12.sp)
                }

                Divider(color = BorderTaupe.copy(alpha = 0.2f), modifier = Modifier.padding(vertical = 4.dp))

                Text("Manual Host Override (Optional):", fontSize = 11.sp, color = TextOffWhite, fontWeight = FontWeight.SemiBold)

                OutlinedTextField(
                    value = manualIp,
                    onValueChange = { manualIp = it },
                    placeholder = { Text("e.g. 192.168.43.120", fontSize = 12.sp, color = BorderTaupe.copy(alpha = 0.5f)) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = TextOffWhite,
                        unfocusedTextColor = TextOffWhite,
                        focusedBorderColor = AlertOrange,
                        unfocusedBorderColor = BorderTaupe.copy(alpha = 0.3f)
                    )
                )
            }
        },
        confirmButton = {
            if (manualIp.isNotBlank()) {
                Button(
                    onClick = {
                        val portInt = manualPort.toIntOrNull() ?: 8080
                        onSaveManual(manualIp.trim(), portInt)
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = MediumCyan, contentColor = BgDeepSlate)
                ) {
                    Text("Connect to IP", fontWeight = FontWeight.Bold)
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Close", color = BorderTaupe)
            }
        },
        shape = RoundedCornerShape(16.dp)
    )
}

// ─── Custom Bottom Navigation Bar ──────────────────────────────────────

@Composable
private fun CyberShieldBottomBar(
    currentTab: Int,
    onTabSelected: (Int) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp),
        colors = CardDefaults.cardColors(containerColor = BgDeepSlate),
        elevation = CardDefaults.cardElevation(defaultElevation = 12.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 8.dp)
                .navigationBarsPadding(),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically
        ) {
            bottomTabs.forEach { tab ->
                val isSelected = currentTab == tab.index
                val animatedAlpha by animateFloatAsState(
                    targetValue = if (isSelected) 1f else 0.6f,
                    animationSpec = tween(200),
                    label = "tab_alpha"
                )

                Column(
                    modifier = Modifier
                        .clip(RoundedCornerShape(12.dp))
                        .clickable(
                            interactionSource = remember { MutableInteractionSource() },
                            indication = rememberRipple(bounded = true, radius = 40.dp)
                        ) { onTabSelected(tab.index) }
                        .padding(horizontal = 16.dp, vertical = 8.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Box {
                        Icon(
                            imageVector = if (isSelected) tab.selectedIcon else tab.unselectedIcon,
                            contentDescription = tab.label,
                            tint = if (isSelected) AlertOrange else BorderTaupe.copy(alpha = animatedAlpha),
                            modifier = Modifier.size(24.dp)
                        )

                        if (isSelected) {
                            Box(
                                modifier = Modifier
                                    .size(6.dp)
                                    .offset(x = 18.dp, y = (-2).dp)
                                    .clip(CircleShape)
                                    .background(AlertOrange)
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(4.dp))

                    Text(
                        text = tab.label,
                        fontSize = 9.sp,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                        color = if (isSelected) AlertOrange else BorderTaupe.copy(alpha = animatedAlpha),
                        letterSpacing = 0.5.sp,
                        maxLines = 1
                    )
                }
            }
        }
    }
}
