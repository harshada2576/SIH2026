package com.i4c.cybershield.ui.cases

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.i4c.cybershield.data.MockDataRepository
import com.i4c.cybershield.model.*
import com.i4c.cybershield.ui.investigation.StatusBadge
import com.i4c.cybershield.ui.theme.*

// ═══════════════════════════════════════════════════════════════════════
//  CASE QUEUE — every suspicious money-flow case the system has flagged,
//  in one list. Tap any case to inspect its evidence and decide on it.
//  This is the investigator's main working screen.
// ═══════════════════════════════════════════════════════════════════════

private enum class QueueFilter(val label: String) {
    PENDING("Needs Review"),
    ALL("All Cases"),
    RESOLVED("Resolved")
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CasesScreen(
    allCases: List<ComplaintTicket>,
    summaries: List<DispatchSummary>,
    userRole: UserRole,
    backendMessage: String = "",
    backendOnline: Boolean = true,
    onCaseSelected: (String) -> Unit
) {
    var filter by remember { mutableStateOf(QueueFilter.PENDING) }

    val visibleCases = when (filter) {
        QueueFilter.PENDING -> if (userRole == UserRole.BANK_OFFICIAL) {
            allCases.filter { it.status == ActionStatus.PENDING }
        } else {
            allCases.filter { it.status == ActionStatus.APPROVED || it.status == ActionStatus.EN_ROUTE }
        }
        QueueFilter.RESOLVED -> allCases.filterNot { it.status == ActionStatus.PENDING }
        QueueFilter.ALL -> allCases
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(BgDeepSlate)
            .padding(horizontal = 16.dp)
            .padding(top = 12.dp, bottom = 90.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        item {
            Text(
                text = if (userRole == UserRole.BANK_OFFICIAL) "Bank review queue" else "Forwarded police cases",
                fontSize = 22.sp,
                fontWeight = FontWeight.Bold,
                color = TextOffWhite
            )
            Text(
                text = backendMessage.ifBlank {
                    if (userRole == UserRole.BANK_OFFICIAL) {
                        "Inspect evidence before placing a provisional hold or forwarding a case."
                    } else {
                        "Cases forwarded by bank officials with location and money-trail evidence."
                    }
                },
                fontSize = 13.sp,
                color = if (backendOnline) BorderTaupe else AlertOrange,
                modifier = Modifier.padding(top = 2.dp)
            )
        }

        // ─── Summary Cards ─────────────────────────────────────────
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                summaries.forEach { summary ->
                    SummaryCard(modifier = Modifier.weight(1f), summary = summary)
                }
            }
        }

        // ─── Filter Chips ──────────────────────────────────────────
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                QueueFilter.entries.forEach { f ->
                    val isSelected = filter == f
                    FilterChip(
                        selected = isSelected,
                        onClick = { filter = f },
                        label = {
                            Text(
                                if (f == QueueFilter.PENDING && userRole == UserRole.POLICE_INVESTIGATOR)
                                    "Forwarded"
                                else f.label,
                                fontSize = 12.sp
                            )
                        },
                        colors = FilterChipDefaults.filterChipColors(
                            containerColor = ChipUnselectedBg,
                            labelColor = BorderTaupe,
                            selectedContainerColor = ChipSelectedBg,
                            selectedLabelColor = AlertOrange
                        ),
                        border = FilterChipDefaults.filterChipBorder(
                            borderColor = BorderTaupe.copy(alpha = 0.3f),
                            selectedBorderColor = AlertOrange.copy(alpha = 0.5f)
                        ),
                        shape = RoundedCornerShape(20.dp)
                    )
                }
            }
        }

        if (visibleCases.isEmpty()) {
            item { EmptyStateCard(message = "No cases in this view right now.") }
        } else {
            items(visibleCases, key = { it.ncrpId }) { case ->
                CaseCard(case = case, onClick = { onCaseSelected(case.ncrpId) })
            }
        }

        item { Spacer(modifier = Modifier.height(16.dp)) }
    }
}

// ─── Summary Card ──────────────────────────────────────────────────────

@Composable
private fun SummaryCard(modifier: Modifier = Modifier, summary: DispatchSummary) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(colors = listOf(summary.accentColor.copy(alpha = 0.3f), Color.Transparent))
        )
    ) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(summary.count.toString(), fontSize = 26.sp, fontWeight = FontWeight.Black, color = summary.accentColor)
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                summary.title, fontSize = 10.sp, color = BorderTaupe,
                fontWeight = FontWeight.Medium, textAlign = androidx.compose.ui.text.style.TextAlign.Center
            )
        }
    }
}

// ─── Case Card (one row per suspicious case) ───────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CaseCard(case: ComplaintTicket, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        onClick = onClick,
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(
                colors = listOf(MockDataRepository.riskBadgeColor(case.riskBreakdown.totalPercent).copy(alpha = 0.35f), Color.Transparent)
            )
        )
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(case.ncrpId, fontSize = 15.sp, fontWeight = FontWeight.Bold, color = TextOffWhite)
                StatusBadge(status = case.status)
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Plain-language summary — the whole point: an officer should
            // understand the case without decoding any jargon.
            Text(
                text = case.summary,
                fontSize = 13.sp,
                color = BorderTaupe,
                lineHeight = 18.sp
            )

            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                IconStat(icon = Icons.Default.MoneyOff, text = case.reportedLoss, tint = AlertOrange)
                IconStat(icon = Icons.Default.Place, text = case.targetTerminal.id, tint = BorderTaupe)
                IconStat(icon = Icons.Default.Timer, text = case.timeElapsed, tint = BorderTaupe)
            }

            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Box(
                        modifier = Modifier
                            .background(
                                MockDataRepository.riskBadgeColor(case.riskBreakdown.totalPercent).copy(alpha = 0.15f),
                                RoundedCornerShape(6.dp)
                            )
                            .padding(horizontal = 8.dp, vertical = 3.dp)
                    ) {
                        Text(
                            "${case.riskBreakdown.totalPercent}% risk",
                            fontSize = 11.sp, fontWeight = FontWeight.Bold,
                            color = MockDataRepository.riskBadgeColor(case.riskBreakdown.totalPercent)
                        )
                    }
                }

                if (case.status == ActionStatus.PENDING) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("Review case", fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = AlertOrange)
                        Icon(Icons.Default.ChevronRight, contentDescription = null, tint = AlertOrange, modifier = Modifier.size(18.dp))
                    }
                } else {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("View details", fontSize = 12.sp, color = BorderTaupe)
                        Icon(Icons.Default.ChevronRight, contentDescription = null, tint = BorderTaupe, modifier = Modifier.size(18.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun IconStat(icon: androidx.compose.ui.graphics.vector.ImageVector, text: String, tint: Color) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(14.dp))
        Text(text, fontSize = 12.sp, color = tint)
    }
}

@Composable
private fun EmptyStateCard(message: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal)
    ) {
        Box(modifier = Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) {
            Text(message, fontSize = 14.sp, color = BorderTaupe)
        }
    }
}
