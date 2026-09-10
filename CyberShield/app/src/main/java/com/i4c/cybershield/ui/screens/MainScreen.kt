package com.i4c.cybershield.ui.screens

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import com.i4c.cybershield.data.MockDataRepository
import com.i4c.cybershield.ui.dispatch.DispatchScreen
import com.i4c.cybershield.ui.investigation.InvestigationScreen
import com.i4c.cybershield.ui.radar.RadarMapScreen
import com.i4c.cybershield.ui.theme.*

// ═══════════════════════════════════════════════════════════════════════
//  MAIN SCREEN – 3-Tab Scaffold with Custom Bottom Navigation
// ═══════════════════════════════════════════════════════════════════════

data class TabItem(
    val index: Int,
    val label: String,
    val selectedIcon: ImageVector,
    val unselectedIcon: ImageVector
)

val bottomTabs = listOf(
    TabItem(0, "CASHOUT RADAR", Icons.Filled.Map, Icons.Outlined.Map),
    TabItem(1, "INVESTIGATION", Icons.Filled.Biotech, Icons.Outlined.Biotech),
    TabItem(2, "DISPATCH CENTER", Icons.Filled.Assignment, Icons.Outlined.Assignment)
)

@Composable
fun MainScreen(viewModel: MainViewModel) {
    val primaryComplaint = MockDataRepository.complaintTickets.first()

    Scaffold(
        containerColor = BgDeepSlate,
        bottomBar = {
            CyberShieldBottomBar(
                currentTab = viewModel.currentTab,
                onTabSelected = viewModel::selectTab
            )
        },
        snackbarHost = {
            // Toast replacement
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
                        colors = CardDefaults.cardColors(
                            containerColor = SuccessGreen.copy(alpha = 0.95f)
                        )
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(14.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            Icon(
                                Icons.Default.CheckCircle,
                                contentDescription = null,
                                tint = TextOffWhite,
                                modifier = Modifier.size(20.dp)
                            )
                            Text(
                                text = message,
                                color = TextOffWhite,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.SemiBold
                            )
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
                    activeFilter = viewModel.activeFilter,
                    selectedTerminal = viewModel.selectedTerminal,
                    onFilterChanged = viewModel::setFilter,
                    onTerminalSelected = viewModel::selectTerminal,
                    onTerminalDismissed = { viewModel.selectTerminal(null) },
                    onNavigateToInvestigation = viewModel::navigateToInvestigation
                )

                1 -> InvestigationScreen(
                    complaint = primaryComplaint,
                    moneyTrail = MockDataRepository.primaryMoneyTrail,
                    riskBreakdown = MockDataRepository.primaryRiskBreakdown,
                    investigationCase = MockDataRepository.primaryInvestigationCase,
                    investigationStatus = viewModel.investigationStatus,
                    showApproveDialog = viewModel.showApproveDialog,
                    showBankHoldDialog = viewModel.showBankHoldDialog,
                    onApproveClick = viewModel::showApproveConfirmation,
                    onApproveConfirm = viewModel::approveAndForward,
                    onApproveDismiss = viewModel::dismissApproveDialog,
                    onBankHoldClick = viewModel::showBankHoldConfirmation,
                    onBankHoldConfirm = viewModel::issueBankHold,
                    onBankHoldDismiss = viewModel::dismissBankHoldDialog,
                    onDismissFalsePositive = viewModel::dismissFalsePositive
                )

                2 -> DispatchScreen(
                    summaries = MockDataRepository.dispatchSummaries,
                    pendingReviews = MockDataRepository.pendingReviewItems,
                    auditLog = viewModel.auditLog,
                    onInspectApprove = { ncrpId ->
                        viewModel.selectTab(1)
                    }
                )
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

                        // Active indicator dot
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
