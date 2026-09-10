package com.i4c.cybershield.model

import androidx.compose.ui.graphics.Color

// ═══════════════════════════════════════════════════════════════════════
//  DATA MODELS – Cyber Shield Predictive Cashout Radar
// ═══════════════════════════════════════════════════════════════════════

/** Types of payment terminals tracked by the system */
enum class TerminalType(val displayName: String) {
    BANK_ATM("Bank ATM"),
    AEPS_MICRO_ATM("AEPS Micro-ATM Agent")
}

/** Risk classification level */
enum class RiskLevel(val displayName: String) {
    CRITICAL("Critical Risk"),
    HIGH("High Risk"),
    MEDIUM("Medium Risk"),
    LOW("Low Risk")
}

/** Current review/dispatch status */
enum class ActionStatus(val displayName: String) {
    PENDING("Pending Human Verification"),
    APPROVED("Approved & Sent to Police"),
    BANK_HOLD("Bank CBS Hold Issued"),
    DISMISSED("Dismissed / False Positive"),
    EN_ROUTE("En Route"),
    LIEN_PLACED("Lien Placed")
}

/** Terminal marker on the cashout radar map */
data class TerminalMarker(
    val id: String,
    val address: String,
    val type: TerminalType,
    val latitude: Double,
    val longitude: Double,
    val riskLevel: RiskLevel,
    val confidencePercent: Int,
    val cashoutWindow: String,
    val bankName: String = "SBI"
)

/** NCRP Cybercrime complaint record */
data class ComplaintTicket(
    val ncrpId: String,
    val reportedLoss: String,
    val timeElapsed: String,
    val victimAccount: String,
    val status: ActionStatus,
    val targetTerminal: TerminalMarker
)

/** Node in the money-laundering trail graph */
data class TrailNode(
    val label: String,
    val type: String, // "victim", "mule", "aggregator", "terminal"
    val accountHint: String = ""
)

/** An edge connecting two nodes in the money trail */
data class TrailEdge(
    val fromIndex: Int,
    val toIndex: Int,
    val label: String = ""
)

/** Money trail visualization: nodes + edges */
data class MoneyTrail(
    val nodes: List<TrailNode>,
    val edges: List<TrailEdge>
)

/** A single XAI signal contributing to the risk score */
data class RiskSignal(
    val icon: String,
    val name: String,
    val contributionPercent: Int,
    val explanation: String
)

/** Full XAI score breakdown for a terminal */
data class RiskBreakdown(
    val totalPercent: Int,
    val signals: List<RiskSignal>
)

/** An audit log entry in the dispatch center */
data class AuditLogEntry(
    val timestamp: String,
    val officerName: String,
    val ncrpId: String,
    val action: String,
    val targetUnit: String,
    val status: ActionStatus
)

/** Summary statistic card for dispatch center */
data class DispatchSummary(
    val title: String,
    val count: Int,
    val accentColor: Color
)

/** OTP session state */
data class OtpSession(
    val email: String,
    val generatedOtp: String,
    val remainingSeconds: Int = 60,
    val attempts: Int = 0,
    val isLocked: Boolean = false,
    val lockoutMinutes: Int = 48 * 60 // 48 hours in minutes
)

/** Pending review queue item */
data class PendingReviewItem(
    val ticket: ComplaintTicket,
    val priorityRank: Int
)

// ═══════════════════════════════════════════════════════════════════════
//  SIH26184 OPERATIONAL & INVESTIGATION MODELS
// ═══════════════════════════════════════════════════════════════════════

/** Standard case lifecycle states */
enum class CaseLifecycle(val displayName: String, val badgeColorHex: String) {
    PRE_COMPLAINT_INTERVENTION("PRE-COMPLAINT INTERVENTION", "#06B6D4"),
    POST_COMPLAINT_ESCALATED("POST-COMPLAINT ESCALATED", "#EF4444"),
    CASHOUT_ATTEMPT_DETECTED("CASHOUT ATTEMPT DETECTED", "#F59E0B"),
    RESOLVED("RESOLVED", "#10B981")
}

/** Selective fund protection breakdown */
data class SelectiveFundBreakdown(
    val existingBalance: String = "₹20,000",
    val suspiciousAmount: String = "₹1,00,000",
    val protectedAmount: String = "₹1,00,000",
    val sourceTxn: String = "TXN-8f2a1e",
    val holdReason: String = "Selective provisional hold on recent suspicious chain funds",
    val isPreComplaint: Boolean = true
)

/** Detailed money trail hop with account details and risk flags */
data class DetailedTrailHop(
    val hopNumber: Int,
    val fromAccount: String,
    val toAccount: String,
    val amount: String,
    val timestamp: String,
    val channel: String,
    val sourceTier: String, // "Victim", "Mule L1", "Mule L2", "Aggregator"
    val targetTier: String,
    val flags: List<String> = emptyList()
)

/** Nearby terminal context for spatial intelligence */
data class NearbyTerminal(
    val id: String,
    val address: String,
    val distanceKm: Double,
    val type: TerminalType = TerminalType.BANK_ATM
)

/** Repeated ATM + Account behavior tracking */
data class TerminalRecurrence(
    val terminalId: String,
    val accountTarget: String,
    val attemptsCount: Int,
    val escalationState: String, // "MONITORED", "ELEVATED_RISK", "PERSISTENT_TERMINAL_RISK"
    val riskMultiplier: Double = 1.5
)

/** Unified Investigation Case representation */
data class InvestigationCase(
    val caseId: String,
    val flaggedAccount: String,
    val lifecycle: CaseLifecycle,
    val riskScorePercent: Int,
    val confidencePercent: Int,
    val suspiciousAmount: String,
    val targetTerminal: TerminalMarker,
    val predictedWindow: String,
    val funds: SelectiveFundBreakdown,
    val trailHops: List<DetailedTrailHop>,
    val xaiBreakdown: RiskBreakdown,
    val nearbyTerminals: List<NearbyTerminal>,
    val recurrence: TerminalRecurrence? = null,
    val bankHoldActive: Boolean = true,
    val atmBlockRequested: Boolean = true,
    val leaNotificationSent: Boolean = true
)

