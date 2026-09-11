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
//
//  Each case below is self-contained (its own money trail + evidence +
//  target terminal) so the case queue -> case detail -> approve/hold/
//  dismiss flow works for EVERY case, not just one hardcoded example.
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

    // ─── Terminal Markers (predicted cash-out locations) ───────────────
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

    private fun terminal(id: String) = terminalMarkers.first { it.id == id }

    // ─── Cases ───────────────────────────────────────────────────────
    // Every case is fully self-contained: its own trail + evidence, so
    // opening ANY case from the queue shows THAT case, not always the
    // same one.
    val cases: List<ComplaintTicket> = listOf(

        ComplaintTicket(
            ncrpId = "NCRP-2026-994821",
            reportedLoss = "₹50,00,000",
            timeElapsed = "12 mins ago",
            victimAccount = "XXXX-XXXX-4521",
            status = ActionStatus.PENDING,
            targetTerminal = terminal("ATM-SBI-ND-042"),
            summary = "₹50 lakh moved through 6 accounts in under 4 minutes — heading toward an SBI ATM in Sector 18, Noida.",
            moneyTrail = MoneyTrail(
                nodes = listOf(
                    TrailNode(label = "Victim Account", type = "victim", accountHint = "XXXX-4521"),
                    TrailNode(label = "Layer-1 Account", type = "mule", accountHint = "Mule-C-441"),
                    TrailNode(label = "Collector\nAccount", type = "aggregator", accountHint = "Agg-Node-C"),
                    TrailNode(label = "Target\nATM-SBI-ND-042", type = "terminal", accountHint = "Sector 18")
                ),
                edges = listOf(
                    TrailEdge(fromIndex = 0, toIndex = 1, amount = "₹50,00,000", timestamp = "10:02:14 AM"),
                    TrailEdge(fromIndex = 1, toIndex = 2, amount = "₹49,60,000", timestamp = "10:04:01 AM"),
                    TrailEdge(fromIndex = 2, toIndex = 3, amount = "Predicted cash-out", timestamp = "10:30–11:15 AM", channel = "ATM withdrawal")
                )
            ),
            riskBreakdown = RiskBreakdown(
                totalPercent = 87,
                signals = listOf(
                    RiskSignal("⚡", "Money moved out unusually fast", 25,
                        "The money left this account in under 4 minutes of arriving — far faster than normal account activity.",
                        "velocity_rule"),
                    RiskSignal("🔀", "Several accounts feeding one account", 25,
                        "6 separate accounts sent money into the same collector account in a short window.",
                        "fan_in_rule"),
                    RiskSignal("📱", "Same device used across accounts", 20,
                        "This account was accessed from a phone already linked to a known mule ring.",
                        "device_fingerprint_rule"),
                    RiskSignal("📍", "Close to a known cash-out spot", 17,
                        "The predicted ATM is 1.2 km from a location used in a previous confirmed cash-out.",
                        "terminal_affinity_rule")
                )
            )
        ),

        ComplaintTicket(
            ncrpId = "NCRP-2026-994822",
            reportedLoss = "₹12,50,000",
            timeElapsed = "23 mins ago",
            victimAccount = "XXXX-XXXX-7832",
            status = ActionStatus.PENDING,
            targetTerminal = terminal("AEPS-PM-ND-118"),
            summary = "Victim's card was used in Mumbai, then again 40 minutes later in a Noida micro-ATM — physically impossible travel.",
            moneyTrail = MoneyTrail(
                nodes = listOf(
                    TrailNode(label = "Victim Account", type = "victim", accountHint = "XXXX-7832"),
                    TrailNode(label = "Layer-1 Account", type = "mule", accountHint = "Mule-D-118"),
                    TrailNode(label = "Target\nAEPS-PM-ND-118", type = "terminal", accountHint = "Atta Market")
                ),
                edges = listOf(
                    TrailEdge(fromIndex = 0, toIndex = 1),
                    TrailEdge(fromIndex = 1, toIndex = 2)
                )
            ),
            riskBreakdown = RiskBreakdown(
                totalPercent = 92,
                signals = listOf(
                    RiskSignal("✈️", "Impossible travel between two locations", 40,
                        "This account was used in Mumbai, then again 40 minutes later in Noida — over 1,400 km apart. No real traveller can do that.",
                        "geo_velocity_rule"),
                    RiskSignal("⚡", "Money moved out unusually fast", 22,
                        "Funds were withdrawn within minutes of arriving in this account.",
                        "velocity_rule"),
                    RiskSignal("📱", "Same device used across accounts", 18,
                        "Linked to a device already flagged on 3 other accounts.",
                        "device_fingerprint_rule"),
                    RiskSignal("🧾", "Many accounts opened on one identity", 12,
                        "This account shares KYC details with 11 other recently opened accounts.",
                        "identity_cluster_rule")
                )
            )
        ),

        ComplaintTicket(
            ncrpId = "NCRP-2026-994823",
            reportedLoss = "₹8,75,000",
            timeElapsed = "35 mins ago",
            victimAccount = "XXXX-XXXX-9156",
            status = ActionStatus.PENDING,
            targetTerminal = terminal("AEPS-FINO-ND-205"),
            summary = "12 newly opened accounts, all under one stolen identity, are funnelling money to a single collector account.",
            moneyTrail = MoneyTrail(
                nodes = listOf(
                    TrailNode(label = "Victim Account", type = "victim", accountHint = "XXXX-9156"),
                    TrailNode(label = "12 Linked\nAccounts", type = "mule", accountHint = "1 shared identity"),
                    TrailNode(label = "Collector\nAccount", type = "aggregator", accountHint = "Agg-Node-F"),
                    TrailNode(label = "Target\nAEPS-FINO-ND-205", type = "terminal", accountHint = "Village Barola")
                ),
                edges = listOf(
                    TrailEdge(fromIndex = 0, toIndex = 1),
                    TrailEdge(fromIndex = 1, toIndex = 2),
                    TrailEdge(fromIndex = 2, toIndex = 3)
                )
            ),
            riskBreakdown = RiskBreakdown(
                totalPercent = 81,
                signals = listOf(
                    RiskSignal("🧾", "Many accounts opened on one identity", 35,
                        "12 accounts, opened in the last few days, all share the same KYC identity — a classic mule-ring pattern.",
                        "identity_cluster_rule"),
                    RiskSignal("🔀", "Several accounts feeding one account", 24,
                        "All 12 accounts are sending money into a single collector account.",
                        "fan_in_rule"),
                    RiskSignal("🆕", "Accounts are only days old", 14,
                        "Every account in this ring was opened within the last week.",
                        "account_age_rule"),
                    RiskSignal("📍", "Close to a known cash-out spot", 8,
                        "The predicted micro-ATM has handled cash-outs from this ring before.",
                        "terminal_affinity_rule")
                )
            )
        ),

        ComplaintTicket(
            ncrpId = "NCRP-2026-994700",
            reportedLoss = "₹35,00,000",
            timeElapsed = "2 hrs ago",
            victimAccount = "XXXX-XXXX-3301",
            status = ActionStatus.APPROVED,
            targetTerminal = terminal("ATM-PNB-ND-031"),
            summary = "Already reviewed and sent to Sector 62 Police — a fast-moving 5-account layering chain.",
            moneyTrail = MoneyTrail(
                nodes = listOf(
                    TrailNode(label = "Victim Account", type = "victim", accountHint = "XXXX-3301"),
                    TrailNode(label = "Layer-1", type = "mule", accountHint = "Mule-P-031"),
                    TrailNode(label = "Layer-2", type = "mule", accountHint = "Mule-P-032"),
                    TrailNode(label = "Target\nATM-PNB-ND-031", type = "terminal", accountHint = "Sector 62")
                ),
                edges = listOf(
                    TrailEdge(fromIndex = 0, toIndex = 1),
                    TrailEdge(fromIndex = 1, toIndex = 2),
                    TrailEdge(fromIndex = 2, toIndex = 3)
                )
            ),
            riskBreakdown = RiskBreakdown(
                totalPercent = 83,
                signals = listOf(
                    RiskSignal("🔁", "Money passed through several accounts quickly", 30,
                        "Funds moved through 2 extra accounts before reaching the collector — a common way to hide the original source.",
                        "layering_rule"),
                    RiskSignal("⚡", "Money moved out unusually fast", 26,
                        "Each hop happened within minutes of the last.",
                        "velocity_rule"),
                    RiskSignal("💰", "Almost all incoming money was forwarded", 15,
                        "97% of the money received was immediately sent onward — very little was kept or spent normally.",
                        "amount_movement_rule"),
                    RiskSignal("📍", "Close to a known cash-out spot", 12,
                        "The predicted ATM matches a location used in a prior confirmed case.",
                        "terminal_affinity_rule")
                )
            )
        ),

        ComplaintTicket(
            ncrpId = "NCRP-2026-994650",
            reportedLoss = "₹22,00,000",
            timeElapsed = "3 hrs ago",
            victimAccount = "XXXX-XXXX-8844",
            status = ActionStatus.BANK_HOLD,
            targetTerminal = terminal("ATM-HDFC-ND-087"),
            summary = "Already reviewed — account frozen after an unusual-behaviour signal flagged a normally quiet account.",
            moneyTrail = MoneyTrail(
                nodes = listOf(
                    TrailNode(label = "Victim Account", type = "victim", accountHint = "XXXX-8844"),
                    TrailNode(label = "Layer-1 Account", type = "mule", accountHint = "Mule-H-087"),
                    TrailNode(label = "Target\nATM-HDFC-ND-087", type = "terminal", accountHint = "Mall of India")
                ),
                edges = listOf(
                    TrailEdge(fromIndex = 0, toIndex = 1),
                    TrailEdge(fromIndex = 1, toIndex = 2)
                )
            ),
            riskBreakdown = RiskBreakdown(
                totalPercent = 74,
                signals = listOf(
                    RiskSignal("🤖", "Unusual behaviour for this account", 38,
                        "This account normally sees very little activity — this transaction pattern doesn't match its history at all.",
                        "ml_anomaly_rule"),
                    RiskSignal("⚡", "Money moved out unusually fast", 20,
                        "Withdrawal attempted minutes after the funds arrived.",
                        "velocity_rule"),
                    RiskSignal("🆕", "Account is only days old", 16,
                        "Opened 6 days ago, with no prior transaction history.",
                        "account_age_rule")
                )
            )
        )
    )

    // ─── Audit Log Entries (accountability trail) ──────────────────────
    val auditLogEntries = mutableListOf(
        AuditLogEntry(
            timestamp = "10:16 AM",
            officerName = "Officer A. Sharma",
            ncrpId = "NCRP-994700",
            action = "Sent to Sector 62 Police Station for action",
            targetUnit = "Sector 62 Police Station",
            status = ActionStatus.EN_ROUTE
        ),
        AuditLogEntry(
            timestamp = "09:45 AM",
            officerName = "Officer R. Verma",
            ncrpId = "NCRP-994700",
            action = "Case approved and forwarded",
            targetUnit = "Sector 62 Police Station",
            status = ActionStatus.APPROVED
        ),
        AuditLogEntry(
            timestamp = "09:30 AM",
            officerName = "Officer K. Patel",
            ncrpId = "NCRP-994650",
            action = "Account frozen — temporary bank hold placed",
            targetUnit = "HDFC Bank",
            status = ActionStatus.LIEN_PLACED
        )
    )

    // ─── Primary Investigation Case and Data (SIH26184) ──────────────────────
    val primaryRiskBreakdown = RiskBreakdown(
        totalPercent = 87,
        signals = listOf(
            RiskSignal(
                icon = "⚡",
                name = "Velocity Signal",
                contributionPercent = 25,
                explanation = "Money transferred in < 4 mins",
                technicalTag = "velocity_rule"
            ),
            RiskSignal(
                icon = "🔀",
                name = "Topology / Fan-In Signal",
                contributionPercent = 25,
                explanation = "6 accounts → 1 aggregator",
                technicalTag = "fan_in_rule"
            ),
            RiskSignal(
                icon = "📱",
                name = "Device Hash Match",
                contributionPercent = 20,
                explanation = "Matches known mule ring C-441",
                technicalTag = "device_fingerprint_rule"
            ),
            RiskSignal(
                icon = "📍",
                name = "Spatial ATM Affinity",
                contributionPercent = 17,
                explanation = "Within 1.2 km of past mule cashout",
                technicalTag = "terminal_affinity_rule"
            )
        )
    )

    val primaryDetailedHops = listOf(
        DetailedTrailHop(
            hopNumber = 1,
            fromAccount = "ACC-VICTIM-01",
            toAccount = "ACC-MULE-A44",
            amount = "₹1,00,000",
            timestamp = "10:14:22 AM",
            channel = "IMPS",
            sourceTier = "Victim Account",
            targetTier = "Layer-1 Mule",
            flags = listOf("Sudden Outflow")
        ),
        DetailedTrailHop(
            hopNumber = 2,
            fromAccount = "ACC-MULE-A44",
            toAccount = "ACC-MULE-B89",
            amount = "₹96,000",
            timestamp = "10:16:05 AM",
            channel = "UPI",
            sourceTier = "Layer-1 Mule",
            targetTier = "Layer-2 Mule",
            flags = listOf("Shared Device Fingerprint", "Rapid Forward <2m")
        ),
        DetailedTrailHop(
            hopNumber = 3,
            fromAccount = "ACC-MULE-B89",
            toAccount = "ACC-AGG-03",
            amount = "₹92,000",
            timestamp = "10:18:40 AM",
            channel = "UPI",
            sourceTier = "Layer-2 Mule",
            targetTier = "Aggregator Node",
            flags = listOf("Shared KYC Ring", "Layering Depth 3")
        )
    )

    val primaryNearbyTerminals = listOf(
        NearbyTerminal(
            id = "AEPS-PM-ND-118",
            address = "Shop 12, Atta Market, Sector 18 (0.21 km)",
            distanceKm = 0.21,
            type = TerminalType.AEPS_MICRO_ATM
        ),
        NearbyTerminal(
            id = "ATM-HDFC-ND-087",
            address = "DLF Mall of India, Sector 18 (0.34 km)",
            distanceKm = 0.34,
            type = TerminalType.BANK_ATM
        ),
        NearbyTerminal(
            id = "ATM-ICICI-ND-063",
            address = "Wave Silver Tower, Sector 18 (0.45 km)",
            distanceKm = 0.45,
            type = TerminalType.BANK_ATM
        )
    )

    val primaryRecurrence = TerminalRecurrence(
        terminalId = "ATM-SBI-ND-042",
        accountTarget = "ACC-AGG-03",
        attemptsCount = 3,
        escalationState = "PERSISTENT_TERMINAL_RISK",
        riskMultiplier = 1.5
    )

    val primaryConfirmation = TransactionConfirmationInfo(
        txnId = "TXN-SCENARIO-03",
        payerAccount = "ACC-VICTIM-01",
        amount = "₹1,00,000",
        status = ConfirmationStatus.CONFIRMED_FRAUD,
        promptChannel = "SMS + CBS Push Notification",
        requestedAt = "10:14:30 AM",
        respondedAt = "10:15:10 AM",
        explanatoryNote = "Victim flagged transfer as unauthorized OTP compromise within 40 seconds."
    )

    val primaryWithdrawalAttempts = listOf(
        RecordedWithdrawal(
            attemptId = "ATTEMPT-WD-9941",
            terminalId = "ATM-SBI-ND-042",
            terminalName = "Sector 18 SBI ATM #042",
            amount = "₹50,000",
            timestamp = "10:32:15 AM",
            status = WithdrawalAttemptStatus.BLOCKED,
            channel = "ATM CASH DISPENSE",
            failureReason = "Provisional CBS Hold active on ACC-AGG-03"
        ),
        RecordedWithdrawal(
            attemptId = "ATTEMPT-WD-9942",
            terminalId = "ATM-SBI-ND-042",
            terminalName = "Sector 18 SBI ATM #042",
            amount = "₹42,000",
            timestamp = "10:33:02 AM",
            status = WithdrawalAttemptStatus.BLOCKED,
            channel = "ATM CASH DISPENSE",
            failureReason = "Provisional CBS Hold active on ACC-AGG-03"
        )
    )

    val primaryTimelineEvents = listOf(
        LocationTimelineEvent(
            timestamp = "10:14:22 AM",
            title = "Root Fraud Inflow",
            description = "₹1,00,000 sent from ACC-VICTIM-01 to ACC-MULE-A44 via IMPS.",
            eventType = "ORIGIN"
        ),
        LocationTimelineEvent(
            timestamp = "10:15:10 AM",
            title = "Payer Confirmation: Fraud",
            description = "Victim confirmed transaction was fraudulent. Pre-complaint hold triggered.",
            eventType = "ACTION"
        ),
        LocationTimelineEvent(
            timestamp = "10:18:40 AM",
            title = "Aggregator Node Convergence",
            description = "₹92,000 reached ACC-AGG-03 after 3 hops in under 4 minutes.",
            eventType = "MULE_HOP"
        ),
        LocationTimelineEvent(
            timestamp = "10:20:00 AM",
            title = "Predictive Radar Triggered",
            description = "High spatial affinity predicted cashout at ATM-SBI-ND-042 (10:30 - 11:15 AM).",
            eventType = "PREDICTION"
        ),
        LocationTimelineEvent(
            timestamp = "10:32:15 AM",
            title = "Cashout Blocked at ATM",
            description = "Card withdrawal of ₹50,000 blocked by automated selective lien.",
            eventType = "ATTEMPT"
        )
    )

    val primaryInvestigationCase = InvestigationCase(
        caseId = "CASE-ALERT-1732",
        flaggedAccount = "ACC-AGG-03",
        lifecycle = CaseLifecycle.CASHOUT_ATTEMPT_DETECTED,
        riskScorePercent = 91,
        confidencePercent = 87,
        suspiciousAmount = "₹92,000",
        targetTerminal = terminalMarkers[0],
        predictedWindow = "10:30 AM – 11:15 AM",
        summaryNarrative = "Multi-hop layering network converging on aggregator node ACC-AGG-03. Predicted cashout attempt blocked at Sector 18 ATM.",
        confirmation = primaryConfirmation,
        funds = SelectiveFundBreakdown(
            existingBalance = "₹20,000",
            suspiciousAmount = "₹1,00,000",
            protectedAmount = "₹92,000",
            sourceTxn = "TXN-SCENARIO-03",
            holdReason = "Selective provisional hold on recent suspicious chain funds",
            isPreComplaint = true
        ),
        trailHops = primaryDetailedHops,
        withdrawalAttempts = primaryWithdrawalAttempts,
        timelineEvents = primaryTimelineEvents,
        xaiBreakdown = primaryRiskBreakdown,
        nearbyTerminals = primaryNearbyTerminals,
        recurrence = primaryRecurrence,
        bankHoldActive = true,
        atmBlockRequested = true,
        leaNotificationSent = true
    )

    val secondaryInvestigationCase = InvestigationCase(
        caseId = "CASE-NCRP-994821",
        flaggedAccount = "ACC-AGG-03",
        lifecycle = CaseLifecycle.POST_COMPLAINT_ESCALATED,
        riskScorePercent = 94,
        confidencePercent = 92,
        suspiciousAmount = "₹50,00,000",
        targetTerminal = terminalMarkers[0],
        predictedWindow = "10:30 AM – 11:15 AM",
        summaryNarrative = "Formal complaint registered on NCRP portal. Full statutory lien and police dispatch en route.",
        confirmation = primaryConfirmation,
        funds = SelectiveFundBreakdown(
            existingBalance = "₹45,000",
            suspiciousAmount = "₹50,00,000",
            protectedAmount = "₹50,00,000",
            sourceTxn = "TXN-NCRP-8812",
            holdReason = "Statutory lien under Section 106 BNSS / CFCFRMS",
            isPreComplaint = false
        ),
        trailHops = primaryDetailedHops,
        withdrawalAttempts = primaryWithdrawalAttempts,
        timelineEvents = primaryTimelineEvents,
        xaiBreakdown = primaryRiskBreakdown,
        nearbyTerminals = primaryNearbyTerminals,
        recurrence = primaryRecurrence,
        bankHoldActive = true,
        atmBlockRequested = true,
        leaNotificationSent = true
    )

    val allCases = listOf(
        primaryInvestigationCase,
        secondaryInvestigationCase
    )

    fun getCaseById(caseId: String): InvestigationCase {
        return allCases.firstOrNull { it.caseId == caseId } ?: primaryInvestigationCase
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

    fun summaryAccentColor(status: ActionStatus): Color = when (status) {
        ActionStatus.PENDING -> AlertOrange
        ActionStatus.APPROVED, ActionStatus.EN_ROUTE -> SuccessGreen
        ActionStatus.BANK_HOLD, ActionStatus.LIEN_PLACED -> MediumCyan
        ActionStatus.DISMISSED, ActionStatus.RELEASED -> BorderTaupe
    }
}
