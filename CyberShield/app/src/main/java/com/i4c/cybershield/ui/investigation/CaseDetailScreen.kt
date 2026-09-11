package com.i4c.cybershield.ui.investigation

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import com.i4c.cybershield.model.*
import com.i4c.cybershield.ui.theme.*

// ═══════════════════════════════════════════════════════════════════════
//  CASE DETAIL — the full inspection view for exactly ONE case: what
//  happened, why the system flagged it (in plain language), and the
//  investigator's decision. Reached by tapping a case in the queue or a
//  marker on the map; always shows the case that was actually tapped.
// ═══════════════════════════════════════════════════════════════════════

@Composable
fun CaseDetailScreen(
    case: ComplaintTicket,
    userRole: UserRole,
    showApproveDialog: Boolean,
    showBankHoldDialog: Boolean,
    onBack: () -> Unit,
    onApproveClick: () -> Unit,
    onApproveConfirm: () -> Unit,
    onApproveDismiss: () -> Unit,
    onBankHoldClick: () -> Unit,
    onBankHoldConfirm: () -> Unit,
    onBankHoldDismiss: () -> Unit,
    onDismissFalsePositive: () -> Unit,
    onReleaseAfterConfirmation: () -> Unit,
    onFileComplaint: () -> Unit = {},
    onSimulateWithdraw: () -> Unit = {}
) {
    Column(modifier = Modifier.fillMaxSize().background(BgDeepSlate)) {
        // ─── Top Bar ────────────────────────────────────────────────
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.Default.ArrowBack, contentDescription = "Back to case list", tint = TextOffWhite)
            }
            Column(modifier = Modifier.weight(1f)) {
                Text(case.ncrpId, fontSize = 16.sp, fontWeight = FontWeight.Bold, color = TextOffWhite)
                Text("Case review", fontSize = 11.sp, color = BorderTaupe)
            }
            StatusBadge(status = case.status)
            Spacer(modifier = Modifier.width(12.dp))
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp)
                .padding(bottom = 90.dp)
        ) {
            // ─── Plain-language headline ────────────────────────────
            SummaryHeadline(case)
            Spacer(modifier = Modifier.height(16.dp))

            CaseOverviewCard(case)
            Spacer(modifier = Modifier.height(16.dp))
            OperationalIntelCard(case)
            Spacer(modifier = Modifier.height(16.dp))

            MoneyTrailVisual(case.moneyTrail)
            Spacer(modifier = Modifier.height(16.dp))

            TransactionEvidenceCard(case.moneyTrail)
            Spacer(modifier = Modifier.height(16.dp))

            RiskBreakdownCard(case.riskBreakdown)
            Spacer(modifier = Modifier.height(16.dp))

            NotificationDeliveryCard(case)
            Spacer(modifier = Modifier.height(16.dp))

            DecisionBar(
                case = case,
                status = case.status,
                userRole = userRole,
                onApproveClick = onApproveClick,
                onBankHoldClick = onBankHoldClick,
                onDismissFalsePositive = onDismissFalsePositive,
                onReleaseAfterConfirmation = onReleaseAfterConfirmation,
                onFileComplaint = onFileComplaint,
                onSimulateWithdraw = onSimulateWithdraw
            )
        }
    }

    // ─── Confirmation Dialogs ──────────────────────────────────────
    if (showApproveDialog) {
        AlertDialog(
            onDismissRequest = onApproveDismiss,
            containerColor = SurfaceCharcoal,
            titleContentColor = TextOffWhite,
            textContentColor = BorderTaupe,
            title = {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Icon(Icons.Default.Send, contentDescription = null, tint = AlertOrange, modifier = Modifier.size(24.dp))
                    Text("Send this case to police?")
                }
            },
            text = {
                Text(
                    "The nearest police unit to the predicted cash-out location will be notified, along with all evidence for this case.\n\nThis is recorded in the activity log and can't be undone.",
                    lineHeight = 22.sp
                )
            },
            confirmButton = {
                Button(
                    onClick = onApproveConfirm,
                    colors = ButtonDefaults.buttonColors(containerColor = AlertOrange, contentColor = TextOffWhite),
                    shape = RoundedCornerShape(10.dp)
                ) { Text("Send to Police", fontWeight = FontWeight.Bold) }
            },
            dismissButton = { TextButton(onClick = onApproveDismiss) { Text("Cancel", color = BorderTaupe) } },
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
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Icon(Icons.Default.Lock, contentDescription = null, tint = MediumCyan, modifier = Modifier.size(24.dp))
                    Text("Freeze this account?")
                }
            },
            text = {
                Text(
                    "This places an immediate, temporary hold on the account with its bank, stopping withdrawals while the case is investigated. The hold automatically expires after 72 hours unless extended.",
                    lineHeight = 22.sp
                )
            },
            confirmButton = {
                Button(
                    onClick = onBankHoldConfirm,
                    colors = ButtonDefaults.buttonColors(containerColor = MediumCyan, contentColor = BgDeepSlate),
                    shape = RoundedCornerShape(10.dp)
                ) { Text("Freeze Account", fontWeight = FontWeight.Bold) }
            },
            dismissButton = { TextButton(onClick = onBankHoldDismiss) { Text("Cancel", color = BorderTaupe) } },
            shape = RoundedCornerShape(16.dp)
        )
    }
}

@Composable
private fun TransactionEvidenceCard(trail: MoneyTrail) {
    var expandedIndex by remember { mutableStateOf<Int?>(null) }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(colors = listOf(MediumCyan.copy(alpha = 0.3f), Color.Transparent))
        )
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("TRANSACTION EVIDENCE & PROVENANCE", fontSize = 11.sp, color = BorderTaupe, letterSpacing = 2.sp, fontWeight = FontWeight.Bold)
                Text("Tap hop to inspect", fontSize = 10.sp, color = MediumCyan)
            }
            Text(
                "Review each recorded hop before deciding. Values come from the evidence feed; downstream accounts maintain provenance to root victim transaction.",
                fontSize = 11.sp, color = BorderTaupe, lineHeight = 15.sp, modifier = Modifier.padding(top = 6.dp)
            )
            Spacer(modifier = Modifier.height(12.dp))
            trail.edges.forEachIndexed { index, edge ->
                val from = trail.nodes.getOrNull(edge.fromIndex)?.label ?: "Unknown source"
                val fromType = trail.nodes.getOrNull(edge.fromIndex)?.type ?: "account"
                val to = trail.nodes.getOrNull(edge.toIndex)?.label ?: "Unknown destination"
                val toType = trail.nodes.getOrNull(edge.toIndex)?.type ?: "account"
                val isExpanded = expandedIndex == index

                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .background(if (isExpanded) BgDeepSlate.copy(alpha = 0.7f) else Color.Transparent)
                        .clickable { expandedIndex = if (isExpanded) null else index }
                        .padding(vertical = 8.dp, horizontal = if (isExpanded) 10.dp else 0.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.Top
                    ) {
                        Text("${index + 1}", color = MediumCyan, fontWeight = FontWeight.Bold, modifier = Modifier.width(24.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Text("$from  →  $to", color = TextOffWhite, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                            Text(
                                "${edge.amount}  •  ${edge.timestamp}  •  ${edge.channel}",
                                color = BorderTaupe, fontSize = 11.sp, lineHeight = 15.sp,
                                modifier = Modifier.padding(top = 3.dp)
                            )
                        }
                        Icon(
                            imageVector = if (isExpanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                            contentDescription = null,
                            tint = BorderTaupe,
                            modifier = Modifier.size(18.dp)
                        )
                    }

                    if (isExpanded) {
                        Spacer(modifier = Modifier.height(8.dp))
                        Card(
                            shape = RoundedCornerShape(8.dp),
                            colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal.copy(alpha = 0.9f))
                        ) {
                            Column(modifier = Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text("Transaction ID: ${edge.label}", fontSize = 11.sp, color = AlertOrange, fontWeight = FontWeight.SemiBold)
                                Text("Source: $from ($fromType)", fontSize = 11.sp, color = TextOffWhite)
                                Text("Destination: $to ($toType)", fontSize = 11.sp, color = TextOffWhite)
                                Text("Amount: ${edge.amount} INR via ${edge.channel}", fontSize = 11.sp, color = MediumCyan)
                                Text("Settlement: High velocity egress / Layering pattern", fontSize = 10.sp, color = BorderTaupe)
                                Text("Trace Status: Provenance preserved with downstream hash audit", fontSize = 10.sp, color = SuccessGreen)
                            }
                        }
                    }
                }
                if (index < trail.edges.lastIndex) {
                    Divider(color = BorderTaupe.copy(alpha = 0.12f))
                }
            }
        }
    }
}

// ─── Plain-language headline ───────────────────────────────────────────

@Composable
private fun SummaryHeadline(case: ComplaintTicket) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = AlertOrange.copy(alpha = 0.10f)),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(colors = listOf(AlertOrange.copy(alpha = 0.4f), Color.Transparent))
        )
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.WarningAmber, contentDescription = null, tint = AlertOrange, modifier = Modifier.size(18.dp))
                Spacer(modifier = Modifier.width(6.dp))
                Text("IN PLAIN TERMS", fontSize = 10.sp, color = AlertOrange, letterSpacing = 1.5.sp, fontWeight = FontWeight.Bold)
            }
            Spacer(modifier = Modifier.height(8.dp))
            Text(case.summary, fontSize = 15.sp, color = TextOffWhite, lineHeight = 21.sp, fontWeight = FontWeight.Medium)
        }
    }
}

@Composable
private fun OperationalIntelCard(case: ComplaintTicket) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(colors = listOf(AlertOrange.copy(alpha = 0.35f), Color.Transparent))
        )
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Text("OPERATIONAL STATUS", fontSize = 11.sp, color = BorderTaupe, letterSpacing = 2.sp, fontWeight = FontWeight.Bold)
            Spacer(modifier = Modifier.height(8.dp))
            Text("Lifecycle: ${case.lifecycle}", color = TextOffWhite, fontSize = 13.sp)
            Text("Confirmation: ${case.confirmationState}", color = BorderTaupe, fontSize = 12.sp, modifier = Modifier.padding(top = 4.dp))
            Text(
                "Pre-complaint: digital slow/hold. After complaint: online + physical ATM block.",
                color = BorderTaupe, fontSize = 11.sp, lineHeight = 15.sp, modifier = Modifier.padding(top = 6.dp)
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                "Digital block: ${if (case.digitalBlockActive) "ON" else "off"}   ATM block: ${if (case.atmBlockActive) "ON" else "off"}",
                color = MediumCyan, fontSize = 12.sp, fontWeight = FontWeight.SemiBold
            )
            Text("Auto action: ${case.interventionTier.ifBlank { "human review" }}", color = BorderTaupe, fontSize = 12.sp, modifier = Modifier.padding(top = 4.dp))
            if (case.justification.isNotBlank()) {
                Text(case.justification, color = TextOffWhite, fontSize = 12.sp, lineHeight = 17.sp, modifier = Modifier.padding(top = 8.dp))
            }
            Spacer(modifier = Modifier.height(10.dp))
            Text("Existing balance available  ₹${"%.0f".format(case.legitimateBalance)}", color = SuccessGreen, fontSize = 12.sp)
            Text("Suspicious exposure held  ₹${"%.0f".format(case.suspiciousExposure)}", color = AlertOrange, fontSize = 12.sp)
            Spacer(modifier = Modifier.height(8.dp))
            Text("SIM  ${case.simHash.ifBlank { "not supplied" }}", color = BorderTaupe, fontSize = 11.sp)
            Text("Device  ${case.deviceFingerprint.ifBlank { "not supplied" }}", color = BorderTaupe, fontSize = 11.sp)
            if (case.repeatActivity.attempts > 0) {
                Text(
                    "Repeat ATM ${case.repeatActivity.terminalId}: ${case.repeatActivity.attempts} attempts → ${case.repeatActivity.escalation}",
                    color = AlertOrange, fontSize = 12.sp, modifier = Modifier.padding(top = 8.dp)
                )
            }
            if (case.withdrawalAttempts.isNotEmpty()) {
                Spacer(modifier = Modifier.height(10.dp))
                Text("WITHDRAWAL ATTEMPTS", fontSize = 11.sp, color = BorderTaupe, letterSpacing = 1.sp, fontWeight = FontWeight.Bold)
                case.withdrawalAttempts.takeLast(6).forEach { attempt ->
                    Text(
                        "${attempt.time.take(19)}  ${attempt.amount}  ${attempt.terminalId}  ${attempt.status}",
                        color = TextOffWhite, fontSize = 11.sp, modifier = Modifier.padding(top = 4.dp)
                    )
                    Text(attempt.location, color = BorderTaupe, fontSize = 10.sp)
                }
            }
            if (case.nearbyTerminals.isNotEmpty()) {
                Spacer(modifier = Modifier.height(10.dp))
                Text("NEARBY TERMINALS FOR POLICE", fontSize = 11.sp, color = BorderTaupe, letterSpacing = 1.sp, fontWeight = FontWeight.Bold)
                case.nearbyTerminals.take(5).forEach { term ->
                    val km = term.distanceKm?.let { "  ${"%.1f".format(it)} km" } ?: ""
                    Text("${term.id}$km  —  ${term.address}", color = TextOffWhite, fontSize = 11.sp, modifier = Modifier.padding(top = 4.dp))
                }
            }
        }
    }
}

// ─── Section 1: Case Overview ──────────────────────────────────────────

@Composable
private fun CaseOverviewCard(case: ComplaintTicket) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(colors = listOf(BorderTaupe.copy(alpha = 0.4f), Color.Transparent))
        )
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Text("CASE DETAILS", fontSize = 11.sp, color = BorderTaupe, letterSpacing = 2.sp, fontWeight = FontWeight.Bold)
            Spacer(modifier = Modifier.height(12.dp))

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                DetailMetricChip(modifier = Modifier.weight(1f), icon = Icons.Default.MoneyOff, label = "Amount at Risk",
                    value = case.reportedLoss, valueColor = AlertOrange)
                DetailMetricChip(modifier = Modifier.weight(1f), icon = Icons.Default.Timer, label = "Reported",
                    value = case.timeElapsed, valueColor = WarningYellow)
            }
            Spacer(modifier = Modifier.height(12.dp))
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                DetailMetricChip(modifier = Modifier.weight(1f), icon = Icons.Default.Place, label = "Predicted Cash-Out",
                    value = case.targetTerminal.id, valueColor = TextOffWhite)
                DetailMetricChip(modifier = Modifier.weight(1f), icon = Icons.Default.Schedule, label = "Expected Window",
                    value = case.targetTerminal.cashoutWindow, valueColor = TextOffWhite)
            }
        }
    }
}

// ─── Section 2: Money Trail ─────────────────────────────────────────────

@Composable
private fun MoneyTrailVisual(trail: MoneyTrail) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(colors = listOf(BorderTaupe.copy(alpha = 0.4f), Color.Transparent))
        )
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Text("HOW THE MONEY MOVED", fontSize = 11.sp, color = BorderTaupe, letterSpacing = 2.sp, fontWeight = FontWeight.Bold)
            Spacer(modifier = Modifier.height(16.dp))

            Row(
                modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically
            ) {
                trail.nodes.forEachIndexed { index, node ->
                    TrailNodeCard(node)
                    if (index < trail.nodes.size - 1) {
                        Icon(
                            Icons.Default.ArrowForward, contentDescription = null,
                            tint = AlertOrange, modifier = Modifier.padding(horizontal = 6.dp).size(22.dp)
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun TrailNodeCard(node: TrailNode) {
    val (bgColor, borderColor, iconColor, icon) = when (node.type) {
        "victim" -> Quadruple(Color(0xFF2D1F1F), ErrorRed.copy(alpha = 0.4f), ErrorRed, Icons.Default.Person)
        "mule" -> Quadruple(Color(0xFF2D291F), WarningYellow.copy(alpha = 0.4f), WarningYellow, Icons.Default.AccountCircle)
        "aggregator" -> Quadruple(Color(0xFF1F252D), MediumCyan.copy(alpha = 0.4f), MediumCyan, Icons.Default.Hub)
        "terminal" -> Quadruple(Color(0xFF2D1F24), AlertOrange.copy(alpha = 0.4f), AlertOrange, Icons.Default.LocalAtm)
        else -> Quadruple(SurfaceCharcoal, BorderTaupe.copy(alpha = 0.3f), BorderTaupe, Icons.Default.Circle)
    }

    Card(
        modifier = Modifier.width(100.dp).heightIn(min = 100.dp),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = bgColor),
        border = CardDefaults.outlinedCardBorder().copy(brush = Brush.linearGradient(colors = listOf(borderColor, Color.Transparent)))
    ) {
        Column(
            modifier = Modifier.fillMaxSize().padding(10.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Box(
                modifier = Modifier.size(32.dp).clip(CircleShape).background(iconColor.copy(alpha = 0.15f)),
                contentAlignment = Alignment.Center
            ) { Icon(icon, contentDescription = null, tint = iconColor, modifier = Modifier.size(18.dp)) }
            Spacer(modifier = Modifier.height(6.dp))
            Text(node.label, fontSize = 10.sp, fontWeight = FontWeight.SemiBold, color = TextOffWhite,
                textAlign = TextAlign.Center, lineHeight = 13.sp, maxLines = 2)
            Text(node.accountHint, fontSize = 8.sp, color = iconColor.copy(alpha = 0.8f), textAlign = TextAlign.Center)
        }
    }
}

// ─── Section 3: Why This Was Flagged (plain-language evidence) ─────────

@Composable
private fun RiskBreakdownCard(breakdown: RiskBreakdown) {
    var showTechnical by remember { mutableStateOf(false) }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(colors = listOf(AlertOrange.copy(alpha = 0.3f), Color.Transparent))
        )
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("WHY THIS WAS FLAGGED", fontSize = 11.sp, color = BorderTaupe, letterSpacing = 2.sp, fontWeight = FontWeight.Bold)
                Card(
                    shape = RoundedCornerShape(8.dp),
                    colors = CardDefaults.cardColors(containerColor = AlertOrange.copy(alpha = 0.15f))
                ) {
                    Text(
                        "${breakdown.totalPercent}% risk",
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                        fontSize = 12.sp, fontWeight = FontWeight.Bold, color = AlertOrange
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            breakdown.signals.forEachIndexed { index, signal ->
                SignalRow(signal, showTechnical)
                if (index < breakdown.signals.size - 1) Spacer(modifier = Modifier.height(14.dp))
            }

            Spacer(modifier = Modifier.height(12.dp))

            TextButton(onClick = { showTechnical = !showTechnical }, modifier = Modifier.align(Alignment.End)) {
                Text(
                    if (showTechnical) "Hide technical details" else "Show technical details",
                    fontSize = 11.sp, color = BorderTaupe
                )
            }

            Spacer(modifier = Modifier.height(4.dp))

            Column {
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("OVERALL RISK SCORE", fontSize = 11.sp, color = TextOffWhite, fontWeight = FontWeight.Bold, letterSpacing = 1.sp)
                    Text("${breakdown.totalPercent}%", fontSize = 14.sp, color = AlertOrange, fontWeight = FontWeight.Black)
                }
                Spacer(modifier = Modifier.height(6.dp))
                LinearProgressIndicator(
                    progress = breakdown.totalPercent / 100f,
                    modifier = Modifier.fillMaxWidth().height(8.dp).clip(RoundedCornerShape(4.dp)),
                    color = AlertOrange, trackColor = AlertOrange.copy(alpha = 0.15f)
                )
                Text(
                    "This score combines every signal below — it is a ranking to help you prioritize, not proof of guilt.",
                    fontSize = 10.sp, color = BorderTaupe, modifier = Modifier.padding(top = 6.dp), lineHeight = 14.sp
                )
            }
        }
    }
}

@Composable
private fun SignalRow(signal: RiskSignal, showTechnical: Boolean) {
    val signalColor = when {
        signal.contributionPercent >= 30 -> AlertOrange
        signal.contributionPercent >= 18 -> MediumCyan
        else -> WarningYellow
    }

    Column(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top
        ) {
            Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.weight(1f)) {
                Text(text = signal.icon, fontSize = 16.sp)
                Column {
                    Text(signal.name, fontSize = 14.sp, fontWeight = FontWeight.SemiBold, color = TextOffWhite)
                    Text(signal.explanation, fontSize = 12.sp, color = BorderTaupe, lineHeight = 16.sp)
                    if (showTechnical && signal.technicalTag.isNotBlank()) {
                        Text(
                            "rule: ${signal.technicalTag}", fontSize = 10.sp, color = BorderTaupe.copy(alpha = 0.6f),
                            modifier = Modifier.padding(top = 2.dp)
                        )
                    }
                }
            }
            Text("+${signal.contributionPercent}%", fontSize = 15.sp, fontWeight = FontWeight.Black, color = signalColor)
        }
        Spacer(modifier = Modifier.height(6.dp))
        LinearProgressIndicator(
            progress = signal.contributionPercent / 100f,
            modifier = Modifier.fillMaxWidth().height(4.dp).clip(RoundedCornerShape(2.dp)),
            color = signalColor, trackColor = signalColor.copy(alpha = 0.12f)
        )
    }
}

// ─── Section 4: Decision Bar ────────────────────────────────────────────

@Composable
private fun DecisionBar(
    case: ComplaintTicket,
    status: ActionStatus,
    userRole: UserRole,
    onApproveClick: () -> Unit,
    onBankHoldClick: () -> Unit,
    onDismissFalsePositive: () -> Unit,
    onReleaseAfterConfirmation: () -> Unit,
    onFileComplaint: () -> Unit,
    onSimulateWithdraw: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(colors = listOf(BorderTaupe.copy(alpha = 0.3f), Color.Transparent))
        )
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Box(
                    modifier = Modifier.size(10.dp).clip(CircleShape).background(
                        when (status) {
                            ActionStatus.APPROVED -> SuccessGreen
                            ActionStatus.BANK_HOLD -> MediumCyan
                            ActionStatus.DISMISSED, ActionStatus.RELEASED -> BorderTaupe
                            else -> AlertOrange
                        }
                    )
                )
                Text(
                    "STATUS: ${status.displayName}".uppercase(), fontSize = 12.sp, fontWeight = FontWeight.Bold,
                    color = when (status) {
                        ActionStatus.APPROVED -> SuccessGreen
                        ActionStatus.BANK_HOLD -> MediumCyan
                        ActionStatus.DISMISSED, ActionStatus.RELEASED -> BorderTaupe
                        else -> AlertOrange
                    },
                    letterSpacing = 1.sp
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            if (userRole == UserRole.POLICE_INVESTIGATOR &&
                (status == ActionStatus.APPROVED || status == ActionStatus.EN_ROUTE)
            ) {
                Text(
                    "Bank officials forwarded this case. Use the predicted terminal and nearby locations as field evidence — the app does not track a person.",
                    fontSize = 12.sp, color = BorderTaupe, lineHeight = 17.sp,
                    modifier = Modifier.padding(bottom = 10.dp)
                )
                Text("Predicted cash-out", fontSize = 11.sp, color = AlertOrange, fontWeight = FontWeight.Bold)
                Text(
                    "${case.targetTerminal.id}\n${case.targetTerminal.address}\nWindow: ${case.targetTerminal.cashoutWindow}",
                    fontSize = 13.sp, color = TextOffWhite, lineHeight = 18.sp,
                    modifier = Modifier.padding(top = 4.dp, bottom = 12.dp)
                )
                Text(
                    "Repeated use of the same account at the same ATM should be treated as persistent terminal risk and passed to the local unit with this evidence pack.",
                    fontSize = 12.sp, color = BorderTaupe, lineHeight = 17.sp
                )
                Spacer(modifier = Modifier.height(12.dp))
                Button(
                    onClick = onSimulateWithdraw,
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = AlertOrange, contentColor = TextOffWhite)
                ) {
                    Text("Record cash-out attempt at this ATM", fontWeight = FontWeight.Bold, fontSize = 13.sp)
                }
            } else if (status == ActionStatus.PENDING && userRole == UserRole.BANK_OFFICIAL) {
                Text(
                    "Choose one action for this case:",
                    fontSize = 12.sp, color = BorderTaupe, modifier = Modifier.padding(bottom = 10.dp)
                )

                Button(
                    onClick = onApproveClick,
                    modifier = Modifier.fillMaxWidth().height(50.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = AlertOrange, contentColor = TextOffWhite)
                ) {
                    Icon(Icons.Default.Send, contentDescription = null, modifier = Modifier.size(20.dp))
                    Spacer(modifier = Modifier.width(10.dp))
                    Text("Send to Police", fontWeight = FontWeight.Bold, fontSize = 14.sp)
                }

                Spacer(modifier = Modifier.height(10.dp))

                OutlinedButton(
                    onClick = onBankHoldClick,
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = BorderTaupe),
                    border = ButtonDefaults.outlinedButtonBorder.copy(
                        brush = Brush.linearGradient(colors = listOf(BorderTaupe.copy(alpha = 0.5f), BorderTaupe.copy(alpha = 0.2f)))
                    )
                ) {
                    Icon(Icons.Default.Lock, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(10.dp))
                    Text("Freeze Account (Bank Hold)", fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                }

                Spacer(modifier = Modifier.height(4.dp))

                TextButton(onClick = onDismissFalsePositive, modifier = Modifier.fillMaxWidth()) {
                    Text("Not Suspicious — Dismiss", color = BorderTaupe.copy(alpha = 0.7f), fontSize = 12.sp, fontWeight = FontWeight.Medium)
                }
                Spacer(modifier = Modifier.height(4.dp))
                TextButton(onClick = onFileComplaint, modifier = Modifier.fillMaxWidth()) {
                    Text("NCRP complaint filed — hard block ATM + digital", color = MediumCyan, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                }
            } else if (status == ActionStatus.BANK_HOLD && userRole == UserRole.BANK_OFFICIAL) {
                Text(
                    "Only release this hold after the bank has confirmed the customer and recorded that the activity is legitimate.",
                    fontSize = 12.sp, color = BorderTaupe, lineHeight = 17.sp,
                    modifier = Modifier.padding(bottom = 10.dp)
                )
                Button(
                    onClick = onApproveClick,
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = AlertOrange, contentColor = TextOffWhite)
                ) {
                    Text("Forward frozen case to police", fontWeight = FontWeight.Bold, fontSize = 13.sp)
                }
                Spacer(modifier = Modifier.height(10.dp))
                var showReleaseConfirmation by remember { mutableStateOf(false) }
                OutlinedButton(
                    onClick = { showReleaseConfirmation = true },
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = SuccessGreen)
                ) {
                    Icon(Icons.Default.LockOpen, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Release after customer confirmation", fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                }
                if (showReleaseConfirmation) {
                    AlertDialog(
                        onDismissRequest = { showReleaseConfirmation = false },
                        containerColor = SurfaceCharcoal,
                        titleContentColor = TextOffWhite,
                        textContentColor = BorderTaupe,
                        title = { Text("Confirm hold release") },
                        text = {
                            Text("Confirm that the bank official has spoken with the customer, verified the activity, and recorded it as not malicious.")
                        },
                        confirmButton = {
                            Button(
                                onClick = {
                                    showReleaseConfirmation = false
                                    onReleaseAfterConfirmation()
                                },
                                colors = ButtonDefaults.buttonColors(containerColor = SuccessGreen, contentColor = BgDeepSlate)
                            ) { Text("Confirm and release") }
                        },
                        dismissButton = {
                            TextButton(onClick = { showReleaseConfirmation = false }) { Text("Cancel", color = BorderTaupe) }
                        }
                    )
                }
            } else {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = when (status) {
                            ActionStatus.APPROVED -> SuccessGreen.copy(alpha = 0.12f)
                            ActionStatus.BANK_HOLD -> MediumCyan.copy(alpha = 0.12f)
                            ActionStatus.RELEASED -> SuccessGreen.copy(alpha = 0.12f)
                            else -> BorderTaupe.copy(alpha = 0.08f)
                        }
                    )
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.Center
                    ) {
                        Icon(
                            imageVector = when (status) {
                                ActionStatus.APPROVED -> Icons.Default.CheckCircle
                                ActionStatus.BANK_HOLD -> Icons.Default.Lock
                                ActionStatus.RELEASED -> Icons.Default.LockOpen
                                else -> Icons.Default.Cancel
                            },
                            contentDescription = null,
                            tint = when (status) {
                                ActionStatus.APPROVED -> SuccessGreen
                                ActionStatus.BANK_HOLD -> MediumCyan
                                ActionStatus.RELEASED -> SuccessGreen
                                else -> BorderTaupe
                            },
                            modifier = Modifier.size(24.dp)
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Text(
                            status.displayName, fontWeight = FontWeight.Bold, fontSize = 16.sp,
                            color = when (status) {
                                ActionStatus.APPROVED -> SuccessGreen
                                ActionStatus.BANK_HOLD -> MediumCyan
                                ActionStatus.RELEASED -> SuccessGreen
                                else -> BorderTaupe
                            }
                        )
                    }
                }
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    "This case has already been reviewed. No further action is needed here.",
                    fontSize = 11.sp, color = BorderTaupe, textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth().padding(top = 4.dp)
                )
            }
        }
    }
}

// ─── Shared Composables ────────────────────────────────────────────────

@Composable
fun StatusBadge(status: ActionStatus) {
    val (color, text) = when (status) {
        ActionStatus.PENDING -> AlertOrange to "NEEDS REVIEW"
        ActionStatus.APPROVED -> SuccessGreen to "SENT TO POLICE"
        ActionStatus.BANK_HOLD -> MediumCyan to "ACCOUNT FROZEN"
        ActionStatus.DISMISSED -> BorderTaupe to "DISMISSED"
        ActionStatus.EN_ROUTE -> InfoBlue to "EN ROUTE"
        ActionStatus.LIEN_PLACED -> SuccessGreen to "HOLD CONFIRMED"
        ActionStatus.RELEASED -> SuccessGreen to "HOLD RELEASED"
    }

    Card(shape = RoundedCornerShape(6.dp), colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.15f))) {
        Text(
            text = text, modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
            fontSize = 10.sp, fontWeight = FontWeight.Bold, color = color, letterSpacing = 1.sp
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
            brush = Brush.linearGradient(colors = listOf(BorderTaupe.copy(alpha = 0.3f), Color.Transparent))
        )
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Icon(icon, contentDescription = null, tint = BorderTaupe, modifier = Modifier.size(14.dp))
                Text(label, fontSize = 10.sp, color = BorderTaupe, letterSpacing = 0.5.sp)
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text(value, fontSize = 16.sp, fontWeight = FontWeight.Bold, color = valueColor, maxLines = 1)
        }
    }
}

@Composable
fun NotificationDeliveryCard(case: ComplaintTicket) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(colors = listOf(MediumCyan.copy(alpha = 0.4f), Color.Transparent))
        )
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Icon(
                    Icons.Default.Notifications,
                    contentDescription = null,
                    tint = MediumCyan,
                    modifier = Modifier.size(18.dp)
                )
                Text(
                    "SMS & Email Notifications",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                    color = TextOffWhite
                )
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                "Authoritative delivery audit log synchronized with backend",
                fontSize = 11.sp,
                color = BorderTaupe
            )
            Spacer(modifier = Modifier.height(12.dp))

            // Channel Badges Row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                val smsStatus = case.notificationStatus["SMS"]
                val emailStatus = case.notificationStatus["EMAIL"]

                ChannelStatusTile(
                    modifier = Modifier.weight(1f),
                    channel = "SMS",
                    status = smsStatus?.status ?: if (case.notifications.any { it.channel == "SMS" }) "SENT" else "NOT_SENT",
                    isSimulated = smsStatus?.isSimulated ?: true,
                    count = smsStatus?.count ?: case.notifications.count { it.channel == "SMS" }
                )

                ChannelStatusTile(
                    modifier = Modifier.weight(1f),
                    channel = "EMAIL",
                    status = emailStatus?.status ?: if (case.notifications.any { it.channel == "EMAIL" }) "SENT" else "NOT_SENT",
                    isSimulated = emailStatus?.isSimulated ?: true,
                    count = emailStatus?.count ?: case.notifications.count { it.channel == "EMAIL" }
                )
            }

            // Recent Notification Items Preview
            if (case.notifications.isNotEmpty()) {
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    "DISPATCHED NOTIFICATIONS (${case.notifications.size})",
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                    color = BorderTaupe,
                    letterSpacing = 0.5.sp
                )
                Spacer(modifier = Modifier.height(6.dp))

                case.notifications.take(3).forEach { notif ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp)
                            .background(BgDeepSlate, RoundedCornerShape(8.dp))
                            .padding(8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Box(
                            modifier = Modifier
                                .background(if (notif.channel == "SMS") MediumCyan.copy(alpha = 0.15f) else AlertOrange.copy(alpha = 0.15f), RoundedCornerShape(4.dp))
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                        ) {
                            Text(
                                notif.channel,
                                fontSize = 10.sp,
                                fontWeight = FontWeight.Bold,
                                color = if (notif.channel == "SMS") MediumCyan else AlertOrange
                            )
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    notif.eventType.replace("_", " "),
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    color = TextOffWhite
                                )
                                Spacer(modifier = Modifier.width(6.dp))
                                Text(
                                    "→ ${notif.recipient}",
                                    fontSize = 10.sp,
                                    color = BorderTaupe,
                                    maxLines = 1
                                )
                            }
                            if (notif.preview.isNotBlank()) {
                                Text(
                                    notif.preview.lines().firstOrNull() ?: notif.preview,
                                    fontSize = 10.sp,
                                    color = BorderTaupe,
                                    maxLines = 1
                                )
                            }
                        }
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            if (notif.status == "SENT") "✓" else "✗",
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            color = if (notif.status == "SENT") Color(0xFF10B981) else Color(0xFFEF4444)
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ChannelStatusTile(
    modifier: Modifier = Modifier,
    channel: String,
    status: String,
    isSimulated: Boolean,
    count: Int
) {
    val isSent = status.equals("SENT", ignoreCase = true)
    val isFailed = status.equals("FAILED", ignoreCase = true)
    val isRetrying = status.equals("RETRYING", ignoreCase = true)

    val badgeBg = when {
        isSent -> Color(0xFF065F46)
        isFailed -> Color(0xFF7F1D1D)
        isRetrying -> Color(0xFF78350F)
        else -> BgDeepSlate
    }
    val badgeText = when {
        isSent -> Color(0xFF34D399)
        isFailed -> Color(0xFFF87171)
        isRetrying -> Color(0xFFFBBF24)
        else -> BorderTaupe
    }
    val statusLabel = when {
        isSent -> "✓ SENT"
        isFailed -> "✗ FAILED"
        isRetrying -> "⟳ RETRYING"
        else -> "STANDBY"
    }

    Box(
        modifier = modifier
            .background(BgDeepSlate, RoundedCornerShape(10.dp))
            .padding(10.dp)
    ) {
        Column {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(channel, fontSize = 12.sp, fontWeight = FontWeight.Bold, color = TextOffWhite)
                Box(
                    modifier = Modifier
                        .background(badgeBg, RoundedCornerShape(4.dp))
                        .padding(horizontal = 6.dp, vertical = 2.dp)
                ) {
                    Text(statusLabel, fontSize = 9.sp, fontWeight = FontWeight.Bold, color = badgeText)
                }
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                if (isSimulated) "Simulated Delivery" else "Live Gateway",
                fontSize = 10.sp,
                color = BorderTaupe
            )
        }
    }
}
