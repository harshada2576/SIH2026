package com.i4c.cybershield.ui.activity

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.History
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.i4c.cybershield.model.ActionStatus
import com.i4c.cybershield.model.AuditLogEntry
import com.i4c.cybershield.ui.theme.*

// ═══════════════════════════════════════════════════════════════════════
//  ACTIVITY — the accountability trail. Every action any officer has taken
//  on any case, in order, so it's always clear who did what and when.
// ═══════════════════════════════════════════════════════════════════════

@Composable
fun ActivityScreen(auditLog: List<AuditLogEntry>) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(BgDeepSlate)
            .padding(horizontal = 16.dp)
            .padding(top = 12.dp, bottom = 90.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Text("Activity", fontSize = 22.sp, fontWeight = FontWeight.Bold, color = TextOffWhite)
            Text(
                "A record of every action taken on every case — for accountability.",
                fontSize = 13.sp, color = BorderTaupe, modifier = Modifier.padding(top = 2.dp, bottom = 8.dp)
            )
        }

        if (auditLog.isEmpty()) {
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(14.dp),
                    colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal)
                ) {
                    Box(modifier = Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) {
                        Text("No actions recorded yet.", fontSize = 14.sp, color = BorderTaupe)
                    }
                }
            }
        } else {
            items(auditLog) { entry -> AuditLogCard(entry = entry) }
        }

        item { Spacer(modifier = Modifier.height(16.dp)) }
    }
}

@Composable
private fun AuditLogCard(entry: AuditLogEntry) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCharcoal),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(colors = listOf(BorderTaupe.copy(alpha = 0.15f), Color.Transparent))
        )
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(14.dp),
            verticalAlignment = Alignment.Top,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Box(
                modifier = Modifier
                    .padding(top = 4.dp)
                    .size(10.dp)
                    .clip(CircleShape)
                    .background(
                        when (entry.status) {
                            ActionStatus.EN_ROUTE -> InfoBlue
                            ActionStatus.LIEN_PLACED, ActionStatus.APPROVED, ActionStatus.RELEASED -> SuccessGreen
                            else -> BorderTaupe
                        }
                    )
            )

            Column(modifier = Modifier.weight(1f)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(entry.officerName, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = TextOffWhite)
                    Text(entry.timestamp, fontSize = 11.sp, color = BorderTaupe)
                }

                Spacer(modifier = Modifier.height(4.dp))
                Text(entry.action, fontSize = 12.sp, color = BorderTaupe, lineHeight = 17.sp)
                Spacer(modifier = Modifier.height(4.dp))

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(entry.ncrpId, fontSize = 10.sp, color = AlertOrange.copy(alpha = 0.8f), fontWeight = FontWeight.Medium)
                    if (entry.targetUnit != "—") {
                        Text("→ ${entry.targetUnit}", fontSize = 10.sp, color = BorderTaupe.copy(alpha = 0.7f))
                    }
                }
            }
        }
    }
}
