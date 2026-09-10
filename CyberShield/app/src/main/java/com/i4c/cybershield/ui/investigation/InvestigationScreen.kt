package com.i4c.cybershield.ui.investigation

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
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
import com.i4c.cybershield.data.MockDataRepository
import com.i4c.cybershield.model.*
import com.i4c.cybershield.ui.theme.*

// ═══════════════════════════════════════════════════════════════════════
//  TAB 2: INVESTIGATION & EXPLAINABILITY WORKBENCH (SIH26184)
//  Full Money Trail, Selective Fund Protection, Spatial Intelligence,
//  Repeated ATM Recurrence, and Human-in-the-Loop Interventions.
// ═══════════════════════════════════════════════════════════════════════

@Composable
fun InvestigationScreen(
    complaint: ComplaintTicket,
    moneyTrail: MoneyTrail,
    riskBreakdown: RiskBreakdown,
    investigationCase: InvestigationCase = MockDataRepository.primaryInvestigationCase,
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
        // ─── Section 1: Case Overview & Lifecycle Banner ───────────
        CaseOverviewCard(investigationCase, complaint)

        Spacer(modifier = Modifier.height(16.dp))

        // ─── Section 2: Selective Fund Protection ──────────────────
        SelectiveFundProtectionCard(investigationCase.funds)

        Spacer(modifier = Modifier.height(16.dp))

        // ─── Section 2.5: Transaction Confirmation Status ──────────
        investigationCase.confirmation?.let { confirmation ->
            TransactionConfirmationCard(confirmation)
            Spacer(modifier = Modifier.height(16.dp))
        }

        // ─── Section 3: Money Trail Network & Detailed Hops ────────
        MoneyTrailVisual(moneyTrail, investigationCase.trailHops)

        Spacer(modifier = Modifier.height(16.dp))

        // ─── Section 4: Spatial Context & Nearby Terminals ─────────
        NearbyTerminalsCard(investigationCase)

        Spacer(modifier = Modifier.height(16.dp))

        // ─── Section 4.5: Recorded Withdrawal & Cashout Attempts ──
        if (investigationCase.withdrawalAttempts.isNotEmpty()) {
            RecordedWithdrawalsCard(investigationCase.withdrawalAttempts)
            Spacer(modifier = Modifier.height(16.dp))
        }

        // ─── Section 5: Location Evidence & Incident Timeline ──────
        if (investigationCase.timelineEvents.isNotEmpty()) {
            TimelineEventsCard(investigationCase.timelineEvents)
            Spacer(modifier = Modifier.height(16.dp))
        }

        // ─── Section 5.5: Repeated ATM Targeting & Recurrence ──────
        investigationCase.recurrence?.let { recurrence ->
            RepeatedAtmCard(recurrence)
            Spacer(modifier = Modifier.height(16.dp))
        }

        // ─── Section 6: XAI Score Breakdown ────────────────────────
        RiskBreakdownCard(riskBreakdown)

        Spacer(modifier = Modifier.height(16.dp))

        // ─── Section 7: Operational Status & Human Decision Bar ────
        DecisionBar(
            investigationCase = investigationCase,
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
                    "Confirm dispatching alert package to Sector 20 Police Patrol?\n\nTarget ATM: ${investigationCase.targetTerminal.id} (${investigationCase.targetTerminal.address})\n\nThis action will be recorded in the audit trail and cannot be undone.",
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
                    "Place immediate selective temporary lien via CFCFRMS?\n\nAccount: ${investigationCase.flaggedAccount}\nAmount Protected: ${investigationCase.funds.protectedAmount}\n(Preserving ${investigationCase.funds.existingBalance} legitimate balance).\n\nProvisional hold will be auto-expired after 72 hours if unescalated.",
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

// ─── Section 1: Case Overview & Lifecycle Banner ───────────────────────

@Composable
private fun CaseOverviewCard(investigationCase: InvestigationCase, complaint: ComplaintTicket) {
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
                    text = "CASE OVERVIEW & LIFECYCLE",
                    fontSize = 11.sp,
                    color = BorderTaupe,
                    letterSpacing = 2.sp,
                    fontWeight = FontWeight.Bold
                )
                LifecycleBadge(lifecycle = investigationCase.lifecycle)
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Case ID & Target Account
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = investigationCase.caseId,
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                        color = TextOffWhite,
                        letterSpacing = 1.sp
                    )
                    Text(
                        text = "Flagged Node: ${investigationCase.flaggedAccount}",
                        fontSize = 12.sp,
                        color = AlertOrange,
                        fontWeight = FontWeight.SemiBold
                    )
                }

                Card(
                    shape = RoundedCornerShape(8.dp),
                    colors = CardDefaults.cardColors(containerColor = AlertOrange.copy(alpha = 0.15f))
                ) {
                    Text(
                        text = "${investigationCase.riskScorePercent}% RISK",
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        color = AlertOrange
                    )
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                MetricChip(
                    modifier = Modifier.weight(1f),
                    icon = Icons.Default.AttachMoney,
                    label = "Suspicious Chain",
                    value = investigationCase.suspiciousAmount,
                    valueColor = AlertOrange
                )

                MetricChip(
                    modifier = Modifier.weight(1f),
                    icon = Icons.Default.Timer,
                    label = "Cashout Window",
                    value = investigationCase.predictedWindow.substringBefore(" –"),
                    valueColor = WarningYellow
                )
            }

            Spacer(modifier = Modifier.height(10.dp))

            // Operational status badges row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OpStatusBadge(
                    label = "Bank Hold",
                    active = investigationCase.bankHoldActive,
                    activeText = "ACTIVE",
                    modifier = Modifier.weight(1f)
                )
                OpStatusBadge(
                    label = "ATM Block",
                    active = investigationCase.atmBlockRequested,
                    activeText = "REQUESTED",
                    modifier = Modifier.weight(1f)
                )
                OpStatusBadge(
                    label = "LEA Dispatch",
                    active = investigationCase.leaNotificationSent,
                    activeText = "SENT",
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

// ─── Section 2: Selective Fund Protection Card ─────────────────────────

@Composable
private fun SelectiveFundProtectionCard(funds: SelectiveFundBreakdown) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF1F2826)),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(
                colors = listOf(SuccessGreen.copy(alpha = 0.4f), Color.Transparent)
            )
        )
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Icon(
                        Icons.Default.Security,
                        contentDescription = null,
                        tint = SuccessGreen,
                        modifier = Modifier.size(16.dp)
                    )
                    Text(
                        text = "SELECTIVE FUND PROTECTION",
                        fontSize = 11.sp,
                        color = SuccessGreen,
                        letterSpacing = 1.5.sp,
                        fontWeight = FontWeight.Bold
                    )
                }

                Card(
                    shape = RoundedCornerShape(6.dp),
                    colors = CardDefaults.cardColors(containerColor = SuccessGreen.copy(alpha = 0.15f))
                ) {
                    Text(
                        text = if (funds.isPreComplaint) "PROVISIONAL" else "STATUTORY",
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                        fontSize = 9.sp,
                        fontWeight = FontWeight.Bold,
                        color = SuccessGreen
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            Text(
                text = "Locks suspicious chain inflow while preserving legitimate pre-existing balance.",
                fontSize = 11.sp,
                color = BorderTaupe,
                lineHeight = 16.sp
            )

            Spacer(modifier = Modifier.height(14.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // Legitimate Balance Preserved
                Card(
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(10.dp),
                    colors = CardDefaults.cardColors(containerColor = BgDeepSlate)
                ) {
                    Column(modifier = Modifier.padding(10.dp)) {
                        Text("Pre-existing Balance", fontSize = 9.sp, color = BorderTaupe)
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(funds.existingBalance, fontSize = 14.sp, fontWeight = FontWeight.Bold, color = TextOffWhite)
                        Spacer(modifier = Modifier.height(2.dp))
                        Text("✓ Unfrozen", fontSize = 9.sp, color = SuccessGreen, fontWeight = FontWeight.SemiBold)
                    }
                }

                // Suspicious Inflow
                Card(
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(10.dp),
                    colors = CardDefaults.cardColors(containerColor = BgDeepSlate)
                ) {
                    Column(modifier = Modifier.padding(10.dp)) {
                        Text("Suspicious Inflow", fontSize = 9.sp, color = BorderTaupe)
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(funds.suspiciousAmount, fontSize = 14.sp, fontWeight = FontWeight.Bold, color = AlertOrange)
                        Spacer(modifier = Modifier.height(2.dp))
                        Text("⚠ Flagged Ingress", fontSize = 9.sp, color = AlertOrange, fontWeight = FontWeight.SemiBold)
                    }
                }

                // Protected Hold Amount
                Card(
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(10.dp),
                    colors = CardDefaults.cardColors(containerColor = BgDeepSlate),
                    border = CardDefaults.outlinedCardBorder().copy(
                        brush = Brush.linearGradient(
                            colors = listOf(MediumCyan.copy(alpha = 0.5f), Color.Transparent)
                        )
                    )
                ) {
                    Column(modifier = Modifier.padding(10.dp)) {
                        Text("Protected Hold", fontSize = 9.sp, color = BorderTaupe)
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(funds.protectedAmount, fontSize = 14.sp, fontWeight = FontWeight.Bold, color = MediumCyan)
                        Spacer(modifier = Modifier.height(2.dp))
                        Text("🔒 Hold Placed", fontSize = 9.sp, color = MediumCyan, fontWeight = FontWeight.SemiBold)
                    }
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            Text(
                text = "Reason: ${funds.holdReason} (Source: ${funds.sourceTxn})",
                fontSize = 10.sp,
                color = BorderTaupe.copy(alpha = 0.8f)
            )
        }
    }
}

// ─── Section 3: Money Trail Network & Detailed Hops ────────────────────

@Composable
private fun MoneyTrailVisual(trail: MoneyTrail, hops: List<DetailedTrailHop>) {
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
                text = "MONEY TRAIL NETWORK & HOPS",
                fontSize = 11.sp,
                color = BorderTaupe,
                letterSpacing = 2.sp,
                fontWeight = FontWeight.Bold
            )

            Spacer(modifier = Modifier.height(14.dp))

            // Horizontal scrolling node trail
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
                            modifier = Modifier.padding(horizontal = 4.dp),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            Icon(
                                imageVector = Icons.Default.ArrowForward,
                                contentDescription = null,
                                tint = AlertOrange,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            Text(
                text = "TRANSACTION HOPS AUDIT",
                fontSize = 10.sp,
                color = BorderTaupe,
                letterSpacing = 1.5.sp,
                fontWeight = FontWeight.Bold
            )

            Spacer(modifier = Modifier.height(10.dp))

            // Detailed step-by-step hops
            hops.forEachIndexed { index, hop ->
                DetailedHopRow(hop)
                if (index < hops.size - 1) {
                    Spacer(modifier = Modifier.height(10.dp))
                }
            }
        }
    }
}

@Composable
private fun DetailedHopRow(hop: DetailedTrailHop) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(10.dp),
        colors = CardDefaults.cardColors(containerColor = BgDeepSlate)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .size(20.dp)
                            .clip(CircleShape)
                            .background(AlertOrange.copy(alpha = 0.2f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "${hop.hopNumber}",
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            color = AlertOrange
                        )
                    }
                    Text(
                        text = "${hop.sourceTier} → ${hop.targetTier}",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        color = TextOffWhite
                    )
                }

                Text(
                    text = hop.amount,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold,
                    color = AlertOrange
                )
            }

            Spacer(modifier = Modifier.height(6.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "${hop.fromAccount} → ${hop.toAccount}",
                    fontSize = 10.sp,
                    color = BorderTaupe
                )
                Text(
                    text = "${hop.channel} • ${hop.timestamp}",
                    fontSize = 10.sp,
                    color = BorderTaupe
                )
            }

            if (hop.flags.isNotEmpty()) {
                Spacer(modifier = Modifier.height(6.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    hop.flags.forEach { flag ->
                        Card(
                            shape = RoundedCornerShape(4.dp),
                            colors = CardDefaults.cardColors(containerColor = WarningYellow.copy(alpha = 0.15f))
                        ) {
                            Text(
                                text = "⚠ $flag",
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                fontSize = 8.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = WarningYellow
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
            .heightIn(min = 96.dp),
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
                .padding(8.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Box(
                modifier = Modifier
                    .size(28.dp)
                    .clip(CircleShape)
                    .background(iconColor.copy(alpha = 0.15f)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = iconColor,
                    modifier = Modifier.size(16.dp)
                )
            }

            Spacer(modifier = Modifier.height(4.dp))

            Text(
                text = node.label,
                fontSize = 9.sp,
                fontWeight = FontWeight.SemiBold,
                color = TextOffWhite,
                textAlign = TextAlign.Center,
                lineHeight = 11.sp,
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

// ─── Section 4: Spatial Context & Nearby Terminals ─────────────────────

@Composable
private fun NearbyTerminalsCard(investigationCase: InvestigationCase) {
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
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Icon(
                        Icons.Default.Place,
                        contentDescription = null,
                        tint = MediumCyan,
                        modifier = Modifier.size(16.dp)
                    )
                    Text(
                        text = "SPATIAL INTELLIGENCE & VICINITY",
                        fontSize = 11.sp,
                        color = BorderTaupe,
                        letterSpacing = 1.5.sp,
                        fontWeight = FontWeight.Bold
                    )
                }

                Text(
                    text = "TARGET: ${investigationCase.targetTerminal.id}",
                    fontSize = 10.sp,
                    color = AlertOrange,
                    fontWeight = FontWeight.Bold
                )
            }

            Spacer(modifier = Modifier.height(10.dp))

            Text(
                text = "Primary Terminal: ${investigationCase.targetTerminal.address} (${investigationCase.targetTerminal.bankName})",
                fontSize = 11.sp,
                color = TextOffWhite
            )

            Spacer(modifier = Modifier.height(12.dp))

            Text(
                text = "NEARBY ALTERNATIVE CASHOUT TERMINALS (RADIUS < 1.0 KM)",
                fontSize = 9.sp,
                color = BorderTaupe,
                letterSpacing = 1.sp,
                fontWeight = FontWeight.SemiBold
            )

            Spacer(modifier = Modifier.height(8.dp))

            investigationCase.nearbyTerminals.forEach { terminal ->
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        Icon(
                            imageVector = if (terminal.type == TerminalType.AEPS_MICRO_ATM) Icons.Default.Smartphone else Icons.Default.LocalAtm,
                            contentDescription = null,
                            tint = if (terminal.distanceKm < 0.3) AlertOrange else BorderTaupe,
                            modifier = Modifier.size(14.dp)
                        )
                        Text(
                            text = "${terminal.id} - ${terminal.address}",
                            fontSize = 10.sp,
                            color = TextOffWhite
                        )
                    }

                    Card(
                        shape = RoundedCornerShape(4.dp),
                        colors = CardDefaults.cardColors(containerColor = BgDeepSlate)
                    ) {
                        Text(
                            text = "${String.format("%.2f", terminal.distanceKm)} km",
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            fontSize = 9.sp,
                            fontWeight = FontWeight.Bold,
                            color = if (terminal.distanceKm < 0.3) AlertOrange else MediumCyan
                        )
                    }
                }
            }
        }
    }
}

// ─── Section 5: Repeated ATM Targeting & Recurrence ────────────────────

@Composable
private fun RepeatedAtmCard(recurrence: TerminalRecurrence) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF2D1F1F)),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(
                colors = listOf(ErrorRed.copy(alpha = 0.5f), Color.Transparent)
            )
        )
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Icon(
                        Icons.Default.Repeat,
                        contentDescription = null,
                        tint = ErrorRed,
                        modifier = Modifier.size(16.dp)
                    )
                    Text(
                        text = "REPEATED CASHOUT RECURRENCE",
                        fontSize = 11.sp,
                        color = ErrorRed,
                        letterSpacing = 1.5.sp,
                        fontWeight = FontWeight.Bold
                    )
                }

                Card(
                    shape = RoundedCornerShape(6.dp),
                    colors = CardDefaults.cardColors(containerColor = ErrorRed.copy(alpha = 0.2f))
                ) {
                    Text(
                        text = recurrence.escalationState,
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                        fontSize = 9.sp,
                        fontWeight = FontWeight.Bold,
                        color = ErrorRed
                    )
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            Text(
                text = "Terminal ${recurrence.terminalId} has been targeted ${recurrence.attemptsCount} times by account ${recurrence.accountTarget} in the active observation window.",
                fontSize = 11.sp,
                color = TextOffWhite,
                lineHeight = 16.sp
            )

            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Text(
                    text = "Risk Multiplier: ${recurrence.riskMultiplier}x",
                    fontSize = 10.sp,
                    color = WarningYellow,
                    fontWeight = FontWeight.SemiBold
                )
                Text(
                    text = "Action: Terminal Hardware Blacklist Suggested",
                    fontSize = 10.sp,
                    color = BorderTaupe
                )
            }
        }
    }
}

// ─── Section 6: XAI Score Breakdown ────────────────────────────────────

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

            breakdown.signals.forEachIndexed { index, signal ->
                XaiSignalRow(signal, index)
                if (index < breakdown.signals.size - 1) {
                    Spacer(modifier = Modifier.height(12.dp))
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

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
                    progress = breakdown.totalPercent / 100f,
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
            progress = signal.contributionPercent / 100f,
            modifier = Modifier
                .fillMaxWidth()
                .height(4.dp)
                .clip(RoundedCornerShape(2.dp)),
            color = signalColor,
            trackColor = signalColor.copy(alpha = 0.12f)
        )
    }
}

// ─── Section 7: Decision Bar ───────────────────────────────────────────

@Composable
private fun DecisionBar(
    investigationCase: InvestigationCase,
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
                    text = "INVESTIGATOR DECISION: ${investigationStatus.displayName}",
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

                // Secondary: Selective Bank Hold
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
                    Icon(Icons.Default.AccountBalance, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(10.dp))
                    Text(
                        "ISSUE SELECTIVE CBS HOLD (${investigationCase.funds.protectedAmount})",
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

// ─── Shared Badges & Chips ─────────────────────────────────────────────

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
fun LifecycleBadge(lifecycle: CaseLifecycle) {
    val (color, text) = when (lifecycle) {
        CaseLifecycle.PRE_COMPLAINT_INTERVENTION -> MediumCyan to "PRE-COMPLAINT HOLD"
        CaseLifecycle.POST_COMPLAINT_ESCALATED -> ErrorRed to "POST-COMPLAINT ESCALATED"
        CaseLifecycle.CASHOUT_ATTEMPT_DETECTED -> WarningYellow to "CASHOUT DETECTED"
        CaseLifecycle.RESOLVED -> SuccessGreen to "RESOLVED"
    }

    Card(
        shape = RoundedCornerShape(6.dp),
        colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.15f))
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
            fontSize = 9.sp,
            fontWeight = FontWeight.Bold,
            color = color,
            letterSpacing = 1.sp
        )
    }
}

@Composable
private fun OpStatusBadge(label: String, active: Boolean, activeText: String, modifier: Modifier = Modifier) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(6.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (active) SuccessGreen.copy(alpha = 0.15f) else BorderTaupe.copy(alpha = 0.1f)
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 4.dp, horizontal = 6.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(label, fontSize = 8.sp, color = BorderTaupe)
            Text(
                text = if (active) activeText else "IDLE",
                fontSize = 9.sp,
                fontWeight = FontWeight.Bold,
                color = if (active) SuccessGreen else BorderTaupe
            )
        }
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
            Text(value, fontSize = 16.sp, fontWeight = FontWeight.Bold, color = valueColor)
        }
    }
}

@Composable
private fun TransactionConfirmationCard(confirmation: TransactionConfirmationInfo) {
    val (statusColor, statusBg, icon) = when (confirmation.status) {
        ConfirmationStatus.CONFIRMED_FRAUD -> Triple(ErrorRed, Color(0xFF2D1F1F), Icons.Default.GppBad)
        ConfirmationStatus.CONFIRMED_LEGITIMATE -> Triple(SuccessGreen, Color(0xFF1F2826), Icons.Default.GppGood)
        ConfirmationStatus.PENDING_CONFIRMATION -> Triple(MediumCyan, Color(0xFF1F252D), Icons.Default.HourglassTop)
        ConfirmationStatus.EXPIRED -> Triple(WarningYellow, Color(0xFF2D291F), Icons.Default.TimerOff)
        ConfirmationStatus.SKIPPED -> Triple(BorderTaupe, SurfaceCharcoal, Icons.Default.Forward)
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = statusBg),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(
                colors = listOf(statusColor.copy(alpha = 0.4f), Color.Transparent)
            )
        )
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Icon(
                        imageVector = icon,
                        contentDescription = null,
                        tint = statusColor,
                        modifier = Modifier.size(16.dp)
                    )
                    Text(
                        text = "TRANSACTION CONFIRMATION STATUS",
                        fontSize = 11.sp,
                        color = statusColor,
                        letterSpacing = 1.5.sp,
                        fontWeight = FontWeight.Bold
                    )
                }

                Card(
                    shape = RoundedCornerShape(6.dp),
                    colors = CardDefaults.cardColors(containerColor = statusColor.copy(alpha = 0.15f))
                ) {
                    Text(
                        text = confirmation.status.displayName,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                        fontSize = 9.sp,
                        fontWeight = FontWeight.Bold,
                        color = statusColor
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            Text(
                text = confirmation.explanatoryNote,
                fontSize = 11.sp,
                color = TextOffWhite,
                lineHeight = 16.sp
            )

            Spacer(modifier = Modifier.height(10.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Card(
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(8.dp),
                    colors = CardDefaults.cardColors(containerColor = BgDeepSlate)
                ) {
                    Column(modifier = Modifier.padding(8.dp)) {
                        Text("Transaction ID", fontSize = 9.sp, color = BorderTaupe)
                        Text(confirmation.txnId, fontSize = 11.sp, fontWeight = FontWeight.SemiBold, color = TextOffWhite)
                    }
                }
                Card(
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(8.dp),
                    colors = CardDefaults.cardColors(containerColor = BgDeepSlate)
                ) {
                    Column(modifier = Modifier.padding(8.dp)) {
                        Text("Prompt Channel", fontSize = 9.sp, color = BorderTaupe)
                        Text(confirmation.promptChannel, fontSize = 10.sp, fontWeight = FontWeight.SemiBold, color = TextOffWhite, maxLines = 1)
                    }
                }
                Card(
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(8.dp),
                    colors = CardDefaults.cardColors(containerColor = BgDeepSlate)
                ) {
                    Column(modifier = Modifier.padding(8.dp)) {
                        Text("Response Time", fontSize = 9.sp, color = BorderTaupe)
                        Text(confirmation.respondedAt ?: "Pending", fontSize = 11.sp, fontWeight = FontWeight.SemiBold, color = statusColor)
                    }
                }
            }
        }
    }
}

@Composable
private fun RecordedWithdrawalsCard(withdrawals: List<RecordedWithdrawal>) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(
                colors = listOf(AlertOrange.copy(alpha = 0.35f), Color.Transparent)
            )
        )
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Icon(
                        Icons.Default.LocalAtm,
                        contentDescription = null,
                        tint = AlertOrange,
                        modifier = Modifier.size(16.dp)
                    )
                    Text(
                        text = "RECORDED WITHDRAWAL ATTEMPTS",
                        fontSize = 11.sp,
                        color = AlertOrange,
                        letterSpacing = 1.5.sp,
                        fontWeight = FontWeight.Bold
                    )
                }

                Card(
                    shape = RoundedCornerShape(6.dp),
                    colors = CardDefaults.cardColors(containerColor = AlertOrange.copy(alpha = 0.15f))
                ) {
                    Text(
                        text = "${withdrawals.size} RECORDED",
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                        fontSize = 9.sp,
                        fontWeight = FontWeight.Bold,
                        color = AlertOrange
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            withdrawals.forEachIndexed { index, withdrawal ->
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(10.dp),
                    colors = CardDefaults.cardColors(containerColor = BgDeepSlate)
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(6.dp)
                            ) {
                                Icon(
                                    Icons.Default.Block,
                                    contentDescription = null,
                                    tint = ErrorRed,
                                    modifier = Modifier.size(16.dp)
                                )
                                Text(
                                    text = "${withdrawal.terminalName} (${withdrawal.terminalId})",
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = TextOffWhite
                                )
                            }
                            Text(
                                text = withdrawal.amount,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold,
                                color = AlertOrange
                            )
                        }

                        Spacer(modifier = Modifier.height(4.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text(
                                text = "${withdrawal.channel} • ${withdrawal.timestamp}",
                                fontSize = 10.sp,
                                color = BorderTaupe
                            )
                            Card(
                                shape = RoundedCornerShape(4.dp),
                                colors = CardDefaults.cardColors(containerColor = ErrorRed.copy(alpha = 0.15f))
                            ) {
                                Text(
                                    text = withdrawal.status.displayName,
                                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                    fontSize = 8.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = ErrorRed
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(4.dp))

                        Text(
                            text = "Result: ${withdrawal.failureReason}",
                            fontSize = 10.sp,
                            color = MediumCyan
                        )
                    }
                }

                if (index < withdrawals.size - 1) {
                    Spacer(modifier = Modifier.height(8.dp))
                }
            }
        }
    }
}

@Composable
private fun TimelineEventsCard(events: List<LocationTimelineEvent>) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(
                colors = listOf(MediumCyan.copy(alpha = 0.35f), Color.Transparent)
            )
        )
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Icon(
                        Icons.Default.Timeline,
                        contentDescription = null,
                        tint = MediumCyan,
                        modifier = Modifier.size(16.dp)
                    )
                    Text(
                        text = "LOCATION EVIDENCE & INCIDENT TIMELINE",
                        fontSize = 11.sp,
                        color = MediumCyan,
                        letterSpacing = 1.5.sp,
                        fontWeight = FontWeight.Bold
                    )
                }

                Card(
                    shape = RoundedCornerShape(6.dp),
                    colors = CardDefaults.cardColors(containerColor = MediumCyan.copy(alpha = 0.15f))
                ) {
                    Text(
                        text = "${events.size} EVENTS",
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                        fontSize = 9.sp,
                        fontWeight = FontWeight.Bold,
                        color = MediumCyan
                    )
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            events.forEachIndexed { index, event ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.Top,
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Box(
                            modifier = Modifier
                                .size(10.dp)
                                .clip(CircleShape)
                                .background(
                                    when (event.eventType) {
                                        "ORIGIN" -> ErrorRed
                                        "ACTION" -> SuccessGreen
                                        "MULE_HOP" -> WarningYellow
                                        "PREDICTION" -> AlertOrange
                                        else -> MediumCyan
                                    }
                                )
                        )
                        if (index < events.size - 1) {
                            Box(
                                modifier = Modifier
                                    .width(2.dp)
                                    .height(36.dp)
                                    .background(BorderTaupe.copy(alpha = 0.25f))
                            )
                        }
                    }

                    Column(modifier = Modifier.weight(1f)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text(
                                text = event.title,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                color = TextOffWhite
                            )
                            Text(
                                text = event.timestamp,
                                fontSize = 10.sp,
                                color = BorderTaupe
                            )
                        }
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            text = event.description,
                            fontSize = 10.sp,
                            color = BorderTaupe,
                            lineHeight = 14.sp
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                    }
                }
            }
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


