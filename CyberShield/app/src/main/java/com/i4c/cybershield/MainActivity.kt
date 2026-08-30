package com.i4c.cybershield

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.navigation.compose.rememberNavController
import com.i4c.cybershield.ui.navigation.CyberShieldNavGraph
import com.i4c.cybershield.ui.theme.BgDeepSlate
import com.i4c.cybershield.ui.theme.CyberShieldTheme

// ═══════════════════════════════════════════════════════════════════════
//  MAIN ACTIVITY – Entry Point
//  Cyber Shield: Predictive Cashout Radar
//  SIH26184 – Ministry of Home Affairs / I4C Cybercrime Defense System
// ═══════════════════════════════════════════════════════════════════════

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            CyberShieldTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = BgDeepSlate
                ) {
                    val navController = rememberNavController()
                    CyberShieldNavGraph(navController = navController)
                }
            }
        }
    }
}
