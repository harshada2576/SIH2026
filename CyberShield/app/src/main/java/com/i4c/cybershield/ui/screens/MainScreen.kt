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
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.i4c.cybershield.MainViewModel
import com.i4c.cybershield.model.UserRole
import com.i4c.cybershield.ui.activity.ActivityScreen
import com.i4c.cybershield.ui.cases.CasesScreen
import com.i4c.cybershield.ui.radar.RadarMapScreen
import com.i4c.cybershield.ui.theme.*

// ═══════════════════════════════════════════════════════════════════════
//  MAIN SCREEN – 3-Tab Scaffold (Map / Cases / Activity)
//
//  Cases is the default landing tab: it's the investigator's actual work
//  queue. Tapping any case (here, or a marker on the Map) opens that
//  SPECIFIC case's detail screen via onOpenCase — never a fixed example.
// ═══════════════════════════════════════════════════════════════════════

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
                    onHeatmapEventTypeChanged = viewModel::setHeatmapEventType,
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
