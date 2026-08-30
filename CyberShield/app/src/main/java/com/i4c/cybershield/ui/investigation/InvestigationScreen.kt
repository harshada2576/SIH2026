package com.i4c.cybershield.ui.investigation

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.i4c.cybershield.model.*
import com.i4c.cybershield.ui.theme.*
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState

// ═══════════════════════════════════════════════════════════════════════
//  TAB 2: INVESTIGATION & EXPLAINABILITY WORKBENCH
//  XAI score breakdown, money trail visualization, and human-in-the-loop
//  decision controls.
// ═══════════════════════════════════════════════════════════════════════

@Composable
fun InvestigationScreen(
    complaint: ComplaintTicket,
    moneyTrail: MoneyTrail,
    riskBreakdown: RiskBreakdown,
    investigationStatus: ActionStatus,
    showApproveDialog: Boolean,
    showBankHoldDialog: Boolean,
    onApproveClick: () -> Unit,
    onApproveConfirm: () -> Unit,
    onApproveDismiss: () -> Unit,
    onBankHoldClick: () -> Unit,
    onBankHoldConfirm: () -> Unit,
    onBankHoldDismiss: () -> Unit,
    onDismissFalsePositive: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BgDeepSlate)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp)
            .padding(top = 12.dp, bottom = 90.dp)
    ) {
        // ─── Section 1: Case Overview Card ─────────────────────────
        CaseOverviewCard(complaint)

        Spacer(modifier = Modifier.height(16.dp))

        // ─── Section 2: Money Trail Network ────────────────────────
        MoneyTrailVisual(moneyTrail)

        Spacer(modifier = Modifier.height(16.dp))

        // ─── Section 3: XAI Score Breakdown ────────────────────────
        RiskBreakdownCard(riskBreakdown)

        Spacer(modifier = Modifier.height(16.dp))

        // ─── Section 4: Human-in-the-Loop Decision Bar ─────────────
        DecisionBar(
            investigationStatus = investigationStatus,
            onApproveClick = onApproveClick,
            onBankHoldClick = onBankHoldClick,
            onDismissFalsePositive = onDismissFalsePositive
        )
    }

    // ─── Confirmation Dialogs ──────────────────────────────────────
    if (showApproveDialog) {
        AlertDialog(
            onDismissRequest = onApproveDismiss,
            containerColor = SurfaceCharcoal,
            titleContentColor = TextOffWhite,
            textContentColor = BorderTaupe,
            title = {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Icon(
                        Icons.Default.Warning,
                        contentDescription = null,
                        tint = AlertOrange,
                        modifier = Modifier.size(24.dp)
                    )
                    Text("Confirm Police Dispatch")
                }
            },
            text = {
                Text(
                    "Confirm dispatching alert package to Sector 20 Police Patrol?\n\nThis action will be recorded in the audit trail and cannot be undone.",
                    lineHeight = 22.sp
                )
            },
            confirmButton = {
                Button(
                    onClick = onApproveConfirm,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = AlertOrange,
                        contentColor = TextOffWhite
                    ),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Text("CONFIRM DISPATCH", fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(onClick = onApproveDismiss) {
                    Text("CANCEL", color = BorderTaupe)
                }
            },
            shape = RoundedCornerShape(16.dp)
        )
    }

    if (showBankHoldDialog) {
        AlertDialog(
            onDismissRequest = onBankHoldDismiss,
            containerColor = SurfaceCharcoal,
            titleContentColor = TextOffWhite,
            textContentColor = BorderTaupe,
            title = {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Icon(
                        Icons.Default.AccountBalance,
                        contentDescription = null,
                        tint = MediumCyan,
                        modifier = Modifier.size(24.dp)
                    )
                    Text("Confirm Bank CBS Hold")
                }
            },
            text = {
                Text(
                    "Place immediate temporary lien via CFCFRMS?\n\nThis will notify SBI Core Banking System to freeze the target account. Lien will be auto-expired after 72 hours.",
                    lineHeight = 22.sp
                )
            },
            confirmButton = {
                Button(
                    onClick = onBankHoldConfirm,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MediumCyan,
                        contentColor = BgDeepSlate
                    ),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Text("ISSUE CBS HOLD", fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(onClick = onBankHoldDismiss) {
                    Text("CANCEL", color = BorderTaupe)
                }
            },
            shape = RoundedCornerShape(16.dp)
        )
    }
}

// ─── Section 1: Case Overview ──────────────────────────────────────────

@Composable
private fun CaseOverviewCard(complaint: ComplaintTicket) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(
                colors = listOf(BorderTaupe.copy(alpha = 0.4f), Color.Transparent)
            )
        )
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "CASE OVERVIEW",
                    fontSize = 11.sp,
                    color = BorderTaupe,
                    letterSpacing = 2.sp,
                    fontWeight = FontWeight.Bold
                )
                StatusBadge(status = complaint.status)
            }

            Spacer(modifier = Modifier.height(12.dp))

            // NCRP ID
            Text(
                text = complaint.ncrpId,
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                color = TextOffWhite,
                letterSpacing = 1.sp
            )

            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                // Reported Loss
                MetricChip(
                    modifier = Modifier.weight(1f),
                    icon = Icons.Default.MoneyOff,
                    label = "Reported Loss",
                    value = complaint.reportedLoss,
                    valueColor = AlertOrange
                )

                // Time Elapsed
                MetricChip(
                    modifier = Modifier.weight(1f),
                    icon = Icons.Default.Timer,
                    label = "Time Elapsed",
                    value = complaint.timeElapsed,
                    valueColor = WarningYellow
                )
            }
        }
    }
}

// ─── Section 2: Money Trail Network ────────────────────────────────────

@Composable
private fun MoneyTrailVisual(trail: MoneyTrail) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(
                colors = listOf(BorderTaupe.copy(alpha = 0.4f), Color.Transparent)
            )
        )
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Text(
                text = "MONEY TRAIL NETWORK",
                fontSize = 11.sp,
                color = BorderTaupe,
                letterSpacing = 2.sp,
                fontWeight = FontWeight.Bold
            )

            Spacer(modifier = Modifier.height(16.dp))

            // Horizontal scrolling trail
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically
            ) {
                trail.nodes.forEachIndexed { index, node ->
                    TrailNodeCard(node)

                    // Arrow between nodes
                    if (index < trail.nodes.size - 1) {
                        Column(
                            modifier = Modifier.padding(horizontal = 6.dp),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            Icon(
                                imageVector = Icons.Default.ArrowForward,
                                contentDescription = null,
                                tint = AlertOrange,
                                modifier = Modifier.size(22.dp)
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun TrailNodeCard(node: TrailNode) {
    val (bgColor, borderColor, iconColor, icon) = when (node.type) {
        "victim" -> Quadruple(
            Color(0xFF2D1F1F),
            ErrorRed.copy(alpha = 0.4f),
            ErrorRed,
            Icons.Default.Person
        )
        "mule" -> Quadruple(
            Color(0xFF2D291F),
            WarningYellow.copy(alpha = 0.4f),
            WarningYellow,
            Icons.Default.AccountCircle
        )
        "aggregator" -> Quadruple(
            Color(0xFF1F252D),
            MediumCyan.copy(alpha = 0.4f),
            MediumCyan,
            Icons.Default.Hub
        )
        "terminal" -> Quadruple(
            Color(0xFF2D1F24),
            AlertOrange.copy(alpha = 0.4f),
            AlertOrange,
            Icons.Default.LocalAtm
        )
        else -> Quadruple(
            SurfaceCharcoal,
            BorderTaupe.copy(alpha = 0.3f),
            BorderTaupe,
            Icons.Default.Circle
        )
    }

    Card(
        modifier = Modifier
            .width(95.dp)
            .heightIn(min = 100.dp),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = bgColor),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(
                colors = listOf(borderColor, Color.Transparent)
            )
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(10.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Box(
                modifier = Modifier
                    .size(32.dp)
                    .clip(CircleShape)
                    .background(iconColor.copy(alpha = 0.15f)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = iconColor,
                    modifier = Modifier.size(18.dp)
                )
            }

            Spacer(modifier = Modifier.height(6.dp))

            Text(
                text = node.label,
                fontSize = 10.sp,
                fontWeight = FontWeight.SemiBold,
                color = TextOffWhite,
                textAlign = TextAlign.Center,
                lineHeight = 13.sp,
                maxLines = 2
            )

            Text(
                text = node.accountHint,
                fontSize = 8.sp,
                color = iconColor.copy(alpha = 0.8f),
                textAlign = TextAlign.Center
            )
        }
    }
}

// ─── Section 3: XAI Score Breakdown ────────────────────────────────────

@Composable
private fun RiskBreakdownCard(breakdown: RiskBreakdown) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(
                colors = listOf(AlertOrange.copy(alpha = 0.3f), Color.Transparent)
            )
        )
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "XAI SCORE BREAKDOWN",
                    fontSize = 11.sp,
                    color = BorderTaupe,
                    letterSpacing = 2.sp,
                    fontWeight = FontWeight.Bold
                )

                // Total score badge
                Card(
                    shape = RoundedCornerShape(8.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = AlertOrange.copy(alpha = 0.15f)
                    )
                ) {
                    Text(
                        text = "${breakdown.totalPercent}% CRITICAL",
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        color = AlertOrange
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Signals
            breakdown.signals.forEachIndexed { index, signal ->
                XaiSignalRow(signal, index)
                if (index < breakdown.signals.size - 1) {
                    Spacer(modifier = Modifier.height(12.dp))
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            // Total bar
            Column {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = "TOTAL COMPOSITE SCORE",
                        fontSize = 11.sp,
                        color = TextOffWhite,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.sp
                    )
                    Text(
                        text = "${breakdown.totalPercent}%",
                        fontSize = 14.sp,
                        color = AlertOrange,
                        fontWeight = FontWeight.Black
                    )
                }

                Spacer(modifier = Modifier.height(6.dp))

                LinearProgressIndicator(
                    progress =  breakdown.totalPercent / 100f ,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(8.dp)
                        .clip(RoundedCornerShape(4.dp)),
                    color = AlertOrange,
                    trackColor = AlertOrange.copy(alpha = 0.15f)
                )
            }
        }
    }
}

@Composable
private fun XaiSignalRow(signal: RiskSignal, index: Int) {
    val signalColor = when {
        signal.contributionPercent >= 25 -> AlertOrange
        signal.contributionPercent >= 20 -> MediumCyan
        else -> WarningYellow
    }

    Column(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text(text = signal.icon, fontSize = 16.sp)
                Column {
                    Text(
                        text = signal.name,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = TextOffWhite
                    )
                    Text(
                        text = signal.explanation,
                        fontSize = 11.sp,
                        color = BorderTaupe
                    )
                }
            }

            Text(
                text = "+${signal.contributionPercent}%",
                fontSize = 16.sp,
                fontWeight = FontWeight.Black,
                color = signalColor
            )
        }

        Spacer(modifier = Modifier.height(6.dp))

        LinearProgressIndicator(
            progress =  signal.contributionPercent / 100f ,
            modifier = Modifier
                .fillMaxWidth()
                .height(4.dp)
                .clip(RoundedCornerShape(2.dp)),
            color = signalColor,
            trackColor = signalColor.copy(alpha = 0.12f)
        )
    }
}

// ─── Section 4: Decision Bar ───────────────────────────────────────────

@Composable
private fun DecisionBar(
    investigationStatus: ActionStatus,
    onApproveClick: () -> Unit,
    onBankHoldClick: () -> Unit,
    onDismissFalsePositive: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(
                colors = listOf(BorderTaupe.copy(alpha = 0.3f), Color.Transparent)
            )
        )
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            // Status Indicator
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Box(
                    modifier = Modifier
                        .size(10.dp)
                        .clip(CircleShape)
                        .background(
                            when (investigationStatus) {
                                ActionStatus.APPROVED -> SuccessGreen
                                ActionStatus.BANK_HOLD -> MediumCyan
                                ActionStatus.DISMISSED -> BorderTaupe
                                else -> AlertOrange
                            }
                        )
                )
                Text(
                    text = "STATUS: ${investigationStatus.displayName}",
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    color = when (investigationStatus) {
                        ActionStatus.APPROVED -> SuccessGreen
                        ActionStatus.BANK_HOLD -> MediumCyan
                        ActionStatus.DISMISSED -> BorderTaupe
                        else -> AlertOrange
                    },
                    letterSpacing = 1.sp
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            if (investigationStatus == ActionStatus.PENDING) {
                // Primary: Approve & Forward
                Button(
                    onClick = onApproveClick,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(50.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = AlertOrange,
                        contentColor = TextOffWhite
                    )
                ) {
                    Icon(Icons.Default.Send, contentDescription = null, modifier = Modifier.size(20.dp))
                    Spacer(modifier = Modifier.width(10.dp))
                    Text(
                        "APPROVE & FORWARD TO POLICE",
                        fontWeight = FontWeight.Bold,
                        fontSize = 14.sp
                    )
                }

                Spacer(modifier = Modifier.height(10.dp))

                // Secondary: Bank Hold
                OutlinedButton(
                    onClick = onBankHoldClick,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = BorderTaupe
                    ),
                    border = ButtonDefaults.outlinedButtonBorder.copy(
                        brush = Brush.linearGradient(
                            colors = listOf(BorderTaupe.copy(alpha = 0.5f), BorderTaupe.copy(alpha = 0.2f))
                        )
                    )
                ) {
                    Icon(Icons.Default.Block, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(10.dp))
                    Text(
                        "ISSUE BANK CBS HOLD",
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 13.sp
                    )
                }

                Spacer(modifier = Modifier.height(4.dp))

                // Tertiary: Dismiss
                TextButton(
                    onClick = onDismissFalsePositive,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        "DISMISS / FALSE POSITIVE",
                        color = BorderTaupe.copy(alpha = 0.7f),
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Medium
                    )
                }
            } else {
                // Show completed status
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = when (investigationStatus) {
                            ActionStatus.APPROVED -> SuccessGreen.copy(alpha = 0.12f)
                            ActionStatus.BANK_HOLD -> MediumCyan.copy(alpha = 0.12f)
                            else -> BorderTaupe.copy(alpha = 0.08f)
                        }
                    )
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.Center
                    ) {
                        Icon(
                            imageVector = when (investigationStatus) {
                                ActionStatus.APPROVED -> Icons.Default.CheckCircle
                                ActionStatus.BANK_HOLD -> Icons.Default.Lock
                                else -> Icons.Default.Cancel
                            },
                            contentDescription = null,
                            tint = when (investigationStatus) {
                                ActionStatus.APPROVED -> SuccessGreen
                                ActionStatus.BANK_HOLD -> MediumCyan
                                else -> BorderTaupe
                            },
                            modifier = Modifier.size(24.dp)
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Text(
                            text = investigationStatus.displayName,
                            fontWeight = FontWeight.Bold,
                            fontSize = 16.sp,
                            color = when (investigationStatus) {
                                ActionStatus.APPROVED -> SuccessGreen
                                ActionStatus.BANK_HOLD -> MediumCyan
                                else -> BorderTaupe
                            }
                        )
                    }
                }
            }
        }
    }
}

// ─── Shared Composables ────────────────────────────────────────────────

@Composable
fun StatusBadge(status: ActionStatus) {
    val (color, text) = when (status) {
        ActionStatus.PENDING -> AlertOrange to "PENDING"
        ActionStatus.APPROVED -> SuccessGreen to "APPROVED"
        ActionStatus.BANK_HOLD -> MediumCyan to "CBS HOLD"
        ActionStatus.DISMISSED -> BorderTaupe to "DISMISSED"
        ActionStatus.EN_ROUTE -> InfoBlue to "EN ROUTE"
        ActionStatus.LIEN_PLACED -> SuccessGreen to "LIEN PLACED"
    }

    Card(
        shape = RoundedCornerShape(6.dp),
        colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.15f))
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
            fontSize = 10.sp,
            fontWeight = FontWeight.Bold,
            color = color,
            letterSpacing = 1.sp
        )
    }
}

@Composable
private fun MetricChip(
    modifier: Modifier = Modifier,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
    value: String,
    valueColor: Color
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = BgDeepSlate),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(
                colors = listOf(BorderTaupe.copy(alpha = 0.3f), Color.Transparent)
            )
        )
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Icon(icon, contentDescription = null, tint = BorderTaupe, modifier = Modifier.size(14.dp))
                Text(label, fontSize = 10.sp, color = BorderTaupe, letterSpacing = 0.5.sp)
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text(value, fontSize = 18.sp, fontWeight = FontWeight.Bold, color = valueColor)
        }
    }
}

// Helper data class for destructuring
private data class Quadruple<A, B, C, D>(
    val first: A,
    val second: B,
    val third: C,
    val fourth: D
)
