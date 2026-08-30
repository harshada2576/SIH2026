package com.i4c.cybershield.ui.dispatch

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.i4c.cybershield.model.*
import com.i4c.cybershield.ui.investigation.StatusBadge
import com.i4c.cybershield.ui.theme.*

// ═══════════════════════════════════════════════════════════════════════
//  TAB 3: DISPATCH CENTER & AUDIT TRAIL
//  Summary metrics, pending review queue, and chronological audit log.
// ═══════════════════════════════════════════════════════════════════════

@Composable
fun DispatchScreen(
    summaries: List<DispatchSummary>,
    pendingReviews: List<PendingReviewItem>,
    auditLog: List<AuditLogEntry>,
    onInspectApprove: (String) -> Unit
) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(BgDeepSlate)
            .padding(horizontal = 16.dp)
            .padding(top = 12.dp, bottom = 90.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // ─── Top Summary Cards Grid ────────────────────────────────
        item {
            Text(
                text = "DISPATCH CENTER",
                fontSize = 11.sp,
                color = BorderTaupe,
                letterSpacing = 2.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(bottom = 4.dp)
            )
        }

        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                summaries.forEach { summary ->
                    SummaryCard(
                        modifier = Modifier.weight(1f),
                        summary = summary
                    )
                }
            }
        }

        // ─── Section A: Pending Review Queue ───────────────────────
        item {
            Spacer(modifier = Modifier.height(4.dp))
            SectionHeader(
                title = "PENDING REVIEW QUEUE",
                count = pendingReviews.size,
                icon = Icons.Default.PendingActions
            )
        }

        if (pendingReviews.isEmpty()) {
            item {
                EmptyStateCard(message = "No pending reviews at this time.")
            }
        } else {
            items(pendingReviews) { item ->
                PendingReviewCard(
                    item = item,
                    onInspectClick = { onInspectApprove(item.ticket.ncrpId) }
                )
            }
        }

        // ─── Section B: Chronological Audit Log ────────────────────
        item {
            Spacer(modifier = Modifier.height(4.dp))
            SectionHeader(
                title = "AUDIT LOG",
                count = auditLog.size,
                icon = Icons.Default.History
            )
        }

        items(auditLog) { entry ->
            AuditLogCard(entry = entry)
        }

        // Bottom spacer
        item { Spacer(modifier = Modifier.height(16.dp)) }
    }
}

// ─── Summary Card ──────────────────────────────────────────────────────

@Composable
private fun SummaryCard(
    modifier: Modifier = Modifier,
    summary: DispatchSummary
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(
                colors = listOf(summary.accentColor.copy(alpha = 0.3f), Color.Transparent)
            )
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = summary.count.toString(),
                fontSize = 32.sp,
                fontWeight = FontWeight.Black,
                color = summary.accentColor
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = summary.title,
                fontSize = 10.sp,
                color = BorderTaupe,
                fontWeight = FontWeight.Medium,
                letterSpacing = 0.5.sp
            )
        }
    }
}

// ─── Section Header ────────────────────────────────────────────────────

@Composable
private fun SectionHeader(
    title: String,
    count: Int,
    icon: ImageVector
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = BorderTaupe,
                modifier = Modifier.size(18.dp)
            )
            Text(
                text = title,
                fontSize = 11.sp,
                color = BorderTaupe,
                letterSpacing = 2.sp,
                fontWeight = FontWeight.Bold
            )
        }

        Card(
            shape = RoundedCornerShape(8.dp),
            colors = CardDefaults.cardColors(
                containerColor = AlertOrange.copy(alpha = 0.15f)
            )
        ) {
            Text(
                text = count.toString(),
                modifier = Modifier.padding(horizontal = 10.dp, vertical = 3.dp),
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                color = AlertOrange
            )
        }
    }
}

// ─── Pending Review Card ───────────────────────────────────────────────

@Composable
private fun PendingReviewCard(
    item: PendingReviewItem,
    onInspectClick: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(
                colors = listOf(AlertOrange.copy(alpha = 0.2f), Color.Transparent)
            )
        )
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Priority badge
                Card(
                    shape = RoundedCornerShape(6.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = AlertOrange.copy(alpha = 0.12f)
                    )
                ) {
                    Text(
                        text = "P${item.priorityRank}",
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                        color = AlertOrange
                    )
                }

                StatusBadge(status = item.ticket.status)
            }

            Spacer(modifier = Modifier.height(10.dp))

            Text(
                text = item.ticket.ncrpId,
                fontSize = 16.sp,
                fontWeight = FontWeight.Bold,
                color = TextOffWhite
            )

            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                // Loss Amount
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Icon(
                        Icons.Default.MoneyOff,
                        contentDescription = null,
                        tint = AlertOrange,
                        modifier = Modifier.size(14.dp)
                    )
                    Text(
                        text = item.ticket.reportedLoss,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = AlertOrange
                    )
                }

                // Target ATM
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Icon(
                        Icons.Default.LocalAtm,
                        contentDescription = null,
                        tint = BorderTaupe,
                        modifier = Modifier.size(14.dp)
                    )
                    Text(
                        text = item.ticket.targetTerminal.id,
                        fontSize = 13.sp,
                        color = BorderTaupe
                    )
                }

                // Time
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Icon(
                        Icons.Default.Timer,
                        contentDescription = null,
                        tint = BorderTaupe,
                        modifier = Modifier.size(14.dp)
                    )
                    Text(
                        text = item.ticket.timeElapsed,
                        fontSize = 13.sp,
                        color = BorderTaupe
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            Button(
                onClick = onInspectClick,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(44.dp),
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = AlertOrange,
                    contentColor = TextOffWhite
                )
            ) {
                Icon(
                    Icons.Default.Visibility,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "Inspect & Approve",
                    fontWeight = FontWeight.Bold,
                    fontSize = 13.sp
                )
            }
        }
    }
}

// ─── Audit Log Card ────────────────────────────────────────────────────

@Composable
private fun AuditLogCard(entry: AuditLogEntry) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(
                colors = listOf(BorderTaupe.copy(alpha = 0.15f), Color.Transparent)
            )
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            verticalAlignment = Alignment.Top,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // Timeline dot and line
            Column(
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Box(
                    modifier = Modifier
                        .size(10.dp)
                        .clip(CircleShape)
                        .background(
                            when (entry.status) {
                                ActionStatus.EN_ROUTE -> InfoBlue
                                ActionStatus.LIEN_PLACED -> SuccessGreen
                                ActionStatus.APPROVED -> SuccessGreen
                                else -> BorderTaupe
                            }
                        )
                )
                Box(
                    modifier = Modifier
                        .width(2.dp)
                        .height(30.dp)
                        .background(BorderTaupe.copy(alpha = 0.2f))
                )
            }

            // Timestamp
            Column(
                modifier = Modifier.width(55.dp)
            ) {
                Text(
                    text = entry.timestamp,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    color = TextOffWhite
                )
            }

            // Details
            Column(modifier = Modifier.weight(1f)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = entry.officerName,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = TextOffWhite
                    )
                    StatusBadge(status = entry.status)
                }

                Spacer(modifier = Modifier.height(4.dp))

                Text(
                    text = entry.action,
                    fontSize = 12.sp,
                    color = BorderTaupe,
                    lineHeight = 17.sp
                )

                Spacer(modifier = Modifier.height(2.dp))

                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Text(
                        text = entry.ncrpId,
                        fontSize = 10.sp,
                        color = AlertOrange.copy(alpha = 0.8f),
                        fontWeight = FontWeight.Medium
                    )
                    Text(
                        text = "→ ${entry.targetUnit}",
                        fontSize = 10.sp,
                        color = BorderTaupe.copy(alpha = 0.7f)
                    )
                }
            }
        }
    }
}

// ─── Empty State ───────────────────────────────────────────────────────

@Composable
private fun EmptyStateCard(message: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal)
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(32.dp),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = message,
                fontSize = 14.sp,
                color = BorderTaupe
            )
        }
    }
}
