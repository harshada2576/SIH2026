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
