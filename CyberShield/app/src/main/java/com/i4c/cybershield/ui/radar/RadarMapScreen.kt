package com.i4c.cybershield.ui.radar

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import org.maplibre.android.MapLibre
import org.maplibre.android.camera.CameraPosition
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.Style
import org.maplibre.android.style.expressions.Expression
import org.maplibre.android.style.layers.CircleLayer
import org.maplibre.android.style.layers.PropertyFactory
import org.maplibre.android.style.layers.RasterLayer
import org.maplibre.android.style.sources.GeoJsonSource
import org.maplibre.android.style.sources.RasterSource
import org.maplibre.geojson.Feature
import org.maplibre.geojson.FeatureCollection
import org.maplibre.geojson.Point
import com.i4c.cybershield.model.RiskLevel
import com.i4c.cybershield.model.TerminalMarker
import com.i4c.cybershield.model.TerminalType
import com.i4c.cybershield.ui.theme.*

// ═══════════════════════════════════════════════════════════════════════
//  TAB 1: LIVE CASHOUT RADAR
//  Interactive GIS map with risk heatmaps and terminal markers.
// ═══════════════════════════════════════════════════════════════════════

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RadarMapScreen(
    terminals: List<TerminalMarker>,
    activeFilter: String,
    selectedTerminal: TerminalMarker?,
    onFilterChanged: (String) -> Unit,
    onTerminalSelected: (TerminalMarker) -> Unit,
    onTerminalDismissed: () -> Unit,
    onNavigateToInvestigation: () -> Unit
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BgDeepSlate)
    ) {
        // ─── Top Bar ───────────────────────────────────────────────
        RadarTopBar(activeFilter, onFilterChanged)

        // ─── Map ───────────────────────────────────────────────────
        Box(
            modifier = Modifier
                .fillMaxSize()
                .weight(1f)
        ) {
            val mapView = remember {
                MapLibre.getInstance(context)
                MapView(context).apply {
                    onCreate(null)
                    onStart()
                    onResume()
                    getMapAsync { mapLibreMap ->
                        mapLibreMap.uiSettings.isZoomGesturesEnabled = true
                        mapLibreMap.uiSettings.isCompassEnabled = true
                        mapLibreMap.cameraPosition = CameraPosition.Builder()
                            .target(LatLng(28.5708, 77.3261))
                            .zoom(14.0)
                            .build()

                        val styleJson = """
                        {
                          "version": 8,
                          "name": "OpenStreetMap",
                          "sources": {
                            "osm": {
                              "type": "raster",
                              "tiles": [
                                "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
                                "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
                                "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png"
                              ],
                              "tileSize": 256,
                              "maxzoom": 19,
                              "attribution": "© OpenStreetMap contributors"
                            }
                          },
                          "layers": [
                            {
                              "id": "osm-layer",
                              "type": "raster",
                              "source": "osm",
                              "minzoom": 0,
                              "maxzoom": 19
                            }
                          ]
                        }
                        """.trimIndent()

                        mapLibreMap.setStyle(org.maplibre.android.maps.Style.Builder().fromJson(styleJson)) { style ->
                            // Layers will be added in update block
                        }

                        mapLibreMap.addOnMapClickListener { point ->
                            val screenPoint = mapLibreMap.projection.toScreenLocation(point)
                            val features = mapLibreMap.queryRenderedFeatures(screenPoint, "markers-layer")
                            if (features.isNotEmpty()) {
                                val id = features[0].getStringProperty("id")
                                val terminal = terminals.find { it.id == id }
                                if (terminal != null) {
                                    onTerminalSelected(terminal)
                                    return@addOnMapClickListener true
                                }
                            }
                            false
                        }
                    }
                }
            }

            DisposableEffect(lifecycleOwner) {
                val observer = LifecycleEventObserver { _, event ->
                    when (event) {
                        Lifecycle.Event.ON_START -> mapView.onStart()
                        Lifecycle.Event.ON_RESUME -> mapView.onResume()
                        Lifecycle.Event.ON_PAUSE -> mapView.onPause()
                        Lifecycle.Event.ON_STOP -> mapView.onStop()
                        Lifecycle.Event.ON_DESTROY -> mapView.onDestroy()
                        else -> {}
                    }
                }
                lifecycleOwner.lifecycle.addObserver(observer)
                onDispose {
                    lifecycleOwner.lifecycle.removeObserver(observer)
                    mapView.onDestroy()
                }
            }

            AndroidView(
                factory = { mapView },
                modifier = Modifier.fillMaxSize(),
                update = { view ->
                    view.getMapAsync { map ->
                        map.getStyle { style ->
                            val features = terminals.map { terminal ->
                                Feature.fromGeometry(Point.fromLngLat(terminal.longitude, terminal.latitude)).apply {
                                    addStringProperty("id", terminal.id)
                                    addNumberProperty("confidence", terminal.confidencePercent)
                                    addBooleanProperty("isHotspot", terminal.confidencePercent >= 70)
                                }
                            }

                            val source = style.getSourceAs<GeoJsonSource>("terminals-source")
                            if (source != null) {
                                source.setGeoJson(FeatureCollection.fromFeatures(features))
                            } else {
                                style.addSource(GeoJsonSource("terminals-source", FeatureCollection.fromFeatures(features)))

                                val hotspotLayer = CircleLayer("hotspots-layer", "terminals-source")
                                    .withFilter(Expression.eq(Expression.get("isHotspot"), true))
                                    .withProperties(
                                        PropertyFactory.circleRadius(80f),
                                        PropertyFactory.circleColor(android.graphics.Color.parseColor("#26FF9800")),
                                        PropertyFactory.circleStrokeColor(android.graphics.Color.parseColor("#4DFF9800")),
                                        PropertyFactory.circleStrokeWidth(2f)
                                    )
                                style.addLayer(hotspotLayer)

                                val markerLayer = CircleLayer("markers-layer", "terminals-source")
                                    .withProperties(
                                        PropertyFactory.circleRadius(8f),
                                        PropertyFactory.circleColor(
                                            Expression.step(
                                                Expression.get("confidence"),
                                                Expression.color(android.graphics.Color.parseColor("#E91E63")),
                                                Expression.stop(80f, Expression.color(android.graphics.Color.parseColor("#FF9800")))
                                            )
                                        ),
                                        PropertyFactory.circleStrokeWidth(1f),
                                        PropertyFactory.circleStrokeColor(android.graphics.Color.WHITE)
                                    )
                                style.addLayer(markerLayer)
                            }
                        }
                    }
                }
            )

            // Risk Legend overlay
            Card(
                modifier = Modifier
                    .align(Alignment.BottomStart)
                    .padding(16.dp),
                shape = RoundedCornerShape(10.dp),
                colors = CardDefaults.cardColors(
                    containerColor = BgDeepSlate.copy(alpha = 0.9f)
                ),
                border = CardDefaults.outlinedCardBorder().copy(
                    brush = Brush.linearGradient(
                        colors = listOf(BorderTaupe.copy(alpha = 0.3f), Color.Transparent)
                    )
                )
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    LegendItem(color = AlertOrange, label = "Critical ≥80%")
                    LegendItem(color = BorderTaupe, label = "Low/Med <80%")
                }
            }
        }
    }

    // ─── Modal Bottom Sheet ────────────────────────────────────────
    if (selectedTerminal != null) {
        ModalBottomSheet(
            onDismissRequest = onTerminalDismissed,
            sheetState = sheetState,
            containerColor = SurfaceCharcoal,
            contentColor = TextOffWhite,
            dragHandle = {
                Box(
                    modifier = Modifier
                        .padding(vertical = 12.dp)
                        .width(40.dp)
                        .height(4.dp)
                        .clip(RoundedCornerShape(2.dp))
                        .background(BorderTaupe.copy(alpha = 0.4f))
                )
            },
            shape = RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp)
        ) {
            TerminalDetailSheet(
                terminal = selectedTerminal,
                onInspect = onNavigateToInvestigation,
                onDismiss = onTerminalDismissed
            )
        }
    }
}

// ─── Sub-Components ────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RadarTopBar(activeFilter: String, onFilterChanged: (String) -> Unit) {
    // Live pulse animation
    val infiniteTransition = rememberInfiniteTransition(label = "live_pulse")
    val pulseAlpha by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 0.3f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulse"
    )
    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.3f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200),
            repeatMode = RepeatMode.Reverse
        ),
        label = "scale"
    )

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(BgDeepSlate)
            .padding(horizontal = 16.dp, vertical = 12.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Title
            Text(
                text = "Cashout Radar",
                fontSize = 22.sp,
                fontWeight = FontWeight.Bold,
                color = TextOffWhite
            )

            Spacer(modifier = Modifier.width(12.dp))

            // Live badge
            Card(
                shape = RoundedCornerShape(20.dp),
                colors = CardDefaults.cardColors(
                    containerColor = SuccessGreen.copy(alpha = 0.15f * pulseAlpha)
                ),
                border = CardDefaults.outlinedCardBorder().copy(
                    brush = Brush.linearGradient(
                        colors = listOf(
                            SuccessGreen.copy(alpha = pulseAlpha),
                            SuccessGreen.copy(alpha = 0.2f)
                        )
                    )
                )
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    // Pulsing green dot
                    Box(
                        modifier = Modifier
                            .size(8.dp)
                            .clip(CircleShape)
                            .background(SuccessGreen.copy(alpha = pulseAlpha))
                    )
                    Text(
                        text = "LIVE STREAMING",
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                        color = SuccessGreen,
                        letterSpacing = 1.sp
                    )
                }
            }

            Spacer(modifier = Modifier.weight(1f))

            // Terminal count
            Text(
                text = "8 Terminals",
                fontSize = 12.sp,
                color = BorderTaupe
            )
        }

        Spacer(modifier = Modifier.height(12.dp))

        // Filter Chips
        val filters = listOf("All Terminals", "Bank ATMs", "AEPS Micro-ATMs")
        LazyRow(
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(filters) { filter ->
                val isSelected = activeFilter == filter
                FilterChip(
                    selected = isSelected,
                    onClick = { onFilterChanged(filter) },
                    label = {
                        Text(
                            text = filter,
                            fontSize = 12.sp,
                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                        )
                    },
                    leadingIcon = if (isSelected) {
                        {
                            Icon(
                                imageVector = Icons.Default.Check,
                                contentDescription = null,
                                modifier = Modifier.size(16.dp)
                            )
                        }
                    } else null,
                    colors = FilterChipDefaults.filterChipColors(
                        containerColor = ChipUnselectedBg,
                        labelColor = BorderTaupe,
                        selectedContainerColor = ChipSelectedBg,
                        selectedLabelColor = AlertOrange,
                        selectedLeadingIconColor = AlertOrange
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
}

@Composable
private fun LegendItem(color: Color, label: String) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        Box(
            modifier = Modifier
                .size(10.dp)
                .clip(CircleShape)
                .background(color)
        )
        Text(
            text = label,
            fontSize = 10.sp,
            color = BorderTaupe
        )
    }
}

@Composable
private fun TerminalDetailSheet(
    terminal: TerminalMarker,
    onInspect: () -> Unit,
    onDismiss: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .padding(bottom = 32.dp)
    ) {
        // ─── Header ────────────────────────────────────────────────
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Terminal icon
            Box(
                modifier = Modifier
                    .size(48.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(
                        if (terminal.type == TerminalType.BANK_ATM)
                            InfoBlue.copy(alpha = 0.15f)
                        else
                            MediumCyan.copy(alpha = 0.15f)
                    ),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = if (terminal.type == TerminalType.BANK_ATM)
                        Icons.Default.CreditCard
                    else
                        Icons.Default.PhoneAndroid,
                    contentDescription = null,
                    tint = if (terminal.type == TerminalType.BANK_ATM) InfoBlue else MediumCyan,
                    modifier = Modifier.size(24.dp)
                )
            }

            Spacer(modifier = Modifier.width(12.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = terminal.id,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold,
                    color = TextOffWhite
                )
                Text(
                    text = terminal.address,
                    fontSize = 13.sp,
                    color = BorderTaupe,
                    lineHeight = 18.sp
                )
            }
        }

        Spacer(modifier = Modifier.height(20.dp))

        // ─── Info Cards Grid ───────────────────────────────────────
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            // Terminal Type
            InfoCard(
                modifier = Modifier.weight(1f),
                label = "Terminal Type",
                value = terminal.type.displayName,
                icon = if (terminal.type == TerminalType.BANK_ATM)
                    Icons.Default.CreditCard
                else
                    Icons.Default.PhoneAndroid
            )

            // Bank
            InfoCard(
                modifier = Modifier.weight(1f),
                label = "Bank",
                value = terminal.bankName,
                icon = Icons.Default.AccountBalance
            )
        }

        Spacer(modifier = Modifier.height(10.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            // Cashout Window
            InfoCard(
                modifier = Modifier.weight(1f),
                label = "Est. Cashout Window",
                value = terminal.cashoutWindow,
                icon = Icons.Default.Schedule
            )

            // Confidence Badge
            val riskColor = when {
                terminal.confidencePercent >= 80 -> AlertOrange
                terminal.confidencePercent >= 60 -> MediumCyan
                else -> BorderTaupe
            }

            Card(
                modifier = Modifier.weight(1f),
                shape = RoundedCornerShape(12.dp),
                colors = CardDefaults.cardColors(
                    containerColor = riskColor.copy(alpha = 0.12f)
                ),
                border = CardDefaults.outlinedCardBorder().copy(
                    brush = Brush.linearGradient(
                        colors = listOf(riskColor.copy(alpha = 0.5f), riskColor.copy(alpha = 0.1f))
                    )
                )
            ) {
                Column(
                    modifier = Modifier.padding(14.dp)
                ) {
                    Text(
                        text = "Confidence Rate",
                        fontSize = 10.sp,
                        color = BorderTaupe,
                        letterSpacing = 0.5.sp
                    )
                    Spacer(modifier = Modifier.height(4.dp))

                    Row(
                        verticalAlignment = Alignment.Bottom
                    ) {
                        Text(
                            text = "${terminal.confidencePercent}%",
                            fontSize = 26.sp,
                            fontWeight = FontWeight.Black,
                            color = riskColor
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = terminal.riskLevel.displayName,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            color = riskColor,
                            modifier = Modifier.padding(bottom = 3.dp)
                        )
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    // Progress bar
                    LinearProgressIndicator(
                        progress = terminal.confidencePercent / 100f,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(6.dp)
                            .clip(RoundedCornerShape(3.dp)),
                        color = riskColor,
                        trackColor = riskColor.copy(alpha = 0.15f)
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(24.dp))

        // ─── Primary Action Button ─────────────────────────────────
        Button(
            onClick = onInspect,
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp),
            shape = RoundedCornerShape(14.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = AlertOrange,
                contentColor = TextOffWhite
            )
        ) {
            Icon(
                imageVector = Icons.Default.Search,
                contentDescription = null,
                modifier = Modifier.size(20.dp)
            )
            Spacer(modifier = Modifier.width(10.dp))
            Text(
                text = "Inspect Evidence for Review",
                fontWeight = FontWeight.Bold,
                fontSize = 15.sp
            )
        }

        Spacer(modifier = Modifier.height(8.dp))

        // Dismiss
        TextButton(
            onClick = onDismiss,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text(
                text = "Dismiss",
                color = BorderTaupe,
                fontSize = 14.sp
            )
        }
    }
}

@Composable
private fun InfoCard(
    modifier: Modifier = Modifier,
    label: String,
    value: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = BgDeepSlate
        ),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(
                colors = listOf(BorderTaupe.copy(alpha = 0.3f), Color.Transparent)
            )
        )
    ) {
        Column(
            modifier = Modifier.padding(14.dp)
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = BorderTaupe,
                    modifier = Modifier.size(14.dp)
                )
                Text(
                    text = label,
                    fontSize = 10.sp,
                    color = BorderTaupe,
                    letterSpacing = 0.5.sp
                )
            }
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = value,
                fontSize = 14.sp,
                fontWeight = FontWeight.SemiBold,
                color = TextOffWhite
            )
        }
    }
}
