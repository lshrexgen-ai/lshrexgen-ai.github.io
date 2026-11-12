package io.github.lshrexgen.smskakao

import android.app.Notification
import android.os.Build
import android.os.Bundle
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import java.util.concurrent.Executors

/**
 * Watches KakaoTalk notifications. For the configured console room it
 *  1. caches the notification's reply action (so the bridge can post text into the room), and
 *  2. treats each new message in the room as a command: "@number text", "@name text", or plain
 *     text (sent to the last SMS sender).
 */
class KakaoNotificationListener : NotificationListenerService() {
    private val worker = Executors.newSingleThreadExecutor()
    private var lastKey: String? = null

    /** Rooms seen recently, newest first, for the settings screen ("name (user N)"). */
    companion object {
        @Volatile var connected = false
        val recentRooms = ArrayDeque<String>()
    }

    override fun onListenerConnected() {
        connected = true
        EventLog.add("알림 리스너 연결됨")
    }

    override fun onListenerDisconnected() {
        connected = false
        EventLog.add("알림 리스너 끊김")
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        if (sbn.packageName != KakaoBridge.KAKAO_PACKAGE) return
        val n = sbn.notification
        if (n.flags and Notification.FLAG_GROUP_SUMMARY != 0) return
        val extras = n.extras ?: return

        val userId = sbn.user.hashCode() // UserHandle.hashCode() == user id (0 = owner, 95 = Dual Messenger)
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString() ?: ""
        val conversation = extras.getCharSequence(Notification.EXTRA_CONVERSATION_TITLE)?.toString()
        val subText = extras.getCharSequence(Notification.EXTRA_SUB_TEXT)?.toString()
        val room = (conversation ?: subText ?: title).trim()
        if (room.isEmpty()) return

        val (sender, text, time) = lastMessage(extras) ?: Triple(
            title,
            extras.getCharSequence(Notification.EXTRA_TEXT)?.toString() ?: return,
            sbn.postTime,
        )

        rememberRoom("$room (user $userId)")

        val prefs = Prefs.get(this)
        if (prefs.roomName.isEmpty() || room != prefs.roomName) return
        prefs.userIdFilter.toIntOrNull()?.let { if (it != userId) return }

        KakaoBridge.updateTarget(this, n, userId)

        // KakaoTalk re-posts the same notification when it updates; process each message once.
        val key = "$userId|$room|$time|$text"
        if (key == lastKey) return
        lastKey = key

        worker.execute { Commands.handle(this, sender, text) }
    }

    /** Last entry of a MessagingStyle notification: (sender, text, time). */
    private fun lastMessage(extras: Bundle): Triple<String, String, Long>? {
        val arr = if (Build.VERSION.SDK_INT >= 33) {
            extras.getParcelableArray(Notification.EXTRA_MESSAGES, Bundle::class.java)
        } else {
            @Suppress("DEPRECATION")
            extras.getParcelableArray(Notification.EXTRA_MESSAGES)?.map { it as Bundle }?.toTypedArray()
        }
        val last = arr?.lastOrNull() ?: return null
        val text = last.getCharSequence("text")?.toString() ?: return null
        val sender = last.getCharSequence("sender")?.toString()
            ?: (last.getParcelable("sender_person", android.app.Person::class.java))?.name?.toString()
            ?: ""
        return Triple(sender, text, last.getLong("time"))
    }

    private fun rememberRoom(label: String) {
        synchronized(recentRooms) {
            recentRooms.remove(label)
            recentRooms.addFirst(label)
            while (recentRooms.size > 8) recentRooms.removeLast()
        }
    }
}
