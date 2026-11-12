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
        @Volatile private var instance: KakaoNotificationListener? = null
        val recentRooms = ArrayDeque<String>()

        /**
         * After a process restart the cached reply action is gone. KakaoTalk notifications that are
         * still in the shade carry a valid one, so look there first.
         */
        fun recoverTarget(): Boolean {
            val svc = instance ?: return false
            val prefs = Prefs.get(svc)
            if (prefs.roomName.isEmpty()) return false
            val filter = prefs.userIdFilter.toIntOrNull()
            val active = runCatching { svc.activeNotifications }.getOrNull() ?: return false
            val match = active
                .filter { it.packageName == KakaoBridge.KAKAO_PACKAGE }
                .filter { filter == null || it.user.hashCode() == filter }
                .filter { roomOf(it.notification) == prefs.roomName }
                .filter { sbn -> sbn.notification.actions?.any { it.remoteInputs?.isNotEmpty() == true } == true }
                .maxByOrNull { it.postTime } ?: return false
            KakaoBridge.updateTarget(svc, match.notification, match.user.hashCode(), flush = false)
            EventLog.add("알림창에 남은 카톡 알림에서 답장 경로 복구")
            return true
        }

        private fun roomOf(n: Notification): String {
            val e = n.extras ?: return ""
            return (e.getCharSequence(Notification.EXTRA_CONVERSATION_TITLE)
                ?: e.getCharSequence(Notification.EXTRA_SUB_TEXT)
                ?: e.getCharSequence(Notification.EXTRA_TITLE))?.toString()?.trim() ?: ""
        }
    }

    override fun onListenerConnected() {
        connected = true
        instance = this
        EventLog.init(this)
        EventLog.add("알림 리스너 연결됨")
        BridgeService.start(this)
        worker.execute { KakaoBridge.flush(this) }
    }

    override fun onListenerDisconnected() {
        connected = false
        instance = null
        EventLog.add("알림 리스너 끊김")
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        if (sbn.packageName != KakaoBridge.KAKAO_PACKAGE) return
        val n = sbn.notification
        if (n.flags and Notification.FLAG_GROUP_SUMMARY != 0) return
        val extras = n.extras ?: return

        val userId = sbn.user.hashCode() // UserHandle.hashCode() == user id (0 = owner, 95 = Dual Messenger)
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString() ?: ""
        val room = roomOf(n)
        if (room.isEmpty()) return

        val (sender, text, time) = lastMessage(extras) ?: Triple(
            title,
            extras.getCharSequence(Notification.EXTRA_TEXT)?.toString() ?: return,
            sbn.postTime,
        )

        rememberRoom("$room (user $userId)")

        val prefs = Prefs.get(this)
        val filter = prefs.userIdFilter.toIntOrNull()
        val hasReply = n.actions?.any { a -> a.remoteInputs?.isNotEmpty() == true } == true

        // KakaoTalk re-posts the same notification when it updates; process each message once.
        val key = "$userId|$room|$time|$text"
        if (key == lastKey) return
        lastKey = key

        // Diagnostic dump for the profile we care about (or every non-owner profile when unset).
        if (filter == userId || (filter == null && userId != 0)) {
            val msgCount = messageCount(extras)
            EventLog.add(
                "알림 user=$userId 제목=\"$title\" 방=\"$room\" 보낸이=\"$sender\" " +
                    "내용=\"${text.take(40)}\" 메시지수=$msgCount 답장액션=${if (hasReply) "있음" else "없음"} " +
                    "공개=${n.visibility}"
            )
            if (room == "새 알림" || text.contains("새 메시지가")) {
                EventLog.add("※ 봇 카톡의 알림 미리보기(내용 표시)가 꺼져 있습니다. 카톡 설정 → 알림 에서 켜 주세요")
            }
        }

        if (prefs.roomName.isEmpty() || room != prefs.roomName) return
        filter?.let { if (it != userId) return }

        KakaoBridge.updateTarget(this, n, userId)

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

    private fun messageCount(extras: Bundle): Int = if (Build.VERSION.SDK_INT >= 33) {
        extras.getParcelableArray(Notification.EXTRA_MESSAGES, Bundle::class.java)?.size ?: 0
    } else {
        @Suppress("DEPRECATION")
        extras.getParcelableArray(Notification.EXTRA_MESSAGES)?.size ?: 0
    }

    private fun rememberRoom(label: String) {
        synchronized(recentRooms) {
            recentRooms.remove(label)
            recentRooms.addFirst(label)
            while (recentRooms.size > 8) recentRooms.removeLast()
        }
    }
}
