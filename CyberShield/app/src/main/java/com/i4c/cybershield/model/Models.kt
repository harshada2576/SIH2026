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

/** Current review/dispatch status of a case */
enum class ActionStatus(val displayName: String) {
    PENDING("Awaiting Review"),
    APPROVED("Sent to Police"),
    BANK_HOLD("Account Frozen (Bank Hold)"),
    DISMISSED("Dismissed – False Positive"),
    EN_ROUTE("Police En Route"),
    LIEN_PLACED("Bank Hold Confirmed")
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

/**
 * A single signal contributing to the risk score, written for a human
 * investigator first. [name]/[explanation] must stand alone in plain
 * English with no jargon. [technicalTag] is the internal rule/model name
 * (e.g. "fan_in_rule", "geo_velocity") shown only as small secondary text
 * for officers who want it — never as the primary label.
 */
data class RiskSignal(
    val icon: String,
    val name: String,
    val contributionPercent: Int,
    val explanation: String,
    val technicalTag: String = ""
)

/** Full explainable score breakdown for a case */
data class RiskBreakdown(
    val totalPercent: Int,
    val signals: List<RiskSignal>
)

/**
 * One suspicious-money-flow case, from complaint to (eventually) resolution.
 * This is the single unit an investigator opens, reviews, and acts on —
 * everything needed for that one decision lives on this object so the
 * detail screen never has to guess which case it's showing.
 */
data class ComplaintTicket(
    val ncrpId: String,
    val reportedLoss: String,
    val timeElapsed: String,
    val victimAccount: String,
    val status: ActionStatus,
    val targetTerminal: TerminalMarker,
    /** One-sentence, plain-English summary shown in the case list — no jargon. */
    val summary: String,
    val moneyTrail: MoneyTrail,
    val riskBreakdown: RiskBreakdown
)

/** An audit log entry — the accountability trail of every action taken */
data class AuditLogEntry(
    val timestamp: String,
    val officerName: String,
    val ncrpId: String,
    val action: String,
    val targetUnit: String,
    val status: ActionStatus
)

/** Summary statistic card shown at the top of the case queue */
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
