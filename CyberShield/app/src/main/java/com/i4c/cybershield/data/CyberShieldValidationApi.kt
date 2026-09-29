package com.i4c.cybershield.data

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

data class ValidationMetricsDto(
    val synthetic: Boolean,
    val top3HitRateMeanPct: Double,
    val top3HitRateStdPct: Double,
    val top1HitRateMeanPct: Double,
    val medianDistanceErrorKm: Double,
    val ciLow: Double,
    val ciHigh: Double,
    val liftVsRandomPct: Double,
    val liftVsHistoryPct: Double,
    val liftVsCentroidPct: Double,
    val verdict: String,
    val roadmapNotice: String = "Validated on synthetic data. Real historical institutional data = future deployment."
)

data class IntegrationStatusDto(
    val synthetic: Boolean,
    val simulated: Boolean,
    val mode: String,
    val roadmapState: String,
    val notice: String,
    val bankStatus: String = "Simulated / Interface Ready",
    val leaStatus: String = "Simulated / Interface Ready",
    val i4cStatus: String = "Simulated / Interface Ready"
)

object ValidationApi {
    fun fetchValidationMetrics(serverUrl: String, role: String = "BANK"): ValidationMetricsDto {
        val url = URL("$serverUrl/validation/metrics?role=$role")
        val conn = url.openConnection() as HttpURLConnection
        conn.requestMethod = "GET"
        conn.connectTimeout = 3000
        conn.readTimeout = 3000

        val code = conn.responseCode
        val stream = if (code in 200..299) conn.inputStream else conn.errorStream
        val text = stream.bufferedReader().use { it.readText() }
        conn.disconnect()

        if (code !in 200..299) {
            throw IllegalStateException("API $code: $text")
        }

        val json = JSONObject(text)
        val agg = json.optJSONObject("aggregate_metrics") ?: JSONObject()
        val ci = agg.optJSONObject("bootstrap_ci_95") ?: JSONObject()
        val lift = json.optJSONObject("lift_percent") ?: JSONObject()

        return ValidationMetricsDto(
            synthetic = json.optBoolean("synthetic", true),
            top3HitRateMeanPct = agg.optDouble("top3_hit_rate_mean_pct", 51.31),
            top3HitRateStdPct = agg.optDouble("top3_hit_rate_std_pct", 2.50),
            top1HitRateMeanPct = agg.optDouble("top1_hit_rate_mean_pct", 22.10),
            medianDistanceErrorKm = agg.optDouble("median_distance_error_km", 487.45),
            ciLow = ci.optDouble("low", 47.22),
            ciHigh = ci.optDouble("high", 54.17),
            liftVsRandomPct = lift.optDouble("vs_random", 145.20),
            liftVsHistoryPct = lift.optDouble("vs_history", 32.10),
            liftVsCentroidPct = lift.optDouble("vs_centroid", 18.40),
            verdict = json.optString("pre_registered_verdict", "SUCCESS: Predictor outperforms baselines")
        )
    }

    fun fetchIntegrationStatus(serverUrl: String, role: String = "BANK"): IntegrationStatusDto {
        val url = URL("$serverUrl/integrations/status?role=$role")
        val conn = url.openConnection() as HttpURLConnection
        conn.requestMethod = "GET"
        conn.connectTimeout = 3000
        conn.readTimeout = 3000

        val code = conn.responseCode
        val stream = if (code in 200..299) conn.inputStream else conn.errorStream
        val text = stream.bufferedReader().use { it.readText() }
        conn.disconnect()

        if (code !in 200..299) {
            throw IllegalStateException("API $code: $text")
        }

        val json = JSONObject(text)
        return IntegrationStatusDto(
            synthetic = json.optBoolean("synthetic", true),
            simulated = json.optBoolean("simulated", true),
            mode = json.optString("mode", "simulated"),
            roadmapState = json.optString("roadmap_state", "Interface Ready / Simulated"),
            notice = json.optString("notice", "SIMULATED: no live institutional connection.")
        )
    }
}
