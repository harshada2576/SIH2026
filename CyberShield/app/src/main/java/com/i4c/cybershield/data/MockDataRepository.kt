package com.i4c.cybershield.data

import androidx.compose.ui.graphics.Color
import com.i4c.cybershield.model.*
import com.i4c.cybershield.ui.theme.AlertOrange
import com.i4c.cybershield.ui.theme.BorderTaupe
import com.i4c.cybershield.ui.theme.MediumCyan
import com.i4c.cybershield.ui.theme.SuccessGreen

// ═══════════════════════════════════════════════════════════════════════
//  MOCK DATA REPOSITORY
//  Provides all pre-populated offline data for every screen.
//  No backend connection required during presentation.
// ═══════════════════════════════════════════════════════════════════════

object MockDataRepository {

    // ─── Authorized Email Domains ──────────────────────────────────────
    val authorizedDomains = listOf(
        "@police.gov.in",
        "@gov.in",
        "@rbi.org.in"
    )

    // ─── OTP for demo (always "123456") ────────────────────────────────
    const val demoOtp = "123456"

    // ─── Terminal Markers ──────────────────────────────────────────────
    val terminalMarkers = listOf(
        TerminalMarker(
            id = "ATM-SBI-ND-042",
            address = "Block K, Sector 18, Noida, UP 201301",
            type = TerminalType.BANK_ATM,
            latitude = 28.5708,
            longitude = 77.3261,
            riskLevel = RiskLevel.CRITICAL,
            confidencePercent = 87,
            cashoutWindow = "10:30 AM – 11:15 AM",
            bankName = "SBI"
        ),
        TerminalMarker(
            id = "AEPS-PM-ND-118",
            address = "Shop 12, Atta Market, Sector 18, Noida",
            type = TerminalType.AEPS_MICRO_ATM,
            latitude = 28.5722,
            longitude = 77.3248,
            riskLevel = RiskLevel.CRITICAL,
            confidencePercent = 92,
            cashoutWindow = "10:45 AM – 11:30 AM",
            bankName = "Paytm Payments Bank"
        ),
        TerminalMarker(
            id = "ATM-HDFC-ND-087",
            address = "DLF Mall of India, Sector 18, Noida",
            type = TerminalType.BANK_ATM,
            latitude = 28.5695,
            longitude = 77.3275,
            riskLevel = RiskLevel.HIGH,
            confidencePercent = 74,
            cashoutWindow = "11:00 AM – 12:00 PM",
            bankName = "HDFC Bank"
        ),
        TerminalMarker(
            id = "AEPS-FINO-ND-205",
            address = "Village Barola, Sector 49, Noida",
            type = TerminalType.AEPS_MICRO_ATM,
            latitude = 28.5801,
            longitude = 77.3385,
            riskLevel = RiskLevel.CRITICAL,
            confidencePercent = 81,
            cashoutWindow = "10:15 AM – 11:00 AM",
            bankName = "Fino Payments Bank"
        ),
        TerminalMarker(
            id = "ATM-ICICI-ND-063",
            address = "Wave Silver Tower, Sector 18, Noida",
            type = TerminalType.BANK_ATM,
            latitude = 28.5715,
            longitude = 77.3230,
            riskLevel = RiskLevel.MEDIUM,
            confidencePercent = 62,
            cashoutWindow = "12:00 PM – 1:00 PM",
            bankName = "ICICI Bank"
        ),
        TerminalMarker(
            id = "AEPS-JIO-ND-099",
            address = "Sector 15, Noida",
            type = TerminalType.AEPS_MICRO_ATM,
            latitude = 28.5850,
            longitude = 77.3150,
            riskLevel = RiskLevel.LOW,
            confidencePercent = 35,
            cashoutWindow = "02:00 PM – 03:00 PM",
            bankName = "Jio Payments Bank"
        ),
        TerminalMarker(
            id = "ATM-PNB-ND-031",
            address = "Sector 62, Noida",
            type = TerminalType.BANK_ATM,
            latitude = 28.6100,
            longitude = 77.3620,
            riskLevel = RiskLevel.CRITICAL,
            confidencePercent = 83,
            cashoutWindow = "10:00 AM – 10:45 AM",
            bankName = "Punjab National Bank"
        ),
        TerminalMarker(
            id = "AEPS-AIRTEL-ND-176",
            address = "Sector 22, Noida",
            type = TerminalType.AEPS_MICRO_ATM,
            latitude = 28.5950,
            longitude = 77.3400,
            riskLevel = RiskLevel.HIGH,
            confidencePercent = 71,
            cashoutWindow = "11:15 AM – 12:15 PM",
            bankName = "Airtel Payments Bank"
        )
    )

    // ─── Complaint Tickets ─────────────────────────────────────────────
    val complaintTickets = listOf(
        ComplaintTicket(
            ncrpId = "NCRP-2026-994821",
            reportedLoss = "₹50,00,000",
            timeElapsed = "12 mins ago",
            victimAccount = "XXXX-XXXX-4521",
            status = ActionStatus.PENDING,
            targetTerminal = terminalMarkers[0]
        ),
        ComplaintTicket(
            ncrpId = "NCRP-2026-994822",
            reportedLoss = "₹12,50,000",
            timeElapsed = "23 mins ago",
            victimAccount = "XXXX-XXXX-7832",
            status = ActionStatus.PENDING,
            targetTerminal = terminalMarkers[1]
        ),
        ComplaintTicket(
            ncrpId = "NCRP-2026-994823",
            reportedLoss = "₹8,75,000",
            timeElapsed = "35 mins ago",
            victimAccount = "XXXX-XXXX-9156",
            status = ActionStatus.PENDING,
            targetTerminal = terminalMarkers[3]
        ),
        ComplaintTicket(
            ncrpId = "NCRP-2026-994700",
            reportedLoss = "₹35,00,000",
            timeElapsed = "2 hrs ago",
            victimAccount = "XXXX-XXXX-3301",
            status = ActionStatus.APPROVED,
            targetTerminal = terminalMarkers[6]
        ),
        ComplaintTicket(
            ncrpId = "NCRP-2026-994650",
            reportedLoss = "₹22,00,000",
            timeElapsed = "3 hrs ago",
            victimAccount = "XXXX-XXXX-8844",
            status = ActionStatus.BANK_HOLD,
            targetTerminal = terminalMarkers[2]
        )
    )

    // ─── Money Trail for primary investigation ────────────────────────
    val primaryMoneyTrail = MoneyTrail(
        nodes = listOf(
            TrailNode(label = "Victim Account", type = "victim", accountHint = "XXXX-4521"),
            TrailNode(label = "Layer-1 Mule", type = "mule", accountHint = "Mule-C-441"),
            TrailNode(label = "Aggregator\nNode C", type = "aggregator", accountHint = "Agg-Node-C"),
            TrailNode(label = "Target\nATM-SBI-ND-042", type = "terminal", accountHint = "Sector 18")
        ),
        edges = listOf(
            TrailEdge(fromIndex = 0, toIndex = 1),
            TrailEdge(fromIndex = 1, toIndex = 2),
            TrailEdge(fromIndex = 2, toIndex = 3)
        )
    )

    // ─── XAI Risk Breakdown ────────────────────────────────────────────
    val primaryRiskBreakdown = RiskBreakdown(
        totalPercent = 87,
        signals = listOf(
            RiskSignal(
                icon = "⚡",
                name = "Velocity Signal",
                contributionPercent = 25,
                explanation = "Money transferred in < 4 mins"
            ),
            RiskSignal(
                icon = "🔀",
                name = "Topology / Fan-In Signal",
                contributionPercent = 25,
                explanation = "6 accounts → 1 aggregator"
            ),
            RiskSignal(
                icon = "📱",
                name = "Device Hash Match",
                contributionPercent = 20,
                explanation = "Matches known mule ring C-441"
            ),
            RiskSignal(
                icon = "📍",
                name = "Spatial ATM Affinity",
                contributionPercent = 17,
                explanation = "Within 1.2 km of past mule cashout"
            )
        )
    )

    // ─── Audit Log Entries ─────────────────────────────────────────────
    val auditLogEntries = mutableListOf(
        AuditLogEntry(
            timestamp = "10:16 AM",
            officerName = "Officer A. Sharma",
            ncrpId = "NCRP-994821",
            action = "Dispatched to Sector 20 Police Patrol",
            targetUnit = "Sector 20 Patrol Unit",
            status = ActionStatus.EN_ROUTE
        ),
        AuditLogEntry(
            timestamp = "10:17 AM",
            officerName = "SBI Branch Manager",
            ncrpId = "NCRP-994821",
            action = "CBS Lien acknowledged via CFCFRMS",
            targetUnit = "SBI Core Banking System",
            status = ActionStatus.LIEN_PLACED
        ),
        AuditLogEntry(
            timestamp = "09:45 AM",
            officerName = "Officer R. Verma",
            ncrpId = "NCRP-994700",
            action = "Dispatched to Sector 62 Police Station",
            targetUnit = "Sector 62 PS",
            status = ActionStatus.APPROVED
        ),
        AuditLogEntry(
            timestamp = "09:30 AM",
            officerName = "Officer K. Patel",
            ncrpId = "NCRP-994650",
            action = "CBS Hold placed via CFCFRMS",
            targetUnit = "HDFC Core Banking System",
            status = ActionStatus.LIEN_PLACED
        )
    )

    // ─── Dispatch Summary Cards ────────────────────────────────────────
    val dispatchSummaries: List<DispatchSummary>
        get() = listOf(
            DispatchSummary(
                title = "Pending Reviews",
                count = complaintTickets.count { it.status == ActionStatus.PENDING },
                accentColor = AlertOrange
            ),
            DispatchSummary(
                title = "Active Dispatches",
                count = 12,
                accentColor = MediumCyan
            ),
            DispatchSummary(
                title = "Bank Holds Placed",
                count = 8,
                accentColor = SuccessGreen
            )
        )

    // ─── Pending Review Queue ──────────────────────────────────────────
    val pendingReviewItems: List<PendingReviewItem>
        get() = complaintTickets
            .filter { it.status == ActionStatus.PENDING }
            .mapIndexed { index, ticket ->
                PendingReviewItem(ticket = ticket, priorityRank = index + 1)
            }

    // ─── Helper: get terminal color by risk ────────────────────────────
    fun markerColorForRisk(confidencePercent: Int): Color {
        return if (confidencePercent >= 80) AlertOrange else BorderTaupe
    }

    fun riskBadgeColor(confidencePercent: Int): Color {
        return when {
            confidencePercent >= 80 -> AlertOrange
            confidencePercent >= 60 -> MediumCyan
            else -> BorderTaupe
        }
    }
}
