package io.github.lshrexgen.smskakao

import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import io.github.lshrexgen.smskakao.databinding.ActivityMainBinding

class MainActivity : AppCompatActivity() {
    private lateinit var b: ActivityMainBinding
    private val prefs by lazy { Prefs.get(this) }

    private val permissions = arrayOf(
        Manifest.permission.RECEIVE_SMS,
        Manifest.permission.SEND_SMS,
        Manifest.permission.READ_CONTACTS,
        Manifest.permission.POST_NOTIFICATIONS,
    )

    private val requestPerms = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
        refresh()
        BridgeService.start(this)
    }

    private val logListener: (List<String>) -> Unit = { lines -> b.log.text = lines.joinToString("\n") }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        b = ActivityMainBinding.inflate(layoutInflater)
        setContentView(b.root)

        b.roomName.setText(prefs.roomName)
        b.userIdFilter.setText(prefs.userIdFilter)
        b.lookupContacts.isChecked = prefs.lookupContacts
        b.replyToLast.isChecked = prefs.replyToLast
        b.sendAck.isChecked = prefs.sendAck

        b.btnNotifAccess.setOnClickListener {
            startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
        }
        b.btnPerms.setOnClickListener { requestPerms.launch(permissions) }
        b.btnBattery.setOnClickListener {
            startActivity(
                Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName"))
            )
        }
        b.btnSave.setOnClickListener {
            prefs.roomName = b.roomName.text.toString()
            prefs.userIdFilter = b.userIdFilter.text.toString()
            prefs.lookupContacts = b.lookupContacts.isChecked
            prefs.replyToLast = b.replyToLast.isChecked
            prefs.sendAck = b.sendAck.isChecked
            Toast.makeText(this, "저장됨", Toast.LENGTH_SHORT).show()
            BridgeService.start(this)
            refresh()
        }
        b.btnTest.setOnClickListener {
            if (KakaoBridge.sendNow(this, "🔧 브리지 테스트 메시지")) {
                Toast.makeText(this, "카톡으로 보냈습니다", Toast.LENGTH_SHORT).show()
            } else {
                Toast.makeText(this, "답장 경로가 없습니다. 봇 카톡에 먼저 아무 메시지나 보내 주세요", Toast.LENGTH_LONG).show()
            }
        }

        if (allPermsGranted()) BridgeService.start(this)
    }

    override fun onResume() {
        super.onResume()
        EventLog.addListener(logListener)
        logListener(EventLog.snapshot())
        refresh()
    }

    override fun onPause() {
        super.onPause()
        EventLog.removeListener(logListener)
    }

    private fun allPermsGranted() = permissions.all {
        ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED
    }

    private fun refresh() {
        val listenerOn = notificationAccessGranted()
        b.statusNotif.text = (if (listenerOn) "✅" else "❌") + " 알림 접근 권한" +
            (if (listenerOn && KakaoNotificationListener.connected) " (연결됨)" else "")
        b.statusPerms.text = (if (allPermsGranted()) "✅" else "❌") + " 문자·연락처·알림 권한"
        val pm = getSystemService(PowerManager::class.java)
        b.statusBattery.text = (if (pm.isIgnoringBatteryOptimizations(packageName)) "✅" else "⚠️") + " 배터리 최적화 제외"
        b.statusTarget.text = (if (KakaoBridge.hasTarget) "✅" else "⏳") + " 카톡 답장 경로" +
            (if (KakaoBridge.hasTarget) "" else " (봇 카톡에 메시지 1개 보내면 생김)")
        val rooms = synchronized(KakaoNotificationListener.recentRooms) { KakaoNotificationListener.recentRooms.toList() }
        b.recentRooms.text = if (rooms.isEmpty()) "아직 감지된 카톡 알림 없음" else rooms.joinToString("\n")
    }

    private fun notificationAccessGranted(): Boolean {
        val enabled = Settings.Secure.getString(contentResolver, "enabled_notification_listeners") ?: return false
        val me = ComponentName(this, KakaoNotificationListener::class.java)
        return enabled.split(":").any { ComponentName.unflattenFromString(it) == me }
    }
}
